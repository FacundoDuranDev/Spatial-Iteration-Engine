#include "perception/onnx_runner.hpp"

#ifdef USE_ONNXRUNTIME
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <onnxruntime/core/session/onnxruntime_cxx_api.h>
#include <stdexcept>
#include <thread>
#include <vector>

namespace perception {

struct OnnxRunnerImpl {
  Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "perception"};
  Ort::SessionOptions session_options;
  std::unique_ptr<Ort::Session> session;
  Ort::AllocatorWithDefaultOptions allocator;
  std::vector<std::string> input_names_str;
  std::vector<std::string> output_names_str;
  std::vector<const char*> input_names;
  std::vector<const char*> output_names;
};

namespace {

struct LetterboxInfo {
  float scale;   // min(target/src_w, target/src_h)
  float pad_x;   // horizontal padding in model pixels
  float pad_y;   // vertical padding in model pixels
};

/** Letterbox resize: maintain aspect ratio, pad with black, output float NCHW 0..1. */
void letterbox_and_normalize_nchw(
    const std::uint8_t* src,
    int src_w,
    int src_h,
    int target_size,
    float* dst,
    LetterboxInfo& info) {
  float scale_w = static_cast<float>(target_size) / src_w;
  float scale_h = static_cast<float>(target_size) / src_h;
  info.scale = std::min(scale_w, scale_h);

  int new_w = static_cast<int>(src_w * info.scale);
  int new_h = static_cast<int>(src_h * info.scale);
  info.pad_x = (target_size - new_w) / 2.0f;
  info.pad_y = (target_size - new_h) / 2.0f;

  // Initialize to black
  std::memset(dst, 0, sizeof(float) * 3 * target_size * target_size);

  int dx_off = static_cast<int>(info.pad_x);
  int dy_off = static_cast<int>(info.pad_y);
  const int c = 3;

  for (int dy = 0; dy < new_h; ++dy) {
    for (int dx = 0; dx < new_w; ++dx) {
      int sx = dx * src_w / new_w;
      int sy = dy * src_h / new_h;
      if (sx >= src_w) sx = src_w - 1;
      if (sy >= src_h) sy = src_h - 1;
      const std::uint8_t* p = src + (sy * src_w + sx) * c;
      int ox = dx_off + dx;
      int oy = dy_off + dy;
      for (int ch = 0; ch < c; ++ch) {
        // BGR→RGB: swap channels 0↔2
        int src_ch = (ch == 0) ? 2 : (ch == 2) ? 0 : ch;
        dst[ch * target_size * target_size + oy * target_size + ox] = p[src_ch] / 255.f;
      }
    }
  }
}

/** Copy output tensor to vector; if 3 values per point (x,y,z) emit only x,y. */
std::vector<float> output_to_xy(const float* data, size_t count) {
  std::vector<float> out;
  if (count % 3 == 0) {
    size_t n = count / 3;
    out.reserve(n * 2);
    for (size_t i = 0; i < n; ++i) {
      out.push_back(data[i * 3 + 0]);
      out.push_back(data[i * 3 + 1]);
    }
  } else if (count % 2 == 0) {
    out.assign(data, data + count);
  }
  return out;
}

/** Post-process YOLOv8 pose output: filter valid detections.
 * YOLOv8 pose outputs shape (1, num_detections, num_keypoints*3+4+1) where:
 * - First 4 values: bbox (x, y, w, h)
 * - Next 1 value: confidence
 * - Remaining: keypoints (x, y, confidence) for each keypoint
 * 
 * This function extracts keypoints from the first valid detection (confidence > 0.5).
 * 
 * @param data Raw output tensor data
 * @param count Total number of elements
 * @param num_keypoints Number of keypoints (17 for YOLOv8n-pose)
 * @param model_size Size of the model input (typically 640)
 * @param orig_width Original image width
 * @param orig_height Original image height
 */
/** Post-process YOLOv8 pose output with letterbox-aware coordinate mapping.
 * Returns keypoints in PIXEL coordinates of the original image. */
std::vector<float> postprocess_yolov8_pose(
    const float* data,
    size_t count,
    int num_keypoints,
    const LetterboxInfo& lb) {
  std::vector<float> out;

  const int detection_size = 4 + 1 + num_keypoints * 3;
  if (count < static_cast<size_t>(detection_size))
    return {};

  size_t num_detections = count / detection_size;
  for (size_t i = 0; i < num_detections; ++i) {
    const float* det = data + i * detection_size;
    float conf = det[4];

    if (conf > 0.25f) {
      const float* keypoints = det + 5;
      out.reserve(num_keypoints * 2);
      for (int k = 0; k < num_keypoints; ++k) {
        float kp_x = keypoints[k * 3 + 0];
        float kp_y = keypoints[k * 3 + 1];
        float kp_conf = keypoints[k * 3 + 2];

        if (kp_conf > 0.3f) {
          // Undo letterbox: model pixels → original pixels
          out.push_back((kp_x - lb.pad_x) / lb.scale);
          out.push_back((kp_y - lb.pad_y) / lb.scale);
        } else {
          out.push_back(0.0f);
          out.push_back(0.0f);
        }
      }
      return out;
    }
  }
  return {};
}

}  // namespace

OnnxRunner::OnnxRunner() = default;

OnnxRunner::~OnnxRunner() = default;

bool OnnxRunner::load(const std::string& model_path) {
  if (model_path.empty()) return false;
  try {
    impl_ = std::make_unique<OnnxRunnerImpl>();
    int num_threads = 4;
    const char* env_threads = std::getenv("ONNX_NUM_THREADS");
    if (env_threads && env_threads[0] != '\0') {
      int parsed = std::atoi(env_threads);
      if (parsed > 0 && parsed <= 32) num_threads = parsed;
    }
    unsigned int hw = std::thread::hardware_concurrency();
    if (hw > 0 && num_threads > static_cast<int>(hw))
      num_threads = static_cast<int>(hw);
    impl_->session_options.SetIntraOpNumThreads(num_threads);
    impl_->session_options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_EXTENDED);
    impl_->session = std::make_unique<Ort::Session>(impl_->env, model_path.c_str(), impl_->session_options);

    Ort::AllocatorWithDefaultOptions allocator;
    const size_t num_inputs = impl_->session->GetInputCount();
    const size_t num_outputs = impl_->session->GetOutputCount();
    if (num_inputs == 0 || num_outputs == 0) return false;

    for (size_t i = 0; i < num_inputs; ++i) {
      auto name = impl_->session->GetInputNameAllocated(i, allocator);
      impl_->input_names_str.push_back(name.get());
    }
    for (size_t i = 0; i < num_outputs; ++i) {
      auto name = impl_->session->GetOutputNameAllocated(i, allocator);
      impl_->output_names_str.push_back(name.get());
    }
    for (const auto& s : impl_->input_names_str) impl_->input_names.push_back(s.c_str());
    for (const auto& s : impl_->output_names_str) impl_->output_names.push_back(s.c_str());

    auto input_shape = impl_->session->GetInputTypeInfo(0).GetTensorTypeAndShapeInfo().GetShape();
    if (input_shape.size() >= 4) {
      int h = static_cast<int>(input_shape[2]);
      int w = static_cast<int>(input_shape[3]);
      input_size_ = (h == w) ? h : 192;
    }

    input_data_.resize(1 * 3 * input_size_ * input_size_);
    loaded_ = true;
    return true;
  } catch (const std::exception& e) {
    // Log error for debugging (en desarrollo, en producción podría ser silencioso)
    #ifdef DEBUG
    std::cerr << "OnnxRunner::load failed: " << e.what() << " for path: " << model_path << std::endl;
    #endif
    impl_.reset();
    loaded_ = false;
    return false;
  }
}

std::vector<float> OnnxRunner::run(const std::uint8_t* image, int width, int height) {
  if (!loaded_ || !impl_ || !image || width <= 0 || height <= 0)
    return {};

  std::lock_guard<std::mutex> lock(run_mutex_);
  try {
    const int size = input_size_;
    LetterboxInfo lb{};
    letterbox_and_normalize_nchw(image, width, height, size, input_data_.data(), lb);

    std::array<int64_t, 4> input_shape = {1, 3, size, size};
    Ort::MemoryInfo mem_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
        mem_info, input_data_.data(), input_data_.size(),
        input_shape.data(), input_shape.size());

    auto output_tensors = impl_->session->Run(
        Ort::RunOptions{nullptr},
        impl_->input_names.data(), &input_tensor, 1,
        impl_->output_names.data(), impl_->output_names.size());

    if (output_tensors.empty()) return {};

    // Pick the output tensor with the most elements (handles multi-output models
    // where small tensors are scores/flags and the largest is landmark data).
    size_t best_idx = 0;
    size_t best_count = 0;
    for (size_t i = 0; i < output_tensors.size(); ++i) {
      size_t n = output_tensors[i].GetTensorTypeAndShapeInfo().GetElementCount();
      if (n > best_count) { best_count = n; best_idx = i; }
    }

    const auto& out_tensor = output_tensors[best_idx];
    auto tinfo = out_tensor.GetTensorTypeAndShapeInfo();
    size_t count = tinfo.GetElementCount();
    const float* data = out_tensor.GetTensorData<float>();
    if (!data) return {};

    // YOLOv8 detection models produce very large outputs (>10k elements).
    if (count > 10000) {
      auto shape = tinfo.GetShape();
      const float* yolo_data = data;
      std::vector<float> transposed;

      // YOLOv8 outputs (1, 56, 8400) but postprocessing expects (1, 8400, 56).
      // Detect and transpose if needed: shape[1] < shape[2] means features < detections.
      if (shape.size() == 3 && shape[1] < shape[2]) {
        int64_t rows = shape[1];  // e.g. 56
        int64_t cols = shape[2];  // e.g. 8400
        transposed.resize(static_cast<size_t>(rows * cols));
        for (int64_t r = 0; r < rows; ++r)
          for (int64_t c_idx = 0; c_idx < cols; ++c_idx)
            transposed[static_cast<size_t>(c_idx * rows + r)] =
                data[static_cast<size_t>(r * cols + c_idx)];
        yolo_data = transposed.data();
      }

      auto yolov8_result = postprocess_yolov8_pose(yolo_data, count, 17, lb);
      if (!yolov8_result.empty()) return yolov8_result;
      yolov8_result = postprocess_yolov8_pose(yolo_data, count, 33, lb);
      if (!yolov8_result.empty()) return yolov8_result;
    }

    // Standard landmark output: extract (x,y) from (x,y,z) triplets
    auto result = output_to_xy(data, count);

    if (!result.empty()) {
      float max_val = *std::max_element(result.begin(), result.end());

      // Convert all coordinates to model pixel space first
      // Face model outputs [0,1], hand model outputs [0,input_size]
      if (max_val <= 1.5f) {
        for (auto& v : result) v *= static_cast<float>(size);
      }

      // Undo letterbox: model pixels → original pixels
      float inv_scale = 1.0f / lb.scale;
      for (size_t i = 0; i < result.size(); i += 2) {
        result[i]     = (result[i]     - lb.pad_x) * inv_scale;
        result[i + 1] = (result[i + 1] - lb.pad_y) * inv_scale;
      }
    }
    return result;
  } catch (const std::exception&) {
    return {};
  }
}

}  // namespace perception

#else  // !USE_ONNXRUNTIME

#include <string>
namespace perception {

struct OnnxRunnerImpl {};

OnnxRunner::OnnxRunner() = default;
OnnxRunner::~OnnxRunner() = default;

bool OnnxRunner::load(const std::string&) { return false; }
std::vector<float> OnnxRunner::run(const std::uint8_t*, int, int) { return {}; }

}  // namespace perception

#endif  // USE_ONNXRUNTIME
