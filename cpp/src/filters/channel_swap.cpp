#include "filters/filter.hpp"
#include <cstdint>

namespace filters {

/**
 * Channel swap: permute BGR by indices. e.g. (2,1,0) => BGR->RGB, (0,2,1)=> BGR->BRG.
 * indices[0]=dest for B, indices[1]=dest for G, indices[2]=dest for R (source channels 0=B,1=G,2=R).
 */
class ChannelSwapFilter : public Filter {
 public:
  ChannelSwapFilter(int dst_for_b, int dst_for_g, int dst_for_r)
      : dst_b_(dst_for_b), dst_g_(dst_for_g), dst_r_(dst_for_r) {}

  void apply(std::uint8_t* frame, int width, int height, int channels) override {
    if (channels != 3) return;
    const int pixels = width * height;
    for (int i = 0; i < pixels; ++i) {
      std::uint8_t b = frame[i * 3 + 0];
      std::uint8_t g = frame[i * 3 + 1];
      std::uint8_t r = frame[i * 3 + 2];
      std::uint8_t out[3];
      out[dst_b_] = b;
      out[dst_g_] = g;
      out[dst_r_] = r;
      frame[i * 3 + 0] = out[0];
      frame[i * 3 + 1] = out[1];
      frame[i * 3 + 2] = out[2];
    }
  }

 private:
  int dst_b_, dst_g_, dst_r_;
};

void apply_channel_swap_impl(std::uint8_t* data, int width, int height, int channels,
                             int dst_for_b, int dst_for_g, int dst_for_r) {
  ChannelSwapFilter f(dst_for_b, dst_for_g, dst_for_r);
  f.apply(data, width, height, channels);
}

}  // namespace filters
