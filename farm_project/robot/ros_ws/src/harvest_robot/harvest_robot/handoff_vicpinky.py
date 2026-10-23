"""Vic Pinky 차체 객체 조립. Node가 관리하는 실제 자원을 명시적으로 전달한다.

bindings는 Nav2Client와 생성 시 사용한 설정을 함께 전달한다. 서버 설정과
wall 관측·출력 차단·기존 ActionHandoff 연결은 호출자가 준비해야 한다.
"""
from typing import Any, Mapping

from .handoff_motion import HarvestHandoffMotion
from .handoff_navigation import HandoffNavigationSteps, NavigationBinding
from .handoff_profile import MotionProfile


def build_vicpinky_motion(*, profile: MotionProfile, bindings: Mapping[str, NavigationBinding],
                         spin: Any, spin_endpoint: str, node: Any, motion: Any,
                         planner: Any, check: Any, settling_check: Any,
                         arm_output: Any, stop_output: Any, record: Any,
                         navigator_factory: Any = None) -> HarvestHandoffMotion:
    """구성은 한 번, 단계 실행에서는 등록된 동작 객체만 선택한다.

외부에서 확보한 실행 소유권 검사를 check로 전달한다. 이 함수에서 예약을
중복 확보하거나 기존 주행 설정을 덮어쓰지 않는다.
"""
    if set(bindings) != set(profile.navigation):
        raise ValueError('프로파일과 클라이언트 단계 불일치')
    if spin_endpoint != profile.spin_endpoint:
        raise ValueError('미세 정렬 Spin 연결 불일치')
    for stage, settings in profile.navigation.items():
        if bindings[stage].settings != settings:
            raise ValueError('클라이언트 설정 불일치: ' + stage)
    steps = HandoffNavigationSteps(
        node=node, motion=motion, spin=spin,
        bindings={stage: NavigationBinding(settings, bindings[stage].client)
                  for stage, settings in profile.navigation.items()},
        capture=planner.capture, plan=planner.plan, check=check,
        settling_check=settling_check, arm_output=arm_output,
        stop_output=stop_output, record=record, navigator_factory=navigator_factory)
    return HarvestHandoffMotion(steps)
