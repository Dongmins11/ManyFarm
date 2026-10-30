#include "farm_wall_controller/wall_input.hpp"
#include "nav2_core/goal_checker.hpp"
#include "nav2_core/controller_exceptions.hpp"
#include "nav2_regulated_pure_pursuit_controller/regulated_pure_pursuit_controller.hpp"
#include "pluginlib/class_list_macros.hpp"
#include <limits>
#include "farm_wall_controller/wait_clock.hpp"
#include "std_msgs/msg/bool.hpp"
namespace farm_wall_controller {
class WallGoalChecker : public nav2_core::GoalChecker {
 WaitClock wait_;
 Node::SharedPtr node_;Config config_;std::unique_ptr<WallInput> input_;std::unique_ptr<Control> control_;
public:
 void initialize(const Node::WeakPtr &parent,const std::string &,const std::shared_ptr<nav2_costmap_2d::Costmap2DROS> cm) override {
  node_=parent.lock();wait_.init(node_);if(!node_)throw std::runtime_error("Missing node");config_=load(node_);
  input_=std::make_unique<WallInput>(node_,cm->getGlobalFrameID(),config_.observation_age,config_.station_docking);
  control_=std::make_unique<Control>(config_);
 }
 void reset() override {if(control_)control_->reset();wait_.reset();}
 bool isGoalReached(const geometry_msgs::msg::Pose &p,const geometry_msgs::msg::Pose &,const geometry_msgs::msg::Twist &v) override {
  try{control_->credit_wait(wait_.take());auto observation=input_->read();const double now=node_->now().seconds();return control_->step(observation,pose(p),now,std::hypot(v.linear.x,v.linear.y),v.angular.z).reached;}
  catch(const ObservationUnavailable &){try{control_->wait(pose(p),node_->now().seconds());}catch(const std::exception &e){RCLCPP_WARN_THROTTLE(node_->get_logger(),*node_->get_clock(),2000,"WallGoalChecker wait: %s",e.what());}return false;}
  catch(const std::exception &e){RCLCPP_WARN_THROTTLE(node_->get_logger(),*node_->get_clock(),2000,"WallGoalChecker: %s",e.what());control_->reset();return false;}
 }
 bool getTolerances(geometry_msgs::msg::Pose &p,geometry_msgs::msg::Twist &v) override {
  const double none=std::numeric_limits<double>::lowest();p.position.x=p.position.y=p.position.z=none;
  p.orientation.x=p.orientation.y=p.orientation.z=p.orientation.w=none;
  v.linear.x=v.linear.y=config_.stopped_linear;v.linear.z=none;
  v.angular.x=v.angular.y=none;v.angular.z=config_.stopped_angular;return true;
 }
};
class WallController : public nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController {
 using Base=nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController;
 rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr wait_pub_;
 WaitClock wait_;
 Node::SharedPtr owner_;Config config_;std::unique_ptr<WallInput> input_;std::unique_ptr<Control> control_;
public:
 void configure(const Node::WeakPtr &parent,std::string name,std::shared_ptr<tf2_ros::Buffer> tf,
                std::shared_ptr<nav2_costmap_2d::Costmap2DROS> cm) override {
  Base::configure(parent,name,tf,cm);wait_pub_=parent.lock()->create_publisher<std_msgs::msg::Bool>("controller_wait",1);owner_=parent.lock();wait_.init(owner_);config_=load(owner_);
  input_=std::make_unique<WallInput>(owner_,cm->getGlobalFrameID(),config_.observation_age,config_.station_docking);
  control_=std::make_unique<Control>(config_);
 }
 void cleanup() override {input_.reset();control_.reset();owner_.reset();Base::cleanup();}
 void setPlan(const nav_msgs::msg::Path &path) override {
  if(path.poses.empty())throw nav2_core::InvalidPath("Wall action requires a nonempty task path");
  Base::setPlan(path);control_->reset();wait_.reset();
 }
 geometry_msgs::msg::TwistStamped computeVelocityCommands(const geometry_msgs::msg::PoseStamped &p,
       const geometry_msgs::msg::Twist &v,nav2_core::GoalChecker *checker) override {
  std::lock_guard<std::mutex> parameter_lock(param_handler_->getMutex());
  std::unique_lock<nav2_costmap_2d::Costmap2D::mutex_t> map_lock(*costmap_->getMutex());
  if(!dynamic_cast<WallGoalChecker*>(checker))throw nav2_core::ControllerException("WallGoalChecker required");
  if(!params_->use_collision_detection)throw nav2_core::ControllerException("Wall collision check must be enabled");
  geometry_msgs::msg::TwistStamped out;out.header=p.header;
  if(cancelling_){finished_cancelling_=true;return out;}
  try {
   control_->credit_wait(wait_.take());
   Command cmd;bool waiting=false;
   try{auto observation=input_->read();const double now=owner_->now().seconds();waiting=now-observation.stamp>config_.observation_age;cmd=control_->step(observation,pose(p.pose),now,std::hypot(v.linear.x,v.linear.y),v.angular.z);}
   catch(const ObservationUnavailable &){waiting=true;cmd=control_->wait(pose(p.pose),owner_->now().seconds());}
   std_msgs::msg::Bool state;state.data=waiting;wait_pub_->publish(state);
   const double limit=std::max(0.,params_->desired_linear_vel);
   out.twist.linear.x=config_.station_docking?std::clamp(cmd.linear,-limit,0.):std::min(cmd.linear,limit);
   out.twist.angular.z=cmd.angular;
  }catch(const std::exception &e){throw nav2_core::NoValidControl(e.what());}
  // 기존 Nav2 footprint 예측 검사. 목표까지의 짧은 거리로 검사 범위를 잘라내지 않는다.
  if(collision_checker_->isCollisionImminent(p,out.twist.linear.x,out.twist.angular.z,100.0))
    throw nav2_core::NoValidControl("Collision on wall alignment");
  return out;
 }
};
}
PLUGINLIB_EXPORT_CLASS(farm_wall_controller::WallController,nav2_core::Controller)
PLUGINLIB_EXPORT_CLASS(farm_wall_controller::WallGoalChecker,nav2_core::GoalChecker)
