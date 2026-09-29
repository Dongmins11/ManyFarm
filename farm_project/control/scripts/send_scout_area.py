#!/usr/bin/env python3
"""Temporary control client: request one or more survey sides, cancel own goal on Ctrl+C."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import signal
import time
import uuid
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.signals import SignalHandlerOptions
from rosidl_runtime_py.convert import message_to_ordereddict
from farm_interfaces.action import ScoutArea


def parse_args(argv=None):
    p=argparse.ArgumentParser()
    group=p.add_mutually_exclusive_group()
    group.add_argument('--section',nargs='+',action='extend',help='예찰할 구역. 입력한 순서로 실행합니다.')
    group.add_argument('--all',action='store_true',help='선택한 survey config의 모든 구역을 순서대로 실행합니다.')
    p.add_argument('--survey-config',type=Path,default=Path(__file__).resolve().parents[2]/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json')
    p.add_argument('--map-id',default='farm_map_v1')
    p.add_argument('--timeout',type=float,default=14400.,help='전체 작업 대기 제한(실제 시간 초), 기본 4시간')
    a=p.parse_args(argv)
    if a.all:
        try:a.section=list(json.loads(a.survey_config.expanduser().read_text())['sections'])
        except (OSError,ValueError,KeyError,TypeError) as exc:p.error(f'survey config 읽기 실패: {exc}')
    if a.section is None:a.section=['BED_01']
    if not a.section or len(set(a.section))!=len(a.section):p.error('구역은 중복 없이 하나 이상 지정하세요.')
    if not 0<a.timeout<float('inf'):p.error('--timeout은 양의 유한한 초 값이어야 합니다.')
    return a


def main():
    a=parse_args();rclpy.init(signal_handler_options=SignalHandlerOptions.NO);node=Node('test_scout_control')
    client=ActionClient(node,ScoutArea,'/scout_01/scout_area');stopped=[False];handle=None;pending=None;result_future=None
    path=Path(__file__).resolve().parents[2]/'runs/control'/('SCOUT_'+uuid.uuid4().hex[:12]+'.jsonl')
    path.parent.mkdir(parents=True,exist_ok=True)
    def log(kind,msg):
        obj={'kind':kind,'received_at':datetime.now(timezone.utc).isoformat(),'data':dict(message_to_ordereddict(msg))}
        with path.open('a') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n')
        if kind=='feedback':
            print(f'{msg.phase}: {msg.section_id} / segment={msg.segment_id or "-"} / segment_expected_count={msg.segment_expected_count} / completed_segments={msg.completed_segment_count} / tasks={len(msg.harvest_tasks)}',flush=True)
            if msg.phase=='SECTION_COMPLETE':print('  베드 완료: 전체 수확 작업 목록을 수신했습니다.',flush=True)
            for task in msg.harvest_tasks:print(f'  {task.window_id}: segment={task.segment_id}, fruits={task.expected_count}, goal=({task.goal_pose.position.x:.3f},{task.goal_pose.position.y:.3f}), yaw={task.goal_pose.yaw:.3f}',flush=True)
        else:print(json.dumps(obj,ensure_ascii=False,indent=2),flush=True)
    signal.signal(signal.SIGINT,lambda *_:stopped.__setitem__(0,True))
    def wait(future,timeout,allow_stop=True):
        end=time.monotonic()+timeout
        while not future.done() and time.monotonic()<end:
            rclpy.spin_once(node,timeout_sec=.1)
            if allow_stop and stopped[0]:raise KeyboardInterrupt
        if not future.done():raise RuntimeError('Action timeout')
        return future.result()
    try:
        if not client.wait_for_server(timeout_sec=10):raise RuntimeError('Start scout_survey.launch.py first')
        g=ScoutArea.Goal();g.robot_id='scout_01';g.task_id=path.stem;g.section_ids=a.section
        g.map_id=a.map_id;g.frame_id='map';g.crop_type='PAPRIKA';g.target_ripeness='RIPE';g.timestamp=datetime.now(timezone.utc).isoformat()
        log('goal',g);pending=client.send_goal_async(g,feedback_callback=lambda m:log('feedback',m.feedback))
        handle=wait(pending,15)
        if not handle.accepted:raise RuntimeError('Goal rejected; check section/map or running mission')
        result_future=handle.get_result_async();result=wait(result_future,a.timeout)
        log('result',result.result)
    except (KeyboardInterrupt,RuntimeError):
        if handle is None and pending is not None:handle=wait(pending,15,False)
        if handle and handle.accepted:
            wait(handle.cancel_goal_async(),15,False)
            result_future=result_future or handle.get_result_async()
            log('result',wait(result_future,35,False).result)
        else:raise
    finally:
        print(f'Control log: {path}');node.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
