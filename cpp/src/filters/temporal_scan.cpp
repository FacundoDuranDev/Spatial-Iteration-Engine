#include "filters/temporal_scan.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace filters {

namespace {

// Smooth-step curve used by CURVE_EASE (standard Perlin smoothstep).
inline double smoothstep(double t) {
  t = std::clamp(t, 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

}  // namespace

TemporalScan::TemporalScan(int max_frames, double angle_deg)
    : max_frames_(std::max(2, max_frames)),
      angle_deg_(angle_deg) {
  frames_.resize(max_frames_);
}

void TemporalScan::ensure_buffer_(int h, int w, int c) {
  if (h == frame_h_ && w == frame_w_ && c == frame_c_) return;
  frame_h_ = h;
  frame_w_ = w;
  frame_c_ = c;
  const size_t frame_bytes = static_cast<size_t>(h) * w * c;
  for (auto& buf : frames_) buf.assign(frame_bytes, 0);
  write_idx_ = 0;
  n_frames_ = 0;
}

void TemporalScan::reset() {
  write_idx_ = 0;
  n_frames_ = 0;
}

void TemporalScan::apply(const std::uint8_t* input, std::uint8_t* output,
                         int h, int w, int c) {
  ensure_buffer_(h, w, c);
  const size_t frame_bytes = static_cast<size_t>(h) * w * c;

  // Write the incoming frame into the ring buffer.
  const int current_slot = write_idx_;
  std::memcpy(frames_[current_slot].data(), input, frame_bytes);
  write_idx_ = (write_idx_ + 1) % max_frames_;
  if (n_frames_ < max_frames_) ++n_frames_;

  // Not enough history yet — pass the input through unchanged.
  if (n_frames_ < 2) {
    std::memcpy(output, input, frame_bytes);
    return;
  }

  // Direction vector in normalized image space. We project every pixel's
  // normalized coord onto it and rescale to [0, n_frames-1].
  const double angle_rad = angle_deg_ * M_PI / 180.0;
  const double cos_a = std::cos(angle_rad);
  const double sin_a = std::sin(angle_rad);
  // Max absolute projection value over the unit square [-1, 1]^2.
  const double proj_max = std::abs(cos_a) + std::abs(sin_a);
  const double proj_norm = (proj_max > 1e-9) ? (1.0 / (2.0 * proj_max)) : 0.0;

  const int denom_h = std::max(1, h - 1);
  const int denom_w = std::max(1, w - 1);
  const int max_t = n_frames_ - 1;

  // For each row, precompute the y contribution (cheap win).
  for (int y = 0; y < h; ++y) {
    const double yn = static_cast<double>(y) / denom_h * 2.0 - 1.0;
    const double y_proj = yn * sin_a;
    for (int x = 0; x < w; ++x) {
      const double xn = static_cast<double>(x) / denom_w * 2.0 - 1.0;
      // Range of (xn*cos + yn*sin) is [-proj_max, proj_max]; map to [0,1].
      double t_norm = (xn * cos_a + y_proj + proj_max) * proj_norm;
      if (curve_ == CURVE_EASE) t_norm = smoothstep(t_norm);
      int t = static_cast<int>(t_norm * max_t + 0.5);
      if (t < 0) t = 0;
      else if (t > max_t) t = max_t;
      // t = 0 -> newest frame (just written), t = max_t -> oldest.
      int slot = current_slot - t;
      if (slot < 0) slot += max_frames_;
      const std::uint8_t* src = frames_[slot].data() + (y * w + x) * c;
      std::uint8_t* dst = output + (y * w + x) * c;
      std::memcpy(dst, src, c);
    }
  }
}

}  // namespace filters
