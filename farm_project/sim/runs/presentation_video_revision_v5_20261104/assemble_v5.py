"""Build the 25-second V5 edit from immutable raw clips, with captions and no scout inset.

Requires ffmpeg (libx264, xfade, libass), Noto Sans CJK fonts.
No simulator, GUI, ROS or manifest write is performed. All cut positions use frames.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent
V3_NAME = 'presentation_video_revision_v3_20261104'
NAMES = ['01_overview', '02_scout', '03_grasp', '04_deposit',
         '05_handoff_continuity', '06_07_transport_sorting']
TRIMS = [(30, 123), (27, 123), (27, 120), (30, 120),
         (30, 120), (30, 330)]
FONT_DIR = Path('/usr/share/fonts/opentype/noto')
ENCODE = ['-an', '-c:v', 'libx264', '-threads', '4', '-preset', 'fast',
          '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
          '-r', '30', '-frames:v', '750']


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list, root: Path) -> None:
    subprocess.run(command, cwd=root, check=True)


def subtitles(root: Path) -> Path:
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Noto Sans CJK KR,42,&H00FFFFFF,&H00FFFFFF,&H80301E12,&H80301E12,-1,0,0,0,100,100,0,0,3,12,0,7,80,80,880,1
Style: Label,Noto Sans CJK KR,29,&H00C6DE79,&H00C6DE79,&H80301E12,&H80301E12,-1,0,0,0,100,100,0,0,3,8,0,7,80,80,830,1
Style: Title,Noto Sans CJK KR,66,&H00FFFFFF,&H00FFFFFF,&H80301E12,&H80301E12,-1,0,0,0,100,100,0,0,3,12,0,7,80,80,830,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = [r'Dialogue: 0,0:00:00.10,0:00:02.85,Title,,0,0,0,,{\fad(150,150)}ManyFarm\N{\fs30\c&H00C6DE79&}시뮬레이션 연출 영상']
    rows = [(3, 6, '02  예찰', '작물 예찰 · 수확 태스크 생성'),
            (6, 9, '03  수확', '과실을 잡아 수확'),
            (9, 12, '04  적재', '수확한 과실을 바구니에 투입'),
            (12, 15, '05  인계', '바구니를 열어 수확물을 전달'),
            (15, 18.8, None, '선별장 도킹 · 수확물 배출'),
            (19.0, 23.6, None, '혼합 과실을 색상별로 분류')]
    events.append(r'Dialogue: 0,0:00:15.13,0:00:23.60,Label,,0,0,0,,{\fad(150,300)}운송 · 선별')
    for start, end, label, caption in rows:
        start += .13
        if end != 23.6:
            end -= .13
        for style, text in [('Label', label), ('Caption', caption)]:
            if text is None:
                continue
            events.append(f'Dialogue: 0,0:00:{start:05.2f},0:00:{end:05.2f},{style},,0,0,0,,{{\\fad(150,300)}}{text}')
    path = root / 'captions.ass'
    path.write_text(header + '\n'.join(events) + '\n')
    return path


def build_clean(root: Path, inputs: list) -> None:
    command = ['ffmpeg', '-y', '-v', 'error', '-filter_complex_threads', '1']
    for path in inputs:
        command += ['-i', str(path)]
    filters = [f'[{i}:v]fps=30,trim=start_frame={start}:end_frame={end},'
               f'settb=AVTB,setpts=PTS-STARTPTS,format=yuv420p[v{i}]'
               for i, (start, end) in enumerate(TRIMS)]
    filters += [
        '[v0][v1]xfade=transition=fade:duration=0.2:offset=2.9[x1]',
        '[x1][v2]xfade=transition=fade:duration=0.2:offset=5.9[x2]',
        '[x2][v3]concat=n=2:v=1:a=0[x3]',
        '[x3][v4]concat=n=2:v=1:a=0[x4]',
        '[x4][v5]concat=n=2:v=1:a=0[x5]',
        # 24 fade samples (726..749), ending on an exactly black sample.
        '[x5]fps=30,fade=t=out:start_frame=726:nb_frames=23,format=yuv420p[out]',
    ]
    run(command + ['-filter_complex', ';'.join(filters), '-map', '[out]'] + ENCODE +
        [str(root / 'ManyFarm_25s_clean.mp4')], root)


def build_captioned(root: Path) -> None:
    """무자막 편집본에 하단 자막만 합성한다. 사진/패널 입력은 받지 않는다."""
    subtitles(root)
    run(['ffmpeg', '-y', '-v', 'error', '-filter_threads', '1',
         '-i', str(root / 'ManyFarm_25s_clean.mp4'),
         '-vf', 'subtitles=captions.ass,format=yuv420p'] + ENCODE +
        [str(root / 'ManyFarm_25s_captioned.mp4')], root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=ROOT)
    parser.add_argument('--grasp', type=Path, help='Preserved original 03_grasp.mp4')
    parser.add_argument('--captions-only', action='store_true', help='Reuse an already assembled clean edit')
    args = parser.parse_args()
    root = args.run_dir.resolve()
    v3 = root.parent / V3_NAME
    inputs = [v3 / f'{name}.mp4' for name in NAMES[:4]] + [root / f'{name}.mp4' for name in NAMES[4:]]
    inputs[2] = (args.grasp or root.parent / 'presentation_video_20261104/03_grasp.mp4').resolve()
    hashes = {str(path): digest(path) for path in inputs}
    originals = json.loads((root / 'original_hashes.json').read_text())
    for path in inputs[:4]:
        source_key = path.resolve().relative_to(root.parents[3]).as_posix()
        if hashes[str(path)] != originals[source_key]:
            raise ValueError('Preserved input changed: ' + source_key)
    if not args.captions_only:
        build_clean(root, inputs)
    build_captioned(root)
    assert hashes == {str(path): digest(path) for path in inputs}, 'Raw source changed during edit'
    decisions = {
        'fps': 30, 'frames': 750, 'duration_s': 25,
        'core_boundaries_frames': [0, 90, 180, 270, 360, 450, 750],
        'source_trims_with_handles': [dict(clip=name, start_frame=a, end_frame_exclusive=b,
                                          sha256=hashes[str(path)])
                                     for name, (a, b), path in zip(NAMES, TRIMS, inputs)],
        'transitions': {'dissolve_duration_frames': 6, 'centres_frames': [90, 180],
                        'direct_cut_frames': [270, 360, 450]},
        'ending': {'stable_hold_start_frame': 690, 'fade_start_frame': 726, 'fade_duration_frames': 24},
        'continuous_segment': {'file': '06_07_transport_sorting.mp4',
            'timeline_frames': [450, 750], 'source_frames': [30, 330],
            'internal_cuts': [], 'action_end_frame': 690},
        'inset': {'enabled': False, 'reason': 'V5: source video and bottom captions only; no image/panel/overlay input'}, 'raw_sources_unchanged': True,
        'outputs': {name: digest(root / name) for name in
                    ('ManyFarm_25s_clean.mp4', 'ManyFarm_25s_captioned.mp4')},
    }
    (root / 'edit_decisions.json').write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + '\n')
    print('25-second clean and captioned edits complete; raw sources unchanged.')


if __name__ == '__main__':
    main()
