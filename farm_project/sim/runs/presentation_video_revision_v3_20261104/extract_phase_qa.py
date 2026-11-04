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
    '05_handoff': [1., 1.35, 1.5, 1.8, 2.1, 2.5, 3.4, 4., None],
    '07_sorting': [1., 2.6, 2.8, 3., 3.3, 3.7, 4., 5.8, 6.9],
    'ManyFarm_22s_captioned': [1.5, 4.5, 7.5, 269 / 30, 9., 10.5, 13.5,
                             16., 18.5, 20.5, 21.2, 21.6, 659 / 30],
}


def main():
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
        indices = [count - 1 if t is None else math.floor(t * 30 + .5) for t in PHASES[stem]]
        assert indices == sorted(set(indices)) and indices[-1] < count
        selection = '+'.join(f'eq(n\\,{index})' for index in indices)
        temporary = qa / f'{stem}-phase-extract-%02d.png'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(source), '-vf', f'select={selection}',
                        '-vsync', '0', '-frames:v', str(len(indices)), str(temporary)], check=True)
        sheet = Image.new('RGB', (4 * 640, math.ceil(len(indices) / 4) * 394), '#11242d')
        draw = ImageDraw.Draw(sheet)
        records = []
        for number, (index, requested_time) in enumerate(zip(indices, PHASES[stem])):
            path = qa / f'{stem}-mp4-frame-{index:04}.png'
            (qa / f'{stem}-phase-extract-{number+1:02d}.png').replace(path)
            with Image.open(path) as image:
                assert image.size == (1920, 1080)
                sheet.paste(image.resize((640, 360), Image.Resampling.LANCZOS),
                            ((number % 4) * 640, (number // 4) * 394 + 34))
            draw.text(((number % 4) * 640 + 12, (number // 4) * 394 + 2),
                      f'{stem}  frame {index:03d}  /  {index/30:.3f}s', fill='#b3f2df', font=font)
            records.append({'requested_time_s': requested_time, 'frame': index,
                            'actual_time_s': index / 30, 'file': path.relative_to(ROOT).as_posix(),
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        sheet_path = qa / f'{stem}-mp4-keyphases.jpg'
        sheet.save(sheet_path, quality=93)
        evidence = {'source': source.name, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'extraction': 'ffmpeg select by decoded MP4 frame number; no GUI preview substitution',
                    'fps': 30, 'frames': records, 'contact_sheet': sheet_path.relative_to(ROOT).as_posix()}
        (qa / f'{stem}-mp4-keyphases.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(f'{stem}: {len(indices)} decoded MP4 frames and key-phase sheet saved')


if __name__ == '__main__':
    main()
