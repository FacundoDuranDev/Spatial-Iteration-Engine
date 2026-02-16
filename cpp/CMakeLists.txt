cmake_minimum_required(VERSION 3.15)
project(spatial_render LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)

# pybind11 via FetchContent
include(FetchContent)
FetchContent_Declare(
  pybind11
  GIT_REPOSITORY https://github.com/pybind/pybind11.git
  GIT_TAG        v2.11.1
)
FetchContent_MakeAvailable(pybind11)

# ---------------------------------------------------------------------------
# filters_cpp: C++ image filters (Phase 1 implemented, Phase 2 stubs)
# ---------------------------------------------------------------------------
set(FILTERS_SOURCES
  src/filters/brightness_contrast.cpp
  src/filters/invert.cpp
  src/filters/grayscale.cpp
  src/filters/channel_swap.cpp
  src/filters/threshold.cpp
  src/filters/edge.cpp
  src/filters/blur.cpp
  src/filters/posterize.cpp
  src/filters/sharpen.cpp
)
pybind11_add_module(filters_cpp src/bridge/pybind_filters.cpp ${FILTERS_SOURCES})
target_include_directories(filters_cpp PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)

# ---------------------------------------------------------------------------
# perception_cpp: face/hands/pose landmarks (MVP_03) con ONNX Runtime opcional
# ---------------------------------------------------------------------------
# Buscar ONNX Runtime (conda: conda install -c conda-forge onnxruntime-cpp)
set(ONNXRUNTIME_ROOT "$ENV{CONDA_PREFIX}" CACHE PATH "Conda prefix or ONNXRUNTIME install root")
if(NOT ONNXRUNTIME_ROOT)
  set(ONNXRUNTIME_ROOT "$ENV{ONNXRUNTIME_ROOT}" CACHE PATH "ONNX Runtime root")
endif()
find_path(ONNXRUNTIME_INCLUDE_DIR onnxruntime_cxx_api.h
  HINTS ${ONNXRUNTIME_ROOT}/include NO_DEFAULT_PATH)
find_library(ONNXRUNTIME_LIB onnxruntime
  HINTS ${ONNXRUNTIME_ROOT}/lib NO_DEFAULT_PATH)
if(ONNXRUNTIME_INCLUDE_DIR AND ONNXRUNTIME_LIB)
  message(STATUS "ONNX Runtime found: ${ONNXRUNTIME_INCLUDE_DIR}, ${ONNXRUNTIME_LIB}")
  set(USE_ONNXRUNTIME 1)
else()
  message(STATUS "ONNX Runtime not found; perception will use stubs (no real landmarks). Install: conda install -c conda-forge onnxruntime-cpp")
  set(USE_ONNXRUNTIME 0)
endif()

set(PERCEPTION_SOURCES
  src/perception/face_landmarks.cpp
  src/perception/hand_landmarks.cpp
  src/perception/pose_landmarks.cpp
  src/perception/onnx_runner.cpp
)
pybind11_add_module(perception_cpp src/bridge/pybind_perception.cpp ${PERCEPTION_SOURCES})
target_include_directories(perception_cpp PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
if(USE_ONNXRUNTIME)
  target_include_directories(perception_cpp PRIVATE ${ONNXRUNTIME_INCLUDE_DIR})
  target_link_libraries(perception_cpp PRIVATE ${ONNXRUNTIME_LIB})
  target_compile_definitions(perception_cpp PRIVATE USE_ONNXRUNTIME=1)
endif()

# ---------------------------------------------------------------------------
# render_bridge (stub for deformed render)
# ---------------------------------------------------------------------------
pybind11_add_module(render_bridge src/bridge/pybind_bridge.cpp)
target_include_directories(render_bridge PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
