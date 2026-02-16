#include "filters/filter.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace filters {

class BrightnessContrastFilter : public Filter {
 public:
  BrightnessContrastFilter(int brightness_delta = 0, double contrast_factor = 1.0)
      : brightness_delta_(brightness_delta), contrast_factor_(contrast_factor) {}

  void apply(std::uint8_t* frame, int width, int height, int channels) override {
    const int n = width * height * channels;
    for (int i = 0; i < n; ++i) {
      double v = static_cast<double>(frame[i]);
      v = (v - 127.5) * contrast_factor_ + 127.5 + brightness_delta_;
      frame[i] = static_cast<std::uint8_t>(std::clamp(std::round(v), 0.0, 255.0));
    }
  }

  void set_brightness(int delta) { brightness_delta_ = delta; }
  void set_contrast(double factor) { contrast_factor_ = factor; }

 private:
  int brightness_delta_;
  double contrast_factor_;
};

void apply_brightness_contrast_impl(std::uint8_t* data, int width, int height,
                                   int channels, int brightness_delta,
                                   double contrast_factor) {
  BrightnessContrastFilter f(brightness_delta, contrast_factor);
  f.apply(data, width, height, channels);
}

}  // namespace filters
