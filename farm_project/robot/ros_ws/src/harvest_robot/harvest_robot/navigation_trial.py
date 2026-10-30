"""실물 시험 목표까지 팔 없이 이동한다. 기존 작업 주행과 소유권을 재사용한다."""
from __future__ import annotations

import json
import math
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from farm_common.action_handoff import ActionInterrupted
from farm_navigation.route import RouteGraph
from farm_navigation.configuration import resolve_file
from .contract import resolve_section
from .mission import MissionCanceled
from .state_controller import HarvestStateController


def trial_target(root: Path, filename: str) -> tuple[int | str, tuple[float, float], float, str]:
    """기존 초기위치 시험 설정에서 목표 노드와 차체 방향(m/rad)을 읽는다. 발행하지 않는다."""
    data = json.loads(resolve_file(root, filename).read_text())
    graph = RouteGraph(resolve_file(root, data['route_graph']))
    xy, other = graph.nodes[data['node_id']], graph.nodes[data['face_away_from_node_id']]
    if math.dist(xy, other) < 1e-6:
        raise ValueError('시험 목표와 방향 기준 노드가 같습니다.')
    return data['node_id'], xy, math.atan2(xy[1]-other[1], xy[0]-other[0]), data['frame_id']


class NavigationTrialMission:
    """준비 후 기존 StagedNavigation만 실행한다. 팔·수량·수확 완료 기록은 호출하지 않는다."""

    def __init__(self, node: Any, section: str, xy: tuple[float, float], yaw: float,
                 prepare: Callable[[Callable[[], None]], None]) -> None:
        self._node, self._section, self._xy, self._yaw = node, section, xy, yaw
        self._prepare = prepare

    def run(self) -> Any:
        self._node.check()
        self._prepare(self._node.check)
        self._node.mission_stage = 'NAVIGATION'
        result = self._node.staged_navigation.navigate(self._section, self._xy, self._yaw)
        self._node.check()
        return result


class NavigationTrial:
    """시험 프로필에서만 여는 NavigateToPose Action. 상태를 강제로 IDLE로 만들지 않는다."""

    def __init__(self, node: Any, *, root: Path, profile: dict,
                 prepare: Callable[[Callable[[], None]], None]) -> None:
        if profile.get('mode') != 'real' or node.staged_navigation is None:
            raise ValueError('시험 이동은 실물 단계별 주행에서만 사용할 수 있습니다.')
        self._node, self._prepare = node, prepare
        self._node_id, self._xy, self._yaw, self._frame = trial_target(root, profile['navigation_trial_config'])
        pose = SimpleNamespace(position=SimpleNamespace(x=self._xy[0], y=self._xy[1]), yaw=self._yaw)
        self._section = resolve_section(None, node.config, pose, **node.section_resolution)
        self._task_id: str | None = None
        self._token = None
        self._canceled = threading.Event()
        self._server = ActionServer(node, NavigateToPose, 'trial/navigate_to_pose',
            execute_callback=self.execute, goal_callback=self.accept,
            cancel_callback=self.cancel, callback_group=node.callbacks)

    def accept(self, goal: Any) -> GoalResponse:
        """설정된 시험 자세만 받는다. 실제 주행 도착 허용치는 기존 Navigator 설정을 따른다."""
        p, q = goal.pose.pose.position, goal.pose.pose.orientation
        expected = (self._xy[0], self._xy[1], 0., 0., 0., math.sin(self._yaw/2), math.cos(self._yaw/2))
        values = (p.x, p.y, p.z, q.x, q.y, q.z, q.w)
        if (goal.pose.header.frame_id != self._frame or goal.behavior_tree
                or any(not math.isfinite(a) or abs(a-b) > 1e-6 for a,b in zip(values, expected))):
            return GoalResponse.REJECT
        with self._node.lock:
            if self._node.busy or self._node.blocked or self._node.stopping:
                return GoalResponse.REJECT
            task_id = 'navigation-trial-'+uuid.uuid4().hex
            if not self._node.handoff.reserve('work', task_id, preempt=False):
                return GoalResponse.REJECT
            self._task_id = task_id
            self._node.busy = True
            self._canceled.clear()
            return GoalResponse.ACCEPT

    def cancel(self, handle: Any) -> CancelResponse:
        """기존 node.check가 진행 중 StagedNavigation 취소를 관측하도록 요청한다."""
        with self._node.lock:
            self._canceled.set()
            if self._token is not None:
                self._token.interrupted.set()
        return CancelResponse.ACCEPT

    def execute(self, handle: Any) -> Any:
        node = self._node
        result = NavigateToPose.Result()
        controller = None
        acquired = False
        canceled = False
        error = ''
        def check() -> None:
            if self._canceled.is_set() or handle.is_cancel_requested or node.stopping:
                raise ActionInterrupted('시험 이동 취소/종료')
            if node.blocked:
                raise RuntimeError('이전 동작 정리 미확인')
        try:
            token = node.handoff.acquire('work', self._task_id, check)
            acquired = True
            with node.lock:
                self._token = token
                if self._canceled.is_set():
                    token.interrupted.set()
            node.navigation_log = []
            controller = HarvestStateController(NavigationTrialMission(
                node, self._section, self._xy, self._yaw, self._prepare))
            controller.start()
            controller.done.wait()
            if controller.error is not None:
                raise controller.error
            check()
        except (ActionInterrupted, MissionCanceled) as exc:
            canceled, error = True, str(exc)
        except Exception as exc:
            error = str(exc)
        finally:
            if controller is not None:
                controller.close()
            if acquired:
                try:
                    node.staged_navigation.cancel_nav()
                except Exception as exc:
                    node.blocked = True
                    error, canceled = 'CANCEL_UNCONFIRMED: '+str(exc), False
                finally:
                    if node.tag_control is not None:
                        try:
                            node.tag_control.end()
                        except Exception as exc:
                            error = error or '태그 세션 종료 오류: '+str(exc)
            if not error and (handle.is_cancel_requested or self._canceled.is_set()):
                canceled, error = True, '시험 이동 완료 직전 취소'
            if canceled and handle.is_cancel_requested and not node.blocked:
                handle.canceled()
            elif error:
                # Jazzy 계약에는 NONE만 정의되어 있다. 시험 서버의 실패는 1과 상세 문자열로 구분한다.
                result.error_code = 1
                handle.abort()
            else:
                handle.succeed()
            result.error_msg = error
            node.get_logger().info(f'NAVIGATION_TRIAL: task={self._task_id}, node={self._node_id}, '
                                   f'result={"CANCELED" if canceled else "FAILED" if error else "SUCCESS"}, detail={error}')
            with node.lock:
                self._token = None
                node.handoff.release('work', self._task_id)
                self._task_id = None
                node.busy = False
        return result

    def close(self) -> None:
        self._server.destroy()
