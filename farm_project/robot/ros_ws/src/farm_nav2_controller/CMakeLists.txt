cmake_minimum_required(VERSION 3.16)
project(farm_nav2_controller)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav2_core REQUIRED)
find_package(nav2_regulated_pure_pursuit_controller REQUIRED)
find_package(pluginlib REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

add_library(${PROJECT_NAME} SHARED src/settling_regulated_pure_pursuit_controller.cpp
  src/reverse_regulated_pure_pursuit_controller.cpp)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
ament_target_dependencies(${PROJECT_NAME}
  geometry_msgs nav2_core nav2_regulated_pure_pursuit_controller
  pluginlib tf2 tf2_geometry_msgs)
target_compile_options(${PROJECT_NAME} PRIVATE -Wall -Wextra -Wpedantic)
pluginlib_export_plugin_description_file(nav2_core controller_plugins.xml)
install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION bin)
install(DIRECTORY include/ DESTINATION include)
ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_dependencies(
  geometry_msgs nav2_core nav2_regulated_pure_pursuit_controller
  pluginlib tf2 tf2_geometry_msgs)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_reverse_approach test/test_reverse_approach.cpp)
  target_link_libraries(test_reverse_approach ${PROJECT_NAME})
  ament_add_gtest(test_settling_controller test/test_settling_controller.cpp)
  target_link_libraries(test_settling_controller ${PROJECT_NAME})
endif()
ament_package()
