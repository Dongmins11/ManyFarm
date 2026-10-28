"""이미 생성된 ROS 의존성을 새 차체 클래스에 조립한다. 서버 시작/설정 변경 없음."""
from typing import Any, Callable, Mapping
from .handoff_motion import HarvestHandoffMotion, configured_motion
from .handoff_navigation import HandoffNavigationSteps, NavigationBinding
from .handoff_planning import HandoffPlanner


def build_motion(*, config: dict, node: Any, motion: Any, spin: Any,
                 bindings: Mapping[str, NavigationBinding], planner: HandoffPlanner,
                 check: Callable[[], None], settling_check: Callable[[], None],
                 arm_output: Callable[[str], None], stop_output: Callable[[], None],
                 record: Callable[[dict], None]) -> HarvestHandoffMotion | None:
    """기존 Node의 선택 분기에서 호출할 조립 함수. 기본 설정은 None이다.

planner의 wall/spec/policy와 bindings의 controller/checker ID는 로봇 설정에서
구성한다. 출력 게이트와 관측 어댑터를 빈 함수로 대신하지 않는다.
"""
    def steps(selection: dict) -> HandoffNavigationSteps:
        return HandoffNavigationSteps(node=node, motion=motion, spin=spin,
            bindings=bindings, capture=planner.capture, plan=planner.plan,
            check=check, settling_check=settling_check, arm_output=arm_output,
            stop_output=stop_output, record=record)
    return configured_motion(config, steps)
