"""수집한 최종 설정 전체를 비교한다. ABSENT는 기본값 확인 전의 부재이지 0이 아니다."""
import csv
import json
from pathlib import Path
import re

base = Path(__file__).resolve().parent

def flatten(value, prefix=''):
    if isinstance(value, dict):
        return {k:v for a,b in value.items()
                for k,v in flatten(b, prefix+'.'+str(a) if prefix else str(a)).items()}
    return {prefix:value}

sim = flatten(json.loads((base/'sim_effective.json').read_text())['groups'])
rows = []
for source in ('drive','harvest'):
    real = flatten(json.loads((base/('real_'+source+'_effective.json')).read_text())['groups'])
    for key in sorted(real.keys() | sim.keys()):
        if key.split('.')[0] not in ('scout','harvest','transport'):
            continue
        if source == 'harvest' and not key.startswith('harvest.'):
            continue
        a, b = real.get(key, '<ABSENT>'), sim.get(key, '<ABSENT>')
        rows.append(dict(source=source, key=key, real=a, sim=b, equal=a==b))
(base/'comparison_all.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
pattern = re.compile(r'tolerance|timeout|limit|threshold|retry|retries|age_s|settle|stopped|stable|hold|deviation|recovery|progress_checker|completion|work_path|movement|confidence|reprojection|reentry|return_position|return_heading|margin|drift|attempt|watchdog|gate|samples|fail|distance|range|velocity|linear|angular|speed|radius|clearance|waiting|wait_forever|enabled')
candidates = [r for r in rows if not r['equal'] and pattern.search(r['key'])]
(base/'threshold_candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2)+'\n')
with (base/'comparison_all.csv').open('w') as stream:
    writer = csv.DictWriter(stream,fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows({**r,'real':json.dumps(r['real'],ensure_ascii=False),
                     'sim':json.dumps(r['sim'],ensure_ascii=False)} for r in rows)
print(json.dumps(dict(compared=len(rows),equal=sum(r['equal'] for r in rows),
                     different=sum(not r['equal'] for r in rows),
                     threshold_candidates=len(candidates))))
