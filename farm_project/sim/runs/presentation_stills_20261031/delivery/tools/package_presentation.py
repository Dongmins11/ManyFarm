from pathlib import Path
import json,shutil,hashlib,subprocess,html,zipfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
root=Path('/home/ysy/main/farm_project');base=root/'sim/runs/presentation_stills_20261031';out=base/'delivery';font='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
for name in ['01-farm-overview','01-work-area-detail']:
 for ext in ['png','json']:shutil.copy2(base/'gui_verified'/(name+'.'+ext),out/('originals' if ext=='png' else 'evidence')/(name+'.'+ext))
# 원본 렌더에 실제 연출 좌표에서 투영한 위치 라벨. 모델/배치는 변경하지 않는다.
r=json.loads((out/'evidence/01-farm-overview.json').read_text());im=Image.open(out/'originals/01-farm-overview.png').convert('RGB');d=ImageDraw.Draw(im)
eye=np.array(r['eye']);f=np.array(r['target'])-eye;f/=np.linalg.norm(f);right=np.cross(f,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,f);scale=r['focal_mm']*1920/36
for name,point,offset in [('예찰',[-6.7,10.5,.4],(60,-25)),('수확',[-6,7.8,.8],(65,-50)),('운송',[-4,12.5,.4],(-140,-45)),('선별장',[-7.2,14.28,.35],(-170,-60))]:
 v=np.array(point)-eye;x=960+scale*np.dot(v,right)/np.dot(v,f);y=540-scale*np.dot(v,up)/np.dot(v,f);tx,ty=x+offset[0],y+offset[1]
 d.line([(x,y),(tx+45,ty+22)],fill='#173b4b',width=3);d.ellipse((x-4,y-4,x+4,y+4),fill='#173b4b');d.rounded_rectangle((tx,ty,tx+115,ty+46),radius=8,fill='white',outline='#9ab0bc',width=2);d.text((tx+15,ty+6),name,font=ImageFont.truetype(font,26),fill='#173b4b')
d.rounded_rectangle((30,25,740,110),radius=12,fill='white');d.text((50,35),'8베드 · 예찰 · 수확 · 운송 · 선별장',font=ImageFont.truetype(font,31),fill='#173b4b');d.text((50,78),'GUI 연출 / 내부 배치를 위해 지붕·외벽 숨김',font=ImageFont.truetype(font,20),fill='#526572');im.save(out/'slides/01-farm-overview-labeled.png')
# 출처와 재현조건
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
# 전체 작업 트리 패치는 촬영 외 변경을 포함하므로 전달하지 않는다.
for name in ['scout_fleet.json','scout_vision.json','student_policy.json','robotarm_physics.json']:
 shutil.copy2(root/'sim/ros_ws/src/farm_sim_config/config'/name,out/'settings'/name)
for name in ['status.json','attempt_001/process_exit.json','attempt_001/scout_result.json']:
 shutil.copy2(root/'sim/runs/section_full_cycle_return_20261031_155740'/name,out/'evidence'/('stopped-'+Path(name).name))
shutil.copy2(root/'sim/runs/section_full_cycle_return_20261031_155740_preflight/execution.json',out/'evidence/campaign-source.json')
shutil.copy2(root/'sim/tools/stage_portfolio_photos.py',out/'tools/stage_portfolio_photos.py')
shutil.copy2('/tmp/package_presentation.py',out/'tools/package_presentation.py')
items=[]
for p in sorted(out.rglob('*.png')):
 n=p.name;kind='actual simulation capture';source='sim/runs/scout_survey/b72bfef3293b';c=commit;notes='실제 예찰 원본 또는 로그 기반 설명 그림';settings=['evidence/scout-survey.json']
 if n.startswith('01-'):
  kind='GUI staged illustration';source='gui_verified';notes='원본 USD의 session layer만 변경. 전체8베드 유지; 외벽/지붕/일부 구조 숨김, 로봇 배치 연출. 물리/ROS 미실행.';settings=['evidence/01-farm-overview.json','evidence/01-work-area-detail.json','settings/fleet.json','settings/sorter.json']
 elif n.startswith('04-'):
  kind='derived augmentation illustration';notes='RGB 후처리 비교. 조명은 밝기 gain/gamma 근사이며 실제 광원 재렌더 아님. 강도는 설명용이며 학습 설정 변경 없음.';settings=['settings/augmentation-example.json','settings/scout_dataset-production.json']
 elif n.startswith('03-u20-staged'):
  kind='GUI staged sensor view';source='gui_final';notes='URDF 손목 광학 변환과 nominal U20 K로 촬영한 연출 시점. 실제 정책 실행 입력 기록 아님.';settings=['evidence/03-u20-staged-input.json','settings/u20_wrist_deployment_v1.json']
 elif n.startswith('03-'):
  source='section_full_cycle_video_20261030_174700/attempt_020 and robotarm/student/fa168336fec6435a85853e1ce4a1da4d/f86c3651c26647419ca7c3a3b913b90d';c=None;notes='기존 실제 실행 자료 재사용. 당시 정확한 프로세스 로딩 커밋은 확정 못함; artifact hash 및 영상 메타데이터 보존. rear는 D435, right는 U20.';settings=['evidence/u20-artifact_sha256.json','evidence/u20-camera_initial_metadata.json','evidence/u20-camera-inventory.json','evidence/03-actual-harvest-video.json']
  if n=='03-u20-harvest-system.png':kind='mixed evidence explanatory layout';c={'new_capture':commit,'existing_staged':'a2db5207fba8e814d4e3cad5409911615f2d56b8','actual_capture_loaded_commit':None};notes+=' 네 패널의 시점과 대상이 다르며 각 패널 구분 표시.'
 elif n.startswith(('harvest-','sorting-','transport-')):
  kind='reused staged illustration';source='sim/runs/portfolio_staged_20261030/selected';c='a2db5207fba8e814d4e3cad5409911615f2d56b8';notes='기존 headless 촬영본 재사용; 원본 자산 연출, 실제 자율 성공 증거 아님. 당시 미커밋 변경 포함.';settings=['evidence/'+p.stem+'.json','evidence/reused-staged-README.md']
 if n=='02-scout-detection-windows.png' or n=='02-scout-window-route.png':kind='actual-log explanatory visualization';notes+=' 순서 연결선은 실제 이동 궤적이 아니며 작업 범위는 설정의 XY 투영.'
 items.append(dict(file=str(p.relative_to(out)),size=list(Image.open(p).size),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),commit=c,uncommitted_changes=True,type=kind,source=source,settings=settings,description=notes))
(out/'manifest.json').write_text(json.dumps({'created':'2026-10-31 KST','capture_commit':commit,'images':items},ensure_ascii=False,indent=2))
rows=['| 파일 | 크기 | 유형 | 커밋 |','|---|---|---|---|']
for i in items:rows.append(f"| [{i['file']}]({i['file']}) | {'×'.join(map(str,i['size']))} | {i['type']} | {str(i['commit']) if i['commit'] else '로딩 커밋 미확정; 해시 보존'} |")
(out/'IMAGE_LIST.md').write_text('# 이미지 목록\n\n'+ '\n'.join(rows)+'\n\n개별 설명·설정·원본 출처·SHA256은 manifest.json 참조.\n')
(out/'README.md').write_text('''# 시뮬레이션 발표 정지 이미지 — 2026-10-31

`index.html`을 브라우저로 열면 라이트모드 목록으로 볼 수 있습니다. 팀 전달은 이 폴더 전체 또는 ZIP을 사용하세요.

## 발표에 바로 쓸 4장

1. `slides/01-farm-overview-labeled.png`: 8베드·예찰·수확·운송·선별장 배치. 새 GUI 연출 촬영, 벽/지붕을 세션에서만 숨김. 글씨 없는 원본과 작업구역 확대도 originals에 있습니다.
2. `slides/02-scout-detection-windows.png`: 최신 SEC01 실제 예찰 검출과 생성 태스크 연결. 5회 관측·9윈도우·expected 13개. 원본 RGB/검출 이미지 및 좌표 JSON 포함. 경로 그림은 로그·설정으로 재구성한 설명도이며 실제 주행 궤적/RViz 캡처가 아닙니다.
3. `slides/03-u20-harvest-system.png`: 손목 U20 RGB, 뒤쪽 D435 대상 검출, 팔 작업/바구니, 장착·파지 자세. 네 화면은 서로 다른 시점/대상입니다. GUI 연출 U20 시점과 기존 실제 시험/연출 자료를 패널마다 표시했습니다. U20는 RGB 전용이며 대상 초기 검출/깊이는 뒤쪽 D435에서 옵니다. 기존 실제 입력의 right_initial은 팔 접힘 상태라 하늘을 보며, 실제 입력 증거로 별도 보존했습니다.
4. `slides/04-synthetic-comparison.png`: 원본·밝기·노이즈·블러 비교. 기존 raw 렌더에 프로젝트의 postprocess_rgb 함수를 적용했습니다. 밝기는 gain/gamma 후처리로서 물리 광원 재렌더가 아닙니다. 비교용 강도와 기존 학습 preset은 분리했습니다. `originals/04-production.png`는 실제 기존 preset 강도로 처리한 결과입니다.

## 파일과 증거

- originals/: 글씨 없는 원본 및 개별 출력. annotated/route 파일은 이름대로 주석·그래프 파생본입니다. 원본 해상도 유지, 발표 배치에서만 크기 조절.
- evidence/: 실제 예찰/수확 로그, 기존 촬영 설정, GUI 카메라·관절·숨김 설정. 기존 자료 원본을 덮어쓰지 않았습니다.
- settings/: U20 K/장착, 시뮬 설정, 증강 seed/범위/샘플값. 실물 U20 보정 완료를 뜻하지 않습니다.
- manifest.json / IMAGE_LIST.md: 이미지별 커밋·설정·실제/연출 구분·SHA256. 기존 실제 U20 시험의 로딩 커밋은 확정 못하므로 추정값 대신 미확정과 원본 해시를 기록했습니다.
- tools/: 촬영/증강 도구 스냅샷. 원본 프로젝트 환경이 필요한 스크립트와 독립 증강 재생을 구분합니다.

## 실행 상태

사용자 요청으로 SEC01~16 시험을 종료했습니다. 캠페인 상태 STOPPED, ROS/Isaac 자식 정리 완료. 중단은 사용자 요청에 따른 것이며 전체 사이클 성공/실패 결과로 집계하지 않습니다. 시험 로그는 기존 폴더에 보존했습니다. 새 촬영은 GUI 세션이며 ROS Goal/물리 시험 없이 별도 연출했습니다. 원본 USD·공통 제어·성공 조건은 변경하지 않았습니다.

## 증강 재현

이 폴더에서 `python3 tools/reproduce_augmentation.py` 실행 (numpy, Pillow, opencv-python 필요). `reproduced/`에 출력하며 기존 원본을 덮어쓰지 않습니다. seed930과 저장한 설정 사용.

촬영 실패 초안(벽 가림, 정수 좌표 처리 오류)은 전달 이미지에서 제외하고 상위 gui_capture 로그에 보존했습니다. GUI 전경은 예찰 mast/U20/선별장 포함 여부와 8베드·벽 가림을 직접 확인했습니다. 실제 시험 전체 성공 또는 모델 성능 향상의 증거로 확대하지 마세요.
''')
slides=sorted((out/'slides').glob('*.png'))
body=''.join(f'<article><h2>{html.escape(p.stem)}</h2><a href="{p.relative_to(out)}"><img src="{p.relative_to(out)}"></a></article>' for p in slides)
extras=''.join(f'<li><a href="{i["file"]}">{i["file"]}</a> — {i["type"]}</li>' for i in items if not i['file'].startswith('slides/'))
(out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="color-scheme" content="light"><title>농장 시뮬레이션 발표 이미지</title><style>body{background:#fff;color:#203440;font:16px sans-serif;max-width:1400px;margin:40px auto;padding:20px}img{width:100%;border:1px solid #dce4e9}article{margin:40px 0}a{color:#195e91}li{margin:10px}</style><h1>농장 시뮬레이션 발표 이미지</h1><p>2026-10-31 · 실제 기록 / GUI 연출 / 로그 설명도 구분</p><p><a href="README.md">사용 안내</a> · <a href="IMAGE_LIST.md">원본 목록</a> · <a href="manifest.json">설정·출처·해시</a></p>'+body+'<h2>원본과 개별 이미지</h2><ul>'+extras+'</ul></html>')
print(len(items),'images indexed')
