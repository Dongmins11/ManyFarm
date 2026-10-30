#pragma once
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <sstream>
#include <iomanip>
#include <limits>
namespace farm_wall_controller {
// 환경별 SI 설정. 벽 분석은 Python 공통 wall_reference가 담당한다.
struct Config {
 // 선택형 스테이션 모드. 기본 false는 기존 인계의 단일 전방 벽 제어다.
 bool station_docking=false;
 double lateral_tolerance=.005, kp_terminal=.3;
 double target_angle=0; // signed observed wall normal at desired alignment (rad)
 double target=0, distance_tolerance=.005, angle_tolerance=.01745329252;
 double kp_distance=.4, kp_angle=.8, max_linear=.01, max_angular=.05;
 // 0이면 기존 P 출력 유지. 장치별 최소 속도는 환경 설정에서 지정한다.
 double min_linear=0, min_angular=0;
 bool sequential_alignment=false; // opt-in: stop, align, hold, approach
 double align_enter=.06981317008, align_exit=.03490658504;
 double dwell=.5, max_distance=.20, max_yaw=.2617993878;
 bool wait_until_fresh=false; // 인계 전용: 지연 중 정지 유지, 정상 관측 후 같은 Goal 재개
 double observation_wait=0; // 0: 기존 즉시 실패, 양수: 정지 대기 상한(초)
 double timeout=40, observation_age=.3, stopped_linear=.005, stopped_angular=.02;
 void validate() const {
  if(station_docking && (!std::isfinite(lateral_tolerance)||lateral_tolerance<=0 ||
      !std::isfinite(kp_terminal)||kp_terminal<=0))throw std::invalid_argument("Invalid docking configuration");
  if(!std::isfinite(observation_wait)||observation_wait<0)throw std::invalid_argument("Invalid observation wait");
  for(double v:{target,distance_tolerance,angle_tolerance,kp_distance,kp_angle,max_linear,max_angular,
      align_enter,align_exit,dwell,max_distance,max_yaw,timeout,observation_age,stopped_linear,stopped_angular})
    if(!std::isfinite(v)||v<=0) throw std::invalid_argument("Wall configuration must be finite and positive");
  if(!std::isfinite(min_linear)||!std::isfinite(min_angular)||min_linear<0||min_angular<0||min_linear>max_linear||min_angular>max_angular)
    throw std::invalid_argument("Invalid minimum wall velocity");
  if(!std::isfinite(target_angle)||std::abs(target_angle)+angle_tolerance>=max_yaw)
    throw std::invalid_argument("Invalid wall target angle");
  if(!(angle_tolerance<align_exit && align_exit<align_enter && align_enter<max_yaw && max_yaw<1.57079632679)
      ||distance_tolerance>=target || dwell<=observation_age)
    throw std::invalid_argument("Invalid wall tolerance / hysteresis / dwell");
 }
};
inline double wrap(double a){return std::atan2(std::sin(a),std::cos(a));}
struct Pose{double x,y,yaw;};
struct Wall{double x,y,yaw,stamp;};
struct Error{double distance,angle;};
inline Error errors(const Wall &w,const Pose &p,const Config &c){
 for(double v:{w.x,w.y,w.yaw,w.stamp,p.x,p.y,p.yaw}) if(!std::isfinite(v))throw std::runtime_error("Nonfinite wall / pose");
 return {(w.x-p.x)*std::cos(w.yaw)+(w.y-p.y)*std::sin(w.yaw)-c.target,wrap(w.yaw-p.yaw-c.target_angle)};
}
struct Command{double linear=0,angular=0;bool reached=false;};
class Control {
 Config c_;bool started_=false,align_=true;Pose origin_{};double start_=0,last_=0,within_=-1;
 enum class Phase { Stop, Align, Approach };
 Phase phase_=Phase::Stop; double aligned_since_=-1, waiting_since_=-1, previous_now_=-1;
 // start_는 실제 시작 ROS 시각으로 고정한다. 보정은 해당 호출 구간의 실행 누계에만 적용한다.
 double active_elapsed_=0, excluded_elapsed_=0, pending_credit_=0;
 double interval_=0, requested_credit_=0, applied_credit_=0;
 bool previous_wait_=false;double distance_=0,yaw_delta_=0;
 [[noreturn]] void fail(const char *reason,double now,double stamp=std::numeric_limits<double>::quiet_NaN()) const {
  std::ostringstream out;out<<std::setprecision(17)<<reason
   <<" now_s="<<now<<" previous_now_s="<<previous_now_<<" start_s="<<start_
   <<" wall_stamp_s="<<stamp<<" last_wall_stamp_s="<<last_
   <<" wall_age_s="<<(now-stamp)<<" observation_age_s="<<c_.observation_age
   <<" interval_s="<<interval_<<" credit_requested_s="<<requested_credit_
   <<" credit_applied_s="<<applied_credit_<<" pending_credit_s="<<pending_credit_
   <<" active_elapsed_s="<<active_elapsed_<<" excluded_elapsed_s="<<excluded_elapsed_
   <<" timeout_s="<<c_.timeout<<" waiting_since_s="<<waiting_since_
   <<" distance_m="<<distance_<<" max_distance_m="<<c_.max_distance
   <<" yaw_delta_rad="<<yaw_delta_<<" max_yaw_rad="<<c_.max_yaw;
  throw std::runtime_error(out.str());
 }
 void check_now(double now) const {
  if(!std::isfinite(now))fail("WALL_INVALID_NOW",now);
  if(started_ && now<previous_now_)fail("WALL_CLOCK_REVERSED",now);
 }
 // 도킹에서는 Wall 필드에 같은 odom 좌표계의 목표 자세를 전달한다.
 Command dock(const Wall &target,const Pose &p,double linear,double angular){
  const double dx=target.x-p.x,dy=target.y-p.y;
  const double longitudinal=std::cos(target.yaw)*dx+std::sin(target.yaw)*dy;
  const double lateral=-std::sin(target.yaw)*dx+std::cos(target.yaw)*dy;
  const double heading=wrap(target.yaw-p.yaw);
  const bool position_ok=std::abs(longitudinal)<=c_.distance_tolerance &&
                         std::abs(lateral)<=c_.lateral_tolerance;
  if(position_ok){
   if(std::abs(heading)>c_.angle_tolerance){
    within_=-1;
    return {0,std::copysign(std::clamp(c_.kp_angle*std::abs(heading),c_.min_angular,c_.max_angular),heading),false};
   }
   if(std::abs(linear)<c_.stopped_linear && std::abs(angular)<c_.stopped_angular){
    if(within_<0)within_=target.stamp;
    return {0,0,target.stamp-within_>=c_.dwell};
   }
   within_=-1;return {};
  }
  within_=-1;
  // 후진 가상 진행 방향(yaw+pi)의 극좌표 자세 오차. 선/각속도를 같은 비율로 제한한다.
  const double bearing=std::atan2(dy,dx),pi=std::acos(-1.);
  const double alpha=wrap(bearing-p.yaw-pi);
  const double beta=wrap(target.yaw+pi-bearing);
  double v=-c_.kp_distance*std::hypot(dx,dy)*std::max(0.,std::cos(alpha));
  double w=c_.kp_angle*alpha-c_.kp_terminal*beta;
  const double scale=std::max({1.,std::abs(v)/c_.max_linear,std::abs(w)/c_.max_angular});
  return {v/scale,w/scale,false};
 }
public:
 explicit Control(Config c):c_(c){c_.validate();}
 // WaitClock의 최신성·단일 발행자·세션 검사를 통과한 초 단위 보정만 받는다.
 // 구간을 넘는 보정은 버리고 다음 정상 동작 구간으로 이월하지 않는다.
 void credit_wait(double seconds){
  if(!std::isfinite(seconds)||seconds<0)fail("WALL_INVALID_CREDIT",previous_now_);
  if(started_){pending_credit_+=seconds;if(!std::isfinite(pending_credit_))fail("WALL_INVALID_CREDIT",previous_now_);}
 }
 void reset(){started_=false;align_=true;within_=-1;phase_=Phase::Stop;aligned_since_=-1;waiting_since_=-1;
  previous_now_=-1;last_=0;start_=0;active_elapsed_=0;excluded_elapsed_=0;pending_credit_=0;
  interval_=0;requested_credit_=0;applied_credit_=0;previous_wait_=false;distance_=0;yaw_delta_=0;}
 // 이전 호출이 관측 대기였던 구간은 무기한 대기 선택 시 전부 제외한다.
 // 같은 구간의 외부 보정은 다시 빼지 않는다. 실행시간은 음수가 되거나 감소하지 않는다.
 void bounds(const Pose &p,double now,bool check_time=true){
  check_now(now);
  if(!std::isfinite(p.x)||!std::isfinite(p.y)||!std::isfinite(p.yaw))fail("WALL_INVALID_POSE",now);
  interval_=started_?now-previous_now_:0;
  requested_credit_=pending_credit_;
  applied_credit_=c_.wait_until_fresh&&previous_wait_?interval_:std::min(interval_,pending_credit_);
  pending_credit_=0;
  active_elapsed_+=interval_-applied_credit_;excluded_elapsed_+=applied_credit_;
  if(!started_){origin_=p;start_=now;started_=true;}
  previous_now_=now;
  distance_=std::hypot(p.x-origin_.x,p.y-origin_.y);yaw_delta_=std::abs(wrap(p.yaw-origin_.yaw));
  if(check_time && active_elapsed_>c_.timeout)fail("WALL_ACTIVE_TIMEOUT",now);
  if(!c_.station_docking && distance_>c_.max_distance)fail("WALL_DISTANCE_BOUND",now);
  if(!c_.station_docking && yaw_delta_>c_.max_yaw)fail("WALL_YAW_BOUND",now);
 }
 Command wait(const Pose &p,double now){
  bounds(p,now,!c_.wait_until_fresh);previous_wait_=true;
  if(!c_.wait_until_fresh && c_.observation_wait<=0)fail("WALL_NO_FRESH_OBSERVATION",now);
  within_=-1;aligned_since_=-1;phase_=Phase::Stop;align_=true;
  if(waiting_since_<0)waiting_since_=now;
  if(!c_.wait_until_fresh && now-waiting_since_>=c_.observation_wait)fail("WALL_OBSERVATION_WAIT_TIMEOUT",now);
  return {};
 }
 Command step(const Wall &w,const Pose &p,double now,double linear,double angular){
  check_now(now);
  if(!std::isfinite(linear)||!std::isfinite(angular))fail("WALL_INVALID_VELOCITY",now,w.stamp);
  auto e=errors(w,p,c_);
  if(w.stamp>now)fail("WALL_OBSERVATION_FUTURE",now,w.stamp);
  if(now-w.stamp>c_.observation_age)return wait(p,now);
  bounds(p,now);
  if(!c_.wait_until_fresh && waiting_since_>=0 && now-waiting_since_>=c_.observation_wait)fail("WALL_OBSERVATION_WAIT_TIMEOUT",now,w.stamp);
  waiting_since_=-1;previous_wait_=false;
  if(w.stamp<last_)fail("WALL_STAMP_REVERSED",now,w.stamp);
  if(last_>0 && w.stamp-last_>c_.observation_age){
   if(!c_.wait_until_fresh && c_.observation_wait<=0)fail("WALL_OBSERVATION_GAP",now,w.stamp);
   within_=-1;aligned_since_=-1;phase_=Phase::Stop;align_=true;
  }
  last_=w.stamp;
  if(c_.station_docking)return dock(w,p,linear,angular);
  if(e.distance < -c_.distance_tolerance)throw std::runtime_error("Already beyond wall target; no automatic reverse");
  if(std::abs(wrap(w.yaw-p.yaw))>c_.max_yaw)throw std::runtime_error("Raw wall angle outside envelope");
  if(std::abs(e.angle)>c_.max_yaw)throw std::runtime_error("Wall angle outside approach envelope");
  bool in=std::abs(e.distance)<=c_.distance_tolerance && std::abs(e.angle)<=c_.angle_tolerance;
  if(in){
   if(std::abs(linear)<c_.stopped_linear && std::abs(angular)<c_.stopped_angular){
    if(within_<0)within_=w.stamp;
    return {0,0,w.stamp-within_>=c_.dwell};
   }
   within_=-1;return {};
  }
  within_=-1;
  if(c_.sequential_alignment){
   const bool stopped=std::abs(linear)<c_.stopped_linear && std::abs(angular)<c_.stopped_angular;
   const bool heading_ok=std::abs(e.angle)<=c_.angle_tolerance;
   if(phase_==Phase::Approach && !heading_ok){
    phase_=Phase::Stop;aligned_since_=-1;return {};
   }
   if(phase_==Phase::Stop){
    if(!stopped)return {};
    phase_=Phase::Align;
   }
   if(phase_==Phase::Align){
    if(!heading_ok){
     aligned_since_=-1;
     return {0,std::copysign(std::clamp(c_.kp_angle*std::abs(e.angle),c_.min_angular,c_.max_angular),e.angle),false};
    }
    if(!stopped){aligned_since_=-1;return {};}
    if(aligned_since_<0)aligned_since_=w.stamp;
    if(w.stamp-aligned_since_<c_.dwell)return {};
    phase_=Phase::Approach;
   }
   return {e.distance>c_.distance_tolerance?std::clamp(c_.kp_distance*e.distance,c_.min_linear,c_.max_linear):0.,0,false};
  }
  if(std::abs(e.angle)>=c_.align_enter)align_=true;
  if(std::abs(e.angle)<=c_.align_exit)align_=false;
  double v=(!align_ && e.distance>c_.distance_tolerance)?std::clamp(c_.kp_distance*e.distance,c_.min_linear,c_.max_linear):0.;
  double omega=std::abs(e.angle)>c_.angle_tolerance?std::copysign(std::clamp(c_.kp_angle*std::abs(e.angle),c_.min_angular,c_.max_angular),e.angle):0.;
  return {v,omega,false};
 }
};
}
