#include "filters/filter.hpp"
#include <cstdint>

namespace filters {

/**
 * Grayscale / Luma: Y = 0.299*R + 0.587*G + 0.114*B.
 * Assumes BGR layout (OpenCV); writes same value to B,G,R so output remains 3-channel.
 */
class GrayscaleFilter : public Filter {
 public:
  void apply(std::uint8_t* frame, int width, int height, int channels) override {
    if (channels != 3) return;
    const int pixels = width * height;
    for (int i = 0; i < pixels; ++i) {
      const int b = frame[i * 3 + 0];
      const int g = frame[i * 3 + 1];
      const int r = frame[i * 3 + 2];
      const std::uint8_t luma =
          static_cast<std::uint8_t>((r * 77 + g * 150 + b * 29) >> 8);  // integer approx
      frame[i * 3 + 0] = luma;
      frame[i * 3 + 1] = luma;
      frame[i * 3 + 2] = luma;
    }
  }
};

void apply_grayscale_impl(std::uint8_t* data, int width, int height, int channels) {
  GrayscaleFilter f;
  f.apply(data, width, height, channels);
}

}  // namespace filters
