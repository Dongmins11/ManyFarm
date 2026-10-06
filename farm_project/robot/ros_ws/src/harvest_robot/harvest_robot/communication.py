"""HarvestTask만 제공하는 통신 계층. 작업은 한 번에 하나만 수락합니다."""
from datetime import datetime, timezone
import uuid
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from farm_interfaces.action import HarvestTask
from .contract import validate_task, result_fields
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
            validate_task(goal, self.node.config)
        except (ValueError, AttributeError) as error:
            self.node.get_logger().warning('HarvestTask 거절: ' + str(error))
            return GoalResponse.REJECT
        with self.node.lock:
            if (self.node.busy or self.node.blocked or self.node.stopping
                    or goal.harvest_task.task_id in self.node.completed_ids):
                return GoalResponse.REJECT
            self.node.busy = True
        return GoalResponse.ACCEPT

    def feedback(self, handle) -> None:
        value = HarvestTask.Feedback()
        value.robot_id = handle.request.robot_id
        value.task_id = handle.request.harvest_task.task_id
        value.success_count = value.failed_count = 0
        value.timestamp = timestamp()
        handle.publish_feedback(value)

    def execute(self, handle):
        node, goal = self.node, handle.request
        node.active_goal = handle
        node.navigation_log = []
        controller = HarvestStateController(HarvestMission(node, goal))
        record = dict(event_id=uuid.uuid4().hex, robot_id=goal.robot_id, map_id=goal.map_id, task_id=goal.harvest_task.task_id, window_id=goal.harvest_task.window_id,
                      started_at=timestamp(), mode=node.mode, arm_operation='SKIPPED',
                      completion_policy='ARRIVAL_ONLY_NO_HARVEST',
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
            code, error_code = 'SUCCESS', 'NONE'
            self.feedback(handle)
            # 완료 직전 취소 요청도 완료로 덮어쓰지 않습니다.
            node.check()
            node.completed_ids.add(goal.harvest_task.task_id)
            handle.succeed()
        except MissionCanceled as error:
            error_message = str(error)
            if handle.is_cancel_requested and not node.blocked:
                code, error_code = 'CANCELED', 'NONE'
                handle.canceled()
            else:
                code, error_code = 'FAILED', 'SHUTDOWN'
                handle.abort()
        except Exception as error:
            code = 'FAILED'
            error_code = 'CANCEL_UNCONFIRMED' if node.blocked else 'NAVIGATION_FAILED'
            error_message = str(error)
            handle.abort()
        finally:
            controller.close()
            fields = result_fields(goal, code, error_code, error_message)
            fields['timestamp'] = timestamp()
            result = HarvestTask.Result()
            for name, value in fields.items(): setattr(result, name, value)
            record.update(result=fields, navigation=node.navigation_log)
            try:
                node.emit_record(record)
            except Exception as error:
                node.get_logger().error('작업 진단 이벤트 발행 실패: ' + str(error))
            with node.lock:
                node.active_goal = None
                node.busy = False
        return result
