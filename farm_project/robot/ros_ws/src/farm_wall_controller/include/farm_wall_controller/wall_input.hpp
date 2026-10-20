#pragma once
#include <chrono>
#include <mutex>
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "tf2/utils.hpp"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"
#include "farm_wall_controller/wall_control.hpp"
namespace farm_wall_controller {
using Node=rclcpp_lifecycle::LifecycleNode;
// Controller/GoalChecker가 동일한 파라미터 계약과 관측 검사를 사용한다.
inline Config load(const Node::SharedPtr &node){
 Config c;
 const std::string sequential="wall_alignment.sequential_alignment";
 if(!node->has_parameter(sequential))node->declare_parameter(sequential,c.sequential_alignment);
 node->get_parameter(sequential,c.sequential_alignment);
 auto p=[&](const std::string &key,double &v){const auto n="wall_alignment."+key;
  if(!node->has_parameter(n))node->declare_parameter(n,v);node->get_parameter(n,v);};
 p("target_angle",c.target_angle);p("target_distance",c.target);p("distance_tolerance",c.distance_tolerance);p("angle_tolerance",c.angle_tolerance);
 p("kp_distance",c.kp_distance);p("kp_angle",c.kp_angle);p("max_linear",c.max_linear);p("max_angular",c.max_angular);
 p("min_linear",c.min_linear);p("min_angular",c.min_angular);
 p("align_enter",c.align_enter);p("align_exit",c.align_exit);p("dwell",c.dwell);p("max_distance",c.max_distance);
 p("max_yaw",c.max_yaw);p("timeout",c.timeout);p("observation_age",c.observation_age);
 p("stopped_linear",c.stopped_linear);p("stopped_angular",c.stopped_angular);c.validate();return c;
}
class WallInput {
 Node::SharedPtr node_;std::string frame_;double age_;std::mutex mutex_;
 geometry_msgs::msg::PoseStamped::SharedPtr msg_;std::chrono::steady_clock::time_point received_;
 rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr sub_;
public:
 WallInput(Node::SharedPtr node,std::string frame,double age):node_(node),frame_(frame),age_(age){
  // 사설 namespace의 관측만 받는다. QoS는 새 데이터만 전달하며 이전 Goal 성공을 재사용하지 않는다.
  sub_=node_->create_subscription<geometry_msgs::msg::PoseStamped>("wall_observation",rclcpp::QoS(1).reliable(),
   [this](geometry_msgs::msg::PoseStamped::SharedPtr m){std::lock_guard<std::mutex> l(mutex_);msg_=m;received_=std::chrono::steady_clock::now();});
 }
 Wall read(){
  std::lock_guard<std::mutex> l(mutex_);
  if(!msg_ || std::chrono::duration<double>(std::chrono::steady_clock::now()-received_).count()>age_)
   throw std::runtime_error("No fresh wall observation");
  if(msg_->header.frame_id!=frame_)throw std::runtime_error("Wall frame mismatch");
  const auto &q=msg_->pose.orientation;
  double norm=q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w;
  if(!std::isfinite(norm)||std::abs(norm-1.)>1e-3 || std::abs(q.x)>1e-4 || std::abs(q.y)>1e-4)
   throw std::runtime_error("Invalid planar wall normal");
  Wall w{msg_->pose.position.x,msg_->pose.position.y,tf2::getYaw(q),rclcpp::Time(msg_->header.stamp).seconds()};
  if(!std::isfinite(w.x)||!std::isfinite(w.y))throw std::runtime_error("Invalid wall observation");return w;
 }
};
inline Pose pose(const geometry_msgs::msg::Pose &p){return {p.position.x,p.position.y,tf2::getYaw(p.orientation)};}
}
