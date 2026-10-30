// 스테이션 선택 모드의 후진 폐루프·정지·관측 만료 검사. 운영 허용치 확정이 아니다.
#include "farm_wall_controller/wall_control.hpp"
#include <iostream>
using namespace farm_wall_controller;
void require(bool ok){if(!ok)throw std::runtime_error("station docking assertion");}
int main(){
 Config c;c.target=.52;c.station_docking=true;c.max_linear=.02;c.max_angular=.05;
 c.timeout=120;c.distance_tolerance=.005;c.lateral_tolerance=.005;c.angle_tolerance=.0174533;
 int cases=0;
 // 좌우 양쪽·초기 방향 오차 및 관측 흔들림을 함께 재현한다.
 for(double depth:{.04,.09,.15})for(double y:{-.04,-.02,0.,.02,.04})
 for(double yaw:{-.174533,0.,.174533})for(bool noise:{false,true}){
  Control control(c);Pose p{depth,y,yaw};Command cmd;bool done=false;
  for(int i=1;i<=2400;i++){
   double t=i*.05,n=noise?.0005*std::sin(i*.3):0.;
   cmd=control.step({n,n,noise?.002*std::sin(i*.2):0.,t},p,t,cmd.linear,cmd.angular);
   require(cmd.linear<=0 && std::abs(cmd.linear)<=c.max_linear+1e-12 && std::abs(cmd.angular)<=c.max_angular+1e-12);
   if(cmd.reached){done=true;break;}
   p.x+=cmd.linear*std::cos(p.yaw)*.05;p.y+=cmd.linear*std::sin(p.yaw)*.05;p.yaw+=cmd.angular*.05;
  }
  require(done);require(std::abs(p.x)<=.0056 && std::abs(p.y)<=.0056 && std::abs(wrap(p.yaw))<=.020);
  ++cases;
 }
 Control q(c);auto a=q.step({0,0,0,1},{0,0,0},1,.01,0);require(!a.reached);
 for(int i=1;i<9;i++)a=q.step({0,0,0,1+i*.1},{0,0,0},1+i*.1,.01,0);
 require(!a.reached);q.reset();
 for(int i=0;i<9;i++)a=q.step({0,0,0,3+i*.1},{0,0,0},3+i*.1,0,0);
 require(a.reached);q.reset();require(!q.step({0,0,0,5},{0,0,0},5,0,0).reached);
 // 뒤 거리만 맞고 횡오차가 남으면 성공할 수 없다.
 q.reset();require(!q.step({0,0,0,10},{0,.02,0},10,0,0).reached);
 Config waiting=c;waiting.wait_until_fresh=true;Control w(waiting);
 w.step({0,0,0,20},{.09,0,0},20,0,0);
 a=w.step({0,0,0,20},{.09,0,0},21,0,0);require(a.linear==0&&a.angular==0&&!a.reached);
 bool rejected=false;try{w.step({NAN,0,0,22},{0,0,0},22,0,0);}catch(...){rejected=true;}require(rejected);
 std::cout<<cases<<" station closed-loop cases + completion/freshness passed\n";
}
