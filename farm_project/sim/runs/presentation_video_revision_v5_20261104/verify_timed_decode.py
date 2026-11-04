"""Record actual 1x/0.25x throttled MP4 decoding, not visual playback viewing."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parent
FRAMES = {'05_handoff_continuity': 150, '06_07_transport_sorting': 360,
          'ManyFarm_25s_clean': 750, 'ManyFarm_25s_captioned': 750}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('clips', nargs='*', help=', '.join(FRAMES))
    args = parser.parse_args()
    clips = args.clips or list(FRAMES)
    if any(stem not in FRAMES for stem in clips):
        parser.error('Unknown clip; expected ' + ', '.join(FRAMES))
    qa = ROOT / 'qa'
    qa.mkdir(exist_ok=True)
    ffmpeg_version = subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0]
    for stem in clips:
        source = ROOT / (stem + '.mp4')
        before = digest(source)
        records = []
        for rate in (1.0, .25):
            command = ['ffmpeg', '-nostdin', '-hide_banner', '-v', 'error',
                       '-readrate', str(rate), '-readrate_initial_burst', '0',
                       '-threads', '1', '-i', source.name, '-map', '0:v:0',
                       '-an', '-vf', f'realtime=speed={rate}', '-vsync', '0',
                       '-progress', 'pipe:1', '-nostats',
                       '-f', 'null', '-']
            expected_elapsed = FRAMES[stem] / 30 / rate
            print(f'{stem}: start readrate={rate:g}; expected approximately {expected_elapsed:g}s', flush=True)
            start = time.monotonic()
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                    timeout=expected_elapsed * 2 + 30)
            elapsed = time.monotonic() - start
            fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
            decoded = int(fields.get('frame', '0').strip())
            passed = (result.returncode == 0 and not result.stderr and fields.get('progress') == 'end'
                      and decoded == FRAMES[stem] and elapsed >= max(0, expected_elapsed - .75))
            records.append(dict(readrate=rate, expected_frames=FRAMES[stem], decoded_frames=decoded,
                                expected_duration_s=FRAMES[stem] / 30,
                                expected_wall_duration_s=expected_elapsed, wall_duration_s=elapsed,
                                returncode=result.returncode, stderr=result.stderr,
                                progress=fields.get('progress'), command=command, passed=passed))
            print(f'{stem}: readrate={rate:g}, decoded={decoded}, elapsed={elapsed:.3f}s, passed={passed}', flush=True)
        unchanged = digest(source) == before
        evidence = dict(source=source.name, source_sha256=before, source_unchanged=unchanged,
                        ffmpeg_version=ffmpeg_version,
                        method='ffmpeg -readrate plus realtime output pacing, full decode to null, monotonic elapsed time',
                        limitations='This does not display video and is not human continuous-playback or naturalness review.',
                        records=records, passed=unchanged and all(row['passed'] for row in records))
        (qa / (stem + '-timed-decode.json')).write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
        if not evidence['passed']:
            raise RuntimeError(stem + ': timed decode failed; see saved evidence')


if __name__ == '__main__':
    main()
