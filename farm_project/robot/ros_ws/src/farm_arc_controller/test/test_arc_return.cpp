#include "farm_arc_controller/arc_math.hpp"
#include <limits>
#include <iostream>
#include <cstdlib>
using namespace farm_arc_controller;
int checks=0;
void require(bool ok){++checks;if(!ok){std::cerr<<"check failed "<<checks<<'\n';std::exit(1);}}
template<class F> void rejects(F f){bool failed=false;try{f();}catch(const std::runtime_error &){failed=true;}require(failed);}
std::vector<Pose> sampled(Pose start,double radius,double angle){
  std::vector<Pose> p;for(int i=0;i<=80;++i)p.push_back(at(start,radius,angle*i/80));return p;
}
int main(){
  int simulations=0;
  for(double yaw:{-3.13,-1.5,0.,1.5,3.13})
  for(double radius:{.1,.15,.2})
  for(double angle:{M_PI/4,M_PI_2}){
    const Pose start{1.2,-2.2,yaw};
    auto forward=sampled(start,radius,angle),inverse=forward;
    std::reverse(inverse.begin(),inverse.end());
    for(const auto & path:{forward,inverse}){
      const auto arc=validate_path(path);const double sign=arc.angle>0?1.:-1.;
      require(std::abs(arc.radius-radius)<1e-12);
      auto now=path.front();bool done=false;
      for(int i=0;i<4000;++i){
        const auto end=path.back();
        if(std::hypot(now.x-end.x,now.y-end.y)<=.008 && std::abs(wrap(now.yaw-end.yaw))<=M_PI/180){done=true;break;}
        auto c=command(arc.start,now,arc.radius,arc.angle,.01,.04,.01,.15);
        require(c.v*sign<0 && c.w*sign>0 && std::abs(c.v)<=.01+1e-12 && std::abs(c.w)<=.15+1e-12);
        const double unit=.0825*M_PI/30;
        const double vl=std::round((c.v-c.w*.4288/2)/unit)*unit;
        const double vr=std::round((c.v+c.w*.4288/2)/unit)*unit;
        const double v=(vl+vr)/2,w=(vr-vl)/.4288,dt=1./30;
        now.x+=v*std::cos(now.yaw+w*dt/2)*dt;
        now.y+=v*std::sin(now.yaw+w*dt/2)*dt;now.yaw=wrap(now.yaw+w*dt);
      }
      require(done);++simulations;
      auto damaged=path;damaged[40].x+=.02;rejects([&]{validate_path(damaged);});
      damaged=path;std::swap(damaged[30],damaged[50]);rejects([&]{validate_path(damaged);});
      damaged=path;damaged[40].yaw=std::numeric_limits<double>::quiet_NaN();rejects([&]{validate_path(damaged);});
      rejects([&]{command(arc.start,{arc.start.x+.05,arc.start.y,arc.start.yaw},radius,arc.angle,.01,.04,.01,.15);});
      auto limited=command(arc.start,arc.start,radius,arc.angle,.01,.04,.01,.02);
      require(std::abs(std::abs(limited.w)-.02)<1e-12);
    }
  }
  rejects([]{validate_path({});});
  rejects([]{validate_path(sampled({0,0,0},.1,0));});
  rejects([]{validate_path(sampled({0,0,0},.1,2));});
  rejects([]{validate_path(sampled({0,0,0},.04,1));});
  rejects([]{validate_path(sampled({0,0,0},.31,-1));});
  std::cout<<"PASS: "<<simulations<<" bidirectional quantized ideal trajectories; "<<checks<<" assertions (not hardware)\n";
}
