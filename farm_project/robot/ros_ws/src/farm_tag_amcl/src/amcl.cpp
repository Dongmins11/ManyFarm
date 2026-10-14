// 수확 전용 AMCL 확장. 작업 보정을 라이다 시각으로 운반하고 원본 필터 갱신을 재사용한다.
#include <atomic>
#include <chrono>
#include <cmath>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <Eigen/Eigenvalues>
#include <nlohmann/json.hpp>
#include "nav2_amcl/amcl_node.hpp"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"
#include "tf2/utils.hpp"
#include "std_msgs/msg/string.hpp"

using Json = nlohmann::json;
using Steady = std::chrono::steady_clock;
class TagAmcl : public nav2_amcl::AmclNode {
public:
  TagAmcl() : nav2_amcl::AmclNode() {
    rcl_interfaces::msg::ParameterDescriptor d; d.read_only = true;
    declare_parameter("tag_correction_protocol", "scan_sync_v1", d);
    declare_parameter("tag_robot_id", "", d);
    declare_parameter("tag_map_id", "", d);
    // 실행 중 TF/토픽 재연결로 이 확장의 콜백이 원본 콜백으로 바뀌는 것을 막는다.
    guard_ = add_pre_set_parameters_callback([this](std::vector<rclcpp::Parameter> & ps) {
      for (const auto & p : ps) {
        if (configured_ && (p.get_name() == "scan_topic" || p.get_name() == "map_topic" ||
            p.get_name() == "base_frame_id" || p.get_name() == "odom_frame_id" ||
            p.get_name() == "global_frame_id" || p.get_name() == "transform_tolerance" ||
            p.get_name() == "set_initial_pose" || p.get_name().rfind("initial_pose.", 0) == 0)) {
          RCLCPP_WARN(get_logger(), "시각 동기 AMCL의 프레임/초기화 설정은 재시작 후 적용하세요.");
          ps.clear(); return;
        }
      }
    });
  }
protected:
  nav2_util::CallbackReturn on_configure(const rclcpp_lifecycle::State & s) override {
    robot_ = get_parameter("tag_robot_id").as_string(); map_id_ = get_parameter("tag_map_id").as_string();
    if (robot_.empty() || map_id_.empty() || get_namespace() != "/" + robot_ ||
        get_parameter("tag_correction_protocol").as_string() != "scan_sync_v1") {
      RCLCPP_ERROR(get_logger(), "수확 보정 robot_id/map_id/namespace/protocol 설정 불일치");
      return nav2_util::CallbackReturn::FAILURE;
    }
    auto result = nav2_amcl::AmclNode::on_configure(s);
    if (result != nav2_util::CallbackReturn::SUCCESS) {return result;}
    events_ = rclcpp::create_publisher<std_msgs::msg::String>(this, "tag_localization/events", rclcpp::QoS(100));
    rclcpp::SubscriptionOptions opts; opts.callback_group = callback_group_;
    control_ = create_subscription<std_msgs::msg::String>("tag_localization/control", 10,
      [this](std_msgs::msg::String::SharedPtr m) {control(m->data);}, opts);
    correction_ = create_subscription<std_msgs::msg::String>("tag_localization/correction", 10,
      [this](std_msgs::msg::String::SharedPtr m) {request(m->data);}, opts);
    initial_pose_sub_.reset();
    initial_pose_sub_ = create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>("initialpose", 10,
      [this](geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr m) {
        std::lock_guard<std::recursive_mutex> lock(mutex_); invalidate("manual_initialpose"); initialPoseReceived(m);
      }, opts);
    map_sub_.reset();
    map_sub_ = create_subscription<nav_msgs::msg::OccupancyGrid>(map_topic_, rclcpp::QoS(1).transient_local().reliable(),
      [this](nav_msgs::msg::OccupancyGrid::SharedPtr m) {
        std::lock_guard<std::recursive_mutex> lock(mutex_); invalidate("map_received"); mapReceived(m);
      }, opts);
    global_loc_srv_.reset();
    global_loc_srv_ = create_service<std_srvs::srv::Empty>("reinitialize_global_localization",
      [this](const std::shared_ptr<rmw_request_id_t> h, const std::shared_ptr<std_srvs::srv::Empty::Request> q,
      std::shared_ptr<std_srvs::srv::Empty::Response> r) {
        std::lock_guard<std::recursive_mutex> lock(mutex_); invalidate("global_localization"); globalLocalizationCallback(h,q,r);
      });
    initial_guess_srv_.reset();
    initial_guess_srv_ = create_service<nav2_msgs::srv::SetInitialPose>("set_initial_pose",
      [this](const std::shared_ptr<rmw_request_id_t> h, const std::shared_ptr<nav2_msgs::srv::SetInitialPose::Request> q,
      std::shared_ptr<nav2_msgs::srv::SetInitialPose::Response> r) {
        std::lock_guard<std::recursive_mutex> lock(mutex_); invalidate("manual_initialpose_service"); initialPoseReceivedSrv(h,q,r);
      });
    laser_scan_connection_.disconnect();
    laser_scan_connection_ = laser_scan_filter_->registerCallback(
      [this](sensor_msgs::msg::LaserScan::ConstSharedPtr m) {scan(m);});
    expiry_ = create_wall_timer(std::chrono::milliseconds(10), [this]() {
      std::lock_guard<std::recursive_mutex> lock(mutex_); expire();
    }, callback_group_);
    configured_ = true; last_clock_ = now().nanoseconds();
    RCLCPP_INFO(get_logger(), "TAG_SCAN_SYNC_READY: scan_sync_v1 (작업 신호·초기 위치 대기)");
    return result;
  }
  nav2_util::CallbackReturn on_deactivate(const rclcpp_lifecycle::State & s) override {
    {std::lock_guard<std::recursive_mutex> lock(mutex_); invalidate("deactivated");}
    return nav2_amcl::AmclNode::on_deactivate(s);
  }
  nav2_util::CallbackReturn on_shutdown(const rclcpp_lifecycle::State & s) override {
    {std::lock_guard<std::recursive_mutex> lock(mutex_); invalidate("shutdown"); active_=false; expiry_.reset();}
    return nav2_amcl::AmclNode::on_shutdown(s);
  }
  nav2_util::CallbackReturn on_cleanup(const rclcpp_lifecycle::State & s) override {
    {std::lock_guard<std::recursive_mutex> lock(mutex_); invalidate("cleanup"); configured_ = false;
      expiry_.reset(); correction_.reset(); control_.reset(); last_scan_ = 0;}
    return nav2_amcl::AmclNode::on_cleanup(s);
  }
private:
  struct Pending {Json metadata; tf2::Transform pose; pf_matrix_t covariance; Steady::time_point deadline;};
  std::optional<Pending> pending_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr control_, correction_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr events_;
  rclcpp::TimerBase::SharedPtr expiry_;
  rclcpp::node_interfaces::PreSetParametersCallbackHandle::SharedPtr guard_;
  std::map<std::string, int64_t> sequences_;
  std::set<std::string> closed_;
  std::string robot_, map_id_, token_, producer_;
  int64_t begin_ = 0, request_seq_ = 0, last_source_ = 0, last_scan_ = 0, last_clock_ = 0, barrier_ = 0;
  std::atomic<bool> configured_{false};
  Steady::time_point lease_{};
  static int64_t integer(const Json & j, const char * key) {
    const auto & v = j.at(key); if (!v.is_number_integer()) {throw std::runtime_error(key);} return v.get<int64_t>();
  }
  static std::string identity(const Json & j, const char * key) {
    auto s = j.at(key).get<std::string>(); if (s.empty() || s.size() > 128) {throw std::runtime_error(key);} return s;
  }
  void event(const std::string & kind, const std::string & reason, Json fields = Json::object()) {
    if (!events_) {return;}
    fields["kind"] = kind; fields["reason"] = reason; fields["robot_id"] = robot_; fields["map_id"] = map_id_;
    fields["receiver_stamp_ns"] = now().nanoseconds();
    std_msgs::msg::String m; m.data = fields.dump(); events_->publish(m);
  }
  void drop(const std::string & why) {
    if (pending_) {event("tag_correction_dropped", why, pending_->metadata); pending_.reset();}
  }
  void invalidate(const std::string & why) {
    drop(why); if (!token_.empty()) {closed_.insert(token_);} lease_ = Steady::time_point{};
    token_.clear(); producer_.clear(); barrier_ = now().nanoseconds();
  }
  void expire() {
    const auto t = now().nanoseconds();
    if (last_clock_ > 0 && t < last_clock_) {invalidate("clock_rewind"); last_scan_ = 0;}
    last_clock_ = t;
    if (!token_.empty() && Steady::now() >= lease_) {invalidate("lease_expired");}
    if (pending_ && Steady::now() >= pending_->deadline) {drop("scan_wait_timeout");}
  }
  bool live() const {return !token_.empty() && Steady::now() < lease_;}
  void control(const std::string & raw) {
    std::lock_guard<std::recursive_mutex> lock(mutex_); expire();
    try {
      if (raw.size() > 4096) {throw std::runtime_error("control_size");}
      auto j = Json::parse(raw);
      if (j.at("robot_id") != robot_ || j.at("map_id") != map_id_) {return;}
      auto token = identity(j,"token"); auto seq = integer(j,"sequence"); auto stamp = integer(j,"stamp_ns");
      auto age = now().nanoseconds() - stamp;
      if (closed_.count(token) || seq < 0 || age < 0 || age > 2000000000LL ||
          (sequences_.count(token) && seq <= sequences_[token]) || (live() && token != token_)) {return;}
      if (sequences_.size() >= 4096 && !sequences_.count(token)) {throw std::runtime_error("task_history_full_restart_required");}
      if (!j.at("enabled").is_boolean()) {throw std::runtime_error("enabled_type");}
      if (!j.at("enabled").get<bool>()) {
        sequences_[token] = seq; closed_.insert(token);
        if (token == token_) {invalidate("task_ended");} return;
      }
      auto begin = integer(j,"begin_ns");
      if (!active_ || begin <= 0 || begin < barrier_ || begin > stamp || (live() && begin != begin_)) {event("tag_control_rejected", "inactive_or_task_begin", {{"begin_ns",begin},{"barrier_ns",barrier_},{"stamp_ns",stamp},{"active",static_cast<bool>(active_)}}); return;}
      sequences_[token] = seq;
      if (token_ != token) {drop("task_changed"); producer_.clear(); request_seq_ = 0; last_source_ = 0;}
      token_ = token; begin_ = begin; lease_ = Steady::now() + std::chrono::seconds(2);
      event("tag_control_accepted", "lease_renewed", {{"token",token},{"sequence",seq}});
    } catch (const std::exception & e) {event("tag_control_rejected", e.what());}
  }
  void request(const std::string & raw) {
    std::lock_guard<std::recursive_mutex> lock(mutex_); expire();
    try {
      if (raw.size() > 8192) {throw std::runtime_error("request_size");}
      auto j = Json::parse(raw); auto t = now().nanoseconds();
      auto source = integer(j,"source_stamp_ns"), pose_stamp = integer(j,"pose_stamp_ns"), sent = integer(j,"sent_stamp_ns");
      auto seq = integer(j,"sequence"); auto producer = identity(j,"producer_session");
      if (integer(j,"protocol") != 1 || j.at("robot_id") != robot_ || j.at("map_id") != map_id_ ||
          j.at("frame_id") != global_frame_id_) {throw std::runtime_error("protocol_robot_map_frame");}
      if (!active_ || !first_map_received_ || !initial_pose_is_known_) {throw std::runtime_error("amcl_not_initialized");}
      if (!live() || j.at("token") != token_) {throw std::runtime_error("task_lease_or_token");}
      if (source < begin_ || source <= last_source_ || seq <= request_seq_ ||
          (!producer_.empty() && producer_ != producer)) {throw std::runtime_error("request_order_or_producer");}
      if (pose_stamp < source || sent < pose_stamp || t < sent || t - source > 1000000000LL ||
          t - pose_stamp > 500000000LL) {throw std::runtime_error("request_time");}
      const auto p = j.at("pose").get<std::vector<double>>(); const auto cov = j.at("covariance").get<std::vector<double>>();
      if (p.size() != 3 || cov.size() != 36) {throw std::runtime_error("pose_shape");}
      for (double v : p) {if (!std::isfinite(v)) {throw std::runtime_error("pose_nonfinite");}}
      for (double v : cov) {if (!std::isfinite(v)) {throw std::runtime_error("covariance_nonfinite");}}
      Eigen::Matrix3d m; const int axes[] = {0,1,5};
      for (int i=0;i<3;++i) {for (int k=0;k<3;++k) {m(i,k)=cov[6*axes[i]+axes[k]];}}
      if (!m.isApprox(m.transpose(),1e-9) || Eigen::SelfAdjointEigenSolver<Eigen::Matrix3d>(m).eigenvalues().minCoeff() < 0) {
        throw std::runtime_error("covariance_not_psd");
      }
      Pending q; q.metadata = j; q.deadline = Steady::now()+std::chrono::milliseconds(250);
      tf2::Quaternion rotation; rotation.setRPY(0,0,p[2]); q.pose = tf2::Transform(rotation,tf2::Vector3(p[0],p[1],0));
      q.covariance = pf_matrix_zero(); for(int i=0;i<3;++i) {for(int k=0;k<3;++k) {q.covariance.m[i][k]=m(i,k);}}
      drop("superseded"); producer_ = producer; request_seq_ = seq; last_source_ = source; pending_ = q;
      event("tag_correction_queued", "waiting_scan", j);
    } catch (const std::exception & e) {event("tag_correction_rejected", e.what());}
  }
  void scan(sensor_msgs::msg::LaserScan::ConstSharedPtr msg) {
    std::lock_guard<std::recursive_mutex> lock(mutex_); expire();
    if (!active_ || !first_map_received_) {return;}
    const auto stamp = rclcpp::Time(msg->header.stamp); const auto ns = stamp.nanoseconds();
    if (ns <= last_scan_) {return;}
    if (pending_ && ns >= integer(pending_->metadata,"pose_stamp_ns")) {
      const auto t = now().nanoseconds();
      if (!live() || t < ns || t-integer(pending_->metadata,"source_stamp_ns") > 1000000000LL ||
          t-integer(pending_->metadata,"pose_stamp_ns") > 500000000LL) {drop("expired_at_scan");}
      else {
        try {
          // 원본 laserReceived에서 필터 초기화 전 필요한 TF·센서 등록을 먼저 확인한다.
          if (msg->ranges.empty() || !std::isfinite(msg->angle_increment) || msg->angle_increment == 0 ||
              msg->header.frame_id.empty() || msg->header.frame_id[0] == '/') {throw std::runtime_error("invalid_scan");}
          auto from = tf_buffer_->lookupTransform(odom_frame_id_,base_frame_id_,rclcpp::Time(integer(pending_->metadata,"pose_stamp_ns"),RCL_ROS_TIME));
          auto to = tf_buffer_->lookupTransform(odom_frame_id_,base_frame_id_,stamp);
          if (!tf_buffer_->canTransform(base_frame_id_,msg->header.frame_id,stamp)) {throw std::runtime_error("laser_tf_unavailable");}
          if (!frame_to_laser_.count(msg->header.frame_id)) {
            int index=-1; geometry_msgs::msg::PoseStamped laser_pose;
            if (!addNewScanner(index,msg,msg->header.frame_id,laser_pose)) {throw std::runtime_error("laser_registration_failed");}
          }
          tf2::Transform a,b; tf2::fromMsg(from.transform,a); tf2::fromMsg(to.transform,b);
          auto aligned = pending_->pose*a.inverse()*b;
          pf_vector_t mean=pf_vector_zero(); mean.v[0]=aligned.getOrigin().x(); mean.v[1]=aligned.getOrigin().y(); mean.v[2]=tf2::getYaw(aligned.getRotation());
          Json report=pending_->metadata; report["scan_stamp_ns"]=ns;
          report["aligned_pose"]={mean.v[0],mean.v[1],mean.v[2]};
          pf_init(pf_,mean,pending_->covariance); pf_init_=false; initial_pose_is_known_=true; init_pose_received_on_inactive=false;
          pending_.reset(); nav2_amcl::AmclNode::laserReceived(msg);
          report["odom_anchor"]={pf_odom_pose_.v[0],pf_odom_pose_.v[1],pf_odom_pose_.v[2]};
          report["filter_initialized"]=pf_init_;
          event("tag_correction_applied", "scan_aligned", report);
          RCLCPP_INFO(get_logger(), "TAG_CORRECTION_APPLIED: %ld scan=%ld", request_seq_, ns);
          last_scan_=ns; return;
        } catch (const std::exception &) {
          // TF가 없는 시각을 최신 값으로 대체하지 않는다. 다음 스캔/250ms 만료를 기다린다.
        }
      }
    }
    nav2_amcl::AmclNode::laserReceived(msg); last_scan_=ns;
  }
};
int main(int argc,char ** argv) {
  rclcpp::init(argc,argv); auto node=std::make_shared<TagAmcl>();
  rclcpp::spin(node->get_node_base_interface()); rclcpp::shutdown(); return 0;
}
