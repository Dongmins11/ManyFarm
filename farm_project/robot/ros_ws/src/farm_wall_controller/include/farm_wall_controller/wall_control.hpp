#pragma once
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace farm_wall_controller {
// 환경별 SI 설정. 벽 분석은 Python 공통 wall_reference가 담당한다.
struct Config {
 double target_angle=0; // signed observed wall normal at desired alignment (rad)
 double target=0, distance_tolerance=.005, angle_tolerance=.01745329252;
 double kp_distance=.4, kp_angle=.8, max_linear=.01, max_angular=.05;
 // 0이면 기존 P 출력 유지. 장치별 최소 속도는 환경 설정에서 지정한다.
 double min_linear=0, min_angular=0;
 bool sequential_alignment=false; // opt-in: stop, align, hold, approach
 double align_enter=.06981317008, align_exit=.03490658504;
 double dwell=.5, max_distance=.20, max_yaw=.2617993878;
 double timeout=40, observation_age=.3, stopped_linear=.005, stopped_angular=.02;
 void validate() const {
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
 Phase phase_=Phase::Stop; double aligned_since_=-1;
public:
 explicit Control(Config c):c_(c){c_.validate();}
 void reset(){started_=false;align_=true;within_=-1;phase_=Phase::Stop;aligned_since_=-1;}
 Command step(const Wall &w,const Pose &p,double now,double linear,double angular){
  if(!std::isfinite(now)||!std::isfinite(linear)||!std::isfinite(angular))throw std::runtime_error("Nonfinite time / velocity");
  auto e=errors(w,p,c_);
  if(w.stamp>now || now-w.stamp>c_.observation_age)throw std::runtime_error("Wall observation expired / future");
  if(!started_){origin_=p;start_=now;last_=w.stamp;started_=true;}
  if(now<start_ || w.stamp<last_)throw std::runtime_error("Clock reversed");
  if(w.stamp-last_>c_.observation_age)throw std::runtime_error("Wall observation gap");
  last_=w.stamp;
  if(now-start_>c_.timeout || std::hypot(p.x-origin_.x,p.y-origin_.y)>c_.max_distance ||
     std::abs(wrap(p.yaw-origin_.yaw))>c_.max_yaw)throw std::runtime_error("Wall motion bound exceeded");
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
