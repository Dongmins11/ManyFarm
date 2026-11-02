"""로봇 업무와 독립적인 공통 Action/구동 제어권 클라이언트."""
from farm_navigation.operation_clock import operation_time
import time
from threading import Lock, RLock, Thread
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
from rclpy.action import ActionClient
from farm_interfaces.action import PrecisionMotion
from farm_interfaces.srv import MotionLease

def wait(future, seconds=5., *, clock=time.monotonic):
    deadline=clock()+seconds
    while not future.done():
        if clock()>deadline:raise TimeoutError('ROS 응답 시간 초과')
        time.sleep(.01)
    return future.result()

def accepted_goal(client, goal, *, clock=time.monotonic):
    future=client.send_goal_async(goal)
    try:return wait(future, clock=clock)
    except TimeoutError:
        # 접수 응답이 늦어도 원격 작업을 방치하지 않는다.
        def cancel_late(done):
            try:
                handle=done.result()
                if handle.accepted:handle.cancel_goal_async()
            except Exception:pass
        future.add_done_callback(cancel_late)
        raise

class LeaseClient:
    def __init__(self,node,group,owner):
        self.io_node=Node(owner+'_lease_io', namespace=node.get_namespace(), context=node.context, use_global_arguments=False)
        self.executor=SingleThreadedExecutor(context=node.context)
        self.executor.add_node(self.io_node)
        self.client=self.io_node.create_client(MotionLease,'motion/lease')
        self.owner,self.token,self.failed=owner,'',False
        self.pending=None
        self.node=node;self.last_renew=None;self.last_error='';self.pending_at=0.;self.diag_at=0.
        self.lock=Lock()
        self.timer=self.io_node.create_timer(.15,self.renew,clock=node.get_clock())
        self.thread=Thread(target=self._spin,name=owner+'_lease_io',daemon=True)
        self.thread.start()
    def _spin(self):
        try:self.executor.spin()
        except ExternalShutdownException:pass
    def close(self):
        self.timer.cancel()
        self.executor.shutdown(timeout_sec=2.)
        self.thread.join(timeout=2.)
        self.io_node.destroy_node()
    def call(self,token='',release=False):
        q=MotionLease.Request();q.owner=self.owner;q.token=token;q.release=release
        started=time.monotonic()
        future=self.client.call_async(q)
        def report(done):
            try:
                r=done.result();dt=time.monotonic()-started
                if not r.accepted or dt>.1:
                    self.node.get_logger().warning(f'Lease response: owner={self.owner} renew={bool(token)} release={release} latency={dt:.3f}s accepted={r.accepted} reason={r.error_message}')
            except Exception as exc:self.node.get_logger().error(f'Lease response exception: {exc!r}')
        future.add_done_callback(report)
        return future
    def acquire(self):
        deadline=operation_time(self.node)+2.
        while not self.client.service_is_ready():
            if operation_time(self.node)>=deadline:raise RuntimeError('motion gate 미연결')
            time.sleep(.01)
        with self.lock:
            result=wait(self.call(),clock=lambda: operation_time(self.node))
            if not result.accepted:raise RuntimeError(result.error_message)
            self.pending=None
            self.token,self.failed=result.token,False
            self.last_error='';self.last_renew=None
    def renew(self):
        # Never block the lease executor while acquire waits for its response.
        if not self.lock.acquire(blocking=False):return
        try:
            if not self.token:return
            now=operation_time(self.node)
            gap=now-self.last_renew if self.last_renew is not None else 0.
            self.last_renew=now
            if gap>.25:self.node.get_logger().warning(f'Lease timer delayed: owner={self.owner} gap={gap:.3f}s')
            if now-self.diag_at>2.:
                self.diag_at=now
                self.node.get_logger().info(f'Lease timing: owner={self.owner} timer_gap={gap:.3f}s pending_age={(now-self.pending_at) if self.pending else 0.:.3f}s failed={self.failed}')
            if self.pending:
                if not self.pending.done():return
                try:
                    if not self.pending.result().accepted:
                        self.failed=True;self.last_error=self.pending.result().error_message
                except Exception as exc:self.failed=True;self.last_error=repr(exc)
                self.pending=None
            if not self.failed:self.pending_at=operation_time(self.node);self.pending=self.call(self.token)
        finally:self.lock.release()
    def check(self):
        if self.failed or not self.token:raise RuntimeError('모터 제어권 상실: '+self.last_error)
    def release(self):
        with self.lock:
            token,self.token=self.token,''
            self.pending=None
        if token:
            result=wait(self.call(token,True),2.,clock=lambda: operation_time(self.node))
            if not result.accepted:raise RuntimeError('제어권 해제 확인 실패')

class ExclusiveNavigator:
    def __init__(self,navigator,lease):self.navigator,self.lease=navigator,lease
    def preflight_navigation(self):return self.navigator.preflight_navigation()
    def plan(self,xy):return self.navigator.plan(xy)
    def navigate(self,xy,yaw,**options):
        self.lease.acquire()
        try:return self.navigator.navigate(xy,yaw,**options)
        finally:self.lease.release()
    def cancel_nav(self):return self.navigator.cancel_nav()

class PrecisionClient:
    def __init__(self,node,group,check,timeout=120.):
        self.client=ActionClient(node,PrecisionMotion,'precision_motion',callback_group=group)
        self.node=node
        self.check,self.timeout=check,timeout
        self.handle=None
        self.pre_entry_stopped=False
        self.result_future=None
        self._goal_lock=RLock()
        self._accept_future=None
        self._late_error=''
    @property
    def pending(self):
        with self._goal_lock:return self.handle is not None or self._accept_future is not None
    def available(self):return not self.pending and self.client.server_is_ready()

    def _accept(self, goal):
        with self._goal_lock:
            if self.pending:raise RuntimeError('이전 정밀주행 종료 미확인')
            future=self.client.send_goal_async(goal)
            self._accept_future=future
            self._late_error=''
        try:
            handle=wait(future,clock=lambda: operation_time(self.node))
        except BaseException:
            # 응답을 기다리던 작업은 실패하더라도 접수 Future의 소유권은 유지한다.
            # 콜백에서는 기다리지 않아 ROS 결과/취소 응답 처리를 막지 않는다.
            future.add_done_callback(self._cancel_late)
            raise
        with self._goal_lock:
            self.handle=handle if handle.accepted else None
            self.result_future=None
            self._accept_future=None
        return handle

    def _cancel_late(self, future):
        with self._goal_lock:
            if self._accept_future is not future:return
            try:
                handle=future.result()
                if not handle.accepted:
                    self._accept_future=None
                    return
                self.handle=handle
                self._accept_future=None
            except Exception as exc:
                self._late_error=str(exc)
                return
            # 결과 구독 오류가 취소 요청을 막지 않도록 각각 수행한다.
            try:handle.cancel_goal_async()
            except Exception as exc:self._late_error=str(exc)
            try:
                self.result_future=handle.get_result_async()
                self.result_future.add_done_callback(lambda done:self._late_finished(handle,done))
            except Exception as exc:
                self._late_error=str(exc)  # 종료 미확인 참조를 유지해 stop에서 재확인한다.

    def _late_finished(self, handle, future):
        with self._goal_lock:
            if self.handle is not handle:return
            try:
                result=future.result()
                if result.status in (4,5,6) and result.result.stopped:
                    self.handle=None;self.result_future=None
                else:self._late_error='늦은 정밀주행 종료/정지 미확인'
            except Exception as exc:self._late_error=str(exc)

    def run(self,request,operation):
        if self.pending:raise RuntimeError('이전 정밀주행 종료 미확인')
        self.pre_entry_stopped=False
        deadline=operation_time(self.node)+2.
        while not self.client.server_is_ready():
            self.check()
            if operation_time(self.node)>=deadline:raise RuntimeError('정밀주행 서버 없음')
            time.sleep(.01)
        q=PrecisionMotion.Goal();q.session_id=request.task_id;q.profile_id=request.profile_id;q.operation=operation
        q.target_marker_id=request.target_marker_id;q.docking_marker_id=request.docking_marker_id
        q.clearance_pose.frame_id='map'
        xy=request.clearance_xy or request.xy
        q.clearance_pose.position.x=float(xy[0]);q.clearance_pose.position.y=float(xy[1])
        q.clearance_pose.yaw=float(request.clearance_yaw if request.clearance_yaw is not None else request.yaw)
        # 접수 결과를 확정한 뒤 취소한다. 늦게 접수된 Goal을 버리지 않는다.
        handle=self._accept(q)
        if not handle.accepted:raise RuntimeError('정밀주행 Goal 거절')
        self.result_future=None
        try:
            self.result_future=self.handle.get_result_async()
            future=self.result_future;deadline=operation_time(self.node)+self.timeout
            while not future.done():
                self.check()
                if operation_time(self.node)>deadline:raise TimeoutError('정밀주행 제한시간 초과')
                time.sleep(.02)
            result=future.result()
            self.check()
            from .initial_marker_recovery import ApproachReentryRequired
            if (operation=='DOCK' and result.status==6 and result.result.stopped
                    and not result.result.success
                    and result.result.error_message.startswith(ApproachReentryRequired.prefix)):
                raise ApproachReentryRequired(result.result.error_message)
            self.pre_entry_stopped=bool(operation=='DOCK' and result.result.stopped
                and not result.result.success and result.result.error_message.startswith('PRE_ENTRY_STOPPED: '))
            if result.status!=4 or not result.result.success or not result.result.stopped:
                raise RuntimeError(result.result.error_message or '정밀주행/정지 실패')
            self.handle=None;self.result_future=None
            return True
        except BaseException as exc:
            try:self.stop()
            except Exception as stop_exc:
                raise RuntimeError(f'{exc}; 정밀주행 종료 미확인: {stop_exc}') from exc
            raise
    def tag(self,request):return self.run(request,'TAG')
    def dock(self,request):return self.run(request,'DOCK')
    def clear(self,request):return self.run(request,'CLEAR')
    def stop(self, *, stationary_confirmed=None):
        with self._goal_lock:
            if self._accept_future is not None:
                raise RuntimeError('정밀주행 접수 응답 대기 중: 응답 시 자동 취소'+(': '+self._late_error if self._late_error else ''))
            handle=self.handle
            if handle is None:return
            if self.result_future is None:self.result_future=handle.get_result_async()
            future=self.result_future
        # 콜백과 독립적으로 결과를 기다린다. 취소 응답 유실도 종료 결과로 확인한다.
        if not future.done():
            try:wait(handle.cancel_goal_async(),3.,clock=lambda: operation_time(self.node))
            except Exception:pass
        result=wait(future,5.,clock=lambda: operation_time(self.node))
        measured_stop = bool(stationary_confirmed and stationary_confirmed())
        if result.status not in (4,5,6) or not (result.result.stopped or measured_stop):
            raise RuntimeError('정밀주행 종료/정지 확인 실패')
        with self._goal_lock:
            if self.handle is handle:self.handle=None;self.result_future=None
