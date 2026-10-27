#include "farm_wall_controller/wait_clock.hpp"
#include "nav2_controller/plugins/pose_progress_checker.hpp"
#include "nav2_behaviors/plugins/spin.hpp"
#include "pluginlib/class_list_macros.hpp"
namespace farm_wall_controller {
class WaitingProgressChecker : public nav2_controller::PoseProgressChecker {
 WaitClock wait_;
public:
 void initialize(const rclcpp_lifecycle::LifecycleNode::WeakPtr &p,const std::string &name) override {
  nav2_controller::PoseProgressChecker::initialize(p,name);wait_.init(p.lock());
 }
 void reset() override {nav2_controller::PoseProgressChecker::reset();wait_.reset();}
 bool check(geometry_msgs::msg::PoseStamped &pose) override {
  double dt=wait_.take();if(baseline_pose_set_)baseline_time_=baseline_time_+rclcpp::Duration::from_seconds(dt);
  return nav2_controller::PoseProgressChecker::check(pose);
 }
};
class WaitingSpin : public nav2_behaviors::Spin {
 WaitClock wait_;
public:
 void onConfigure() override {nav2_behaviors::Spin::onConfigure();wait_.init(node_.lock());}
 nav2_behaviors::ResultStatus onRun(const std::shared_ptr<const SpinActionGoal> goal) override {wait_.reset();return nav2_behaviors::Spin::onRun(goal);}
 nav2_behaviors::ResultStatus onCycleUpdate() override {
  end_time_=end_time_+rclcpp::Duration::from_seconds(wait_.take());
  return nav2_behaviors::Spin::onCycleUpdate();
 }
};
}
PLUGINLIB_EXPORT_CLASS(farm_wall_controller::WaitingProgressChecker,nav2_core::ProgressChecker)
PLUGINLIB_EXPORT_CLASS(farm_wall_controller::WaitingSpin,nav2_core::Behavior)
