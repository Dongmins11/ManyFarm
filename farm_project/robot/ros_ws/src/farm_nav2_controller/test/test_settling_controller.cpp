#include <cmath>
#include <limits>
#include <memory>

#include "gtest/gtest.h"
#include "farm_nav2_controller/reverse_regulated_pure_pursuit_controller.hpp"
#include "farm_nav2_controller/settling_regulated_pure_pursuit_controller.hpp"
#include "geometry_msgs/msg/transform_stamped.hpp"
#include "nav2_core/controller_exceptions.hpp"
#include "tf2_ros/buffer.h"

namespace
{

geometry_msgs::msg::Quaternion yawQuaternion(double yaw)
{
  geometry_msgs::msg::Quaternion result;
  result.z = std::sin(yaw / 2.0);
  result.w = std::cos(yaw / 2.0);
  return result;
}

class ReverseHeadingProbe : public farm_nav2_controller::ReverseRegulatedPurePursuitController
{
public:
  using ReverseRegulatedPurePursuitController::validateHeading;
};

TEST(ReverseArrival, FinalAlignmentAllowsBothHalfTurnsWithoutRelaxingTracking)
{
  for (double angle : {M_PI, -M_PI, 2.0, -2.0}) {
    EXPECT_NO_THROW(ReverseHeadingProbe::validateHeading(angle, true));
    EXPECT_THROW(ReverseHeadingProbe::validateHeading(angle, false), nav2_core::InvalidPath);
  }
  EXPECT_NO_THROW(ReverseHeadingProbe::validateHeading(0.01092, false));
  EXPECT_NO_THROW(ReverseHeadingProbe::validateHeading(M_PI_2 + 0.1, false));
  EXPECT_THROW(ReverseHeadingProbe::validateHeading(M_PI_2 + 0.1001, false), nav2_core::InvalidPath);
}

TEST(ReverseArrival, InvalidAnglesFailInBothPhasesWithDiagnostic)
{
  for (bool at_goal : {false, true}) {
    for (double angle : {std::numeric_limits<double>::quiet_NaN(),
      std::numeric_limits<double>::infinity()})
    {
      EXPECT_THROW(ReverseHeadingProbe::validateHeading(angle, at_goal), nav2_core::InvalidPath);
    }
  }
  try {
    ReverseHeadingProbe::validateHeading(2.0, false);
    FAIL() << "후진 방향과 반대인 경로를 거절해야 한다";
  } catch (const nav2_core::InvalidPath & error) {
    EXPECT_NE(std::string(error.what()).find("phase=TRACKING"), std::string::npos);
    EXPECT_NE(std::string(error.what()).find("angle_rad=2.000000"), std::string::npos);
  }
}

class GoalChecker : public nav2_core::GoalChecker
{
public:
  geometry_msgs::msg::Pose tolerance;
  bool valid = true;
  GoalChecker()
  {
    tolerance.position.x = tolerance.position.y = 0.015;
    tolerance.orientation = yawQuaternion(0.01);
  }
  void initialize(
    const rclcpp_lifecycle::LifecycleNode::WeakPtr &, const std::string &,
    const std::shared_ptr<nav2_costmap_2d::Costmap2DROS>) override {}
  void reset() override {}
  bool isGoalReached(
    const geometry_msgs::msg::Pose &, const geometry_msgs::msg::Pose &,
    const geometry_msgs::msg::Twist &) override
  {
    ADD_FAILURE() << "제어기는 GoalChecker 성공/상태를 변경하면 안 된다";
    return false;
  }
  bool getTolerances(
    geometry_msgs::msg::Pose & pose, geometry_msgs::msg::Twist &) override
  {
    pose = tolerance;
    return valid;
  }
};

class Controller : public farm_nav2_controller::SettlingRegulatedPurePursuitController
{
public:
  explicit Controller(const std::shared_ptr<tf2_ros::Buffer> & tf)
  {
    path_handler_ = std::make_unique<nav2_regulated_pure_pursuit_controller::PathHandler>(
      tf2::durationFromSec(0.0), tf, nullptr);
  }
  using SettlingRegulatedPurePursuitController::settleAtGoal;
};

// 설치된 원본 RPP의 도착 전환을 직접 호출한다. 제어 로직을 시험에 복사하지 않는다.
class RppArrivalProbe
  : public nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController
{
public:
  explicit RppArrivalProbe(bool stateful)
  {
    parameters_.use_rotate_to_heading = true;
    parameters_.stateful = stateful;
    params_ = &parameters_;
    goal_dist_tol_ = 0.03;
  }
  bool rotatesAtDistance(double distance)
  {
    geometry_msgs::msg::PoseStamped carrot;
    carrot.pose.position.x = distance;
    return shouldRotateToGoalHeading(carrot);
  }

private:
  nav2_regulated_pure_pursuit_controller::Parameters parameters_{};
};

TEST(RppArrivalCorrection, StatefulRetainsRotationAfterLocalizationMovesOutside)
{
  RppArrivalProbe controller(true);
  EXPECT_FALSE(controller.rotatesAtDistance(0.10));
  EXPECT_TRUE(controller.rotatesAtDistance(0.025));
  EXPECT_TRUE(controller.rotatesAtDistance(0.03066));
  EXPECT_TRUE(controller.rotatesAtDistance(0.048));
}

TEST(RppArrivalCorrection, CurrentPositionResumesTrackingWithoutResettingGoal)
{
  RppArrivalProbe controller(false);
  EXPECT_FALSE(controller.rotatesAtDistance(0.10));
  EXPECT_TRUE(controller.rotatesAtDistance(0.025));
  // 태그 보정 전 CPU 재현에서도 약0.66mm 밖으로 벗어난 뒤 같은 정체가 발생했다.
  EXPECT_FALSE(controller.rotatesAtDistance(0.03066));
  // 예찰 실패 구간의 추정 거리 범위. 같은 Goal에서 추종을 재개해야 한다.
  EXPECT_FALSE(controller.rotatesAtDistance(0.0366357));
  EXPECT_FALSE(controller.rotatesAtDistance(0.0543634));
  EXPECT_TRUE(controller.rotatesAtDistance(0.025));
}

class SettlingTest : public ::testing::Test
{
protected:
  std::shared_ptr<tf2_ros::Buffer> tf = std::make_shared<tf2_ros::Buffer>(
    std::make_shared<rclcpp::Clock>(RCL_ROS_TIME));
  Controller controller{tf};
  GoalChecker checker;
  geometry_msgs::msg::PoseStamped pose;
  geometry_msgs::msg::TwistStamped command;
  nav_msgs::msg::Path path;

  void SetUp() override
  {
    pose.header.frame_id = "map";
    pose.header.stamp.sec = 12;
    pose.pose.orientation = yawQuaternion(0.0);
    command.header = pose.header;
    command.twist.linear.x = 0.1;
    command.twist.angular.z = 0.06;
    path.header.frame_id = "map";
    path.poses.push_back(pose);
    controller.setPlan(path);
  }
  void settle() {controller.settleAtGoal(pose, &checker, command);}
};

TEST_F(SettlingTest, StopsAllAxesInsideBothTolerancesWithoutChangingHeader)
{
  pose.pose.position.x = 0.008;
  pose.pose.position.y = 0.008;
  pose.pose.orientation = yawQuaternion(0.005);
  command.twist.linear.y = 0.2;
  command.twist.angular.x = 0.4;
  settle();
  EXPECT_EQ(command.twist, geometry_msgs::msg::Twist{});
  EXPECT_EQ(command.header, pose.header);
}

TEST_F(SettlingTest, DoesNotStopWhenEitherPositionOrYawIsOutside)
{
  pose.pose.position.x = 0.016;
  settle();
  EXPECT_DOUBLE_EQ(command.twist.linear.x, 0.1);
  EXPECT_DOUBLE_EQ(command.twist.angular.z, 0.06);
  pose.pose.position.x = 0.0;
  pose.pose.orientation = yawQuaternion(0.011);
  settle();
  EXPECT_DOUBLE_EQ(command.twist.angular.z, 0.06);
}

TEST_F(SettlingTest, UsesRadialPositionTolerance)
{
  pose.pose.position.x = pose.pose.position.y = 0.012;
  settle();
  EXPECT_DOUBLE_EQ(command.twist.linear.x, 0.1);
}

TEST_F(SettlingTest, WrapsYawAcrossPi)
{
  path.poses.back().pose.orientation = yawQuaternion(M_PI - 0.002);
  controller.setPlan(path);
  pose.pose.orientation = yawQuaternion(-M_PI + 0.002);
  settle();
  EXPECT_EQ(command.twist, geometry_msgs::msg::Twist{});
}

TEST_F(SettlingTest, UsesFinalGoalRatherThanPassedPathPoint)
{
  auto goal = pose;
  goal.pose.position.x = 1.0;
  path.poses.push_back(goal);
  controller.setPlan(path);
  settle();
  EXPECT_DOUBLE_EQ(command.twist.linear.x, 0.1);
}

TEST_F(SettlingTest, UsesPlanFrameAndCurrentPoseStampForTransform)
{
  geometry_msgs::msg::TransformStamped transform;
  transform.header.frame_id = "odom";
  transform.child_frame_id = "map";
  transform.transform.rotation = yawQuaternion(0.0);
  transform.header.stamp.sec = 11;
  transform.transform.translation.x = 5.0;
  ASSERT_TRUE(tf->setTransform(transform, "test"));
  transform.header.stamp.sec = 12;
  transform.transform.translation.x = 8.0;
  ASSERT_TRUE(tf->setTransform(transform, "test"));
  path.poses.back().header.frame_id = "ignored_individual_frame";
  path.poses.back().header.stamp.sec = 1;
  controller.setPlan(path);
  pose.header.frame_id = "odom";
  pose.pose.position.x = 8.0;
  settle();
  EXPECT_EQ(command.twist, geometry_msgs::msg::Twist{});
}

TEST_F(SettlingTest, FailsOnMissingTransformAndEmptyPath)
{
  pose.header.frame_id = "missing_frame";
  EXPECT_THROW(settle(), nav2_core::ControllerTFError);
  path.poses.clear();
  controller.setPlan(path);
  EXPECT_THROW(settle(), nav2_core::InvalidPath);
}

TEST_F(SettlingTest, RejectsMissingAndInvalidTolerances)
{
  checker.valid = false;
  EXPECT_THROW(settle(), nav2_core::ControllerException);
  checker.valid = true;
  checker.tolerance.position.x = -1.0;
  EXPECT_THROW(settle(), nav2_core::ControllerException);
  checker.tolerance.position.x = std::numeric_limits<double>::quiet_NaN();
  EXPECT_THROW(settle(), nav2_core::ControllerException);
  checker.tolerance.position.x = 0.015;
  checker.tolerance.orientation = yawQuaternion(-0.01);
  EXPECT_THROW(settle(), nav2_core::ControllerException);
  checker.tolerance.orientation = geometry_msgs::msg::Quaternion{};
  checker.tolerance.orientation.w = 0.0;
  EXPECT_THROW(settle(), nav2_core::ControllerException);
}

TEST_F(SettlingTest, RejectsInvalidPoseInsteadOfStopping)
{
  pose.pose.orientation = geometry_msgs::msg::Quaternion{};
  pose.pose.orientation.w = 0.0;
  EXPECT_THROW(settle(), nav2_core::ControllerException);
  pose.pose.orientation = yawQuaternion(0.0);
  pose.pose.position.y = std::numeric_limits<double>::infinity();
  EXPECT_THROW(settle(), nav2_core::ControllerException);
}

TEST_F(SettlingTest, NullCheckerFailsBeforeBaseControllerAccess)
{
  EXPECT_THROW(
    controller.computeVelocityCommands(pose, geometry_msgs::msg::Twist{}, nullptr),
    nav2_core::ControllerException);
}

}  // namespace
