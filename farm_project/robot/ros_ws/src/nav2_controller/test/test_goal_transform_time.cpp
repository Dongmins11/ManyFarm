// Copyright (c) 2026 Farm Team
// SPDX-License-Identifier: Apache-2.0

#include <cmath>
#include <memory>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "nav2_controller/controller_server.hpp"
#include "nav2_controller/plugins/simple_goal_checker.hpp"
#include "nav2_core/controller_exceptions.hpp"
#include "nav2_regulated_pure_pursuit_controller/path_handler.hpp"
#include "nav_2d_utils/tf_help.hpp"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"

namespace
{

class MeasuringGoalChecker : public nav2_controller::SimpleGoalChecker
{
public:
  double distance = 0.0;

  bool isGoalReached(
    const geometry_msgs::msg::Pose & pose, const geometry_msgs::msg::Pose & goal,
    const geometry_msgs::msg::Twist & velocity) override
  {
    distance = std::hypot(goal.position.x - pose.position.x, goal.position.y - pose.position.y);
    return SimpleGoalChecker::isGoalReached(pose, goal, velocity);
  }
};

class ControllerProbe : public nav2_controller::ControllerServer
{
public:
  using ControllerServer::isGoalReached;

  void prepare()
  {
    // 활성 주행 없이 실제 TF buffer와 costmap을 생성한다.
    costmap_ros_->set_parameters({
        rclcpp::Parameter("global_frame", "odom"),
        rclcpp::Parameter("robot_base_frame", "base_link"),
        rclcpp::Parameter("plugins", std::vector<std::string>{}),
        rclcpp::Parameter("transform_tolerance", 0.0)});
    costmap_ros_->configure();
    odom_sub_ = std::make_unique<nav_2d_utils::OdomSubscriber>(shared_from_this());
    declare_parameter("goal_checker.xy_goal_tolerance", 0.04);
    declare_parameter("goal_checker.yaw_goal_tolerance", 2.5 * M_PI / 180.0);
    checker = std::make_shared<MeasuringGoalChecker>();
    checker->initialize(shared_from_this(), "goal_checker", costmap_ros_);
    current_goal_checker_ = "goal_checker";
    goal_checkers_[current_goal_checker_] = checker;
  }

  void goal(const geometry_msgs::msg::PoseStamped & goal) {end_pose_ = goal;}
  auto costmap() {return costmap_ros_;}
  std::shared_ptr<MeasuringGoalChecker> checker;
};

class GoalTransformTime : public ::testing::Test
{
protected:
  std::shared_ptr<ControllerProbe> server;
  std::shared_ptr<tf2_ros::Buffer> tf;
  geometry_msgs::msg::PoseStamped robot;
  geometry_msgs::msg::PoseStamped goal;

  static void SetUpTestSuite() {rclcpp::init(0, nullptr);}
  static void TearDownTestSuite() {rclcpp::shutdown();}

  void transform(const std::string & parent, const std::string & child, int second, double x)
  {
    geometry_msgs::msg::TransformStamped value;
    value.header.frame_id = parent;
    value.child_frame_id = child;
    value.header.stamp.sec = second;
    value.transform.translation.x = x;
    value.transform.rotation.w = 1.0;
    ASSERT_TRUE(tf->setTransform(value, "goal_time_test"));
  }

  void SetUp() override
  {
    server = std::make_shared<ControllerProbe>();
    server->prepare();
    tf = server->costmap()->getTfBuffer();
    robot.header.frame_id = "odom";
    robot.header.stamp.sec = 100;
    robot.pose.position.x = 0.95;
    robot.pose.orientation.w = 1.0;
    goal.header.frame_id = "map";
    goal.header.stamp.sec = 50;  // TF 캐시보다 오래된 경로 생성 시각
    goal.pose.position.x = 1.0;
    goal.pose.orientation.w = 1.0;
    server->goal(goal);
    // 같은 목표에 현재 시각은 3.9407cm, latest는 5.0957cm가 되는 AMCL 보정.
    transform("map", "odom", 92, 0.01059262782036149);
    transform("map", "odom", 100, 0.01059262782036149);
    transform("map", "odom", 101, -0.00095746930915274);
    transform("odom", "base_link", 100, robot.pose.position.x);
  }

  void TearDown() override
  {
    server->costmap()->cleanup();
    server.reset();
    tf.reset();
  }
};

TEST_F(GoalTransformTime, OldPathFallbackDisagreesButCurrentPoseMatchesRpp)
{
  // 수정 전 helper를 실행해 오래된 stamp가 latest로 대체되는 것을 확인한다.
  geometry_msgs::msg::PoseStamped old_goal;
  auto tolerance = rclcpp::Duration::from_seconds(0.0);
  ASSERT_TRUE(nav_2d_utils::transformPose(
      tf, "odom", goal, old_goal, tolerance));
  EXPECT_NEAR(std::abs(old_goal.pose.position.x - robot.pose.position.x),
    0.05095746930915274, 1e-12);

  nav_msgs::msg::Path path;
  path.header = goal.header;
  path.poses.push_back(goal);
  nav2_regulated_pure_pursuit_controller::PathHandler rpp(
    tf2::durationFromSec(0.0), tf, server->costmap());
  rpp.setPlan(path);
  const auto local_path = rpp.transformGlobalPlan(robot, 10.0);
  ASSERT_FALSE(local_path.poses.empty());
  const auto & target = local_path.poses.back().pose.position;
  const double rpp_distance = std::hypot(target.x, target.y);
  ASSERT_NEAR(rpp_distance, 0.03940737217963851, 1e-12);
  ASSERT_TRUE(server->isGoalReached(robot));
  EXPECT_NEAR(server->checker->distance, rpp_distance, 1e-12);
}

TEST_F(GoalTransformTime, PathStampDoesNotChangeArrival)
{
  for (const int stamp : {0, 50, 100, 101}) {
    goal.header.stamp.sec = stamp;
    server->goal(goal);
    server->checker->reset();
    EXPECT_TRUE(server->isGoalReached(robot));
    EXPECT_NEAR(server->checker->distance, 0.03940737217963851, 1e-12);
  }
}

TEST_F(GoalTransformTime, UsesControlPoseEvenWhenNewerRobotTfArrives)
{
  transform("odom", "base_link", 101, 0.80);
  EXPECT_TRUE(server->isGoalReached(robot));
  EXPECT_NEAR(server->checker->distance, 0.03940737217963851, 1e-12);
}

TEST_F(GoalTransformTime, OutsidePositionAndYawStillFail)
{
  robot.pose.position.x -= 0.02;
  EXPECT_FALSE(server->isGoalReached(robot));
  server->checker->reset();
  robot.pose.position.x += 0.02;
  robot.pose.orientation.z = std::sin(0.1 / 2.0);
  robot.pose.orientation.w = std::cos(0.1 / 2.0);
  EXPECT_FALSE(server->isGoalReached(robot));
}

TEST_F(GoalTransformTime, SameFrameGoalStillWorks)
{
  goal.header.frame_id = "odom";
  goal.pose.position.x = 0.98;
  server->goal(goal);
  EXPECT_TRUE(server->isGoalReached(robot));
  EXPECT_NEAR(server->checker->distance, 0.03, 1e-12);
}

TEST_F(GoalTransformTime, MissingCurrentTransformCannotFallbackToLatest)
{
  robot.header.stamp.sec = 110;
  EXPECT_THROW(server->isGoalReached(robot), nav2_core::ControllerTFError);
  robot.header.stamp.sec = 80;
  EXPECT_THROW(server->isGoalReached(robot), nav2_core::ControllerTFError);
  robot.header.stamp.sec = 100;
  goal.header.frame_id = "missing_map";
  server->goal(goal);
  EXPECT_THROW(server->isGoalReached(robot), nav2_core::ControllerTFError);
}

}  // namespace
