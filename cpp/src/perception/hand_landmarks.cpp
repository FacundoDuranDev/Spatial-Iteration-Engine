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

std::string get_hand_model_path() {
  return get_models_dir() + "/hand_landmark_new.onnx";
}

}  // namespace

std::vector<float> run_hands(std::uint8_t* image, int width, int height) {
#ifdef USE_ONNXRUNTIME
  static OnnxRunner runner;
  if (!runner.is_loaded() && !runner.load(get_hand_model_path()))
    return {};
  return runner.run(image, width, height);
#else
  (void)image;
  (void)width;
  (void)height;
  return {};
#endif
}

}  // namespace perception
