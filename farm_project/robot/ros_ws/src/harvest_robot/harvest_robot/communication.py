"""수확 작업 통신. 복귀와의 소유권 교체는 공통 handoff에 위임한다."""
from datetime import datetime, timezone
import uuid
from typing import Any
from farm_common.action_handoff import ActionInterrupted
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from farm_interfaces.action import HarvestTask
from .contract import validate_task, result_fields, validate_counts
from .arm_client import ArmExecutionError
from .mission import HarvestMission, MissionCanceled
from .state_controller import HarvestStateController


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class HarvestCommunication:
    def __init__(self, node) -> None:
        self.node = node
        self.server = ActionServer(node, HarvestTask, 'harvest_task', execute_callback=self.execute,
            goal_callback=self.accept, cancel_callback=lambda _: CancelResponse.ACCEPT,
            callback_group=node.callbacks)

    def accept(self, goal):
        try:
            validate_task(goal, self.node.config, getattr(self.node, 'section_resolution', None))
        except (ValueError, AttributeError) as error:
            self.node.get_logger().warning('HarvestTask 거절: ' + str(error))
            return GoalResponse.REJECT
        with self.node.lock:
            if (self.node.busy or self.node.blocked or self.node.stopping
                    or goal.harvest_task.task_id in self.node.completed_ids):
                return GoalResponse.REJECT
            if not self.node.handoff.reserve('work', goal.harvest_task.task_id):
                return GoalResponse.REJECT
            self.node.busy = True
        return GoalResponse.ACCEPT

    def feedback(self, handle) -> None:
        value = HarvestTask.Feedback()
        value.robot_id = handle.request.robot_id
        value.task_id = handle.request.harvest_task.task_id
        value.success_count, value.failed_count = getattr(self.node, 'arm_counts', (0, 0))
        value.timestamp = timestamp()
        handle.publish_feedback(value)

    def arm_feedback(self, success: int, failed: int) -> None:
        """장치가 확정한 수량만 전달합니다. 예상값·도착·접촉으로 성과를 계산하지 않습니다."""
        with self.node.lock:
            counts = validate_counts(success, failed, self.node.arm_counts)
            self.node.harvest_load.observe(success, failed)
            self.node.arm_counts = counts
            handle = self.node.active_goal
        transfer = getattr(self.node, 'transfer', None)
        if transfer is not None:
            transfer.update_harvest_load()
        if handle is not None:
            self.feedback(handle)

    def execute(self, handle: Any) -> Any:
        node, task_id = self.node, handle.request.harvest_task.task_id
        try:
            def check() -> None:
                if handle.is_cancel_requested or node.stopping:
                    raise ActionInterrupted('수확 작업 시작 전 취소/종료')
                if node.blocked:
                    raise RuntimeError('이전 동작 정지 미확인')
            node.handoff.acquire('work', task_id, check)
        except Exception as error:
            code = 'CANCELED' if isinstance(error, ActionInterrupted) else 'FAILED'
            result = HarvestTask.Result()
            fields = result_fields(handle.request, code, 'NONE' if code == 'CANCELED' else 'CANCEL_UNCONFIRMED', str(error))
            fields['timestamp'] = timestamp()
            for name, value in fields.items():
                setattr(result, name, value)
            if handle.is_cancel_requested:
                handle.canceled()
            else:
                handle.abort()
            with node.lock:
                node.busy = False
            node.handoff.release('work', task_id)
            return result
        try:
            return self._execute_work(handle)
        finally:
            node.handoff.release('work', task_id)

    def _execute_work(self, handle: Any) -> Any:
        node, goal = self.node, handle.request
        runtime = getattr(node, 'handoff_runtime', None)
        if runtime is not None:
            runtime.invalidate_window()
        node.active_goal = handle
        node.navigation_log = []
        node.arm_counts = (0, 0)
        with node.lock:
            node.harvest_load.begin()
        node.arm_result = node.arrival_result = None
        node.mission_stage = 'NAVIGATION'
        controller = HarvestStateController(HarvestMission(node, goal))
        record = dict(event_id=uuid.uuid4().hex, robot_id=goal.robot_id, map_id=goal.map_id, task_id=goal.harvest_task.task_id, window_id=goal.harvest_task.window_id,
                      started_at=timestamp(), mode=node.mode, arm_operation='SKIPPED',
                      completion_policy=getattr(node, 'config', {}).get('completion_policy', 'ARRIVAL_ONLY_NO_HARVEST'),
                      goal_pose=dict(x=goal.harvest_task.goal_pose.position.x,
                                     y=goal.harvest_task.goal_pose.position.y,
                                     yaw=goal.harvest_task.goal_pose.yaw))
        code, error_code, error_message = 'FAILED', 'INTERNAL_ERROR', ''
        try:
            self.feedback(handle)
            controller.start()
            controller.done.wait()
            if controller.error is not None:
                raise controller.error
            node.check()
            record['arrival'] = controller.outcome
            if node.arm_result is None:
                code, error_code = 'SUCCESS', 'NONE'
            else:
                code = node.arm_result['result_code']
                error_code, error_message = node.arm_result['error_code'], node.arm_result['error_message']
                record['arm_operation'] = 'EXECUTED'
            self.feedback(handle)
            # 완료 직전 취소 요청도 완료로 덮어쓰지 않습니다.
            node.check()
            if code == 'SUCCESS':
                if runtime is not None:
                    runtime.remember_window(goal, controller.outcome)
                node.completed_ids.add(goal.harvest_task.task_id)
                handle.succeed()
            else:
                # 외부 Goal 취소가 없는데 내부만 취소된 경우 ROS 취소 상태로 위장하지 않습니다.
                if code == 'CANCELED':
                    code, error_code = 'FAILED', 'ARM_CANCELED'
                handle.abort()
        except MissionCanceled as error:
            error_message = str(error)
            if (handle.is_cancel_requested or node.handoff.work_interrupted) and not node.blocked:
                code, error_code = 'CANCELED', 'NONE'
                if handle.is_cancel_requested:
                    handle.canceled()
                else:
                    handle.abort()
            else:
                code, error_code = 'FAILED', 'SHUTDOWN'
                handle.abort()
        except Exception as error:
            code = 'FAILED'
            error_code = ('CANCEL_UNCONFIRMED' if node.blocked else
                          error.code if isinstance(error, ArmExecutionError) else
                          'ARM_EXECUTION_FAILED' if node.mission_stage == 'ARM' else 'NAVIGATION_FAILED')
            error_message = str(error)
            handle.abort()
        finally:
            controller.close()
            if runtime is not None and code != 'SUCCESS':
                runtime.invalidate_window()
            fields = result_fields(goal, code, error_code, error_message,
                harvested_count=node.arm_counts[0], failed_count=node.arm_counts[1])
            fields['timestamp'] = timestamp()
            result = HarvestTask.Result()
            for name, value in fields.items(): setattr(result, name, value)
            record.update(result=fields, navigation=node.navigation_log)
            if node.arrival_result is not None:
                record['arrival'] = node.arrival_result
            if node.arm_result is not None:
                record['arm_operation'] = 'EXECUTED'
                record['arm_result'] = node.arm_result
            record['final_stage'] = node.mission_stage
            try:
                node.emit_record(record)
            except Exception as error:
                node.get_logger().error('작업 진단 이벤트 발행 실패: ' + str(error))
            with node.lock:
                node.harvest_load.end()
                # 결과 수량/취소 상태는 보존하되 접힘 미확인 상태에서 다음 이동을 받지 않는다.
                if not getattr(node, 'arm_travel_ready', True):
                    node.blocked = True
                node.active_goal = None
                node.busy = False
        return result
