"""Extract key-phase QA from encoded MP4 frames, independently of GUI previews."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
PHASES = {
    '05_handoff_continuity': [0., .9, 1., 1.1, 1.2, 1.35, 1.5, 1.65, 1.8, 1.95,
                              2.1, 2.3, 2.5, 2.7, 3., 3.35, 3.5, 3.9, None],
    '06_07_transport_sorting': [0., 1., 1.8, 2.3, 2.8, 3.3, 3.8, 4.3, 4.6, 5.,
                              5.6, 6.2, 6.8, 7.4, 8., 8.6, 9., 10., 10.9, None],
    'ManyFarm_25s_captioned': [1.5, 3.5, 4.5, 5.5, 7.5, 269 / 30, 9., 10.5,
                             359 / 30, 12., 12.1, 13., 13.5, 14.5, 449 / 30,
                             15., 15.1, 16.5, 18., 19.5, 21., 22.5, 23.5, 24.2, 24.6, 749 / 30],
}
PHASES['ManyFarm_25s_clean'] = list(PHASES['ManyFarm_25s_captioned'])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('clips', nargs='*', metavar='CLIP', help=', '.join(PHASES))
    args = parser.parse_args()
    args.clips = args.clips or list(PHASES)
    if any(stem not in PHASES for stem in args.clips):
        parser.error('Unknown clip; expected ' + ', '.join(PHASES))
    qa = ROOT / 'qa'
    qa.mkdir(exist_ok=True)
    font = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 23)
    for stem in args.clips:
        source = ROOT / f'{stem}.mp4'
        if stem.startswith('ManyFarm_'):
            count = json.loads((ROOT / 'edit_decisions.json').read_text())['frames']
        else:
            metadata = json.loads((ROOT / f'{stem}.json').read_text())
            assert not metadata['preview_only'] and metadata['frames'] == metadata['expected_frames']
            count = metadata['frames']
        times = list(PHASES[stem])
        if stem == '05_handoff_continuity':
            motion = json.loads((ROOT / 'settings/05_handoff_continuity_evidence.json').read_text())
            times += [max(0., min((count - 1) / 30, event + delta / 30))
                      for event in motion.get('timing', {}).values() if isinstance(event, (int, float))
                      for delta in (-1, 0, 1)]
        if stem == '06_07_transport_sorting':
            # 실제 베이크 시각의 집기/놓임 직전·순간·직후도 남긴다.
            motion = json.loads((ROOT / 'settings/06_07_motion_evidence.json').read_text())
            events = list(motion['mechanism'].values())
            events += [pick[key] for pick in motion['picks']
                       for key in ('attach_time_s', 'release_time_s')]
            times += [max(0., min((count - 1) / 30, event + delta / 30))
                      for event in events if isinstance(event, (int, float))
                      for delta in (-1, 0, 1)]
        indices = sorted({count - 1 if t is None else math.floor(t * 30 + .5) for t in times})
        assert indices == sorted(set(indices)) and indices[-1] < count
        selection = '+'.join(f'eq(n\\,{index})' for index in indices)
        temporary = qa / f'{stem}-phase-extract-%02d.png'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(source), '-vf', f'select={selection}',
                        '-vsync', '0', '-frames:v', str(len(indices)), str(temporary)], check=True)
        sheet = Image.new('RGB', (4 * 640, math.ceil(len(indices) / 4) * 394), '#11242d')
        draw = ImageDraw.Draw(sheet)
        records = []
        for number, index in enumerate(indices):
            path = qa / f'{stem}-mp4-frame-{index:04}.png'
            (qa / f'{stem}-phase-extract-{number+1:02d}.png').replace(path)
            with Image.open(path) as image:
                assert image.size == (1920, 1080)
                sheet.paste(image.resize((640, 360), Image.Resampling.LANCZOS),
                            ((number % 4) * 640, (number // 4) * 394 + 34))
            draw.text(((number % 4) * 640 + 12, (number // 4) * 394 + 2),
                      f'{stem}  frame {index:03d}  /  {index/30:.3f}s', fill='#b3f2df', font=font)
            records.append({'requested_time_s': index / 30, 'frame': index,
                            'actual_time_s': index / 30, 'file': path.relative_to(ROOT).as_posix(),
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        sheet_path = qa / f'{stem}-mp4-keyphases.jpg'
        sheet.save(sheet_path, quality=93)
        evidence = {'source': source.name, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'extraction': 'ffmpeg select by decoded MP4 frame number; no GUI preview substitution',
                    'fps': 30, 'frames': records, 'contact_sheet': sheet_path.relative_to(ROOT).as_posix()}
        (qa / f'{stem}-mp4-keyphases.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(f'{stem}: {len(indices)} decoded MP4 frames and key-phase sheet saved')
    # 검수 편의를 위한 실제 MP4 플레이어다. 파일 생성으로 시각 검수 PASS를 만들지 않는다.
    players = []
    for stem in PHASES:
        if (ROOT / (stem + '.mp4')).is_file():
            players.append(f'<section><h2>{stem}</h2><video controls preload="metadata" '
                           f'src="../{stem}.mp4"></video><p>'
                           '<button onclick="this.closest(\'section\').querySelector(\'video\').playbackRate=1">1×</button> '
                           '<button onclick="this.closest(\'section\').querySelector(\'video\').playbackRate=0.25">0.25×</button>'
                           '</p></section>')
    (qa / 'playback_review.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<title>V5 실제 MP4 재생 검수</title><style>body{font:16px sans-serif;background:#17252b;color:white;'
        'max-width:1500px;margin:2em auto}video{width:100%}button{font-size:20px;padding:.4em 1em}</style>'
        '<h1>V5 실제 MP4 정상·저속 재생</h1><p>검수 보조 페이지이며 완료 판정은 별도 JSON에 기록합니다.</p>'
        + ''.join(players) + '</html>')


if __name__ == '__main__':
    main()
