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

/** Resize RGB image (width*height*3) to target_size x target_size, nearest neighbor, into float NCHW 0..1. */
void resize_and_normalize_nchw(
    const std::uint8_t* src,
    int src_w,
    int src_h,
    int target_size,
    float* dst) {
  const int c = 3;
  for (int dy = 0; dy < target_size; ++dy) {
    for (int dx = 0; dx < target_size; ++dx) {
      int sx = (dx * src_w) / target_size;
      int sy = (dy * src_h) / target_size;
      if (sx >= src_w) sx = src_w - 1;
      if (sy >= src_h) sy = src_h - 1;
      const std::uint8_t* p = src + (sy * src_w + sx) * c;
      for (int ch = 0; ch < c; ++ch)
        dst[ch * target_size * target_size + dy * target_size + dx] = p[ch] / 255.f;
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
std::vector<float> postprocess_yolov8_pose(
    const float* data, 
    size_t count, 
    int num_keypoints = 17,
    int model_size = 640,
    int orig_width = 640,
    int orig_height = 480) {
  std::vector<float> out;
  
  // YOLOv8 pose output format: (num_detections, 4+1+num_keypoints*3)
  // Each detection: [bbox_x, bbox_y, bbox_w, bbox_h, conf, kp1_x, kp1_y, kp1_conf, ...]
  const int detection_size = 4 + 1 + num_keypoints * 3;  // bbox(4) + conf(1) + keypoints(3*num_keypoints)
  
  if (count < detection_size) {
    // Not enough data for even one detection, return as-is
    return output_to_xy(data, count);
  }
  
  // Calculate scale factors to convert from model space to original image space
  float scale_x = static_cast<float>(orig_width) / static_cast<float>(model_size);
  float scale_y = static_cast<float>(orig_height) / static_cast<float>(model_size);
  
  // Find first detection with confidence > 0.5
  size_t num_detections = count / detection_size;
  for (size_t i = 0; i < num_detections; ++i) {
    const float* det = data + i * detection_size;
    float conf = det[4];  // Confidence is at index 4
    
    if (conf > 0.5f) {
      // Extract keypoints (skip bbox and conf)
      const float* keypoints = det + 5;  // Start after bbox(4) + conf(1)
      out.reserve(num_keypoints * 2);
      for (int k = 0; k < num_keypoints; ++k) {
        float kp_x = keypoints[k * 3 + 0];
        float kp_y = keypoints[k * 3 + 1];
        float kp_conf = keypoints[k * 3 + 2];
        
        // Only include keypoints with confidence > 0.3
        if (kp_conf > 0.3f) {
          // Scale from model space (model_size x model_size) to original image space
          out.push_back(kp_x * scale_x);
          out.push_back(kp_y * scale_y);
        } else {
          // Invalid keypoint, use (0, 0) as placeholder
          out.push_back(0.0f);
          out.push_back(0.0f);
        }
      }
      return out;  // Return first valid detection
    }
  }
  
  // No valid detections found, return empty
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
    resize_and_normalize_nchw(image, width, height, size, input_data_.data());

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

    const auto& out = output_tensors[best_idx];
    auto info = out.GetTensorTypeAndShapeInfo();
    size_t count = info.GetElementCount();
    const float* data = out.GetTensorData<float>();
    if (!data) return {};

    // YOLOv8 detection models produce very large outputs (>10k elements)
    // with many anchors. Landmark models produce much smaller outputs.
    if (count > 10000) {
      auto yolov8_result = postprocess_yolov8_pose(data, count, 17, size, width, height);
      if (!yolov8_result.empty()) {
        return yolov8_result;
      }
      yolov8_result = postprocess_yolov8_pose(data, count, 33, size, width, height);
      if (!yolov8_result.empty()) {
        return yolov8_result;
      }
    }

    // Standard landmark output: extract (x,y) from (x,y,z) triplets
    auto result = output_to_xy(data, count);

    // Normalize to [0,1] if coords are in model input space (values > 1).
    // Some models (e.g. MediaPipe face) already output [0,1]; others
    // (e.g. hand_landmark) output in model-pixel space (0..input_size).
    if (!result.empty()) {
      float max_val = *std::max_element(result.begin(), result.end());
      if (max_val > 1.5f) {
        float inv = 1.0f / static_cast<float>(size);
        for (auto& v : result) v *= inv;
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
