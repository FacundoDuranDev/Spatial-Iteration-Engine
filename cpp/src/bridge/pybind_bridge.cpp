/**
 * Stub bridge Python <-> C++ for render/deformed pipeline.
 * Contract: NumPy buffers C-contiguous, uint8 RGB; see docs/integration_v1.md.
 */
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <cstdint>
#include <cstring>
#include <tuple>

namespace py = pybind11;

// Stub: store last frame dimensions for get_output_shape
static int g_width = 0, g_height = 0;

void send_frame(py::array_t<uint8_t> frame) {
  if (frame.ndim() != 3 || frame.shape(2) != 3) return;
  g_height = static_cast<int>(frame.shape(0));
  g_width  = static_cast<int>(frame.shape(1));
  // Stub: no-op (no copy to internal buffer)
}

std::tuple<int, int> get_output_shape() {
  return std::make_tuple(g_width, g_height);
}

py::array_t<uint8_t> render(py::array_t<uint8_t> frame,
                            py::object mask) {
  py::buffer_info buf = frame.request();
  if (buf.ndim != 3 || buf.shape[2] != 3)
    throw std::runtime_error("frame must be (H, W, 3) uint8");
  (void)mask;  // stub: ignore mask
  // Stub: return copy of frame (no deformation)
  auto out = py::array_t<uint8_t>({buf.shape[0], buf.shape[1], buf.shape[2]});
  std::memcpy(out.mutable_data(), buf.ptr, static_cast<size_t>(buf.size * buf.itemsize));
  return out;
}

PYBIND11_MODULE(render_bridge, m) {
  m.doc() = "Stub bridge for spatial render (Python <-> C++)";
  m.def("send_frame", &send_frame, "Send frame to C++ (stub: no-op)");
  m.def("get_output_shape", &get_output_shape, "Get output (width, height)");
  m.def("render", &render,
        py::arg("frame"),
        py::arg("mask") = py::none(),
        "Render deformed frame; stub returns copy of frame");
}
