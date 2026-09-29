#!/usr/bin/env python3
"""Migrate the current sim survey to per-capture segments; preserve other tuning."""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def configure(data):
    previous=copy.deepcopy(data)
    sections=data.get('sections')
    if not isinstance(sections,dict) or not sections:raise ValueError('sections must be nonempty')
    for section_id,section in sections.items():
        section.setdefault('segmentation',{'mode':'auto','id_prefix':section_id+'_S',
            'overlap_fraction':data.get('overlap_fraction',.15)})
        section.setdefault('finish_at','last_segment')
        section.pop('segment_id',None)
    data['notes']=[note for note in data.get('notes',[]) if not note.startswith('One batch per bed is temporarily')]
    return data!=previous


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=ROOT/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json')
    a=p.parse_args();path=a.config.expanduser().resolve()
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if configure(data):
            backups=ROOT/'runs/config_backups';backups.mkdir(parents=True,exist_ok=True)
            backup=backups/('scout_survey_before_segments_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')+'.json')
            shutil.copy2(path,backup)
            temporary=None
            try:
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                    prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
                    temporary=Path(stream.name);stream.write(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
                temporary.chmod(path.stat().st_mode);temporary.replace(path)
            finally:
                if temporary is not None:temporary.unlink(missing_ok=True)
            print(f'원본 백업: {backup}')
        for sid,section in data['sections'].items():
            print(f"{sid}: segmentation={section['segmentation']['mode']}, finish_at={section['finish_at']}")
        print('기존 2cm 허용 범위·카메라·수확 설정은 보존했습니다. 예찰 서버를 재시작하세요.')
    except (OSError,ValueError,KeyError,TypeError) as exc:p.exit(1,f'적용 실패: {exc}\n')


if __name__=='__main__':main()
