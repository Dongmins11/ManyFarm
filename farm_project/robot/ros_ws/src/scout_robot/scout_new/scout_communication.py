"""관제 통신만 담당합니다. State 전환이나 관측 순서를 여기서 실행하지 않습니다."""
from __future__ import annotations

from typing import TYPE_CHECKING

from farm_interfaces.action import ScoutArea
from farm_interfaces.msg import HarvestTask
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle

from .runtime import utc
from .scout_state_controller import ScoutStateController

if TYPE_CHECKING:
    from .scout_node import ScoutNode


class ScoutCommunication:
    def __init__(self, node: ScoutNode, controller: ScoutStateController) -> None:
        self._node: ScoutNode = node
        self._controller: ScoutStateController = controller
        self._server: ActionServer = ActionServer(
            node, ScoutArea, 'scout_area',
            execute_callback=self.execute,
            goal_callback=self.accept,
            cancel_callback=self.cancel,
            callback_group=node._cb,
        )

    def accept(self, goal: ScoutArea.Goal) -> GoalResponse:
        node = self._node
        logger = node.get_logger()
        logger.info(
            f'ScoutArea Goal 수신: task_id={goal.task_id!r}, '
            f'robot_id={goal.robot_id!r}, map_id={goal.map_id!r}, '
            f'frame_id={goal.frame_id!r}, section_ids={list(goal.section_ids)!r}, '
            f'crop_type={goal.crop_type!r}, target_ripeness={goal.target_ripeness!r}, '
            f'timestamp={goal.timestamp!r}'
        )
        # 수락 조건은 유지하고, 관제 값과 로봇 기대값의 차이를 모두 기록합니다.
        reasons: list[str] = []
        for field, expected in (
            ('robot_id', node._cfg['robot_id']),
            ('map_id', node._cfg['map_id']),
            ('frame_id', 'map'),
            ('crop_type', 'PAPRIKA'),
            ('target_ripeness', 'RIPE'),
        ):
            received = getattr(goal, field)
            if received != expected:
                reasons.append(f'{field} 불일치: received={received!r}, expected={expected!r}')
        if not goal.task_id:
            reasons.append('task_id가 비어 있음')
        if not goal.section_ids:
            reasons.append('section_ids가 비어 있음')
        if len(set(goal.section_ids)) != len(goal.section_ids):
            reasons.append('section_ids에 중복된 구역이 있음')
        unknown_sections = [section for section in goal.section_ids if section not in node._beds]
        if unknown_sections:
            reasons.append(
                f'등록되지 않은 구역: received={unknown_sections!r}, '
                f'available={list(node._beds)!r}'
            )
        if node._readiness_error:
            reasons.append(f'준비 오류: {node._readiness_error}')
        vision = getattr(node, '_vision', None)
        if vision is not None and vision.readiness_error:
            reasons.append(vision.readiness_error)
        with node._lock:
            if node._busy:
                reasons.append('_busy=True: 기존 미션 실행 중')
            if node._shutdown_requested:
                reasons.append('_shutdown_requested=True: 종료 처리 중')
            if node._motion_uncertain:
                reasons.append('_motion_uncertain=True: 주행 정지 상태 확인 필요')
            if reasons:
                logger.warning(f'ScoutArea Goal REJECT: task_id={goal.task_id!r}; ' + '; '.join(reasons))
                return GoalResponse.REJECT
            node._busy = True  # 실행 콜백 이전부터 미션 한 건을 예약합니다.
        logger.info(f'ScoutArea Goal ACCEPT: task_id={goal.task_id!r}')
        return GoalResponse.ACCEPT

    def cancel(self, goal: ServerGoalHandle) -> CancelResponse:
        # 정리를 시작한 뒤 추가 취소를 승인하여 SUCCESS/CANCELED가 엇갈리지 않게 합니다.
        if self._controller.finishing:
            return CancelResponse.REJECT
        return CancelResponse.ACCEPT

    def execute(self, goal: ServerGoalHandle) -> ScoutArea.Result:
        """ROS execute 콜백은 전체 결과만 기다립니다. 상태 실행은 별도 타이머가 담당합니다."""
        try:
            result = self._controller.start(goal).result()
            if result.result_code == 'SUCCESS':
                goal.succeed()
            elif goal.is_cancel_requested:
                goal.canceled()
            else:
                goal.abort()
            return result
        except Exception as error:
            self._node._motion_uncertain = True
            result = ScoutArea.Result()
            result.robot_id = goal.request.robot_id
            result.task_id = goal.request.task_id
            result.result_code = 'FAILED'
            result.error_code = 'STATE_CONTROLLER_FAILED'
            result.error_message = str(error)
            result.timestamp = utc()
            if goal.is_cancel_requested:
                goal.canceled()
            else:
                goal.abort()
            return result
        finally:
            self._node._active_goal = None
            with self._node._lock:
                self._node._busy = False

    def feedback(
        self, goal: ServerGoalHandle, section: str, phase: str,
        tasks: list[HarvestTask], completed: int, segments: int,
        segment_id: str, segment_expected_count: int,
    ) -> None:
        feedback = ScoutArea.Feedback()
        feedback.robot_id = goal.request.robot_id
        feedback.task_id = goal.request.task_id
        feedback.phase = phase
        feedback.section_id = section
        feedback.segment_id = segment_id
        feedback.completed_section_count = completed
        feedback.completed_segment_count = segments
        feedback.segment_expected_count = segment_expected_count
        feedback.harvest_tasks = tasks
        feedback.timestamp = utc()
        goal.publish_feedback(feedback)

    def close(self) -> None:
        self._server.destroy()
