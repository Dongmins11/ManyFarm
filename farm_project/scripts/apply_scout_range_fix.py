#!/usr/bin/env python3
"""Set per-face 20mm harvest allowance, preserving other survey settings."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def configure(data):
    sections=data.get('sections')
    if not isinstance(sections,dict) or not sections:
        raise ValueError('sections must be a nonempty object')
    for name,section in sections.items():
        if not isinstance(section.get('harvest'),dict):
            raise ValueError(f'{name}: harvest settings are missing')
    changed=False
    for section in sections.values():
        harvest=section['harvest']
        for key,value in [('range_tolerance_m',0.02),('membership_margin_m',0.0)]:
            changed=changed or harvest.get(key)!=value
            harvest[key]=value
    return changed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,
        default=ROOT/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json')
    args=parser.parse_args();path=args.config.expanduser().resolve()
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if configure(data):
            backups=ROOT/'runs/config_backups';backups.mkdir(parents=True,exist_ok=True)
            stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
            backup=backups/f'scout_survey_before_range_{stamp}.json'
            shutil.copy2(path,backup)
            temporary=None
            try:
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                    prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
                    temporary=Path(stream.name)
                    stream.write(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
                temporary.chmod(path.stat().st_mode);temporary.replace(path)
            finally:
                if temporary is not None:temporary.unlink(missing_ok=True)
            print(f'원본 백업: {backup}')
        print(f'설정 파일: {path}')
        print('수확 허용 범위: 기본 큐브 각 면 바깥 0.02m. 좌우 배치 마진은 기존 값 유지.')
        print('scout_robot 빌드 후 예찰 서버를 재시작하세요.')
    except (OSError,ValueError,TypeError) as exc:
        parser.exit(1,f'설정 적용 실패: {exc}\n')


if __name__=='__main__':main()
