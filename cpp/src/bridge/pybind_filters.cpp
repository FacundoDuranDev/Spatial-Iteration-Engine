/**
 * Python bindings for C++ image filters. NumPy buffer must be C-contiguous, writable.
 * Frame layout: (height, width, channels), uint8, BGR (OpenCV convention).
 */
#include "filters/filters_api.hpp"
#include "filters/temporal_scan.hpp"
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <cstring>
#include <functional>
#include <stdexcept>

namespace py = pybind11;

static void require_3d_uint8(const py::array_t<std::uint8_t>& frame, int expected_channels = 3) {
  if (frame.ndim() != 3)
    throw std::runtime_error("frame must be 3D (height, width, channels)");
  if (frame.shape(2) != expected_channels)
    throw std::runtime_error("frame must have 3 channels (BGR)");
}

static void apply_in_place(py::array_t<std::uint8_t> frame,
                           std::function<void(std::uint8_t*, int, int, int)> f) {
  require_3d_uint8(frame);
  py::buffer_info buf = frame.request(true);  // writable
  int h = static_cast<int>(buf.shape[0]);
  int w = static_cast<int>(buf.shape[1]);
  int c = static_cast<int>(buf.shape[2]);
  auto* ptr = static_cast<std::uint8_t*>(buf.ptr);
  // Release the GIL while the C++ kernel runs so other Python threads can
  // progress (the numpy buffer is owned by Python and the pointer stays valid).
  py::gil_scoped_release release;
  f(ptr, w, h, c);
}

PYBIND11_MODULE(filters_cpp, m) {
  m.doc() = "C++ image filters for Spatial-Iteration-Engine (Phase 1: brightness, invert, grayscale, channel_swap)";

  m.def(
      "apply_brightness_contrast",
      [](py::array_t<std::uint8_t> frame, int brightness_delta, double contrast_factor) {
        apply_in_place(frame, [&](std::uint8_t* p, int w, int h, int c) {
          filters::apply_brightness_contrast_impl(p, w, h, c, brightness_delta, contrast_factor);
        });
      },
      py::arg("frame"),
      py::arg("brightness_delta") = 0,
      py::arg("contrast_factor") = 1.0,
      "In-place brightness and contrast adjustment.");

  m.def(
      "apply_invert",
      [](py::array_t<std::uint8_t> frame) {
        apply_in_place(frame, [](std::uint8_t* p, int w, int h, int c) {
          filters::apply_invert_impl(p, w, h, c);
        });
      },
      py::arg("frame"),
      "In-place invert (negative): pixel = 255 - pixel.");

  m.def(
      "apply_grayscale",
      [](py::array_t<std::uint8_t> frame) {
        apply_in_place(frame, [](std::uint8_t* p, int w, int h, int c) {
          filters::apply_grayscale_impl(p, w, h, c);
        });
      },
      py::arg("frame"),
      "In-place grayscale (luma); output remains 3-channel BGR.");

  m.def(
      "apply_channel_swap",
      [](py::array_t<std::uint8_t> frame, int dst_for_b, int dst_for_g, int dst_for_r) {
        apply_in_place(frame, [&](std::uint8_t* p, int w, int h, int c) {
          filters::apply_channel_swap_impl(p, w, h, c, dst_for_b, dst_for_g, dst_for_r);
        });
      },
      py::arg("frame"),
      py::arg("dst_for_b") = 2,
      py::arg("dst_for_g") = 1,
      py::arg("dst_for_r") = 0,
      "In-place channel permutation. (2,1,0) = BGR->RGB.");

  // Phase 2 stubs (no-op; interface ready for implementation)
  m.def("apply_threshold", [](py::array_t<std::uint8_t> frame, std::uint8_t threshold) {
        apply_in_place(frame, [&](std::uint8_t* p, int w, int h, int c) {
          filters::apply_threshold_impl(p, w, h, c, threshold);
        });
      }, py::arg("frame"), py::arg("threshold") = 127, "Phase 2 stub: binary threshold.");
  m.def("apply_edge", [](py::array_t<std::uint8_t> frame) {
        apply_in_place(frame, [](std::uint8_t* p, int w, int h, int c) {
          filters::apply_edge_impl(p, w, h, c);
        });
      }, py::arg("frame"), "Phase 2 stub: edge detection.");
  m.def("apply_blur", [](py::array_t<std::uint8_t> frame, int kernel_size) {
        apply_in_place(frame, [&](std::uint8_t* p, int w, int h, int c) {
          filters::apply_blur_impl(p, w, h, c, kernel_size);
        });
      }, py::arg("frame"), py::arg("kernel_size") = 5, "Phase 2 stub: Gaussian blur.");
  m.def("apply_posterize", [](py::array_t<std::uint8_t> frame, int levels) {
        apply_in_place(frame, [&](std::uint8_t* p, int w, int h, int c) {
          filters::apply_posterize_impl(p, w, h, c, levels);
        });
      }, py::arg("frame"), py::arg("levels") = 4, "Phase 2 stub: color quantization.");
  m.def("apply_sharpen", [](py::array_t<std::uint8_t> frame, double strength) {
        apply_in_place(frame, [&](std::uint8_t* p, int w, int h, int c) {
          filters::apply_sharpen_impl(p, w, h, c, strength);
        });
      }, py::arg("frame"), py::arg("strength") = 1.0, "Phase 2 stub: sharpen.");

  // ---------------------------------------------------------------------------
  // TemporalScan — stateful angle-aware temporal slit-scan.
  // ---------------------------------------------------------------------------
  py::class_<filters::TemporalScan>(m, "TemporalScan")
      .def(py::init<int, double>(),
           py::arg("max_frames") = 30,
           py::arg("angle_deg") = 0.0,
           "Create a TemporalScan with a ring buffer of `max_frames` frames "
           "and an initial scan angle in degrees.")
      .def("apply",
           [](filters::TemporalScan& self, py::array_t<std::uint8_t> frame) {
             require_3d_uint8(frame);
             py::buffer_info buf = frame.request(false);  // read-only source
             const int h = static_cast<int>(buf.shape[0]);
             const int w = static_cast<int>(buf.shape[1]);
             const int c = static_cast<int>(buf.shape[2]);

             // Output array of the same shape; memory owned by numpy.
             auto out = py::array_t<std::uint8_t>({h, w, c});
             py::buffer_info obuf = out.request(true);
             const std::uint8_t* in_ptr = static_cast<const std::uint8_t*>(buf.ptr);
             std::uint8_t* out_ptr = static_cast<std::uint8_t*>(obuf.ptr);

             {
               // Kernel is heap-only; safe to release the GIL.
               py::gil_scoped_release release;
               self.apply(in_ptr, out_ptr, h, w, c);
             }
             return out;
           },
           py::arg("frame"),
           "Push `frame` into the ring buffer and return the temporally-"
           "scanned output as a new ndarray of the same shape.")
      .def("reset", &filters::TemporalScan::reset,
           "Clear the ring buffer.")
      .def_property("angle_deg",
                    &filters::TemporalScan::angle_deg,
                    &filters::TemporalScan::set_angle_deg,
                    "Scan direction in degrees (0 = right-to-left, 90 = top-to-bottom, "
                    "arbitrary values produce diagonal scans).")
      .def_property("curve",
                    &filters::TemporalScan::curve,
                    &filters::TemporalScan::set_curve,
                    "Mapping curve from spatial projection to temporal index: "
                    "0 = linear, 1 = ease (smoothstep).")
      .def_property_readonly("max_frames", &filters::TemporalScan::max_frames)
      .def_property_readonly("stored_frames", &filters::TemporalScan::stored_frames);
}
