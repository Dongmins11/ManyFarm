"""미션 데이터와 작업 수명 관리. 단계별 실행 순서는 State가 담당합니다."""
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from farm_interfaces.action import ScoutArea
from rclpy.action.server import ServerGoalHandle
from scout_robot.survey_core import Survey
from scout_robot.task_messages import tasks_from_windows, task_record

from .mission_types import MissionContext
from .observer import SurveyObserver
from .runtime import utc, write_json

if TYPE_CHECKING:
    from .scout_node import ScoutNode


class ScoutMission:
    def __init__(self, node: ScoutNode) -> None:
        self._node: ScoutNode = node
        self._context: MissionContext | None = None  # 처음 작업을 받기 전 None

    @property
    def node(self) -> ScoutNode:
        return self._node

    @property
    def context(self) -> MissionContext:
        if self._context is None:
            raise RuntimeError('활성 미션 데이터가 없습니다.')
        return self._context

    def begin(self, goal: ServerGoalHandle) -> None:
        """작업 한 건의 데이터를 초기화합니다. 이동·관측 반복문은 없습니다."""
        session = uuid.uuid4().hex[:12]
        report = {
            'session_id': session,
            'goal': {key: getattr(goal.request, key) for key in (
                'robot_id', 'task_id', 'section_id', 'map_id',
                'frame_id', 'crop_type', 'target_ripeness',
            )},
            'config': self._node._cfg,
            'vision_config': self._node._vcfg,
            'started_at': utc(),
            'status': 'RUNNING',
            'sections': {},
            'observations': [],
            'completed_segments': [],
            'completed_segment_count': 0,
        }
        self._node._active_goal = goal
        self._node._navigation_log = []
        report['navigation'] = self._node._navigation_log
        self._context = MissionContext(
            goal=goal,
            session=session,
            folder=self._node._root / self._node._cfg['output_dir'] / session,
            report=report,
            started_wall=time.monotonic(),
        )
        self.select_section()

    def select_section(self) -> None:
        """현재 section_index의 공유 데이터를 준비합니다. 다음 상태는 선택하지 않습니다."""
        context = self.context
        context.bed = self._node._beds[context.section]
        context.survey = Survey(
            context.bed,
            context.session + '_' + context.section,
            self._node._cfg['association_distance_m'],
        )
        context.segment_index = 0
        context.design = {}
        context.current_segment = None
        context.observation = None
        context.tasks = []
        context.section_reported = False

    def open_observer(self) -> None:
        """이번 작업이 소유하는 실제 워커를 준비합니다. I/O 작업 스레드에서 호출합니다."""
        context = self.context
        vision = getattr(self._node, '_vision', None)
        if vision is not None:
            context.worker = vision.acquire()
            context.report['vision_worker_log'] = str(vision.log_path)
            self._node.get_logger().info('준비된 영상 워커 연결 완료')
            return
        command = [
            str(self._node._python),
            str(self._node._root / 'scripts/run_scout_survey_worker.py'),
            '--config', str(self._node._root / self._node._cfg['vision_config']),
            '--device', str(self._node.get_parameter('device').value),
        ]
        if self._node.get_parameter('headless').value:
            command.append('--headless')
        self._node.check()
        if self._node._vcfg.get('backend') == 'realsense_legacy':
            from .real_observer import RealObserver
            command=[str(self._node._python),str(self._node._root/'scripts/run_scout_real_worker.py'),
                     '--config',str(self._node._root/self._node._cfg['vision_config'])]
            context.worker=RealObserver(command,context.folder/'vision_worker.log',self._node)
        else:
            context.worker = SurveyObserver(command, context.folder / 'vision_worker.log')
        if not context.worker.receive(self._node.check, float(self._node._vcfg.get("startup_timeout_s",120))).get('ready'):
            raise RuntimeError('Vision worker failed to initialize')

    def begin_segment(self) -> None:
        context = self.context
        context.segment_started = time.monotonic()
        context.observation = None
        context.current_segment = dict(context.segment, status='MOVING', started_at=utc())
        context.report['sections'][context.section]['segments'].append(context.current_segment)

    def record_segment(self) -> None:
        """실제 관측 자료 저장이 성공한 뒤 진행 기록을 확정합니다."""
        context = self.context
        assert context.current_segment is not None
        assert context.survey is not None
        context.current_segment.update(
            status='COMPLETE', finished_at=utc(),
            observation_wall_s=time.monotonic() - context.capture_started,
            elapsed_wall_s=time.monotonic() - context.segment_started,
        )
        context.completed_segments += 1
        context.report['completed_segments'].append({
            'section_id': context.section, 'segment_id': context.segment_id,
        })
        context.report['completed_segment_count'] = context.completed_segments
        context.report['sections'][context.section]['survey'] = context.survey.record()

    def save_segment(self) -> None:
        """저장 성공한 관측까지만 Result용 부분 목록으로 확정합니다.

        I/O 직렬 큐에서 저장 후 commit하므로 취소 정리도 이 작업 이후 실행됩니다.
        """
        context = self.context
        section = context.report['sections'][context.section]
        windows = section['survey']['windows']
        tasks = tasks_from_windows(windows)
        section['batch'] = [dict(task_record(task), section_id=context.section,
                                 segment_id=window.get('segment_id', ''), sequence=i + 1)
                            for i, (task, window) in enumerate(zip(tasks, windows))]
        self.save()
        context.tasks = tasks

    def record_section(self) -> None:
        context = self.context
        context.report['sections'][context.section]['status'] = 'COMPLETE'
        context.completed.append(context.section)
        context.total_tasks = len(context.tasks)
        context.total_fruits = sum(task.expected_count for task in context.tasks)

    def save(self) -> None:
        write_json(self.context.folder / 'survey.json', self.context.report)

    def close_observer(self, reusable: bool = False) -> None:
        context = self.context
        if context.worker is not None:
            vision = getattr(self._node, '_vision', None)
            if vision is not None:
                vision.release(reusable)
            else:
                context.worker.close()
            context.worker = None

    def finish(self, code: str, error: Exception | None = None) -> ScoutArea.Result:
        """중단·자원 정리가 끝난 뒤 결과를 만듭니다. 관제 송신은 Communication 담당입니다."""
        context = self.context
        result = ScoutArea.Result()
        result.robot_id = context.goal.request.robot_id
        result.task_id = context.goal.request.task_id
        result.result_code = code
        result.error_code = 'NONE' if error is None else ('CANCELED' if code == 'CANCELED' else 'SURVEY_FAILED')
        if error is not None and type(error).__name__ == 'NavigationConfigurationError':
            result.error_code = 'NAV_CONFIG_MISMATCH'
        result.error_message = '' if error is None else str(error)
        result.section_id = context.section
        result.harvest_tasks = list(context.tasks)
        result.completed_segment_count = context.completed_segments
        result.harvest_task_count = len(result.harvest_tasks)
        result.total_expected_count = sum(task.expected_count for task in result.harvest_tasks)
        result.timestamp = utc()
        context.report.update(
            status=code, finished_at=utc(),
            elapsed_wall_s=time.monotonic() - context.started_wall,
            completed_section_ids=context.completed,
            section_id=context.section,
            harvest_tasks=[task_record(task) for task in result.harvest_tasks],
            harvest_task_count=result.harvest_task_count,
            total_expected_count=result.total_expected_count,
        )
        if error is not None:
            context.report['error'] = str(error)
            segment = context.current_segment
            if segment is not None and segment['status'] != 'COMPLETE':
                segment.update(status=code, error=str(error), finished_at=utc())
            if context.survey is not None:
                section = context.report['sections'].setdefault(context.section, {})
                section['survey'] = context.survey.record()
                if section.get('status') != 'COMPLETE':
                    section['status'] = code
                tail = section.get('post_capture_navigation', {})
                if tail.get('status') == 'MOVING':
                    tail.update(status=code, error=str(error), finished_at=utc())
            if self._node._navigation_log and self._node._navigation_log[-1]['status'] in ('MOVING', 'SETTLING'):
                self._node._navigation_log[-1].update(status=code, error=str(error), finished_at=utc())
        try:
            self.save()
        except Exception as save_error:
            # 저장 실패를 성공으로 감추지 않습니다. 이미 수행된 구역 수는 보존합니다.
            self._node.get_logger().error(f'Final report save failed: {save_error}')
            if code == 'SUCCESS':
                result.result_code = 'FAILED'
                result.error_code = 'REPORT_SAVE_FAILED'
                result.error_message = str(save_error)
        return result
