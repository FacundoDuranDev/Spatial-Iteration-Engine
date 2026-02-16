#include "filters/filter.hpp"
#include <cstdint>

namespace filters {

class InvertFilter : public Filter {
 public:
  void apply(std::uint8_t* frame, int width, int height, int channels) override {
    const int n = width * height * channels;
    for (int i = 0; i < n; ++i) {
      frame[i] = static_cast<std::uint8_t>(255 - frame[i]);
    }
  }
};

void apply_invert_impl(std::uint8_t* data, int width, int height, int channels) {
  InvertFilter f;
  f.apply(data, width, height, channels);
}

}  // namespace filters
