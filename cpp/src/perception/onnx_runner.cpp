#include "perception/onnx_runner.hpp"

#ifdef USE_ONNXRUNTIME
#include <algorithm>
#include <cstring>
#include <onnxruntime_cxx_api.h>
#include <stdexcept>
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

}  // namespace

OnnxRunner::OnnxRunner() = default;

OnnxRunner::~OnnxRunner() = default;

bool OnnxRunner::load(const std::string& model_path) {
  if (model_path.empty()) return false;
  try {
    impl_ = std::make_unique<OnnxRunnerImpl>();
    impl_->session_options.SetIntraOpNumThreads(1);
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

    loaded_ = true;
    return true;
  } catch (const std::exception&) {
    impl_.reset();
    loaded_ = false;
    return false;
  }
}

std::vector<float> OnnxRunner::run(const std::uint8_t* image, int width, int height) {
  if (!loaded_ || !impl_ || !image || width <= 0 || height <= 0)
    return {};

  try {
    const int size = input_size_;
    std::vector<float> input_data(1 * 3 * size * size);
    resize_and_normalize_nchw(image, width, height, size, input_data.data());

    std::array<int64_t, 4> input_shape = {1, 3, size, size};
    Ort::MemoryInfo mem_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
        mem_info, input_data.data(), input_data.size(),
        input_shape.data(), input_shape.size());

    auto output_tensors = impl_->session->Run(
        Ort::RunOptions{nullptr},
        impl_->input_names.data(), &input_tensor, 1,
        impl_->output_names.data(), impl_->output_names.size());

    if (output_tensors.empty()) return {};

    const auto& out = output_tensors[0];
    auto info = out.GetTensorTypeAndShapeInfo();
    size_t count = info.GetElementCount();
    const float* data = out.GetTensorData<float>();
    if (!data) return {};

    return output_to_xy(data, count);
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
