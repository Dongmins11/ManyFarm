"""환경 파일의 경로를 project_root 기준으로 해석합니다. sim/real 로직을 복제하지 않습니다."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import yaml


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


def load_environment(path: str | Path, root: Path, mode: str, *, require_survey: bool = True) -> dict[str,Any]:
    """환경별 지도·그래프·예찰·장치 설정의 한 선택점입니다."""
    data=read_mapping(path)
    if data.get('mode')!=mode or mode not in ('sim','real'): raise ValueError('환경 파일과 mode가 다릅니다.')
    if data.get('schema_version')!=1: raise ValueError('environment schema_version=1 필요')
    for key in ('robot_id','map_id'):
        if not isinstance(data.get(key),str) or not data[key].strip(): raise ValueError(f'{key} 필요')
    if not isinstance(data.get('navigation'),dict): raise ValueError('navigation 설정 필요')
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
