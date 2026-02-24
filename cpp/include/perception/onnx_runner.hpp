#ifndef SPATIAL_PERCEPTION_ONNX_RUNNER_HPP
#define SPATIAL_PERCEPTION_ONNX_RUNNER_HPP

#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

namespace perception {

struct OnnxRunnerImpl;

/**
 * Runner ONNX para modelos de landmarks (face, hands, pose).
 * Preprocesa imagen RGB a entrada del modelo (resize, normalizar 0-1, NCHW),
 * ejecuta inferencia y devuelve landmarks como [x1,y1, x2,y2, ...] en 0..1.
 */
class OnnxRunner {
 public:
  OnnxRunner();
  ~OnnxRunner();

  /** Carga el modelo desde path. Devuelve true si OK. */
  bool load(const std::string& model_path);

  /**
   * Ejecuta inferencia.
   * image: RGB, row-major, size width*height*3.
   * Devuelve landmarks normalizados (x,y) o vacío si falla.
   */
  std::vector<float> run(const std::uint8_t* image, int width, int height);

  int input_size() const { return input_size_; }
  bool is_loaded() const { return loaded_; }

 private:
  bool loaded_ = false;
  int input_size_ = 192;
  std::unique_ptr<OnnxRunnerImpl> impl_;
  std::vector<float> input_data_;
  std::mutex run_mutex_;
};

}  // namespace perception

#endif
