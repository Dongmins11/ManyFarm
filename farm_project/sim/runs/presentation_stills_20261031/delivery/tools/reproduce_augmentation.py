"""전달 폴더의 raw RGB와 저장한 설정으로 증강 예시를 재현한다."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from scout_dataset_core import postprocess_rgb
root=Path(__file__).resolve().parents[1]
spec=json.loads((root/'settings/augmentation-example.json').read_text())
raw=np.asarray(Image.open(root/spec['input']).convert('RGB'))
out=root/'reproduced';out.mkdir(exist_ok=True)
for name,entry in spec['variants'].items():
 rgb=raw.copy() if entry['config'] is None else postprocess_rgb(raw,entry['config'],np.random.default_rng(spec['seed']))[0]
 Image.fromarray(rgb).save(out/f'04-{name}.png')
 original=np.asarray(Image.open(root/f'originals/04-{name}.png'))
 assert np.array_equal(rgb,original),f'{name}: original mismatch'
print('5 variants pixel-identical')
