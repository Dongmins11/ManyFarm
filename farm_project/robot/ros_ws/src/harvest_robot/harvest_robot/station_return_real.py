"""실물 복귀 통신·미션 연결. 공통 Action 수명·주행과 복귀 전용 상태를 조합한다."""
from __future__ import annotations

from copy import copy
from pathlib import Path
from typing import Any, Callable

from rclpy.action import GoalResponse
from farm_common.station_return import StationReturn
from farm_navigation.configuration import read_mapping, resolve_file
from geometry_msgs.msg import Twist
from .station_return_states import ReturnController
from .station_return_mission import StationReturnMission, tag_section, reverse_control_error


def return_profile(root: Path, profile: dict, settings: Any) -> tuple[dict, Any]:
    """스테이션 목표를 읽는다(m/rad). 주행·오차 기록 설정은 기존 값을 유지한다."""
    data = read_mapping(resolve_file(root, profile['station_return_config']))
    if data.get('map_id') != profile['map_id']:
        raise ValueError('스테이션 복귀 map_id 불일치')
    station = data['stations'][profile['robot_id']]
    values = [station[key] for key in ('station_id', 'node_id', 'xy_m', 'yaw_rad')]
    selected = dict(profile)
    selected.pop('station_config', None)
    if any(value is None for value in values):
        return selected, settings
    selected['station_config'] = profile['station_return_config']
    return selected, settings


class RealStationReturn(StationReturn):
    """수확 복귀 통신 어댑터. 공통 Action 수명 관리와 단계별 수확 미션을 연결한다."""

    def __init__(self, node: Any, *, root: Path, profile: dict, settings: Any,
                 prepare: Callable[[Callable[[], None]], None],
                 recovery_output: Any = None, **kwargs: Any) -> None:
        if profile.get('mode') != 'real':
            raise ValueError('실물 스테이션 복귀는 real 프로필 전용입니다.')
        self._mission: StationReturnMission | None = None
        self._controller: ReturnController | None = None
        self._recovery_output = recovery_output
        self._real_node = node
        self._map_aliases = dict(node.config.get('control_aliases', {}).get('map_ids', {}))
        self._prepare_existing = prepare
        # 태그 구역 판별에도 기존 주행 설정을 사용한다.
        self._tag_settings = settings
        selected, configured = return_profile(root, profile, settings)
        if configured.collision_retry_count and recovery_output is None:
            raise ValueError('복귀 재시도는 기존 출력 소유자 연결이 필요합니다.')
        super().__init__(node, root=root, profile=selected, settings=configured,
                         prepare=self._prepare_real, **kwargs)
        if self._client is not None and configured.collision_retry_count:
            self._client.set_recovery_stop(self._stop_for_recovery)
        self._docking = None
        self._docked = False
        self._corner_navigation = None
        if profile.get('station_corner_radius_m') is not None and self._navigator is not None:
            from farm_navigation.transfer_arc import ArcSpec
            from .station_corner_navigation import CornerNavigation
            radius = ArcSpec(radius=profile['station_corner_radius_m']).radius
            if recovery_output is None:
                raise ValueError('복귀 코너에는 기존 출력 소유자 연결이 필요합니다.')
            self._corner_navigation = CornerNavigation(node, straight=self._navigator,
                settings=configured, radius=radius, graph=self._graph, robot_id=profile['robot_id'],
                poses=self._poses, motion=kwargs['motion'], callbacks=kwargs['callbacks'],
                check=self._check, owns_output=self._owns_corner_output,
                recovery_stop=self._stop_for_recovery)

        if profile.get('station_docking_config'):
            from .station_docking import StationDocking, load_config
            self._docking = StationDocking(node, config=load_config(root, profile['station_docking_config']),
                settings=configured, robot_id=profile['robot_id'], poses=self._poses,
                motion=kwargs['motion'], callbacks=kwargs['callbacks'], check=self._cancel_check,
                owns_output=self._owns_corner_output)

    def _mission_docked(self) -> bool:
        return self._docked

    def _owns_corner_output(self) -> bool:
        """기존 복귀 소유권과 출력 오류를 확인한다. 인계 출력 상태는 변경하지 않는다."""
        return (self._handle is not None and not self._unavailable()
                and not self._recovery_output.error
                and self._handoff.current == ('return', self._handle.request.task_id))

    def accept(self, goal: Any) -> GoalResponse:
        """관제 지도 별칭을 검증용 복사본에만 적용한다. 원본 Goal과 실물 지도는 보존한다."""
        checked = copy(goal)
        checked.map_id = self._map_aliases.get(goal.map_id, goal.map_id)
        return super().accept(checked)

    def _prepare_real(self, check: Callable[[], None]) -> None:
        self._prepare_existing(check)
        # 소유권 인수가 끝난 뒤 기존 공개 API로 이전 구간 도착 문맥을 무효화한다.
        staged = self._real_node.staged_navigation
        if staged is not None:
            staged.cancel_nav()
        connection = getattr(self._real_node, 'jetson_connection', None)
        # 차체 단독 시험에서만 명시적으로 생략한다. 실제 팔 상태를 생성하거나 변경하지 않는다.
        if connection is not None and not self._profile.get('station_return_skip_arm_status', False):
            snapshot = connection.snapshot()
            status = snapshot.get('status') or {}
            # 팔 Goal 수락용 ready와 차체 주행 준비는 다르다. 시작 시 한 번만 확인한다.
            if snapshot.get('stale', True) or not all(status.get(key) is True for key in
                    ('device_state_valid', 'arm_stowed', 'arm_stopped')):
                raise RuntimeError('ARM_TRAVEL_NOT_READY: 최신 팔 유효·접힘·정지 확인 필요')
        check()

    def prepare_travel(self, check: Callable[[], None]) -> None:
        """실물 차체 시험에서도 동일한 팔·이전 주행 준비 정책을 사용한다."""
        self._prepare_real(check)

    def _check(self) -> None:
        if self._mission is None:
            self._cancel_check()
        else:
            self._mission.check()

    def _stop_for_recovery(self) -> None:
        """복귀가 소유한 동안 기존 출력으로 0만 발행한다. 인계 상태·gate는 수정하지 않는다."""
        output = self._recovery_output
        with output.lock:
            self._cancel_check()
            owner = self._handoff.current
            if owner != ('return', self._handle.request.task_id) or output.error:
                raise RuntimeError('복귀 재시도 출력 소유권 상실')
            output.publisher.publish(Twist())

    def _run_mission(self) -> None:
        self._docked = False
        self._mission = StationReturnMission(prepare=lambda: self._prepare_real(self._cancel_check),
            check=self._cancel_check, navigator=self._corner_navigation or self._navigator, graph=self._graph,
            station=self._station, poses=self._poses, settings=self._settings,
            tag_control=self._tag_control,
            corridors=self._real_node.section_resolution.get('corridors', {}), docking=self._docking)
        self._controller = ReturnController(self._mission)
        self._controller.run()
        self._cancel_check()
        self._docked = self._mission.docked

    def _cleanup_mission(self) -> None:
        try:
            if self._controller is not None:
                if self._controller.cleanup_error is not None:
                    raise self._controller.cleanup_error
            else:
                super()._cleanup_mission()
        finally:
            self._mission = self._controller = None

    def close(self) -> None:
        if self._docking is not None:
            self._docking.close()
        if self._corner_navigation is not None:
            self._corner_navigation.close()
        super().close()
