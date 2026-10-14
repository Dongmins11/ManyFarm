"""환경 파일의 경로를 project_root 기준으로 해석합니다. sim/real 로직을 복제하지 않습니다."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from copy import deepcopy
import json
import yaml
import atexit
import math
import tempfile


def read_mapping(path: str | Path) -> dict[str,Any]:
    file=Path(path).expanduser()
    value=json.loads(file.read_text()) if file.suffix=='.json' else yaml.safe_load(file.read_text())
    if not isinstance(value,dict): raise ValueError(f'객체형 설정이 필요합니다: {file}')
    if value.get('configured',True) is not True: raise ValueError(f'미완성 설정입니다: {file}')
    return value


def resolve_file(root: Path, value: str) -> Path:
    if not isinstance(value,str) or not value.strip(): raise ValueError('빈 설정 파일 경로')
    path=Path(value).expanduser()
    path=(path if path.is_absolute() else root/path).resolve()
    if not path.is_file(): raise FileNotFoundError(f'설정 파일이 없습니다: {path}')
    return path


_NAV2_BINDINGS = {'base_footprint_frame', 'base_link_frame', 'odom_frame',
                  'scan_topic', 'initial_pose', 'set_initial_pose'}
_BT_FILES = ('default_nav_to_pose_bt_xml', 'default_nav_through_poses_bt_xml')


def _resolve_bt_files(data: dict[str, Any], directory: Path) -> None:
    """BT 파일은 해당 경로를 선언한 설정 파일의 디렉터리에서 찾는다."""
    bt = data.get('bt_navigator', {}).get('ros__parameters', {})
    for name in _BT_FILES:
        if bt.get(name) is not None and bt[name] != '':
            bt[name] = str(resolve_file(directory, bt[name]))


def merge_mappings(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """공통 기본값에 명시적 설정을 재귀 병합한다. 리스트는 교체하고 입력은 보존한다."""
    if not isinstance(defaults, dict) or not isinstance(overrides, dict):
        raise ValueError('기본값과 변경 설정은 객체형 mapping이어야 합니다.')
    result = deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_mappings(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_nav2_parameters(path: str | Path, root: Path | None = None) -> dict[str, Any]:
    """공통 Nav2 기본값에 장치 연결과 명시적인 환경별 overrides를 적용한다."""
    path = Path(path).expanduser().resolve()
    source_directory = path.parent
    data = read_mapping(path)
    if 'shared_nav2' in data:
        if set(data) - {'shared_nav2', 'bindings', 'overrides'} or 'bindings' not in data:
            raise ValueError('Nav2 환경 파일에는 shared_nav2, bindings, overrides를 지정합니다.')
        bindings = data['bindings']
        overrides = data.get('overrides', {})
        if not isinstance(bindings, dict) or set(bindings) != _NAV2_BINDINGS:
            raise ValueError(f'Nav2 장치 연결 항목은 {sorted(_NAV2_BINDINGS)}이어야 합니다.')
        for name in _NAV2_BINDINGS - {'initial_pose', 'set_initial_pose'}:
            if not isinstance(bindings[name], str) or not bindings[name].strip():
                raise ValueError(f'Nav2 {name}: 비어 있지 않은 이름이 필요합니다.')
        if not isinstance(bindings['set_initial_pose'], bool):
            raise ValueError('Nav2 set_initial_pose: bool이 필요합니다.')
        pose = bindings['initial_pose']
        if (not isinstance(pose, dict) or set(pose) != {'x', 'y', 'z', 'yaw'} or
                any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
                    for v in pose.values())):
            raise ValueError('Nav2 initial_pose: 유한한 x/y/z/yaw가 필요합니다.')
        path = resolve_file(root if root is not None else Path.cwd(), data['shared_nav2'])

        def bind(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: bind(item) for key, item in value.items()}
            if isinstance(value, list):
                return [bind(item) for item in value]
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                name = value[2:-1]
                if name not in _NAV2_BINDINGS:
                    raise ValueError(f'알 수 없는 Nav2 연결 변수: {name}')
                return bindings[name]
            return value

        defaults = bind(read_mapping(path))
        _resolve_bt_files(defaults, path.parent)
        data = merge_mappings(defaults, overrides)
    # 이전 외부 도구의 완성된 ROS YAML 입력도 지원한다. 운영 프로파일은 위 공통 참조를 쓴다.
    _resolve_bt_files(data, source_directory)
    return data


def materialize_nav2_parameters(path: str | Path, root: Path) -> str:
    """공통 해석 결과를 ROS 파라미터 파일로 만든다. 원본 설정 복사본을 관리하지 않는다."""
    data = load_nav2_parameters(path, root)
    with tempfile.NamedTemporaryFile(mode='w', prefix='farm_nav2_', suffix='.yaml', delete=False) as output:
        yaml.safe_dump(data, output, allow_unicode=True, sort_keys=False)
        filename = output.name
    atexit.register(Path(filename).unlink, missing_ok=True)
    return filename


def load_environment(path: str | Path, root: Path, mode: str, *, require_survey: bool = True) -> dict[str,Any]:
    """환경별 지도·그래프·예찰·장치 설정의 한 선택점입니다."""
    data=read_mapping(path)
    if data.get('mode')!=mode or mode not in ('sim','real'): raise ValueError('환경 파일과 mode가 다릅니다.')
    if data.get('schema_version')!=1: raise ValueError('environment schema_version=1 필요')
    for key in ('robot_id','map_id'):
        if not isinstance(data.get(key),str) or not data[key].strip(): raise ValueError(f'{key} 필요')
    if not isinstance(data.get('navigation'),dict): raise ValueError('navigation 설정 필요')
    if 'navigation_policy' in data:
        policy = read_mapping(resolve_file(root, data['navigation_policy']))
        data['navigation'] = merge_mappings(policy, data['navigation'])
    for key in ('map_yaml','route_graph','nav_params','device_config'):
        data[key]=str(resolve_file(root,data[key]))
    device=read_mapping(data['device_config'])
    for key in ('robot_id','map_id'):
        if device.get(key)!=data[key]: raise ValueError(f'환경·장치 {key} 불일치')
    # 주행에는 베드·관측·영상 설정이 필요하지 않습니다.
    if not require_survey:
        return data
    if data.get('survey_configured',True) is not True:
        raise ValueError('예찰 설정은 미완성입니다. navigation:=true survey:=false로 주행만 실행하세요.')
    data['survey_config']=str(resolve_file(root,data['survey_config']))
    survey=read_mapping(data['survey_config'])
    for key in ('robot_id','map_id'):
        if survey.get(key)!=data[key] or device.get(key)!=data[key]: raise ValueError(f'환경·장치·예찰 {key} 불일치')
    for section in survey['sections'].values():
        if resolve_file(root,section['route_file'])!=Path(data['route_graph']):
            raise ValueError('베드 정의와 주행 그래프가 다릅니다.')
    resolve_file(root,survey['vision_config'])
    return data
