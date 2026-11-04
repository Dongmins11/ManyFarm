"""콘티의 프레임 구간을 그대로 연결해 20초 무자막·자막 편집본을 만든다."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
names = ['01_overview','02_scout','03_grasp','04_deposit','05_handoff','06_transport','07_sorting']
command = ['ffmpeg','-y','-v','error','-filter_complex_threads','1']
for name in names:
    command += ['-i',str(root/(name+'.mp4'))]
filters = [f'[{i}:v]trim=start_frame=30:end_frame={90 if i==5 else 120},setpts=PTS-STARTPTS[v{i}]' for i in range(7)]
filters.append(''.join(f'[v{i}]' for i in range(7))+'concat=n=7:v=1:a=0[out]')
clean = root/'ManyFarm_20s_clean.mp4'
subprocess.run(command + ['-filter_complex',';'.join(filters),'-map','[out]','-c:v','libx264','-threads','4','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(clean)],check=True)
subtitle = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Noto Sans CJK KR,44,&H00FFFFFF,&H00FFFFFF,&H80301E12,&H80301E12,-1,0,0,0,100,100,0,0,3,14,0,1,70,70,65,1
Style: Title,Noto Sans CJK KR,66,&H00FFFFFF,&H00FFFFFF,&H80301E12,&H80301E12,-1,0,0,0,100,100,0,0,3,16,0,7,70,70,65,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:03.00,Title,,0,0,0,,ManyFarm\\N{\\fs34}시뮬레이션 연출 영상
Dialogue: 0,0:00:03.00,0:00:06.00,Caption,,0,0,0,,작물 예찰
Dialogue: 0,0:00:06.00,0:00:09.00,Caption,,0,0,0,,과실 수확 · 파지
Dialogue: 0,0:00:09.00,0:00:12.00,Caption,,0,0,0,,과실 수확 · 바구니 투입
Dialogue: 0,0:00:12.00,0:00:15.00,Caption,,0,0,0,,수확물 인계
Dialogue: 0,0:00:15.00,0:00:17.00,Caption,,0,0,0,,선별장 운송
Dialogue: 0,0:00:17.00,0:00:20.00,Caption,,0,0,0,,색상별 선별
'''
(root/'captions.ass').write_text(subtitle)
subprocess.run(['ffmpeg','-y','-v','error','-i',str(clean),'-vf','subtitles=captions.ass','-c:v','libx264','-threads','4','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(root/'ManyFarm_20s_captioned.mp4')],cwd=root,check=True)
print('20초 무자막·자막 편집본 저장 완료')
