#include "farm_wall_controller/wall_control.hpp"
#include <iostream>
#include <functional>
using namespace farm_wall_controller;
int count=0;
void require(bool good){++count;if(!good)throw std::runtime_error("test assertion "+std::to_string(count));}
void rejects(std::function<void()> f){bool rejected=false;try{f();}catch(const std::exception &){rejected=true;}require(rejected);}
int main(){
 Config c;c.target=.4325;Control k(c);Pose p{0,0,0};Wall w{.525,0,0,10};
 auto a=k.step(w,p,10,0,0);require(a.linear==.01 && a.angular==0);
 k.reset();w.yaw=.1;w.x=.525*std::cos(.1);w.y=.525*std::sin(.1);
 a=k.step(w,p,10,0,0);require(a.linear==0 && a.angular>0);
 k.reset();w.yaw=-.1;w.y=-w.y;a=k.step(w,p,10,0,0);require(a.angular<0 && a.linear==0);
 k.reset();w={.43,0,0,10};require(!k.step(w,p,10,0,0).reached);
 for(int i=1;i<=6;++i){w.stamp=10+i*.1;a=k.step(w,p,w.stamp,0,0);}require(a.reached);
 k.reset();w={.43,0,0,10};for(int i=0;i<20;++i)a=k.step(w,p,10,0,0);require(!a.reached);
 rejects([&]{k.step(w,p,10.31,0,0);});
 k.reset();w={.42,0,0,10};rejects([&]{k.step(w,p,10,0,0);});
 k.reset();w={.525,0,0,10};k.step(w,p,10,0,0);w.stamp=9.9;rejects([&]{k.step(w,p,10,0,0);});
 k.reset();w.stamp=10;rejects([&]{k.step(w,p,9.99,0,0);});
 rejects([&]{Config bad=c;bad.target=0;Control x(bad);});
 k.reset();w={.525,0,0,10};k.step(w,p,10,0,0);w.stamp=10.1;rejects([&]{k.step(w,{.21,0,0},10.1,0,0);});
 k.reset();w={.525,0,0,10};rejects([&]{k.step(w,p,10,NAN,0);});
 k.reset();w={.43,0,0,10};for(int i=0;i<10;++i){w.stamp=10+i*.1;a=k.step(w,{0,0,0},w.stamp,.01,0);}require(!a.reached);
 k.reset();w={.525,0,.3,10};rejects([&]{k.step(w,{0,0,0},10,0,0);});
 {Config short_time=c;short_time.timeout=.1;Control timed(short_time);w={.525,0,0,10};timed.step(w,{0,0,0},10,0,0);w.stamp=10.2;rejects([&]{timed.step(w,{0,0,0},10.2,0,0);});}
 k.reset();w={.525,0,.1,10};k.step(w,{0,0,0},10,0,0);w={.525,0,.05,10.1};require(k.step(w,{0,0,0},10.1,0,0).linear==0);
 w={.525,0,.02,10.2};require(k.step(w,{0,0,0},10.2,0,0).linear>0);
 // 이상적인 차동구동 모델에서 좌우 초기 각도로 동일 제어 코드를 평가한다.
 for(double initial:{-.12,-.025,0.,.025,.12}){
  k.reset();p={0,0,initial};double t=20,v=0,omega=0;bool done=false;
  for(int i=0;i<800;++i){w={.525,0,0,t};a=k.step(w,p,t,v,omega);
   if(a.reached){done=true;break;}v=a.linear;omega=a.angular;
   p.x+=v*std::cos(p.yaw)*.05;p.y+=v*std::sin(p.yaw)*.05;p.yaw+=omega*.05;t+=.05;}
  require(done);require(std::abs(.525-p.x-c.target)<=c.distance_tolerance);
  require(std::abs(p.yaw)<=c.angle_tolerance);
 }
 // 최소 출력은 허용오차 밖에만 적용하고, 정지·오류 검사는 유지한다.
 {Config m=c;m.min_linear=.006;m.min_angular=.03;Control q(m);
  auto cmd=q.step({.4385,0,0,10},{0,0,0},10,0,0);require(cmd.linear==.006 && cmd.angular==0);
  for(double sign:{-1.,1.}){q.reset();double angle=sign*.02;
   cmd=q.step({.434*std::cos(angle),.434*std::sin(angle),angle,10},{0,0,0},10,0,0);
   require(cmd.linear==0 && cmd.angular==sign*.03);}
  q.reset();cmd=q.step({.4325,0,0,10},{0,0,0},10,0,0);require(cmd.linear==0 && cmd.angular==0 && !cmd.reached);
  for(int i=1;i<=6;i++)cmd=q.step({.4325,0,0,10+i*.1},{0,0,0},10+i*.1,0,0);
  require(cmd.reached && cmd.linear==0 && cmd.angular==0);
  q.reset();rejects([&]{q.step({.5,0,0,10},{0,0,0},10.31,0,0);});
  q.reset();rejects([&]{q.step({.42,0,0,10},{0,0,0},10,0,0);});
  for(double bad:{-.001,double(NAN),double(INFINITY)}){Config invalid=m;invalid.min_linear=bad;rejects([&]{invalid.validate();});}
  {Config invalid=m;invalid.min_angular=.051;rejects([&]{invalid.validate();});}
 }
 // Sequential option: no simultaneous translation/rotation; measured stop first.
 {Config seq=c;seq.sequential_alignment=true;seq.min_linear=.006;seq.min_angular=.03;
  Control q(seq);double t=100;
  auto step=[&](double angle,double v=0.,double omega=0.){
   t+=.1;return q.step({.525*std::cos(angle),.525*std::sin(angle),angle,t},{0,0,0},t,v,omega);
  };
  auto cmd=step(.025,.01,0);require(cmd.linear==0 && cmd.angular==0);
  cmd=step(.025);require(cmd.linear==0 && cmd.angular==.03);
  cmd=step(.01,0,.03);require(cmd.linear==0 && cmd.angular==0);
  for(int i=0;i<5;++i){cmd=step(.01);require(cmd.linear==0 && cmd.angular==0);}
  cmd=step(.025);require(cmd.linear==0 && cmd.angular==.03); // dwell reset
  for(int i=0;i<5;++i){cmd=step(.01);require(cmd.linear==0);}
  for(int i=0;i<2;++i)cmd=step(.01);
  require(cmd.linear>0 && cmd.angular==0);
  cmd=step(-.025,.01);require(cmd.linear==0 && cmd.angular==0);
  cmd=step(-.025,.008);require(cmd.linear==0 && cmd.angular==0);
  cmd=step(-.025);require(cmd.linear==0 && cmd.angular==-.03);
  q.reset();cmd=step(0);require(cmd.linear==0); // new goal cannot inherit alignment
  for(int i=0;i<20;++i){cmd=q.step({.525,0,0,t},{0,0,0},t,0,0);require(cmd.linear==0);}
  q.reset();rejects([&]{q.step({.525,0,0,t},{0,0,0},t+.31,0,0);});
  q.reset();rejects([&]{q.step({.42,0,0,t},{0,0,0},t,0,0);});
  q.reset();cmd=q.step({.4325,0,0,t},{0,0,0},t,0,0);require(!cmd.reached);
  for(int i=0;i<7;++i){t+=.1;cmd=q.step({.4325,0,0,t},{0,0,0},t,0,0);}
  require(cmd.reached && cmd.linear==0 && cmd.angular==0);
  // Ideal motion, both directions, start near/far tolerance.
  for(double initial:{-.12,-.025,-.017,0.,.017,.025,.12}){
   q.reset();Pose pos{0,0,initial};double tm=200,v=0,om=0;bool done=false;
   for(int n=0;n<800;++n){
    auto out=q.step({.525,0,0,tm},pos,tm,v,om);
    if(out.linear!=0 && out.angular!=0)throw std::runtime_error("mixed sequential command");
    if(out.reached){done=true;break;}
    v=out.linear;om=out.angular;pos.x+=v*std::cos(pos.yaw)*.05;
    pos.y+=v*std::sin(pos.yaw)*.05;pos.yaw+=om*.05;tm+=.05;
   }
   require(done);require(std::abs(pos.yaw)<=seq.angle_tolerance);
   require(std::abs(.525-pos.x-seq.target)<=seq.distance_tolerance);
  }
 }
 {
  Config off=c;off.target_angle=0.04276056667386108;off.sequential_alignment=true;off.min_angular=.03;
  // Observed -0.636 deg vs desired +2.45 deg => turn RIGHT, not left.
  const double observed=-0.6361298137083946*3.141592653589793/180.;
  auto err=errors({off.target,0,observed,1},{0,0,0},off);
  require(err.angle<-.05 && err.angle>-.06);
  Control q(off);auto out=q.step({.525,0,observed,1},{0,0,0},1,0,0);
  require(out.angular<0 && out.linear==0);
  // Raw zero must no longer count as aligned.
  q.reset();out=q.step({off.target,0,0,2},{0,0,0},2,0,0);require(!out.reached && out.angular<0);
  // Desired raw angle, distance and dwell satisfy completion.
  q.reset();const double x=off.target/std::cos(off.target_angle);
  for(int i=0;i<8;++i)out=q.step({x,0,off.target_angle,3+i*.1},{0,0,0},3+i*.1,0,0);
  require(out.reached && out.linear==0 && out.angular==0);
  // Both sign offsets, same controller / goal checker calculation.
  for(double target:{-.04276056667386108,0.,.04276056667386108}){
   Config cfg=off;cfg.target_angle=target;Control control(cfg);Pose pos{0,0,0};double now=10,v=0,om=0;bool done=false;
   for(int i=0;i<800;++i){
    auto cmd=control.step({.525,0,0,now},pos,now,v,om);
    if(cmd.reached){done=true;break;}
    require(cmd.linear==0 || cmd.angular==0);
    v=cmd.linear;om=cmd.angular;pos.x+=v*std::cos(pos.yaw)*.05;pos.y+=v*std::sin(pos.yaw)*.05;pos.yaw+=om*.05;now+=.05;
   }
   require(done);require(std::abs(wrap(-pos.yaw-target))<=cfg.angle_tolerance);
  }
  off.target_angle=std::nan("");rejects([&]{off.validate();});
  off.target_angle=.25;rejects([&]{off.validate();});
 }
 std::cout<<"wall control assertions: "<<count<<" PASS (ideal model, not hardware)\n";
}
