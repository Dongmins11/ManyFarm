"""SECTION_COMPLETE: 구역 기록/보고, 추가 이동 및 다음 구역·미션 종료 판단."""
from __future__ import annotations

import time

from ..runtime import utc
from .mission_state import MissionState


class SectionCompleteState(MissionState):
    name = 'SECTION_COMPLETE'

    def enter(self) -> None:
        super().enter()
        context = self._mission.context
        if context.section_reported:
            # 경로 끝 추가 이동에서 돌아온 경우 보고를 중복하지 않습니다.
            self._controller.run_async(self, self._mission.save, self._on_tail_saved)
            return
        expected = len(context.design['segments'])
        records = context.report['sections'][context.section]['segments']
        if len(records) != expected or any(record['status'] != 'COMPLETE' for record in records):
            raise RuntimeError('모든 관측 지점이 끝나기 전에 구역 완료를 요청했습니다.')
        self._mission.record_section()
        self._controller.run_async(self, self._mission.save, self._on_section_saved)

    def _on_section_saved(self, result: None) -> None:
        context = self._mission.context
        self._mission.node._communication.feedback(
            context.goal, context.section, 'SECTION_COMPLETE', context.tasks,
            len(context.completed), context.completed_segments,
            context.segment_id, context.segment_expected_count,
        )
        context.section_reported = True
        context.tail_started = time.monotonic()
        tail = {'finish_at': context.design['finish_at'], 'started_at': utc(), 'status': 'SKIPPED'}
        context.report['sections'][context.section]['post_capture_navigation'] = tail
        assert context.bed is not None
        if context.design['finish_at'] == 'route_end' and context.segment['offset_m'] < context.bed.length - 1e-6:
            tail['status'] = 'MOVING'
            from .navigation_move_state import NavigationMoveState
            self._controller.request_transition(
                self, NavigationMoveState(self._mission, self._controller, 'section_exit'),
            )
            return
        tail.update(finished_at=utc(), elapsed_wall_s=time.monotonic() - context.tail_started)
        self._advance_section()

    def _on_tail_saved(self, result: None) -> None:
        self._advance_section()

    def _advance_section(self) -> None:
        context = self._mission.context
        if context.section_index + 1 >= len(context.goal.request.section_ids):
            self._controller.complete(self)
            return
        context.section_index += 1
        self._mission.select_section()
        from .navigation_move_state import NavigationMoveState
        self._controller.request_transition(
            self, NavigationMoveState(self._mission, self._controller, 'section_start'),
        )
