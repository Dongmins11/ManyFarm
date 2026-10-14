"""NAVIGATION_MOVE: 준비/이동 요청, 실제 도착 결과 처리 및 다음 단계 결정."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np
from scout_robot.segments import plan_segments
from farm_navigation.navigation_types import NavigationResult

from ..mission_types import JsonObject, MovePurpose
from ..runtime import utc
from .mission_state import MissionState

if TYPE_CHECKING:
    from ..scout_mission import ScoutMission
    from ..scout_state_controller import ScoutStateController


class NavigationMoveState(MissionState):
    name = 'NAVIGATION_MOVE'

    def __init__(self, mission: ScoutMission, controller: ScoutStateController, purpose: MovePurpose) -> None:
        super().__init__(mission, controller)
        self._purpose: MovePurpose = purpose  # 시작점 / 촬영 지점 / 구역 출구

    def enter(self) -> None:
        super().enter()
        if not self._mission.context.prepared:
            self._controller.run_async(self, self._prepare, self._on_prepared)
            return
        self._request_move()

    def _prepare(self) -> None:
        """첫 이동 전 실제 Nav2·영상 워커 준비. enter는 이 작업을 기다리지 않습니다."""
        context = self._mission.context
        context.folder.mkdir(parents=True, exist_ok=False)
        context.report['navigation_preflight'] = self._mission.node._navigator.preflight_navigation()
        self._mission.save()
        self._mission.open_observer()

    def _on_prepared(self, result: None) -> None:
        self._mission.context.prepared = True
        self._request_move()

    def _request_move(self) -> None:
        if self._purpose == 'observation':
            self._mission.begin_segment()
        self._controller.run_async(self, self._move, self._on_arrived)

    def _move(self) -> NavigationResult:
        context = self._mission.context
        assert context.bed is not None
        if self._purpose == 'section_start':
            if context.bed.cfg.get('patrol_segments'):
                first = context.bed.cfg['patrol_segments'][0]['observation_node_id']
                xy = self._mission.node._route_graph.nodes[first]
            else:
                xy = context.bed.origin
        elif self._purpose == 'section_exit':
            xy = context.bed.world(context.bed.length, 0)
        else:
            xy = context.bed.world(context.segment['offset_m'], 0)
        # 공통 이동 결과에 도착 측정과 정지 확인 시각(ns)이 포함됩니다.
        # 그래프는 XY, bed.world()는 XYZ를 반환합니다.
        # 시뮬·실물 모두 공통 주행부에는 평면 좌표 XY만 전달합니다.
        target_xy = (float(xy[0]), float(xy[1]))
        node = self._mission.node
        control = getattr(node, '_tag_control', None)
        # 반복 ID는 진입 후 해당 구역의 관측 이동에서만 보정에 사용한다.
        # 접근/이탈에서는 구역 권한을 열지 않으며 완료·실패·취소 시 즉시 닫는다.
        node.check()
        if control is not None:
            if self._purpose == 'observation':
                control.begin(context.section)
            else:
                control.end()
        try:
            return node._navigator.navigate(target_xy, context.bed.yaw)
        finally:
            if control is not None:
                control.end()

    def _on_arrived(self, result: NavigationResult) -> None:
        context = self._mission.context
        context.stamp = result.stamp_ns
        if self._purpose == 'section_start':
            self._controller.run_async(self, self._plan_observations, self._on_planned)
            return
        if self._purpose == 'section_exit':
            tail = context.report['sections'][context.section]['post_capture_navigation']
            tail.update(status='ARRIVED', finished_at=utc(), elapsed_wall_s=time.monotonic() - context.tail_started)
            from .section_complete_state import SectionCompleteState
            self._controller.request_transition(self, SectionCompleteState(self._mission, self._controller))
            return
        assert context.current_segment is not None
        context.current_segment['navigation_wall_s'] = time.monotonic() - context.segment_started
        from .segment_progress_state import SegmentProgressState
        self._controller.request_transition(self, SegmentProgressState(self._mission, self._controller))

    def _plan_observations(self) -> JsonObject:
        """구역 시작점의 실제 카메라 정보로 기존 관측 지점 계획을 계산합니다."""
        context = self._mission.context
        node = self._mission.node
        assert context.worker is not None and context.bed is not None
        info = context.worker.call('info', node.check, after_stamp_ns=context.stamp, session=context.camera_session)
        meta = info['metadata']
        context.camera_session = meta['session']
        base = node.lookup(meta['pose_frame'], node._cfg['base_frame'], meta['stamp_ns'])
        camera = np.linalg.inv(base) @ np.array(meta['T_odom_camera_optical'])
        if context.bed.cfg.get('patrol_segments'):
            from ..patrol_config import patrol_design
            return patrol_design(context.bed,node._route_graph)
        return plan_segments(
            context.bed, context.section, meta['K'], camera,
            info['width'], info['height'], node._vcfg['preprocess'], node._cfg['overlap_fraction'],
        )

    def _on_planned(self, design: JsonObject) -> None:
        context = self._mission.context
        assert context.survey is not None
        if not design['segments']:
            raise RuntimeError('현재 구역의 관측 지점이 없습니다.')
        context.design = design
        context.report['sections'][context.section] = {
            'design': design, 'status': 'RUNNING',
            'survey': context.survey.record(), 'segments': [],
        }
        self._controller.run_async(self, self._mission.save, self._on_plan_saved)

    def _on_plan_saved(self, result: None) -> None:
        context = self._mission.context
        if context.design.get('segmentation_mode') == 'graph_nodes':
            # 첫 관측 노드에는 이미 도착했으므로 이동 요청을 반복하지 않습니다.
            self._mission.begin_segment()
            context.current_segment['navigation_wall_s'] = 0.0
            from .segment_progress_state import SegmentProgressState
            self._controller.request_transition(self, SegmentProgressState(self._mission,self._controller))
            return
        self._controller.request_transition(
            self, NavigationMoveState(self._mission, self._controller, 'observation'),
        )
