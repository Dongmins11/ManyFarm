"""로봇별 연결 구성을 읽는다. 서버의 속도·플러그인 설정은 변경하지 않는다."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from farm_navigation.navigation_types import NavigationSettings


@dataclass(frozen=True)
class MotionProfile:
    navigation: Mapping[str, NavigationSettings]
    spin_endpoint: str

    @classmethod
    def from_mapping(cls, config: dict) -> 'MotionProfile':
        if set(config) != {'navigation', 'spin_endpoint'}:
            raise ValueError('navigation과 spin_endpoint 설정 필요')
        stages = {'departure', 'wall', 'retreat', 'return'}
        if not isinstance(config['navigation'], dict) or set(config['navigation']) not in (stages, stages | {'window'}):
            raise ValueError('주행 4단계 설정 필요')
        endpoint = config['spin_endpoint']
        if not isinstance(endpoint, str) or not endpoint.startswith('/') or endpoint == '/' or any(c.isspace() for c in endpoint):
            raise ValueError('전용 Spin 절대 endpoint 필요')
        settings = {stage: NavigationSettings.from_mapping(values)
                    for stage, values in config['navigation'].items()}
        if any(value.mode != 'follow_path' for value in settings.values()):
            raise ValueError('차체 경로는 follow_path 설정 필요')
        return cls(MappingProxyType(settings), endpoint)


def select_motion(config: dict, builders: Mapping[str, object]):
    """로봇 구성부 등록 지점. 미선택 환경에서는 로더·클라이언트도 생성하지 않는다.

예: builders={'vicpinky_arc_wall': build_vicpinky, 'other': build_other}
각 builder는 검증된 연결 프로파일을 받아 HarvestHandoffMotion을 반환한다.
"""
    selection = config.get('handoff_components')
    if selection is None:
        return None
    if not isinstance(selection, dict) or set(selection) != {'implementation', 'profile'}:
        raise ValueError('handoff_components 선택 형식 오류')
    name = selection['implementation']
    if not isinstance(name, str) or name not in builders or not callable(builders[name]):
        raise ValueError('등록되지 않은 동작 구성')
    profile = MotionProfile.from_mapping(selection['profile'])
    return builders[name](profile)
