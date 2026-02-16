#ifndef SPATIAL_PERCEPTION_API_HPP
#define SPATIAL_PERCEPTION_API_HPP

#include <cstdint>
#include <vector>

namespace perception {

std::vector<float> run_face(std::uint8_t* image, int width, int height);
std::vector<float> run_hands(std::uint8_t* image, int width, int height);
std::vector<float> run_pose(std::uint8_t* image, int width, int height);

}  // namespace perception

#endif
