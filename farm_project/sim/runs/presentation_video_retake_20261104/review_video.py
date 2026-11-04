"""Extract action contact sheets directly from the delivered MP4 files."""
from pathlib import Path
import sys, cv2
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parent
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
for name in sys.argv[1:]:
    cap=cv2.VideoCapture(str(root/(name+'.mp4')))
    indices=[0,30,60,75,90,99,105,119,149] if name!='07_sorting' else [0,30,60,75,78,82,86,105,149]
    canvas=Image.new('RGB',(1920,1170),(25,29,34));draw=ImageDraw.Draw(canvas)
    for k,index in enumerate(indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,bgr=cap.read();assert ok,(name,index)
        im=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)).resize((640,360))
        x,y=(k%3)*640,(k//3)*390
        canvas.paste(im,(x,y+30));draw.text((x+12,y+4),f'{name} / {index:03d} / {index/30:.2f}s',font=font,fill='white')
    cap.release();canvas.save(root/'qa'/(name+'-motion.jpg'),quality=94)
