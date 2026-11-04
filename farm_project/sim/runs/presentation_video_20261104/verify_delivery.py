"""배포 폴더를 기존 manifest와 대조한다. 촬영 이력은 덮어쓰지 않는다.

Git 체크아웃 없이 실행 가능하며 육안·물리 검사를 대신하지 않는다.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import numpy as np

root=Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_text())
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
names=['01_overview','02_scout','03_grasp','04_deposit','05_handoff','06_transport','07_sorting']
video_names=names+['ManyFarm_20s_clean','ManyFarm_20s_captioned']
records={record['file']:record for record in manifest['videos']}
assert len(records)==len(manifest['videos'])==len(video_names), '영상 목록 중복/누락'
assert set(records)=={name+'.mp4' for name in video_names}, '영상 목록 불일치'
for name in video_names:
    path=root/(name+'.mp4')
    record=records[path.name]
    assert path.stat().st_size==record['bytes'], f'{name}: 파일 크기 불일치'
    assert digest(path)==record['sha256'], f'{name}: 영상 SHA256 불일치'
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_read_frames,duration','-of','json',str(path)]))['streams'][0]
    expected=600 if name.startswith('ManyFarm') else (120 if name=='06_transport' else 150)
    assert (probe['width'],probe['height'],probe['r_frame_rate'],int(probe['nb_read_frames']))==(1920,1080,'30/1',expected),probe
    assert abs(float(probe['duration'])-expected/30)<.0001
    assert probe['codec_name']=='h264' and probe['pix_fmt']=='yuv420p',probe
    assert probe==record['stream'], f'{name}: 저장 규격과 실제 규격 불일치'
    decoded=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],capture_output=True,text=True)
    assert decoded.returncode==0 and not decoded.stderr,decoded.stderr
    assert record['full_decode_errors']==0
    if name in names:
        ledger=[json.loads(l) for l in (root/(name+'-frames.jsonl')).read_text().splitlines()]
        assert len(ledger)==expected and [r['frame'] for r in ledger]==list(range(expected))
        assert all(b['render_reference_time']>a['render_reference_time'] for a,b in zip(ledger,ledger[1:]))
        assert all(abs(r['time_s']-i/30)<1e-9 for i,r in enumerate(ledger))
        assert record['fresh_render_frames']==len(ledger)
        assert record['unique_rgb_hashes']==len({r['sha256'] for r in ledger})
        assert record['settings']=='settings/'+name+'.json'
        assert digest(root/record['settings'])==record['settings_sha256'], f'{name}: 설정 SHA256 불일치'
    print(name,expected,'frames PASS',flush=True)
a=json.loads((root/'preview/03_grasp-0149.png.json').read_text())
b=json.loads((root/'preview/04_deposit-0000.png.json').read_text())
assert a['state']['joints']==b['state']['joints']
assert a['state']['attach_fruits']==b['state']['attach_fruits']
continuity={key:float(np.max(np.abs(np.array(a['inspected'][key])-np.array(b['inspected'][key])))) for key in manifest['continuity_03_to_04_max_abs_matrix_difference']}
assert max(continuity.values())==0
assert continuity==manifest['continuity_03_to_04_max_abs_matrix_difference']
sources=('stage_portfolio_photos.py','presentation_video_frames.py','request_presentation_capture.py')
assert set(manifest['source_tools'])=={'sim/tools/'+name for name in sources}
for name in sources:
    assert digest(root/'capture_tools'/name)==manifest['source_tools']['sim/tools/'+name], f'{name}: 촬영 도구 SHA256 불일치'
print('03→04 연속성 · 설정 · 촬영 도구 SHA256 PASS; manifest 원본 보존')
