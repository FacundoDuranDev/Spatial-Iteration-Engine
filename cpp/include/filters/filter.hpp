#ifndef SPATIAL_FILTERS_FILTER_HPP
#define SPATIAL_FILTERS_FILTER_HPP

#include <cstdint>

namespace filters {

/**
 * Interfaz genérica de filtros de imagen (in-place).
 * Buffer: C-contiguous, uint8, layout (height, width, channels).
 */
class Filter {
 public:
  virtual ~Filter() = default;
  virtual void apply(std::uint8_t* frame, int width, int height, int channels) = 0;
};

}  // namespace filters

#endif
