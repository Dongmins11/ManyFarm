"""SEGMENT_PROGRESS: 정지 관측 요청과 과실/윈도우 갱신. 완료 보고는 다음 상태 담당."""
from __future__ import annotations

import time
import numpy as np
from scout_robot.survey_core import transform_points

from ..mission_types import JsonObject, Observation
from ..runtime import utc
from .mission_state import MissionState


class SegmentProgressState(MissionState):
    name = 'SEGMENT_PROGRESS'

    def enter(self) -> None:
        super().enter()
        context = self._mission.context
        context.capture_started = time.monotonic()
        assert context.current_segment is not None
        context.current_segment.update(status='CAPTURING', capture_started_at=utc())
        self._controller.run_async(self, self._capture, self._on_captured)

    def _capture(self) -> JsonObject:
        context = self._mission.context
        node = self._mission.node
        assert context.worker is not None
        response = context.worker.call(
            'capture', node.check,
            after_stamp_ns=context.stamp, session=context.camera_session,
        )
        if not hasattr(context.worker, 'wait_ready') and not node._navigator.stationary_now():
            raise RuntimeError('Robot moved during observation; result rejected')
        return response

    def _on_captured(self, response: JsonObject) -> None:
        # 영상 응답을 받아야 등록을 시작합니다. enter에서 순차 실행하지 않습니다.
        self._controller.run_async(self, lambda: self._register(response), self._on_registered)

    def _register(self, response: JsonObject) -> Observation:
        context = self._mission.context
        node = self._mission.node
        assert context.bed is not None and context.survey is not None
        meta = response['metadata']
        transform = (np.asarray(meta['T_map_camera_reference']) if 'T_map_camera_reference' in meta
                     else node.lookup('map', meta['pose_frame'], meta['stamp_ns']))
        accepted: list[JsonObject] = []
        ignored: list[JsonObject] = []
        for detection in response['detections']:
            node.check()
            position = transform_points(transform, [detection['position_odom_m']])[0].tolist()
            local = context.bed.local(position)
            in_section = 0 <= local[0] <= context.bed.length
            in_bed = abs(local[1] - context.bed.bed_n) <= node._cfg['association_band_half_depth_m']
            if not in_section or not in_bed:
                ignored.append(dict(detection, position_map_m=position, reason='outside_section_or_bed_band'))
                continue
            accepted.append(dict(detection, position_map_m=position, stamp_ns=int(meta['stamp_ns'])))
        node.check()
        ids = context.survey.ingest(accepted, segment_id=context.segment_id)
        return Observation(response, transform.tolist(), accepted, ignored, ids)

    def _on_registered(self, observation: Observation) -> None:
        self._mission.context.observation = observation
        from .segment_complete_state import SegmentCompleteState
        self._controller.request_transition(self, SegmentCompleteState(self._mission, self._controller))
