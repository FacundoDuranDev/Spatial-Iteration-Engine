#ifndef SPATIAL_FILTERS_FILTERS_API_HPP
#define SPATIAL_FILTERS_FILTERS_API_HPP

#include <cstdint>

namespace filters {

void apply_brightness_contrast_impl(std::uint8_t* data, int width, int height,
                                   int channels, int brightness_delta,
                                   double contrast_factor);

void apply_invert_impl(std::uint8_t* data, int width, int height, int channels);

void apply_grayscale_impl(std::uint8_t* data, int width, int height, int channels);

void apply_channel_swap_impl(std::uint8_t* data, int width, int height, int channels,
                             int dst_for_b, int dst_for_g, int dst_for_r);

// Phase 2 stubs (no-op until implemented)
void apply_threshold_impl(std::uint8_t* data, int width, int height, int channels,
                          std::uint8_t threshold);
void apply_edge_impl(std::uint8_t* data, int width, int height, int channels);
void apply_blur_impl(std::uint8_t* data, int width, int height, int channels, int kernel_size);
void apply_posterize_impl(std::uint8_t* data, int width, int height, int channels, int levels);
void apply_sharpen_impl(std::uint8_t* data, int width, int height, int channels, double strength);

}  // namespace filters

#endif
