#include "filters/filter.hpp"
#include <cstdint>

namespace filters {

/**
 * Phase 2 stub: binary threshold. TODO: implement.
 */
class ThresholdFilter : public Filter {
 public:
  explicit ThresholdFilter(std::uint8_t thresh = 127) : thresh_(thresh) {}
  void apply(std::uint8_t* frame, int width, int height, int channels) override {
    (void)frame;
    (void)width;
    (void)height;
    (void)channels;
    // TODO: threshold to 0 or 255 per channel
  }
 private:
  std::uint8_t thresh_;
};

void apply_threshold_impl(std::uint8_t* data, int width, int height, int channels,
                         std::uint8_t threshold) {
  (void)data;
  (void)width;
  (void)height;
  (void)channels;
  (void)threshold;
  // Stub: no-op
}

}  // namespace filters
