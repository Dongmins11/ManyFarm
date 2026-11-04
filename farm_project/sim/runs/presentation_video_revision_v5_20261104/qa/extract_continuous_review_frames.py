"""완료된 실제 MP4의 모든 프레임을 디코딩해 순서별 검수 시트를 만든다."""
from pathlib import Path
import hashlib
import json
import subprocess
from PIL import Image, ImageDraw

RUN=Path(__file__).resolve().parent.parent
QA=RUN/'qa'
OUT=QA/'all_frames'
NAME='06_07_transport_sorting'

def main():
    OUT.mkdir(exist_ok=True)
    meta=json.loads((RUN/(NAME+'.json')).read_text())
    assert meta['frames']==meta['expected_frames']==360 and not meta['preview_only']
    video=RUN/(NAME+'.mp4'); original_sha=hashlib.sha256(video.read_bytes()).hexdigest()
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_streams','-of','json',str(video)]))
    stream=probe['streams'][0]
    assert stream['width']==1920 and stream['height']==1080 and int(stream['nb_read_frames'])==360
    assert stream['r_frame_rate']=='30/1'
    key={0,69,87,99,114,138,150,165,168,175,183,193,200,219,222,232,245,250,267,270,329,359}
    proc=subprocess.Popen(['ffmpeg','-v','error','-i',str(video),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE)
    sheets=[];frames=[];full=[];sheet=None
    for n in range(360):
        raw=proc.stdout.read(1920*1080*3)
        assert len(raw)==1920*1080*3,(n,len(raw))
        image=Image.frombytes('RGB',(1920,1080),raw)
        frames.append({'frame':n,'time_s':n/30,'decoded_rgb_sha256':hashlib.sha256(raw).hexdigest()})
        if n in key:
            path=OUT/f'{NAME}-mp4-frame-{n:04d}.png';image.save(path)
            full.append({'frame':n,'path':str(path.relative_to(RUN)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        if n%20==0:sheet=Image.new('RGB',(1920,1470),(18,18,18))
        x=(n%20)%4*480;y=(n%20)//4*294
        sheet.paste(image.resize((480,270),Image.Resampling.LANCZOS),(x,y))
        ImageDraw.Draw(sheet).text((x+8,y+273),f'{n:03d} | {n/30:.3f}s',fill='white')
        if n%20==19:
            path=OUT/f'{NAME}-mp4-allframes-{n-19:03d}-{n:03d}.jpg';sheet.save(path,quality=88)
            sheets.append({'frame_range':[n-19,n],'path':str(path.relative_to(RUN)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    assert proc.stdout.read()==b'' and proc.wait()==0
    assert hashlib.sha256(video.read_bytes()).hexdigest()==original_sha
    result={'video':str(video.relative_to(RUN)),'video_sha256':original_sha,'decoded_frame_count':len(frames),'stream':stream,
            'contact_sheets':sheets,'full_resolution_frames':full,'frames':frames,'review_performed_by_extraction':False}
    (QA/(NAME+'-mp4-decoded-frames.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'video_sha256':original_sha,'decoded_frames':len(frames),'sheets':len(sheets),'full_resolution':len(full)}))

if __name__=='__main__':main()
