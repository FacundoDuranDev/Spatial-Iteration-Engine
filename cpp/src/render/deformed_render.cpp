/**
 * Stub for deformed render: frame + optional mask -> output buffer.
 * Real implementation will apply geometry/warp from mask or control data.
 */
#include <cstdint>
#include <cstring>

namespace spatial {

// Stub: copy input to output (same size). Caller ensures out has size >= w*h*3.
void deformed_render(const uint8_t* frame, int width, int height, int stride,
                     uint8_t* out) {
  if (!frame || !out || width <= 0 || height <= 0) return;
  if (stride <= 0) stride = width * 3;
  for (int y = 0; y < height; ++y) {
    std::memcpy(out + y * width * 3, frame + y * stride, static_cast<size_t>(width * 3));
  }
}

}  // namespace spatial
