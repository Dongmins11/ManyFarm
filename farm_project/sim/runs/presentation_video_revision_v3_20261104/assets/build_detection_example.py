"""Draw concise labels at the recorded detection boxes; do not infer new detections."""
from pathlib import Path
import hashlib
import json

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SOURCE = 'sim/runs/presentation_stills_20261031/delivery/evidence/scout-observation-2'
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'


def main():
    image = Image.open(ROOT / '02_scout_rgb.png').convert('RGB')
    metadata = json.loads((ROOT / '02_scout_map_detections.json').read_text())
    assert image.size == (640, 384)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, 15)
    records = []
    for detection in metadata['accepted']:
        box = detection['mask_box_original_xyxy']
        label, color = {'Yellow': ('노랑', '#ffe06d'), 'Red': ('빨강', '#ff7d76')}[detection['class_name']]
        draw.rectangle(tuple(box), outline=color, width=2)
        text_box = draw.textbbox((0, 0), label, font=font)
        width, height = text_box[2] - text_box[0], text_box[3] - text_box[1]
        x, y = round(box[0]), max(0, round(box[1]) - height - 9)
        draw.rectangle((x, y, x + width + 8, y + height + 6), fill='#112c32')
        draw.text((x + 4, y + 3 - text_box[1]), label, font=font, fill=color)
        records.append({key: detection[key] for key in
                        ('class_name', 'confidence', 'mask_box_original_xyxy', 'source_index', 'stamp_ns')})
    image.save(ROOT / '02_scout_detection_example.png')
    provenance = {
        'source': SOURCE,
        'type': 'actual recorded simulation observation; relabelled presentation derivative',
        'section_id': metadata['section_id'], 'segment_id': metadata['segment_id'],
        'source_image_size': [640, 384],
        'annotation': 'Only accepted mask_box_original_xyxy rectangles and short colour labels are drawn. No new detections or mask pixels are generated.',
        'limitation': 'Source contains mask bounding boxes and mask pixel counts, not a per-pixel mask bitmap. Boxes are visualized without reconstructing masks.',
        'source_files': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                         for name in ('02_scout_rgb.png', '02_scout_observation.json', '02_scout_map_detections.json')},
        'detections': records,
    }
    (ROOT / '02_scout_detection_provenance.json').write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
