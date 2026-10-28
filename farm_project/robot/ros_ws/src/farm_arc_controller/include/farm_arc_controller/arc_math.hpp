#pragma once
#include <cmath>
#include <stdexcept>
#include <algorithm>
#include <vector>
namespace farm_arc_controller {
struct Pose {double x,y,yaw;};
struct Command {double v,w;};
struct Arc {Pose start; double radius,angle;};
inline double wrap(double a) {return std::atan2(std::sin(a),std::cos(a));}
inline Pose at(Pose start,double radius,double angle) {
  const double x=-radius*std::sin(angle),y=-radius*(1-std::cos(angle));
  return {start.x+std::cos(start.yaw)*x-std::sin(start.yaw)*y,
    start.y+std::sin(start.yaw)*x+std::cos(start.yaw)*y,wrap(start.yaw+angle)};
}
// 양의 각도는 후진 좌회전, 음의 각도는 그 역경로인 전진 우회전이다.
// 경로를 잘라내거나 재생성하지 않고 모든 입력 자세를 검증한다.
inline Arc validate_path(const std::vector<Pose> & path) {
  if(path.size()<3) throw std::runtime_error("Arc needs a sampled path");
  for(const auto & p:path)
    if(!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.yaw))
      throw std::runtime_error("Non-finite arc pose");
  const auto start=path.front(),end=path.back();
  const double angle=wrap(end.yaw-start.yaw),total=std::abs(angle);
  if(total<=0 || total>M_PI_2+1e-6)
    throw std::runtime_error("Arc angle must be nonzero and <=90deg");
  const double direction=angle>0 ? 1.0 : -1.0;
  const double radius=std::hypot(end.x-start.x,end.y-start.y)/(2*std::sin(total/2));
  if(!std::isfinite(radius) || radius<.05 || radius>.30)
    throw std::runtime_error("Trial radius outside 5-30cm");
  double previous=-1e-6;
  for(const auto & p:path){
    const double t=wrap(p.yaw-start.yaw),progress=direction*t;
    const auto target=at(start,radius,t);
    if(progress<previous-1e-6 || progress>total+1e-6 ||
       std::hypot(target.x-p.x,target.y-p.y)>.001)
      throw std::runtime_error("Invalid arc sample");
    previous=progress;
  }
  return {start,radius,angle};
}
// 로봇의 실제 위치에서 원호 위의 선행점을 선택한다. RPM 변환은 기존 드라이버 책임이다.
inline Command command(Pose start,Pose now,double radius,double total,double speed,
                       double lookahead,double deviation,double max_w) {
  if (!(radius>0 && speed>0 && lookahead>0 && deviation>0 && max_w>0 &&
        std::abs(total)>0 && std::abs(total)<=M_PI_2+1e-6) ||
      !std::isfinite(radius+speed+lookahead+deviation+max_w+total+now.x+now.y+now.yaw+start.x+start.y+start.yaw))
    throw std::runtime_error("invalid arc input");
  const double direction=total>0 ? 1.0 : -1.0;
  const double extent=std::abs(total);
  const double progress=direction*wrap(now.yaw-start.yaw);
  if (progress < -.05 || progress > extent+.05) throw std::runtime_error("arc heading exceeded");
  const auto expected=at(start,radius,direction*std::clamp(progress,0.0,extent));
  if (std::hypot(now.x-expected.x,now.y-expected.y)>deviation)
    throw std::runtime_error("arc deviation exceeded");
  const double dx=now.x-start.x,dy=now.y-start.y;
  const double x=std::cos(start.yaw)*dx+std::sin(start.yaw)*dy;
  const double y=-std::sin(start.yaw)*dx+std::cos(start.yaw)*dy;
  const double nearest=std::atan2(-direction*x,y+radius);
  // 종료 직전에도 원호 접선을 유지하도록 원을 수학적으로 연장한다.
  const auto target=at(start,radius,direction*(nearest+lookahead/radius));
  const double tx=target.x-now.x,ty=target.y-now.y;
  const double bx=std::cos(now.yaw)*tx+std::sin(now.yaw)*ty;
  const double by=-std::sin(now.yaw)*tx+std::cos(now.yaw)*ty;
  const double squared=bx*bx+by*by;
  if (direction*bx>=0 || squared<1e-8) throw std::runtime_error("arc carrot direction invalid");
  const double curvature=2*by/squared;
  double v=-direction*speed,w=v*curvature;
  if (direction*w<=0) throw std::runtime_error("wrong arc direction");
  if(std::abs(w)>max_w){v*=max_w/std::abs(w);w=direction*max_w;}
  return {v,w};
}
}
