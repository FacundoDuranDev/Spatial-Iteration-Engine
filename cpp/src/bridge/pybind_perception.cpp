/**
 * Bridge pybind11: perception_cpp — detect_face, detect_hands, detect_pose,
 * detect_objects, detect_emotion, detect_segmentation, detect_pose_with_confidence.
 * Input: frame uint8 (H,W,3) BGR. Output: numpy float32 arrays.
 */
#include "perception/perception_api.hpp"
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <stdexcept>
#include <vector>

namespace py = pybind11;

static void require_3d_uint8(const py::array_t<std::uint8_t>& frame) {
  if (frame.ndim() != 3)
    throw std::runtime_error("frame must be 3D (height, width, channels)");
  if (frame.shape(2) != 3)
    throw std::runtime_error("frame must have 3 channels");
}

static py::array_t<float> landmarks_to_numpy(const std::vector<float>& data) {
  if (data.size() % 2 != 0) {
    std::vector<py::ssize_t> shape = {0, 2};
    return py::array_t<float>(shape);
  }
  size_t n = data.size() / 2;
  std::vector<py::ssize_t> shape = {static_cast<py::ssize_t>(n), 2};
  py::array_t<float> out(shape);
  py::buffer_info buf = out.request(true);
  float* ptr = static_cast<float*>(buf.ptr);
  for (size_t i = 0; i < data.size(); ++i)
    ptr[i] = data[i];
  return out;
}

/** Convert a flat float vector to a 1D numpy array. */
static py::array_t<float> flat_to_numpy(const std::vector<float>& data) {
  std::vector<py::ssize_t> shape = {static_cast<py::ssize_t>(data.size())};
  py::array_t<float> out(shape);
  py::buffer_info buf = out.request(true);
  float* ptr = static_cast<float*>(buf.ptr);
  for (size_t i = 0; i < data.size(); ++i)
    ptr[i] = data[i];
  return out;
}

PYBIND11_MODULE(perception_cpp, m) {
  m.doc() = "Perception C++ (face, hands, pose, objects, emotion, segmentation). MVP_03.";

  m.def(
      "detect_face",
      [](py::array_t<std::uint8_t> frame) {
        require_3d_uint8(frame);
        py::buffer_info buf = frame.request();
        int h = static_cast<int>(buf.shape[0]);
        int w = static_cast<int>(buf.shape[1]);
        std::uint8_t* ptr = static_cast<std::uint8_t*>(buf.ptr);
        std::vector<float> data;
        {
          py::gil_scoped_release release;
          data = perception::run_face(ptr, w, h);
        }
        return landmarks_to_numpy(data);
      },
      py::arg("frame"),
      "Detect face landmarks. Returns (N,2) float32 normalized 0..1. Stub: empty.");

  m.def(
      "detect_hands",
      [](py::array_t<std::uint8_t> frame) {
        require_3d_uint8(frame);
        py::buffer_info buf = frame.request();
        int h = static_cast<int>(buf.shape[0]);
        int w = static_cast<int>(buf.shape[1]);
        std::uint8_t* ptr = static_cast<std::uint8_t*>(buf.ptr);
        std::vector<float> data;
        {
          py::gil_scoped_release release;
          data = perception::run_hands(ptr, w, h);
        }
        return landmarks_to_numpy(data);
      },
      py::arg("frame"),
      "Detect hand landmarks. Returns (N,2) float32. Stub: empty.");

  m.def(
      "detect_pose",
      [](py::array_t<std::uint8_t> frame) {
        require_3d_uint8(frame);
        py::buffer_info buf = frame.request();
        int h = static_cast<int>(buf.shape[0]);
        int w = static_cast<int>(buf.shape[1]);
        std::uint8_t* ptr = static_cast<std::uint8_t*>(buf.ptr);
        std::vector<float> data;
        {
          py::gil_scoped_release release;
          data = perception::run_pose(ptr, w, h);
        }
        return landmarks_to_numpy(data);
      },
      py::arg("frame"),
      "Detect pose landmarks. Returns (N,2) float32. Stub: empty.");

  m.def(
      "detect_pose_with_confidence",
      [](py::array_t<std::uint8_t> frame) {
        require_3d_uint8(frame);
        py::buffer_info buf = frame.request();
        int h = static_cast<int>(buf.shape[0]);
        int w = static_cast<int>(buf.shape[1]);
        std::uint8_t* ptr = static_cast<std::uint8_t*>(buf.ptr);
        std::vector<float> data;
        {
          py::gil_scoped_release release;
          data = perception::run_pose_with_confidence(ptr, w, h);
        }
        // Returns flat 1D array: [x, y, conf, x, y, conf, ...]
        return flat_to_numpy(data);
      },
      py::arg("frame"),
      "Detect pose with confidence. Returns 1D float32 (N*3): x, y, conf per joint.");

  m.def(
      "detect_objects",
      [](py::array_t<std::uint8_t> frame) {
        require_3d_uint8(frame);
        py::buffer_info buf = frame.request();
        int h = static_cast<int>(buf.shape[0]);
        int w = static_cast<int>(buf.shape[1]);
        std::uint8_t* ptr = static_cast<std::uint8_t*>(buf.ptr);
        std::vector<float> data;
        {
          py::gil_scoped_release release;
          data = perception::run_object_detection(ptr, w, h);
        }
        // Return as 1D float array; Python does NMS and reshape
        return flat_to_numpy(data);
      },
      py::arg("frame"),
      "Detect objects (YOLOv8-nano). Returns flat float32 array.");

  m.def(
      "detect_emotion",
      [](py::array_t<std::uint8_t> frame) {
        require_3d_uint8(frame);
        py::buffer_info buf = frame.request();
        int h = static_cast<int>(buf.shape[0]);
        int w = static_cast<int>(buf.shape[1]);
        std::uint8_t* ptr = static_cast<std::uint8_t*>(buf.ptr);
        std::vector<float> data;
        {
          py::gil_scoped_release release;
          data = perception::run_emotion(ptr, w, h);
        }
        // Return raw logits as 1D float array; Python applies softmax
        return flat_to_numpy(data);
      },
      py::arg("frame"),
      "Detect emotion. Returns 1D float32 logits (7 values).");

  m.def(
      "detect_segmentation",
      [](py::array_t<std::uint8_t> frame) {
        require_3d_uint8(frame);
        py::buffer_info buf = frame.request();
        int h = static_cast<int>(buf.shape[0]);
        int w = static_cast<int>(buf.shape[1]);
        std::uint8_t* ptr = static_cast<std::uint8_t*>(buf.ptr);
        std::vector<float> data;
        {
          py::gil_scoped_release release;
          data = perception::run_segmentation(ptr, w, h);
        }
        // Return raw logits as flat float array; Python reshapes and argmax
        return flat_to_numpy(data);
      },
      py::arg("frame"),
      "Detect scene segmentation. Returns flat float32 logits.");
}
