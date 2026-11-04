"""Build contact sheets from actual Isaac RGB frames, without altering source frames."""
from pathlib import Path
import argparse
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('names',nargs='+');parser.add_argument('--output',required=True)
a=parser.parse_args()
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
canvas=Image.new('RGB',(1920,390*len(a.names)),(25,29,34));d=ImageDraw.Draw(canvas)
for row,name in enumerate(a.names):
    for col,index in enumerate((0,75,149)):
        im=Image.open(root/'preview'/f'{name}-{index:04d}.png').convert('RGB').resize((640,360))
        canvas.paste(im,(col*640,row*390+30))
        d.text((col*640+12,row*390+4),f'{name} / {index/30:.2f}s',font=font,fill='white')
canvas.save(root/'qa'/a.output,quality=94)
print(root/'qa'/a.output)
