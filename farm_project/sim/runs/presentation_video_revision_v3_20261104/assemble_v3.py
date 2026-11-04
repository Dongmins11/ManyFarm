"""Build the 22-second V3 edit from immutable raw clips and a real observation inset.

Requires ffmpeg (libx264, xfade, libass), Pillow and Noto Sans CJK fonts.
No simulator, GUI, ROS or manifest write is performed. All cut positions use frames.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
NAMES = ['01_overview', '02_scout', '03_grasp', '04_deposit',
         '05_handoff', '06_transport', '07_sorting']
TRIMS = [(30, 123), (27, 123), (27, 120), (30, 123),
         (27, 123), (27, 93), (27, 180)]
FONT_DIR = Path('/usr/share/fonts/opentype/noto')
ENCODE = ['-an', '-c:v', 'libx264', '-threads', '4', '-preset', 'fast',
          '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
          '-r', '30', '-frames:v', '660']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, root):
    subprocess.run(command, cwd=root, check=True)


def card_image(root, config):
    x, y, width, height = config['rect_px']
    px, py, panel_width, panel_height = config['panel_rect_px']
    assert width / height == 640 / 384 and 480 <= width <= 560
    assert px >= 0 and py >= 0 and px + panel_width <= 1920 and py + panel_height <= 1080
    image = Image.open(root / config['image_path']).convert('RGB')
    assert image.size == (640, 384)
    panel = Image.new('RGBA', (panel_width, panel_height), (13, 34, 41, 245))
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle((0, 0, panel_width - 1, panel_height - 1),
                           radius=10, outline='#79dec6', width=2)
    title = ImageFont.truetype(str(FONT_DIR / 'NotoSansCJK-Bold.ttc'), 25)
    detail = ImageFont.truetype(str(FONT_DIR / 'NotoSansCJK-Regular.ttc'), 22)
    draw.text((17, 11), config['title'], fill='#b3f2df', font=title)
    panel.paste(image.resize((width, height), Image.Resampling.LANCZOS), (x - px, y - py))
    draw.rectangle((x - px - 1, y - py - 1, x - px + width, y - py + height),
                   outline='#79dec6', width=1)
    draw.text((17, y - py + height + 7), config['description'], fill='#e6f0f4', font=detail)
    path = root / 'assets/02_scout_insert_card.png'
    panel.save(path)
    return path


def make_placement_previews(root, config, card):
    destination = root / 'qa'
    destination.mkdir(exist_ok=True)
    for frame in (0, 75, 149):
        source = root / 'preview' / f'02_scout-{frame:04}.png'
        if not source.exists():
            continue
        base = Image.open(source).convert('RGBA')
        assert base.size == (1920, 1080)
        base.alpha_composite(Image.open(card).convert('RGBA'), tuple(config['panel_rect_px'][:2]))
        base.convert('RGB').save(destination / f'02_scout-inset-placement-{frame:04}.png')


def subtitles(root):
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
            (15, 17, '06  운송', '수확물을 선별장으로 운송'),
            (17, 20.6, '07  선별', '과실을 해당 분류함으로 이동')]
    for start, end, label, caption in rows:
        start += .13
        if end != 20.6:
            end -= .13
        for style, text in [('Label', label), ('Caption', caption)]:
            events.append(f'Dialogue: 0,0:00:{start:05.2f},0:00:{end:05.2f},{style},,0,0,0,,{{\\fad(150,300)}}{text}')
    path = root / 'captions.ass'
    path.write_text(header + '\n'.join(events) + '\n')
    return path


def build_clean(root, inputs):
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
        '[x3][v4]xfade=transition=fade:duration=0.2:offset=11.9[x4]',
        '[x4][v5]xfade=transition=fade:duration=0.2:offset=14.9[x5]',
        '[x5][v6]xfade=transition=fade:duration=0.2:offset=16.9[x6]',
        # 24 displayed fade frames (636..659); the last delivered sample is black.
        '[x6]fps=30,fade=t=out:start_frame=636:nb_frames=23,format=yuv420p[out]',
    ]
    run(command + ['-filter_complex', ';'.join(filters), '-map', '[out]'] + ENCODE +
        [str(root / 'ManyFarm_22s_clean.mp4')], root)


def build_captioned(root, config, card):
    subtitles(root)
    px, py = config['panel_rect_px'][:2]
    start, end, fade = 3 + config['start_s'], 3 + config['end_s'], config['fade_s']
    filters = (f'[1:v]format=rgba,fade=t=in:st={start}:d={fade}:alpha=1,'
               f'fade=t=out:st={end-fade}:d={fade}:alpha=1[inset];'
               f'[0:v][inset]overlay={px}:{py}:eof_action=pass:shortest=1,'
               'subtitles=captions.ass,format=yuv420p[out]')
    run(['ffmpeg', '-y', '-v', 'error', '-filter_complex_threads', '1',
         '-i', str(root / 'ManyFarm_22s_clean.mp4'), '-loop', '1', '-framerate', '30',
         '-i', str(card), '-filter_complex', filters, '-map', '[out]'] + ENCODE +
        [str(root / 'ManyFarm_22s_captioned.mp4')], root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=ROOT)
    parser.add_argument('--grasp', type=Path, help='Preserved original 03_grasp.mp4')
    parser.add_argument('--qa-only', action='store_true', help='Only build inset card and placement stills')
    parser.add_argument('--captions-only', action='store_true', help='Reuse an already assembled clean edit')
    args = parser.parse_args()
    root = args.run_dir.resolve()
    config = json.loads((root / 'overlays/02_scout_insert.json').read_text())
    card = card_image(root, config)
    make_placement_previews(root, config, card)
    if args.qa_only:
        return
    if config['placement_status'] != 'verified on final V3 start, middle and end':
        raise ValueError('Confirm the final V3 inset placement before producing delivery edits')
    inputs = [root / f'{name}.mp4' for name in NAMES]
    inputs[2] = (args.grasp or root.parent / 'presentation_video_20261104/03_grasp.mp4').resolve()
    hashes = {str(path): digest(path) for path in inputs}
    if not args.captions_only:
        build_clean(root, inputs)
    build_captioned(root, config, card)
    assert hashes == {str(path): digest(path) for path in inputs}, 'Raw source changed during edit'
    decisions = {
        'fps': 30, 'frames': 660, 'duration_s': 22,
        'core_boundaries_frames': [0, 90, 180, 270, 360, 450, 510, 660],
        'source_trims_with_handles': [dict(clip=name, start_frame=a, end_frame_exclusive=b,
                                          sha256=hashes[str(path)])
                                     for name, (a, b), path in zip(NAMES, TRIMS, inputs)],
        'transitions': {'dissolve_duration_frames': 6, 'centres_frames': [90, 180, 360, 450, 510],
                        'direct_cut_03_to_04_frame': 270},
        'ending': {'stable_hold_start_frame': 600, 'fade_start_frame': 636, 'fade_duration_frames': 24},
        'inset': config, 'raw_sources_unchanged': True,
        'outputs': {name: digest(root / name) for name in
                    ('ManyFarm_22s_clean.mp4', 'ManyFarm_22s_captioned.mp4')},
    }
    (root / 'edit_decisions.json').write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + '\n')
    print('22-second clean and captioned edits complete; raw sources unchanged.')


if __name__ == '__main__':
    main()
