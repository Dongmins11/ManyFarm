#pragma once
#include <chrono>
#include <mutex>
#include <cmath>
#include "std_msgs/msg/float64_multi_array.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
namespace farm_wall_controller {
// runtime의 0출력 대기 누계만 사용한다. 오래된/다중 발행자/역행/다른 세션은 시간을 벌지 못한다.
class WaitClock {
 using Clock=std::chrono::steady_clock;
 rclcpp_lifecycle::LifecycleNode::SharedPtr node_;
 rclcpp::Subscription<std_msgs::msg::Float64MultiArray>::SharedPtr sub_;
 std::mutex mutex_;bool have_=false,valid_=false,bound_=false;
 bool unlimited_=false;
 double epoch_=0,seq_=0,total_=0,last_total_=0,goal_epoch_=0,used_=0;
 Clock::time_point received_,last_check_;
public:
 void init(rclcpp_lifecycle::LifecycleNode::SharedPtr node){
  const std::string key="wall_alignment.wait_until_fresh";
  if(!node->has_parameter(key))node->declare_parameter(key,false);
  node->get_parameter(key,unlimited_);
  node_=node;sub_=node->create_subscription<std_msgs::msg::Float64MultiArray>("handoff_wait_clock",rclcpp::QoS(1),[this](const std_msgs::msg::Float64MultiArray::SharedPtr m){
   std::lock_guard<std::mutex> lock(mutex_);
   if(m->data.size()!=4)return;
   for(double x:m->data)if(!std::isfinite(x))return;
   double age=node_->now().seconds()-m->data[3];
   if(age<-.1||age>.2||m->data[2]<0)return;
   if(have_&&m->data[0]==epoch_&&(m->data[1]<=seq_||m->data[2]<total_))return;
   epoch_=m->data[0];seq_=m->data[1];total_=m->data[2];received_=Clock::now();have_=true;
  });
 }
 void reset(){std::lock_guard<std::mutex> lock(mutex_);last_check_=Clock::now();last_total_=total_;goal_epoch_=epoch_;bound_=have_;used_=0;valid_=false;}
 double take(){
  std::lock_guard<std::mutex> lock(mutex_);auto now=Clock::now();double dt=std::chrono::duration<double>(now-last_check_).count();last_check_=now;
  bool fresh=have_&&std::chrono::duration<double>(now-received_).count()<=.2&&node_->count_publishers("handoff_wait_clock")==1;
  if(!bound_&&fresh){goal_epoch_=epoch_;bound_=true;}
  fresh=fresh&&epoch_==goal_epoch_;
  double credit=(fresh&&valid_)?std::max(0.,std::min({total_-last_total_,dt,.2,unlimited_?dt:30.-used_})):0.;
  last_total_=total_;valid_=fresh;used_+=credit;return credit;
 }
};
}
