#!/usr/bin/env python3
"""Temporary manual test: existing 42 approach -> operator readiness -> 41 dock."""
import argparse
import time
import uuid

def completed(status,result):
    return status==4 and result.success and result.stopped

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Print plan without sending any goal')
    args=parser.parse_args()
    if args.check:
        print('현재 위치 → harvest_approach_42 DOCK → 정지 확인 → Enter로 41번 준비 확인 → harvest_dock_41 DOCK → 종료')
        print('Nav2 경로주행, transfer_event, 펌웨어, 도킹해제는 실행하지 않습니다.')
        return
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.signals import SignalHandlerOptions
    from farm_interfaces.action import PrecisionMotion
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node=rclpy.create_node('harvest_approach_dock_test_'+uuid.uuid4().hex[:8])
    client=ActionClient(node,PrecisionMotion,'/transport_01/precision_motion')
    active=None;result_future=None;send_future=None
    def wait(future,seconds=None):
        end=None if seconds is None else time.monotonic()+seconds
        while rclpy.ok() and not future.done():
            if end is not None and time.monotonic()>=end:raise TimeoutError('응답 대기 시간 초과')
            rclpy.spin_once(node,timeout_sec=.1)
        return future.result()
    try:
        if not client.wait_for_server(timeout_sec=10.):raise RuntimeError('precision_motion 서버 연결 안 됨')
        for profile,marker in [('harvest_approach_42',42),('harvest_dock_41',41)]:
            if marker==41:
                input('42 접근 완료·정지 확인. 수확로봇의 41번 확인 면이 준비되면 Enter (취소: Ctrl+C): ')
            goal=PrecisionMotion.Goal();goal.session_id='harvest_test_'+uuid.uuid4().hex
            goal.profile_id=profile;goal.operation='DOCK';goal.target_marker_id=marker;goal.docking_marker_id=marker
            print('START:',profile,flush=True)
            result_future=None
            send_future=client.send_goal_async(goal,feedback_callback=lambda msg:print('phase:',msg.feedback.phase,flush=True))
            active=wait(send_future)
            if not active.accepted:raise RuntimeError('Goal 거절: '+profile)
            result_future=active.get_result_async();response=wait(result_future)
            active=None;send_future=None
            print('RESULT:',response.status,response.result,flush=True)
            if not completed(response.status,response.result):raise RuntimeError('실패 또는 정지 미확인. 다음 단계는 실행하지 않습니다.')
        print('완료: 접근 + 라이다 도킹. 추가 동작 없음.',flush=True)
    finally:
        # Even if interrupted while sending, resolve acceptance before cancelling.
        if active is None and send_future is not None:
            try:active=wait(send_future,5.)
            except Exception as exc:print('Goal 수락 여부 확인 실패:',exc,flush=True)
        if active is not None and active.accepted:
            try:
                wait(active.cancel_goal_async(),5.)
                if result_future is None:result_future=active.get_result_async()
                response=wait(result_future,10.)
                print('취소 후 결과:',response.status,response.result,flush=True)
            except Exception as exc:print('정지 결과 확인 실패:',exc,flush=True)
        node.destroy_node();rclpy.shutdown()

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('사용자가 테스트를 취소했습니다.');raise SystemExit(130)
    except Exception as exc:print('TEST FAILED:',exc);raise SystemExit(1)
