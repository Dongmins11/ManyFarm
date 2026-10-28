// 기존 제어기를 수정하지 않는 선택형 공통 플러그인. Nav2 충돌 검사를 그대로 호출한다.
#include <mutex>
#include "farm_arc_controller/arc_math.hpp"
#include "nav2_regulated_pure_pursuit_controller/regulated_pure_pursuit_controller.hpp"
#include "nav2_core/controller_exceptions.hpp"
#include "tf2/utils.hpp"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"
#include "pluginlib/class_list_macros.hpp"
namespace farm_arc_controller {
class ArcController : public nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController {
public:
  geometry_msgs::msg::TwistStamped computeVelocityCommands(
      const geometry_msgs::msg::PoseStamped & pose,const geometry_msgs::msg::Twist &,
      nav2_core::GoalChecker *) override {
    std::lock_guard<std::mutex> parameters_lock(param_handler_->getMutex());
    std::unique_lock<nav2_costmap_2d::Costmap2D::mutex_t> costmap_lock(*costmap_->getMutex());
    if(!params_->use_collision_detection || !params_->allow_reversing || params_->use_rotate_to_heading)
      throw nav2_core::ControllerException("Arc requires collision checking and reversing");
    const auto plan=path_handler_->getPlan();
    if(plan.poses.size()<3)throw nav2_core::InvalidPath("Arc needs a sampled path");
    // 원호 중심·시작점을 잘라내는 transformGlobalPlan 대신 원본 전체 경로를 사용한다.
    std::vector<Pose> samples;
    samples.reserve(plan.poses.size());
    for(const auto & original:plan.poses){
      auto input=original;
      input.header.frame_id=plan.header.frame_id;
      input.header.stamp=pose.header.stamp;
      geometry_msgs::msg::PoseStamped transformed;
      if(!path_handler_->transformPose(pose.header.frame_id,input,transformed))
        throw nav2_core::ControllerTFError("Cannot transform arc sample");
      samples.push_back({transformed.pose.position.x,transformed.pose.position.y,
                         tf2::getYaw(transformed.pose.orientation)});
    }
    Arc arc;
    try {arc=validate_path(samples);}
    catch(const std::exception & error){throw nav2_core::InvalidPath(error.what());}
    Pose now{pose.pose.position.x,pose.pose.position.y,tf2::getYaw(pose.pose.orientation)};
    geometry_msgs::msg::TwistStamped out;out.header=pose.header;
    if(cancelling_){finished_cancelling_=true;return out;}
    Command cmd;
    try {cmd=command(arc.start,now,arc.radius,arc.angle,std::min(params_->desired_linear_vel,.01),.04,.01,.15);}
    catch(const std::exception & error){throw nav2_core::NoValidControl(error.what());}
    out.twist.linear.x=cmd.v;out.twist.angular.z=cmd.w;
    // carrot 거리로 자르지 않고 설정된 예측 시간까지 footprint를 검사한다.
    if(collision_checker_->isCollisionImminent(pose,cmd.v,cmd.w,100.0))
      throw nav2_core::NoValidControl("Collision on transfer arc");
    return out;
  }
};
}
PLUGINLIB_EXPORT_CLASS(farm_arc_controller::ArcController, nav2_core::Controller)
