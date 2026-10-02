"""SEGMENT_COMPLETE: 관측 자료 저장, 지점 완료 확정, 다음 지점 판단."""
from __future__ import annotations

from farm_interfaces.msg import HarvestTask
from geometry_msgs.msg import Point

from ..runtime import write_json
from .mission_state import MissionState


class SegmentCompleteState(MissionState):
    name = 'SEGMENT_COMPLETE'

    def enter(self) -> None:
        super().enter()
        self._controller.run_async(self, self._save_observation, self._on_observation_saved)

    def _save_observation(self) -> None:
        context = self._mission.context
        node = self._mission.node
        observation = context.observation
        assert observation is not None and context.worker is not None and context.survey is not None
        meta = observation.response['metadata']
        directory = context.folder / context.section / f'observation_{context.segment_index + 1:03d}'
        labels = [{'id': fruit_id, 'box': detection['mask_box_original_xyxy']}
                  for detection, fruit_id in zip(observation.accepted, observation.ids)]
        context.worker.call(
            'annotate', node.check, stamp_ns=int(meta['stamp_ns']),
            T_map_odom=observation.transform, labels=labels,
            windows=context.survey.windows(), section_id=context.section,
            segment_id=context.segment_id, directory=str(directory),
        )
        node.check()
        write_json(directory / 'map_detections.json', {
            'section_id': context.section, 'segment_id': context.segment_id,
            'accepted': observation.accepted, 'ids': observation.ids, 'ignored': observation.ignored,
        })

    def _on_observation_saved(self, result: None) -> None:
        context = self._mission.context
        observation = context.observation
        assert observation is not None and context.current_segment is not None
        context.segment_expected_count = len(set(observation.ids))
        context.current_segment['segment_expected_count'] = context.segment_expected_count
        context.report['observations'].append({
            'section': context.section, 'segment_id': context.segment_id,
            'index': context.segment_index + 1,
            'stamp_ns': int(observation.response['metadata']['stamp_ns']),
            'timings': observation.response['timings'],
            'valid_depth_detection_count': len(observation.response['detections']),
            'depth_rejected_count': len(observation.response['rejected']),
            'section_accepted_count': len(observation.accepted),
            'segment_expected_count': context.segment_expected_count,
            'outside_section_count': len(observation.ignored),
        })
        self._mission.record_segment()
        self._controller.run_async(self, self._mission.save, self._on_record_saved)

    def _on_record_saved(self, result: None) -> None:
        context = self._mission.context
        assert context.survey is not None
        self._mission.node.show(context.survey)
        if context.last_segment:
            # 현재 정책: 구역 전체 관측 후 수확 작업 목록 확정. Window 정책은 바꾸지 않습니다.
            self._controller.run_async(self, self._build_tasks, self._on_tasks_ready)
            return
        self._mission.node._communication.feedback(
            context.goal, context.section, 'SEGMENT_COMPLETE', [],
            len(context.completed), context.completed_segments,
            context.segment_id, context.segment_expected_count,
        )
        context.current_segment = None
        context.segment_index += 1
        from .navigation_move_state import NavigationMoveState
        self._controller.request_transition(
            self, NavigationMoveState(self._mission, self._controller, 'observation'),
        )

    def _build_tasks(self) -> list[HarvestTask]:
        context = self._mission.context
        assert context.survey is not None
        tasks: list[HarvestTask] = []
        for window in context.survey.windows():
            self._mission.node.check()
            task = HarvestTask()
            task.task_id = window['window_id'].replace('_W', '_TASK')
            task.window_id = window['window_id']
            task.section_id = context.section
            task.segment_id = window['segment_id']
            task.sequence = len(tasks) + 1
            task.goal_pose.frame_id = 'map'
            task.goal_pose.position = Point(
                x=window['goal_pose']['position'][0], y=window['goal_pose']['position'][1], z=0.0,
            )
            task.goal_pose.yaw = window['goal_pose']['yaw']
            task.expected_count = window['expected_count']
            tasks.append(task)
        return tasks

    def _on_tasks_ready(self, tasks: list[HarvestTask]) -> None:
        context = self._mission.context
        context.tasks = tasks
        context.current_segment = None
        from .section_complete_state import SectionCompleteState
        self._controller.request_transition(self, SectionCompleteState(self._mission, self._controller))
