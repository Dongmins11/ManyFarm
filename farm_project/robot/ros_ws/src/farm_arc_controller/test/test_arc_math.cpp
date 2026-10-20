#include "farm_arc_controller/arc_math.hpp"
#include <iostream>
#include <cstdlib>
using namespace farm_arc_controller;
void require(bool ok,const char * message){if(!ok){std::cerr<<message<<'\n';std::exit(1);}}
int main(){
  Pose start{1.2,-2.2,-1.5};const auto end=at(start,.1,M_PI_2);
  auto c=command(start,start,.1,M_PI_2,.01,.04,.01,.15);
  require(std::abs(c.v+.01)<1e-9 && std::abs(c.w-.1)<1e-9,"initial curvature");
  for(double radius:{.1,.15,.2}){
    auto now=start;bool done=false;double max_error=0;
    for(int i=0;i<1800;i++){
      const auto target=at(start,radius,M_PI_2);
      if(std::hypot(now.x-target.x,now.y-target.y)<=.005 && std::abs(wrap(now.yaw-target.yaw))<=.04){done=true;break;}
      c=command(start,now,radius,M_PI_2,.01,.04,.01,.15);
      // 첨부 드라이버와 같은 정수 RPM 명령을 이상적 차동 구동에 적용한다.
      const double unit=.0825*M_PI/30;
      const double vl=std::round((c.v-c.w*.4288/2)/unit)*unit;
      const double vr=std::round((c.v+c.w*.4288/2)/unit)*unit;
      const double v=(vl+vr)/2,w=(vr-vl)/.4288,dt=1.0/30;
      now.x+=v*std::cos(now.yaw+w*dt/2)*dt;now.y+=v*std::sin(now.yaw+w*dt/2)*dt;now.yaw=wrap(now.yaw+w*dt);
      const auto expected=at(start,radius,wrap(now.yaw-start.yaw));
      max_error=std::max(max_error,std::hypot(now.x-expected.x,now.y-expected.y));
    }
    require(done,"quantized trajectory failed");
    std::cout<<"radius="<<radius<<" max_ideal_error="<<max_error<<" PASS\n";
  }
  bool rejected=false;try{command(start,{start.x+.02,start.y,start.yaw},.1,M_PI_2,.01,.04,.01,.15);}catch(...){rejected=true;}
  require(rejected,"deviation must reject");
  rejected=false;try{command(start,{start.x,start.y,start.yaw-.1},.1,M_PI_2,.01,.04,.01,.15);}catch(...){rejected=true;}
  require(rejected,"wrong direction must reject");
  (void)end;std::cout<<"arc math checks PASS\n";
}
