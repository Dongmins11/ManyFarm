// 설치된 Nav2 플러그인으로 회전 진행과 실제 정지 실패를 검증한다.
#include <cmath>
#include <iostream>
#include <stdexcept>
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "nav2_controller/plugins/pose_progress_checker.hpp"
#include "nav2_controller/plugins/simple_progress_checker.hpp"
#include "rcl/time.h"

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp_lifecycle::LifecycleNode>("progress_checker_regression");
  node->declare_parameter("simple.required_movement_radius", 0.1);
  node->declare_parameter("pose.required_movement_radius", 0.1);
  node->declare_parameter("pose.required_movement_angle", 0.5);
  nav2_controller::SimpleProgressChecker simple;
  nav2_controller::PoseProgressChecker pose;
  simple.initialize(node, "simple"); pose.initialize(node, "pose");
  auto clock = node->get_clock()->get_clock_handle();
  if (rcl_enable_ros_time_override(clock) != RCL_RET_OK) throw std::runtime_error("clock override");
  auto time = [&](double seconds) {
    if (rcl_set_ros_time_override(clock, static_cast<int64_t>(seconds*1e9)) != RCL_RET_OK)
      throw std::runtime_error("set clock");
  };
  auto position = [](double x, double yaw) {
    geometry_msgs::msg::PoseStamped p;
    p.pose.position.x = x;
    p.pose.orientation.z = std::sin(yaw/2.);
    p.pose.orientation.w = std::cos(yaw/2.);
    return p;
  };
  auto expect = [](bool condition, const char *label) {
    if (!condition) throw std::runtime_error(label);
    std::cout << "PASS " << label << '\n';
  };
  // 저속 약 180도 회전: XY가 고정되어도 각도가 진행하며 ±π 경계를 통과한다.
  bool simple_failed=false, pose_failed=false;
  for (int i=0; i<=150; ++i) {
    time(100.+i*.1); auto p=position(0., 2.8+i*.02);
    simple_failed |= !simple.check(p); pose_failed |= !pose.check(p);
  }
  expect(simple_failed, "original checker rejects ongoing rotation after 10s");
  expect(!pose_failed, "pose checker accepts 15s rotation including yaw wrap");
  pose.reset(); time(200.); auto p=position(0.,0.); expect(pose.check(p),"reset starts new baseline");
  time(210.1); expect(!pose.check(p), "stationary robot fails after 10s");
  pose.reset(); time(300.); p=position(0.,0.); pose.check(p);
  for(int i=1;i<=100;++i) {time(300.+i*.1);p=position(.005*std::sin(i),.05*std::sin(i));pose.check(p);}
  time(310.1); expect(!pose.check(p),"small pose jitter does not mask stall");
  pose.reset(); bool moving_failed=false;
  for(int i=0;i<=150;++i) {time(400.+i*.1);p=position(i*.01,0.);moving_failed |= !pose.check(p);}
  expect(!moving_failed,"translation still counts as progress");
  time(425.2);expect(!pose.check(p),"stall after translation still fails");
  node.reset();rclcpp::shutdown();
}
