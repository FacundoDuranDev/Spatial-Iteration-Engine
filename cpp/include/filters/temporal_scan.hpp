#ifndef SPATIAL_FILTERS_TEMPORAL_SCAN_HPP
#define SPATIAL_FILTERS_TEMPORAL_SCAN_HPP

#include <cstdint>
#include <vector>

namespace filters {

// Temporal scan: each pixel samples from a different past frame in a ring
// buffer. The frame-index at each pixel is a function of the pixel's position
// projected onto a direction vector (angle_deg). Degenerates to the classic
// slit-scan effect when angle_deg = 0 (all columns) or 90 (all rows), and
// produces diagonal / arbitrary-angle scans in between.
class TemporalScan {
 public:
  enum Curve : int {
    CURVE_LINEAR = 0,
    CURVE_EASE = 1,
  };

  TemporalScan(int max_frames, double angle_deg);

  // Write the current frame into the ring buffer and produce an output of the
  // same shape. Input is read-only; output is written fully.
  // Both pointers must point to contiguous H*W*C uint8 data.
  void apply(const std::uint8_t* input, std::uint8_t* output,
             int h, int w, int c);

  // Clear the ring buffer so the next frame starts fresh.
  void reset();

  void set_angle_deg(double a) { angle_deg_ = a; }
  double angle_deg() const { return angle_deg_; }

  void set_curve(int c) { curve_ = c; }
  int curve() const { return curve_; }

  int max_frames() const { return max_frames_; }
  int stored_frames() const { return n_frames_; }

 private:
  int max_frames_;
  double angle_deg_;
  int curve_ = CURVE_LINEAR;

  // Ring buffer of flattened frames; allocated lazily on first apply with the
  // actual resolution, and reallocated if the resolution changes.
  std::vector<std::vector<std::uint8_t>> frames_;
  int frame_h_ = 0;
  int frame_w_ = 0;
  int frame_c_ = 0;
  int write_idx_ = 0;   // next slot to overwrite
  int n_frames_ = 0;    // how many slots contain valid data (≤ max_frames_)

  void ensure_buffer_(int h, int w, int c);
};

}  // namespace filters

#endif
