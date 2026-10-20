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
    auto first=plan.poses.front(),last=plan.poses.back();
    first.header.frame_id=last.header.frame_id=plan.header.frame_id;
    first.header.stamp=last.header.stamp=pose.header.stamp;
    geometry_msgs::msg::PoseStamped a,b;
    if(!path_handler_->transformPose(pose.header.frame_id,first,a) ||
       !path_handler_->transformPose(pose.header.frame_id,last,b))
      throw nav2_core::ControllerTFError("Cannot transform arc");
    Pose start{a.pose.position.x,a.pose.position.y,tf2::getYaw(a.pose.orientation)};
    Pose end{b.pose.position.x,b.pose.position.y,tf2::getYaw(b.pose.orientation)};
    Pose now{pose.pose.position.x,pose.pose.position.y,tf2::getYaw(pose.pose.orientation)};
    const double angle=wrap(end.yaw-start.yaw);
    if(angle<=0 || angle>M_PI_2+1e-6)throw nav2_core::InvalidPath("Only reverse left arcs <=90deg");
    const double radius=std::hypot(end.x-start.x,end.y-start.y)/(2*std::sin(angle/2));
    if(radius<.05 || radius>.30)throw nav2_core::InvalidPath("Trial radius outside 5-30cm");
    auto ideal=at(start,radius,angle);
    if(std::hypot(end.x-ideal.x,end.y-ideal.y)>.001)throw nav2_core::InvalidPath("Not a reverse left arc");
    // 중간 경로가 임의 경로인 경우 시작·끝만 보고 원호로 대체하지 않는다.
    double previous=-1e-6;
    for(const auto & original:plan.poses){
      auto input=original;input.header.frame_id=plan.header.frame_id;input.header.stamp=pose.header.stamp;
      geometry_msgs::msg::PoseStamped transformed;
      if(!path_handler_->transformPose(pose.header.frame_id,input,transformed))
        throw nav2_core::ControllerTFError("Cannot transform arc sample");
      const double t=wrap(tf2::getYaw(transformed.pose.orientation)-start.yaw);
      const auto target=at(start,radius,t);
      if(t < previous-1e-6 || t > angle+1e-6 || std::hypot(target.x-transformed.pose.position.x,target.y-transformed.pose.position.y)>.001)
        throw nav2_core::InvalidPath("Invalid arc sample");
      previous=t;
    }
    geometry_msgs::msg::TwistStamped out;out.header=pose.header;
    if(cancelling_){finished_cancelling_=true;return out;}
    Command cmd;
    try {cmd=command(start,now,radius,angle,std::min(params_->desired_linear_vel,.01),.04,.01,.15);}
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
