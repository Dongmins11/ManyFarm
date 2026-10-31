from pathlib import Path
import json,shutil,hashlib,zipfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
root=Path('/home/ysy/main/farm_project');b=root/'sim/runs/presentation_stills_20261031';out=b/'delivery';gui=b/'gui_topdown'
for ext in ['png','json']:shutil.copy2(gui/('01-farm-overview.'+ext),out/('originals' if ext=='png' else 'evidence')/('01-farm-overview.'+ext))
shutil.copy2(root/'sim/ros_ws/src/farm_sim_config/config/station_spawn.json',out/'settings/station_spawn.json')
r=json.loads((gui/'01-farm-overview.json').read_text());im=Image.open(out/'originals/01-farm-overview.png').convert('RGB');d=ImageDraw.Draw(im);font=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',23)
eye=np.array(r['eye']);f=np.array(r['target'])-eye;f/=np.linalg.norm(f);right=np.cross(f,r['up']);right/=np.linalg.norm(right);up=np.cross(right,f);scale=r['focal_mm']*1920/36
for label,point in [('예찰',[-5.,13.25,.4]),('수확',[-2.,13.25,.65]),('운송',[2.,13.25,.4]),('선별장',[-7.2,14.28,.35])]:
 v=np.array(point)-eye;x=960+scale*np.dot(v,right)/np.dot(v,f);y=540-scale*np.dot(v,up)/np.dot(v,f);tx,ty=x+45,y-20
 d.line([(x,y),(tx,ty+20)],fill='#173b4b',width=2);d.rounded_rectangle((tx,ty,tx+100,ty+42),radius=7,fill='white');d.text((tx+12,ty+4),label,font=font,fill='#173b4b')
im.save(out/'slides/01-farm-overview-labeled.png')
m=json.loads((out/'manifest.json').read_text())
for i in m['images']:
 if i['file'] in ['originals/01-farm-overview.png','slides/01-farm-overview-labeled.png']:
  i.update(sha256=hashlib.sha256((out/i['file']).read_bytes()).hexdigest(),source='gui_topdown',settings=['evidence/01-farm-overview.json','settings/station_spawn.json','settings/fleet.json','settings/sorter.json'],description='GUI 수직 탑뷰. 로봇3대는 설정의 스테이션 xy/yaw 배치, 수확팔 접힘 자세. map +Y는 화면 왼쪽, +X는 위쪽. 29.5m 수평 시야로 배경 최소화. 외벽/지붕은 session layer에서 숨김. 물리/ROS 미실행.')
(out/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
p=out/'README.md';s=p.read_text().replace('새 GUI 연출 촬영, 벽/지붕을 세션에서만 숨김. 글씨 없는 원본과 작업구역 확대도 originals에 있습니다.','새 GUI 수직 탑뷰 촬영. 세 로봇은 station_spawn.json의 스테이션 위치·방향에 배치하고 8베드 바깥 배경을 최소화했습니다. 벽/지붕은 세션에서만 숨겼습니다. 글씨 없는 원본은 originals에 있으며, 기존 작업구역 확대는 이전 연출 위치의 보조 자료로 그대로 유지했습니다.')
p.write_text(s)
# 예전 실행용 포장 스크립트는 현행 전경을 덮어쓰지 않도록 기록용임을 명시.
shutil.copy2('/tmp/update_topdown_delivery.py',out/'tools/update_topdown_delivery.py')
with (out/'README.md').open('a') as f:f.write('\n전경 변경 이력: 수직 탑뷰/스테이션 배치로 전경 2PNG만 교체. 다른 32PNG는 이전 전달본과 SHA256 동일 확인. tools/package_presentation.py는 이전 사선 구도 포장 당시 기록이며 최종 전경 갱신 기록은 tools/update_topdown_delivery.py입니다.\n')
old=json.loads((b/'before_topdown/manifest.json').read_text())
for i in old['images']:
 if i['file'] not in ['originals/01-farm-overview.png','slides/01-farm-overview-labeled.png']:assert hashlib.sha256((out/i['file']).read_bytes()).hexdigest()==i['sha256'],i['file']
paths=[p for p in out.rglob('*') if p.is_file() and 'reproduced' not in p.parts and '__pycache__' not in p.parts and p.name!='SHA256SUMS.txt']
(out/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in sorted(paths)))
archive=b/'presentation-stills-20261031.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in paths+[out/'SHA256SUMS.txt']:z.write(p,Path('presentation-stills-20261031')/p.relative_to(out))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
(gui/'request.json').write_text('{"quit":true}')
print('overview replaced; 32 other PNG unchanged; ZIP checked')
