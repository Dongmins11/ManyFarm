"""발표 연출용 키프레임 보간/동기 렌더 저장. 실제 업무 로직과 연결하지 않는다."""
from __future__ import annotations
import copy
import hashlib
import json
import subprocess
from pathlib import Path
import numpy as np


def merge(base: dict, patch: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in patch.items():
        result[key] = merge(result.get(key, {}), value) if isinstance(value, dict) else copy.deepcopy(value)
    return result


def blend(a, b, u: float, key: str = ''):
    from scipy.spatial.transform import Rotation, Slerp
    if key in ('attach_fruits','show','hide','inspect','ik'):
        return copy.deepcopy(a if u < 1 else b)
    if isinstance(a, dict) and isinstance(b, dict):
        return {k:blend(a.get(k,b.get(k)),b.get(k,a.get(k)),u,k) for k in a.keys() | b.keys()}
    if key == 'matrix':
        x,y=np.asarray(a,float),np.asarray(b,float)
        t=np.eye(4);t[:3,3]=x[:3,3]*(1-u)+y[:3,3]*u
        sx=np.linalg.norm(x[:3,:3],axis=0);sy=np.linalg.norm(y[:3,:3],axis=0)
        rotation=Slerp([0,1],Rotation.from_matrix([x[:3,:3]/sx,y[:3,:3]/sy]))([u]).as_matrix()[0]
        t[:3,:3]=rotation*(sx*(1-u)+sy*u)
        return t.tolist()
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        return a*(1-u)+b*u
    if isinstance(a,list) and isinstance(b,list) and len(a)==len(b) and all(isinstance(v,(int,float)) for v in a+b):
        return (np.array(a)*(1-u)+np.array(b)*u).tolist()
    return copy.deepcopy(a if u < 1 else b)


def state_at(request: dict, t: float) -> dict:
    frames=[]; state=copy.deepcopy(request['base'])
    for item in request['keyframes']:
        state=merge(state,item.get('state',{}));frames.append((item['time'],state))
    if t <= frames[0][0]:return copy.deepcopy(frames[0][1])
    for (ta,a),(tb,b) in zip(frames,frames[1:]):
        if t <= tb:
            u=(t-ta)/(tb-ta)
            if request.get('easing','smooth')=='smooth':u=u*u*(3-2*u)
            return blend(a,b,u)
    return copy.deepcopy(frames[-1][1])


def capture(request: dict, out: Path, app: object, camera: object, apply_state, inspect_state) -> None:
    from PIL import Image
    name=request['name'];fps=int(request.get('fps',30));duration=float(request['duration_s'])
    if fps != 30 or duration not in (4,5,7):
        raise ValueError('발표 원본은 30fps, 4/5/7초만 지원합니다.')
    count=round(fps*duration); previews=out/'preview';previews.mkdir(exist_ok=True)
    preview_only=request.get('preview_only',False)
    indices=sorted({0,count//2,count-1} | {min(count-1,round(f['time']*fps)) for f in request['keyframes']}) if preview_only else range(count)
    if preview_only and 'preview_frames' in request:
        indices=sorted(set(request['preview_frames']))
        if not indices or any(not isinstance(i,int) or not 0 <= i < count for i in indices):
            raise ValueError('preview_frames must contain valid frame indices')
    apply_state(state_at(request,0))
    for _ in range(80):app.update()
    def render_id():
        value=camera.get_current_frame().get('rendering_frame',0)
        if isinstance(value,dict):
            return value['referenceTimeNumerator']/value['referenceTimeDenominator']
        return float(value)
    encoder=None; ledger=[]; saved=[]
    if not preview_only:
        encoder=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','medium','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(out/(name+'.mp4'))],stdin=subprocess.PIPE)
    try:
        for index in indices:
            state=state_at(request,index/fps)
            before=render_id()
            apply_state(state)
            # 자세 적용 전 프레임을 저장하지 않도록 동기 렌더를 진행한다.
            for _ in range(int(request.get('preview_warmup_frames',48)) if preview_only else 6):app.update()
            frame=camera.get_current_frame(); after=render_id()
            if after <= before:raise RuntimeError(f'new rendered frame missing: {index} {before}->{after}')
            rgb=np.asarray(camera.get_rgb(),dtype=np.uint8)
            if rgb.shape!=(1080,1920,3) or np.std(rgb)<1:raise RuntimeError('invalid camera RGB')
            if preview_only or index in (0,count//2,count-1):
                filename=f'{name}-{index:04d}.png';Image.fromarray(rgb).save(previews/filename);saved.append(filename)
                (previews/(filename+'.json')).write_text(json.dumps(dict(frame=index,time_s=index/fps,state=state,inspected=inspect_state(state)),indent=2)+'\n')
            if encoder:encoder.stdin.write(rgb.tobytes())
            ledger.append(dict(frame=index,time_s=index/fps,render_reference_time=after,render_time=float(frame.get('rendering_time',0)),sha256=hashlib.sha256(rgb.tobytes()).hexdigest()))
            if index%30==0:print(f'VIDEO_FRAME {name} {index}/{count}',flush=True)
        if encoder:
            encoder.stdin.close()
            if encoder.wait(timeout=60)!=0:raise RuntimeError('ffmpeg failed')
    except BaseException:
        if encoder and encoder.poll() is None:encoder.kill();encoder.wait()
        raise
    meta=dict(request,scope='GUI staged animation; no autonomous performance claim',resolution=[1920,1080],frames=len(ledger),expected_frames=count,fps=fps,preview_only=preview_only,previews=saved,final_state=state_at(request,(count-1)/fps),inspected=inspect_state(state_at(request,(count-1)/fps)))
    suffix='-preview' if preview_only else ''
    (out/(name+suffix+'.json')).write_text(json.dumps(meta,indent=2)+'\n')
    (out/(name+suffix+'-frames.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in ledger))
    print('VIDEO_SAVED '+name+suffix,flush=True)
