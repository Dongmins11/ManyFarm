// 복귀 속도 후보의 가감속·정수 RPM·3mm 외란 추종 시험. 실제 바닥 시험은 아니다.
#include "farm_arc_controller/arc_math.hpp"
#include <iostream>
using namespace farm_arc_controller;
int main(){int failed=0;
for(double speed:{.01,.03,.05,.054})for(double hz:{20.,30.})for(bool rpm:{false,true})for(double perturb:{0.,.003}){
 Pose start{0,0,0},now=start;double v=0,w=0,t=0,maxerr=0;bool done=false,injected=false;
 try{for(int i=0;i<4000;++i){
 auto goal=at(start,.2,M_PI_2);
 if(std::hypot(now.x-goal.x,now.y-goal.y)<=.005 && std::abs(wrap(now.yaw-goal.yaw))<=.04){done=true;break;}
 auto cmd=command(start,now,.2,M_PI_2,speed,.04,.01,.3);double dt=1/hz;
 v+=std::clamp(cmd.v-v,-1.8*dt,1.8*dt);w+=std::clamp(cmd.w-w,-2.*dt,2.*dt);
 double actual_v=v,actual_w=w;
 if(rpm){double unit=.0825*M_PI/30;auto l=std::round((v-w*.4288/2)/unit)*unit,r=std::round((v+w*.4288/2)/unit)*unit;actual_v=(l+r)/2;actual_w=(r-l)/.4288;}
 now.x+=actual_v*std::cos(now.yaw+actual_w*dt/2)*dt;now.y+=actual_v*std::sin(now.yaw+actual_w*dt/2)*dt;now.yaw=wrap(now.yaw+actual_w*dt);t+=dt;
 if(!injected && now.yaw>.5){now.x+=perturb;injected=true;}
 auto ideal=at(start,.2,wrap(now.yaw));maxerr=std::max(maxerr,std::hypot(now.x-ideal.x,now.y-ideal.y));
 }}catch(std::exception&e){std::cout<<e.what()<<" ";}
 std::cout<<"speed="<<speed<<" hz="<<hz<<" rpm="<<rpm<<" perturb="<<perturb<<" done="<<done<<" time="<<t<<" max_error="<<maxerr<<"\n";if(!done || maxerr>.01)++failed;
}
// 속도가 높아져도 기존 1cm 경로 이탈 보호를 유지한다.
bool rejected=false;
try{command({0,0,0},{.011,0,0},.2,M_PI_2,.05,.04,.01,.30);}
catch(const std::exception&){rejected=true;}
if(!rejected)++failed;
return failed?1:0;
}
