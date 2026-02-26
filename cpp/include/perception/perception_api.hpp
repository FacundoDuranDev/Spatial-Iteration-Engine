#ifndef SPATIAL_PERCEPTION_API_HPP
#define SPATIAL_PERCEPTION_API_HPP

#include <cstdint>
#include <vector>

namespace perception {

std::vector<float> run_face(std::uint8_t* image, int width, int height);
std::vector<float> run_hands(std::uint8_t* image, int width, int height);
std::vector<float> run_pose(std::uint8_t* image, int width, int height);
std::vector<float> run_pose_with_confidence(std::uint8_t* image, int width, int height);
// TODO: perception team must implement these:
// std::vector<float> run_object_detection(std::uint8_t* image, int width, int height);
// std::vector<float> run_emotion(std::uint8_t* image, int width, int height);
// std::vector<float> run_segmentation(std::uint8_t* image, int width, int height);

}  // namespace perception

#endif
