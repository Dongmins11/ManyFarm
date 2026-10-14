#include "farm_nav2_controller/settling_regulated_pure_pursuit_controller.hpp"

#include <algorithm>
#include <cmath>

#include "nav2_core/controller_exceptions.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "tf2/utils.hpp"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"

namespace farm_nav2_controller
{
namespace
{

// 잘못된 quaternion을 0rad로 취급하여 정지 조건을 통과시키지 않는다.
double checkedYaw(const geometry_msgs::msg::Quaternion & q)
{
  const double norm_sq = q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w;
  if (!std::isfinite(norm_sq) || std::abs(norm_sq - 1.0) > 1e-3) {
    throw nav2_core::ControllerException("Settling RPP requires a valid unit quaternion");
  }
  return tf2::getYaw(q);
}

}  // namespace

geometry_msgs::msg::TwistStamped
SettlingRegulatedPurePursuitController::computeVelocityCommands(
  const geometry_msgs::msg::PoseStamped & pose,
  const geometry_msgs::msg::Twist & velocity,
  nav2_core::GoalChecker * goal_checker)
{
  if (goal_checker == nullptr) {
    throw nav2_core::ControllerException("Settling RPP requires a goal checker");
  }
  // 기존 경로 처리·속도 규제·충돌 검사를 먼저 수행하고 예외를 그대로 전파한다.
  auto command = RegulatedPurePursuitController::computeVelocityCommands(
    pose, velocity, goal_checker);
  settleAtGoal(pose, goal_checker, command);
  return command;
}

void SettlingRegulatedPurePursuitController::settleAtGoal(
  const geometry_msgs::msg::PoseStamped & pose,
  nav2_core::GoalChecker * goal_checker,
  geometry_msgs::msg::TwistStamped & command) const
{
  geometry_msgs::msg::Pose tolerance;
  geometry_msgs::msg::Twist velocity_tolerance;
  if (goal_checker == nullptr || !goal_checker->getTolerances(tolerance, velocity_tolerance)) {
    throw nav2_core::ControllerException("Settling RPP cannot read goal tolerances");
  }
  const double yaw_tolerance = checkedYaw(tolerance.orientation);
  if (!std::isfinite(tolerance.position.x) || !std::isfinite(tolerance.position.y) ||
    tolerance.position.x < 0.0 || tolerance.position.y < 0.0 || yaw_tolerance < 0.0)
  {
    throw nav2_core::ControllerException("Settling RPP requires finite XY and yaw tolerances");
  }
  if (!path_handler_) {
    throw nav2_core::ControllerException("Settling RPP is not configured");
  }
  const auto plan = path_handler_->getPlan();
  if (plan.poses.empty()) {
    throw nav2_core::InvalidPath("Settling RPP received an empty path");
  }
  if (plan.header.frame_id.empty() || pose.header.frame_id.empty()) {
    throw nav2_core::ControllerTFError("Settling RPP requires explicit pose and path frames");
  }
  auto goal = plan.poses.back();
  // RPP PathHandler와 동일하게 개별 경로점의 과거 시각 대신 현재 pose 시각을 쓴다.
  goal.header.frame_id = plan.header.frame_id;
  goal.header.stamp = pose.header.stamp;
  geometry_msgs::msg::PoseStamped transformed_goal;
  if (!path_handler_->transformPose(pose.header.frame_id, goal, transformed_goal)) {
    throw nav2_core::ControllerTFError("Settling RPP cannot transform the final goal pose");
  }
  const double dx = transformed_goal.pose.position.x - pose.pose.position.x;
  const double dy = transformed_goal.pose.position.y - pose.pose.position.y;
  if (!std::isfinite(dx) || !std::isfinite(dy)) {
    throw nav2_core::ControllerException("Settling RPP requires finite goal and robot positions");
  }
  const double yaw_error = checkedYaw(transformed_goal.pose.orientation) -
    checkedYaw(pose.pose.orientation);
  const double wrapped_yaw_error = std::atan2(std::sin(yaw_error), std::cos(yaw_error));
  const double xy_tolerance = std::min(tolerance.position.x, tolerance.position.y);
  if (std::hypot(dx, dy) <= xy_tolerance && std::abs(wrapped_yaw_error) <= yaw_tolerance) {
    // 속도가 남아 있어도 성공으로 간주하지 않는다. 0명령으로 제동한 뒤
    // StoppedGoalChecker가 실제 odom 속도와 자세를 다시 확인한다.
    command.twist = geometry_msgs::msg::Twist{};
  }
}

}  // namespace farm_nav2_controller

PLUGINLIB_EXPORT_CLASS(
  farm_nav2_controller::SettlingRegulatedPurePursuitController, nav2_core::Controller)
