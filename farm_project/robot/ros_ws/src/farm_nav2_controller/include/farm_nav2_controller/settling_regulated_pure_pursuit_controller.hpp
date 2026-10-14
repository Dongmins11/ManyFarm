#ifndef FARM_NAV2_CONTROLLER__SETTLING_REGULATED_PURE_PURSUIT_CONTROLLER_HPP_
#define FARM_NAV2_CONTROLLER__SETTLING_REGULATED_PURE_PURSUIT_CONTROLLER_HPP_

#include "nav2_regulated_pure_pursuit_controller/regulated_pure_pursuit_controller.hpp"

namespace farm_nav2_controller
{

// StoppedGoalChecker와 함께 사용한다. XY 이탈 시 경로 추종을 재개하려면
// 제어기의 stateful도 false로 설정한다(GoalChecker 설정과 별개).
class SettlingRegulatedPurePursuitController
  : public nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController
{
public:
  // pose[m, rad]와 측정 velocity[m/s, rad/s]로 RPP 명령을 계산한 뒤,
  // 목표 자세 허용치 안에서만 0속도를 반환한다. 성공 판정은 GoalChecker 책임이다.
  geometry_msgs::msg::TwistStamped computeVelocityCommands(
    const geometry_msgs::msg::PoseStamped & pose,
    const geometry_msgs::msg::Twist & velocity,
    nav2_core::GoalChecker * goal_checker) override;

protected:
  // 경로의 최종 자세를 pose 시각/프레임으로 변환해 정지 명령을 적용한다.
  // 유효한 TF·허용치가 없으면 ControllerException을 발생시킨다.
  void settleAtGoal(
    const geometry_msgs::msg::PoseStamped & pose,
    nav2_core::GoalChecker * goal_checker,
    geometry_msgs::msg::TwistStamped & command) const;
};

}  // namespace farm_nav2_controller
#endif  // FARM_NAV2_CONTROLLER__SETTLING_REGULATED_PURE_PURSUIT_CONTROLLER_HPP_
