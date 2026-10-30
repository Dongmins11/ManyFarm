#ifndef FARM_NAV2_CONTROLLER__REVERSE_REGULATED_PURE_PURSUIT_CONTROLLER_HPP_
#define FARM_NAV2_CONTROLLER__REVERSE_REGULATED_PURE_PURSUIT_CONTROLLER_HPP_
#include "nav2_regulated_pure_pursuit_controller/regulated_pure_pursuit_controller.hpp"
namespace farm_nav2_controller
{
// 복귀 전용. RPP의 후진 추종·속도 규제·충돌 검사를 재사용하며 전진은 허용하지 않는다.
class ReverseRegulatedPurePursuitController
  : public nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController
{
public:
  // 인스턴스별 선택값만 읽는다. 기존 인계·시뮬의 기본값은 false다.
  void configure(const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
    std::string name, std::shared_ptr<tf2_ros::Buffer> tf,
    std::shared_ptr<nav2_costmap_2d::Costmap2DROS> costmap_ros) override;
  geometry_msgs::msg::TwistStamped computeVelocityCommands(
    const geometry_msgs::msg::PoseStamped & pose,
    const geometry_msgs::msg::Twist & velocity,
    nav2_core::GoalChecker * goal_checker) override;

protected:
  // 위치 전용 목표의 기존 lookahead 범위(m)에서만 경로 방향 제자리 정렬을 생략한다.
  bool skipApproachRotation(double distance, double lookahead, double yaw_tolerance) const;
  bool _skip_position_approach_rotation = false;
  // 실물 접근만 표준 RPP의 고정 곡률 선행점/종점 연장을 선택한다. 기본은 기존 계산이다.
  bool _use_work_curvature = false;
  geometry_msgs::msg::Point curvaturePoint(
    const nav_msgs::msg::Path & path, const geometry_msgs::msg::Point & carrot);
};
}
#endif
