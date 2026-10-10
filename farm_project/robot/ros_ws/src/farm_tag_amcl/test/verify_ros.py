"""실제 AMCL 실행파일을 별도 ROS domain에서 검사한다. 모터·주행 명령 없음."""
import json,math,sys
import rclpy
from rclpy.parameter import Parameter
from rcl_interfaces.srv import SetParameters
from pathlib import Path
from ros_harness import Harness,OUTPUT

def run(executable: str) -> None:
 results=[]
 h=Harness(executable,'production')
 try:
  client=h.n.create_client(SetParameters,'/probe/amcl/set_parameters')
  assert client.wait_for_service(timeout_sec=3)
  future=client.call_async(SetParameters.Request(parameters=[Parameter('scan_topic',value='/wrong').to_parameter_msg()]))
  rclpy.spin_until_future_complete(h.n,future,timeout_sec=3)
  assert future.done() and not future.result().results[0].successful
  results.append('dynamic_scan_rewire_rejected_before_base_callback')
  h.clock(100.05);h.tf(100.05,.05);h.request(100.,1.)
  h.scan(100.1);assert not h.applied()
  h.clock(100.1);h.tf(100.1,.1);h.spin(.08)
  assert len(h.applied())==1,h.events
  e=h.applied()[0];assert abs(e['aligned_pose'][0]-1.1)<1e-8 and abs(e['odom_anchor'][0]-.1)<1e-8 and e['filter_initialized'],e
  results.append('delayed_TF_scan_aligned')
  h.clock(100.2);h.tf(100.2,.2);h.scan(100.2);h.spin(.08)
  assert abs(h.poses[-1].pose.pose.position.x-1.2)<1e-7,h.poses[-1]
  results.append('next_scan_motion_counted_once')
  h.request(100.,9.);assert h.events[-1]['kind']=='tag_correction_rejected';results.append('duplicate_source_rejected')
  h.request(101.,2.);assert h.events[-1]['kind']=='tag_correction_rejected';results.append('future_pose_rejected')
  h.request(99.,2.);assert h.events[-1]['kind']=='tag_correction_rejected';results.append('stale_pose_rejected')
  h.request(100.2,2.,robot_id='other');assert h.events[-1]['kind']=='tag_correction_rejected';results.append('wrong_robot_rejected')
  h.request(100.2,2.,map_id='wrong');assert h.events[-1]['kind']=='tag_correction_rejected';results.append('wrong_map_rejected')
  h.request(100.2,2.,token='other');assert h.events[-1]['kind']=='tag_correction_rejected';results.append('wrong_token_rejected')
  h.request(100.2,2.,producer_session='other');assert h.events[-1]['kind']=='tag_correction_rejected';results.append('producer_swap_rejected')
  cov=[0.]*36;cov[0]=-1.
  h.request(100.2,2.,covariance=cov);assert h.events[-1]['kind']=='tag_correction_rejected';results.append('invalid_covariance_rejected')
  h.clock(100.25);h.request(100.2,2.);h.control(False);h.tf(100.3,.3);h.scan(100.3)
  assert len(h.applied())==1 and any(e['reason']=='task_ended' for e in h.events);results.append('task_end_cancels_pending')
  h.control(True);h.request(100.25,2.);assert h.events[-1]['kind']=='tag_correction_rejected';results.append('closed_token_not_replayed')
  h.clock(100.35);h.new_task();h.tf(100.35,.35);h.request(100.35,2.);h.spin(.28)
  assert any(e['reason']=='scan_wait_timeout' for e in h.events);results.append('pending_timeout_no_apply')
  h.clock(100.4);h.tf(100.4,.4);h.request(100.4,2.);h.pinitial.publish(h.pose(100.4,3.));h.spin(.04)
  assert any(e['reason']=='manual_initialpose' for e in h.events);results.append('manual_pose_cancels_pending_and_token')
  h.clock(100.5);h.new_task();h.tf(100.5,.5);h.request(100.5,2.);h.transition(4);h.transition(3)
  h.clock(100.6);h.tf(100.6,.6);h.scan(100.6);assert len(h.applied())==1;results.append('deactivation_clears_pending')
  h.new_task();h.clock(100.7);h.tf(100.7,.7,0.,math.pi/2);h.request(100.7,2.,3.,0.)
  h.clock(100.8);h.tf(100.8,.7,.1,math.pi/2+.2);h.scan(100.8)
  e=h.applied()[-1];assert len(h.applied())==2 and max(abs(a-b) for a,b in zip(e['aligned_pose'],[2.1,3.,.2]))<1e-7,e
  results.append('rotated_SE2_transport')
  h.scan(100.75);assert len(h.applied())==2;results.append('out_of_order_scan_no_reapply')
  h.spin(2.1);h.clock(100.9);h.request(100.8,9.);assert h.events[-1]['kind']=='tag_correction_rejected';results.append('heartbeat_expiry_blocks_correction')
  h.new_task();h.clock(101.);h.tf(101.,1.);h.request(101.,3.);h.clock(99.)
  assert any(e['reason']=='clock_rewind' for e in h.events);results.append('clock_rewind_cancels_pending')
  h.new_task();h.request(99.,3.);h.pmap.publish(h.map_message);h.spin(.1)
  assert any(e['kind']=='tag_correction_dropped' and e['reason']=='map_received' for e in h.events)
  results.append('map_update_cancels_pending')
  h.clock(99.1);h.new_task();h.request(99.1,3.);h.transition(7)
  assert any(e['kind']=='tag_correction_dropped' and e['reason']=='shutdown' for e in h.events)
  results.append('shutdown_cancels_pending')
 finally:h.close()
 assert 'Failed to transform initial pose in time' not in h.log.read_text(),h.log.read_text()[-3000:]
 (OUTPUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 print(json.dumps(results,indent=2))
if __name__=='__main__':run(sys.argv[1])
