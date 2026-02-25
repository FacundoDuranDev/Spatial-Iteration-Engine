#include "perception/perception_common.hpp"
#include "perception/onnx_runner.hpp"
#include <cstdint>
#include <cstdlib>
#include <string>
#include <vector>

namespace perception {

namespace {

std::string get_models_dir() {
  const char* env = std::getenv("ONNX_MODELS_DIR");
  if (env && env[0] != '\0') return std::string(env);
  return "onnx_models/mediapipe";
}

std::string get_pose_model_path() {
  return get_models_dir() + "/pose_landmark.onnx";
}

}  // namespace

std::vector<float> run_pose(std::uint8_t* image, int width, int height) {
#ifdef USE_ONNXRUNTIME
  static OnnxRunner runner;
  if (!runner.is_loaded() && !runner.load(get_pose_model_path()))
    return {};
  return runner.run(image, width, height);
#else
  (void)image;
  (void)width;
  (void)height;
  return {};
#endif
}

std::vector<float> run_pose_with_confidence(std::uint8_t* image, int width, int height) {
#ifdef USE_ONNXRUNTIME
  // Uses the same model as run_pose but preserves per-keypoint confidence.
  // Note: shares the static runner with run_pose (same model path).
  static OnnxRunner runner;
  if (!runner.is_loaded() && !runner.load(get_pose_model_path()))
    return {};
  return runner.run_with_confidence(image, width, height);
#else
  (void)image;
  (void)width;
  (void)height;
  return {};
#endif
}

}  // namespace perception
