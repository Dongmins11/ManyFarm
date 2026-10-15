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
  geometry_msgs::msg::TwistStamped computeVelocityCommands(
    const geometry_msgs::msg::PoseStamped & pose,
    const geometry_msgs::msg::Twist & velocity,
    nav2_core::GoalChecker * goal_checker) override;
};
}
#endif
