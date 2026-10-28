# Test dynamic parameters
ament_add_gtest(test_dynamic_parameters
  test_dynamic_parameters.cpp
)
ament_target_dependencies(test_dynamic_parameters
  ${dependencies}
)
target_link_libraries(test_dynamic_parameters
  ${library_name}
)

# 실측 105 원인: 현재 pose TF와 미래 시각 latest TF가 다른 조건을 재현한다.
find_package(nav2_regulated_pure_pursuit_controller REQUIRED)
ament_add_gtest(test_goal_transform_time test_goal_transform_time.cpp)
ament_target_dependencies(test_goal_transform_time
  ${dependencies} nav2_regulated_pure_pursuit_controller)
target_link_libraries(test_goal_transform_time ${library_name} simple_goal_checker)
