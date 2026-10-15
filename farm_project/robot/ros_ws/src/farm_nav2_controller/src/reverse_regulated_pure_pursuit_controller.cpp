#include "farm_nav2_controller/reverse_regulated_pure_pursuit_controller.hpp"
#include <algorithm>
#include <cmath>
#include <mutex>
#include "nav2_core/controller_exceptions.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "tf2/utils.hpp"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"

namespace farm_nav2_controller
{
geometry_msgs::msg::TwistStamped
ReverseRegulatedPurePursuitController::computeVelocityCommands(
  const geometry_msgs::msg::PoseStamped & pose,
  const geometry_msgs::msg::Twist & velocity,
  nav2_core::GoalChecker * goal_checker)
{
  {
    std::lock_guard<std::mutex> parameters_lock(param_handler_->getMutex());
    std::unique_lock<nav2_costmap_2d::Costmap2D::mutex_t> costmap_lock(*costmap_->getMutex());
    if (!params_->allow_reversing || params_->use_rotate_to_heading || !params_->use_collision_detection) {
      throw nav2_core::ControllerException("Reverse RPP requires reversing, collision detection and no forward rotation mode");
    }
    geometry_msgs::msg::Pose tolerance;
    geometry_msgs::msg::Twist velocity_tolerance;
    if (!goal_checker || !goal_checker->getTolerances(tolerance, velocity_tolerance)) {
      throw nav2_core::ControllerException("Reverse RPP requires goal tolerances");
    }
    const auto plan = path_handler_->getPlan();
    if (plan.poses.empty()) {throw nav2_core::InvalidPath("Empty reverse route");}
    auto goal = plan.poses.back();
    goal.header.frame_id = plan.header.frame_id;
    goal.header.stamp = pose.header.stamp;
    geometry_msgs::msg::PoseStamped local_goal;
    if (!path_handler_->transformPose(pose.header.frame_id, goal, local_goal)) {
      throw nav2_core::ControllerTFError("Cannot transform reverse goal");
    }
    const double distance = std::hypot(local_goal.pose.position.x - pose.pose.position.x,
      local_goal.pose.position.y - pose.pose.position.y);
    const double xy_tolerance = std::min(tolerance.position.x, tolerance.position.y);
    double angle = 0.0;
    double carrot_distance = distance;
    bool rotate = false;
    nav_msgs::msg::Path local;
    geometry_msgs::msg::Point carrot;
    const bool at_goal = distance <= xy_tolerance;
    if (at_goal) {
      // 역방향 주행을 마치면 출발 때의 스테이션 자세만 맞춘다. 180도 뒤집지 않는다.
      angle = tf2::getYaw(local_goal.pose.orientation) - tf2::getYaw(pose.pose.orientation);
      angle = std::atan2(std::sin(angle), std::cos(angle));
      rotate = std::abs(angle) > std::abs(tf2::getYaw(tolerance.orientation));
    } else {
      local = path_handler_->transformGlobalPlan(pose, params_->max_robot_pose_search_dist);
      carrot = getLookAheadPoint(getLookAheadDistance(velocity), local).pose.position;
      const auto & p = carrot;
      carrot_distance = std::hypot(p.x, p.y);
      // 뒤쪽 경로점을 향한 차체 방향. 전진 RPP처럼 carrot 방향으로 몸을 뒤집지 않는다.
      angle = std::atan2(-p.y, -p.x);
      rotate = std::abs(angle) > params_->rotate_to_heading_min_angle;
    }
    if (!std::isfinite(angle) || std::abs(angle) > M_PI_2 + 0.1) {
      throw nav2_core::InvalidPath("Reverse route requires opposite body heading; check station-to-current route");
    }
    if (!cancelling_ && (rotate || at_goal)) {
      geometry_msgs::msg::TwistStamped command;
      command.header = pose.header;
      if (rotate) {
        rotateToHeading(command.twist.linear.x, command.twist.angular.z, angle, velocity);
      }
      // 추가한 회전도 기존 RPP와 같은 footprint·costmap 충돌 검사를 통과해야 한다.
      if (collision_checker_->isCollisionImminent(pose, 0.0, command.twist.angular.z, carrot_distance)) {
        throw nav2_core::NoValidControl("Collision on reverse heading alignment");
      }
      return command;
    }
    // 복귀는 전 구간 후진이다. 기본 RPP의 cusp 기반 전/후진 선택을 쓰지 않는다.
    // 같은 carrot으로 정렬·곡률·충돌 검사를 수행하고 기존 속도 제한을 재사용한다.
    const double squared_distance = carrot.x * carrot.x + carrot.y * carrot.y;
    const double curvature = squared_distance > 0.001 ? 2.0 * carrot.y / squared_distance : 0.0;
    double linear = params_->desired_linear_vel;
    double sign = -1.0;
    if (!at_goal) {
      applyConstraints(curvature, velocity,
        collision_checker_->costAtPose(pose.pose.position.x, pose.pose.position.y),
        local, linear, sign);
    } else {
      linear = 0.0;
    }
    if (cancelling_) {
      linear = std::min(0.0, velocity.linear.x + control_duration_ * params_->cancel_deceleration);
      finished_cancelling_ = linear >= 0.0;
    }
    geometry_msgs::msg::TwistStamped command;
    command.header = pose.header;
    command.twist.linear.x = linear;
    command.twist.angular.z = linear * curvature;
    if (collision_checker_->isCollisionImminent(
        pose, linear, command.twist.angular.z, carrot_distance))
    {
      throw nav2_core::NoValidControl("Collision on reverse route");
    }
    return command;
  }
}
}
PLUGINLIB_EXPORT_CLASS(farm_nav2_controller::ReverseRegulatedPurePursuitController, nav2_core::Controller)
