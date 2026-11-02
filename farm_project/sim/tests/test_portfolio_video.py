"""실제 경과시간과 무관한 영상 길이 및 양면 베드 촬영 방향 검증."""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.portfolio_video import PortfolioVideo,frame_count


def test_timeline_is_fixed_simulation_duration():
    assert frame_count(0,15,30)==1
    assert frame_count(1,15,30)==16
    assert frame_count(29.94,15,30)==450
    assert frame_count(60,15,30)==450


def test_closeup_rotates_with_bed_side():
    capture=PortfolioVideo.__new__(PortfolioVideo)
    transform=np.eye(4)
    a,b,_=capture.view('harvest',dict(transform=transform),0)
    transform[:2,:2]=[[-1,0],[0,-1]]
    c,d,_=capture.view('harvest',dict(transform=transform),0)
    assert np.allclose(c[:2],-a[:2]) and np.allclose(d[:2],-b[:2])
    assert c[2]==a[2] and d[2]==b[2]


def test_four_distinct_travel_views_and_native_tag_source():
    capture=PortfolioVideo.__new__(PortfolioVideo)
    assert [capture.view_mode('travel_scout_01',i) for i in range(4)]==[
        'fixed_route_wide','low_oblique','fixed_route_long','follow_drone']
    assert capture.view_mode('apriltag_scout_01',0)=='sensor_original'
    capture.view_seed=1
    assert capture.view_mode('travel_scout_01',0)=='low_oblique'


def test_fixed_view_does_not_follow_robot():
    # 실제 갱신 함수에서 카메라 자세 호출 여부만 관측한다.
    capture=PortfolioVideo.__new__(PortfolioVideo)
    capture.duration=30
    capture.source_camera=type('Camera',(),{'get_current_frame':lambda self:dict(rendering_time=1.)})()
    capture._pose=lambda *a: (_ for _ in ()).throw(AssertionError('fixed camera moved'))
    evidence=dict(transform=np.eye(4).tolist())
    capture.candidates=lambda *a:{'travel_scout_01':evidence}
    capture.clip=dict(kind='travel_scout_01',index=0,view_mode='fixed_route_wide',
        last_render=1.,requested_sim_s=0.,start_sim_s=1.,evidence={},pose={'fixed':True})
    capture._update_video(1.,[],None,None)
    assert capture.clip['pose']=={'fixed':True}
