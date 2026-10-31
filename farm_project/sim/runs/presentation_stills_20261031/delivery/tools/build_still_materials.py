from pathlib import Path
import json,shutil,sys,copy
import numpy as np
from PIL import Image,ImageDraw,ImageFont
root=Path('/home/ysy/main/farm_project');out=root/'sim/runs/presentation_stills_20261031/delivery';out.mkdir(exist_ok=True)
for d in ['originals','evidence','slides','settings','tools']:(out/d).mkdir(exist_ok=True)
font='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def panel(title,sub):
 im=Image.new('RGB',(2560,1440),'white');d=ImageDraw.Draw(im);d.text((70,40),title,font=ImageFont.truetype(font,54),fill='#172b3a');d.text((72,120),sub,font=ImageFont.truetype(font,26),fill='#526572');return im,d
def paste(im,path,box):
 pic=Image.open(path).convert('RGB');scale=min(box[2]/pic.width,box[3]/pic.height);pic=pic.resize((round(pic.width*scale),round(pic.height*scale)),Image.Resampling.LANCZOS);im.paste(pic,(box[0],box[1]));return pic.size
survey=root/'sim/runs/scout_survey/b72bfef3293b';sj=json.loads((survey/'survey.json').read_text());shutil.copy2(survey/'survey.json',out/'evidence/scout-survey.json')
for i in range(1,6):
 p=survey/f'SEC01/observation_{i:03d}';dest=out/f'evidence/scout-observation-{i}';dest.mkdir(exist_ok=True)
 for n in ['rgb.png','annotated.png','observation.json','map_detections.json']:shutil.copy2(p/n,dest/n)
for n in ['rgb','annotated']:shutil.copy2(survey/f'SEC01/observation_001/{n}.png',out/f'originals/02-scout-{n}.png')
# 실제 생성된 task goal과 검출점. 연결선은 실행 궤적이 아닌 task 순서.
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
plt.rcParams['font.family']='DejaVu Sans'
fig,ax=plt.subplots(figsize=(8,8),dpi=180);ax.set_facecolor('#f4f7fa')
for i in range(1,6):
 j=json.loads((survey/f'SEC01/observation_{i:03d}/map_detections.json').read_text())
 for a in j['accepted']:
  x,y,z=a['position_map_m'];ax.scatter(x,y,c='#e4ad00' if a['class_name']=='Yellow' else '#d54a40',s=32,edgecolors='white')
tasks=sj['harvest_tasks'];xx=[t['goal_pose']['position']['x'] for t in tasks];yy=[t['goal_pose']['position']['y'] for t in tasks]
ax.plot(xx,yy,'o-',color='#2658a5',label='Harvest task order')
for i,t in enumerate(tasks):
 ax.annotate(f'W{i+1:03d} ({t["expected_count"]})',(xx[i],yy[i]),xytext=(-80,0),textcoords='offset points',fontsize=9)
 ax.plot([xx[i],-5.515],[yy[i],yy[i]],color='#8a6db1',lw=1,ls=':')
 # horizontal projection of configured work region (0.10m depth x .35m width)
 from matplotlib.patches import Rectangle
 ax.add_patch(Rectangle((-5.565,yy[i]-.19-.175),.1,.35,facecolor='#aa87ce',alpha=.18,edgecolor='#7245a4'))
sec=sj['config']['sections']['SEC01'];a=sec['survey_geometry']['start_xy_m'];b=sec['survey_geometry']['end_xy_m'];ax.plot([a[0],b[0]],[a[1],b[1]],'--',color='#178c83',label='Scout configured route')
ax.set_xlim(-7.25,-5.05);ax.set_ylim(1.4,10.6);ax.set_xlabel('Map X (m)');ax.set_ylabel('Map Y (m)');ax.grid(alpha=.2);ax.legend(loc='lower left');fig.tight_layout();fig.savefig(out/'originals/02-scout-window-route.png');plt.close(fig)
im,d=panel('02  예찰 RGB 검출 → 수확 윈도우·태스크','실제 SEC01 예찰 로그 재구성 | 5회 관측 · 9개 윈도우 · expected 13개')
paste(im,out/'originals/02-scout-annotated.png',(70,250,1350,760));paste(im,out/'originals/02-scout-window-route.png',(1480,190,1000,1050))
d.text((70,1080),'RGB-D 검출점의 map 좌표를 바탕으로 수확 태스크 생성',font=ImageFont.truetype(font,32),fill='#173b4b')
d.text((70,1150),'보라 영역: 설정 기반 작업 범위의 평면 투영\n파란 선: 생성 태스크 순서 (실제 주행 궤적 아님)\n초록 점선: 설정된 예찰 경로',font=ImageFont.truetype(font,28),fill='#526572',spacing=15)
d.text((70,1350),'출처: b72bfef3293b / SEC01 · a547f6b + 실행 당시 미커밋 설정',font=ImageFont.truetype(font,24),fill='#526572');im.save(out/'slides/02-scout-detection-windows.png')
# 기존 근접 사진 원본 재사용
old=root/'sim/runs/portfolio_staged_20261030/selected'
for n in ['harvest-grasp-closeup','harvest-working-context','transport-docking-context','sorting-pickup-closeup','sorting-transfer-closeup']:
 for ext in ['png','json']:shutil.copy2(old/(n+'.'+ext),out/('originals' if ext=='png' else 'evidence')/(n+'.'+ext))
shutil.copy2(old/'README.md',out/'evidence/reused-staged-README.md')
job=root/'sim/runs/robotarm/student/fa168336fec6435a85853e1ce4a1da4d/f86c3651c26647419ca7c3a3b913b90d'
for n in ['student_mission.json','camera_initial_metadata.json','result.json','request.json','artifact_sha256.json']:
 shutil.copy2(job/n,out/'evidence'/('u20-'+n))
for n in ['rear_initial.png','right_initial.png']:shutil.copy2(job/n,out/'originals'/('03-'+n))
events=[json.loads(s) for s in (job/'trace.jsonl').read_text().splitlines()];ev=next(e for e in events if e['event']=='CAMERA_INVENTORY');(out/'evidence/u20-camera-inventory.json').write_text(json.dumps(ev,indent=2))
r=Image.open(job/'rear_initial.png').convert('RGB');dr=ImageDraw.Draw(r)
for det in ev['detections']:
 x1,y1,x2,y2=det['bbox'];dr.rectangle((x1,y1,x2,y2),outline='#ffee22',width=4);dr.text((x1-50,y1-42),'Yellow 0.899',font=ImageFont.truetype(font,24),fill='#ffff33')
r.save(out/'originals/03-rear-target-annotated.png')
# RGB 합성 증강 비교: 기존 예찰 raw 렌더를 입력, 저장 코드의 동일 처리 함수 사용.
sys.path.insert(0,str(root/'sim/tools'));from scout_dataset.core import postprocess_rgb
cfg=json.loads((root/'sim/config/scout_dataset.json').read_text());base=cfg['postprocess'];raw=np.asarray(Image.open(out/'originals/02-scout-rgb.png').convert('RGB'));records={}
neutral=copy.deepcopy(base)
for k in ['read_noise_sigma_8bit','signal_noise_sigma_8bit','chroma_noise_sigma_8bit','gaussian_sigma_px','strong_gaussian_sigma_px']:neutral[k]=[0.,0.]
neutral.update(gain=[1.,1.],gamma=[1.,1.],strong_blur_probability=0.,motion_blur_probability=0.,jpeg_probability=0.)
variants={'original':None,'lighting':dict(neutral,gain=[.65,.65],gamma=[1.1,1.1]),'noise':dict(neutral,read_noise_sigma_8bit=[10.,10.],signal_noise_sigma_8bit=[4.,4.],chroma_noise_sigma_8bit=[2.,2.]),'blur':dict(neutral,gaussian_sigma_px=[2.8,2.8]),'production':base}
for name,c in variants.items():
 if c is None:arr,meta=raw,{'enabled':False}
 else:arr,meta=postprocess_rgb(raw,c,np.random.default_rng(930))
 Image.fromarray(arr).save(out/f'originals/04-{name}.png');records[name]={'config':c,'sampled':meta}
(out/'settings/augmentation-example.json').write_text(json.dumps({'seed':930,'scope':'illustrative RGB postprocessing, not new training data; lighting is gain/gamma not physical relighting','input':'originals/02-scout-rgb.png','variants':records},indent=2))
shutil.copy2(root/'sim/config/scout_dataset.json',out/'settings/scout_dataset-production.json');shutil.copy2(root/'sim/tools/scout_dataset/core.py',out/'tools/scout_dataset_core.py')
im,d=panel('04  합성 데이터 — 원본과 영상 증강 비교','동일 렌더 원본 · seed 930 | 밝기·노이즈·블러는 차이를 보여주기 위한 설명용 강도')
for (name,label),(x,y) in zip([('original','원본'),('lighting','밝기 / 감마'),('noise','센서 노이즈 근사'),('blur','블러')],[(70,220),(1340,220),(70,790),(1340,790)]):
 d.text((x,y-42),label,font=ImageFont.truetype(font,32),fill='#173b4b');paste(im,out/f'originals/04-{name}.png',(x,y,1150,470))
d.text((70,1360),'실제 학습 preset은 별도 보존. 04-production.png는 기존 preset 적용 결과. 광학·센서 실측 모델 아님.',font=ImageFont.truetype(font,25),fill='#526572');im.save(out/'slides/04-synthetic-comparison.png')
print(out)
