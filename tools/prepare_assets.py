"""Cut Image-generated transparent artwork, align frames and export runtime GIFs.
No model calls. Coordinates are tied to the retained, inspectable source sheets.
"""
from pathlib import Path
from PIL import Image, ImageSequence
import numpy as np
import cv2
ROOT=Path(__file__).resolve().parents[1]
sheet=Image.open(ROOT/'assets/source/worker-atlas.png').convert('RGBA')
# Rectangles exclude captions, neighboring characters and the UI reference column.
rects={
 'idle':[(173,10,330,194),(347,10,500,194),(513,10,668,194),(684,10,837,194),(854,10,1030,194)],
 'walk':[(153,226,288,389),(288,226,399,389),(399,226,510,389),(510,226,621,389),(621,226,732,389),(732,226,843,389),(843,226,951,389),(951,226,1045,389)],
 'work':[(171,411,349,582),(358,411,527,582),(533,411,692,582),(703,411,871,582),(884,411,1042,582)],
 'harvest':[(177,598,343,778),(355,598,523,778),(531,598,696,778),(707,598,859,778),(873,598,1039,778)],
 'carry':[(167,791,321,1003),(337,791,496,1003),(512,791,670,1003),(677,791,845,1003),(869,791,1025,1003)]
}

def cleaned(rect):
 im=sheet.crop(rect)
 a=np.asarray(im).copy(); alpha=a[:,:,3]
 # Remove detached source-sheet labels, not character colors.
 mask=(alpha>100).astype('uint8')
 n,l,stats,cents=cv2.connectedComponentsWithStats(mask,8)
 if n>1:
  big=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA])); x,y,w,h,_=stats[big]
  # Keep the largest connected sprite and nearby props; strip caption remnants at left.
  keep=(l==big)
  grown=cv2.dilate(keep.astype('uint8'),np.ones((3,3),np.uint8))
  a[:,:,3]*=grown
 im=Image.fromarray(a); box=im.getchannel('A').point(lambda v:255 if v>30 else 0).getbbox()
 return im.crop(box) if box else im

counts={}
for name,rs in rects.items():
 frames=[]
 # Consistent height/baseline; no procedural animation, all poses are from Image.
 raw=[cleaned(r) for r in rs]
 if name=='walk':raw=[raw[i] for i in [0,1,2,3,4,3,2,1]] # Last source cells clip the tail; omit those cells.
 maxh=max(f.height for f in raw)
 scale=135/maxh
 for f in raw:
  f=f.resize((round(f.width*scale),round(f.height*scale)),Image.Resampling.LANCZOS)
  out=Image.new('RGBA',(160,160));out.alpha_composite(f,((160-f.width)//2,151-f.height));frames.append(out)
 # GIF has binary transparency: reserve palette index 255 and threshold alpha.
 quant=[]
 for f in frames:
  a=np.asarray(f)[:,:,3];p=f.convert('RGB').quantize(colors=255,method=Image.Quantize.MEDIANCUT)
  data=np.asarray(p).copy();data[a<100]=255
  q=Image.fromarray(data,'P');palette=p.getpalette()[:765]+[0,0,0];q.putpalette(palette)
  q.info['transparency']=255;quant.append(q)
 path=ROOT/'assets/animations'/f'{name}.gif'
 quant[0].save(path,save_all=True,append_images=quant[1:],duration=130 if name=='walk' else 180,loop=0,disposal=2,transparency=255,optimize=False)
 frames[0].save(ROOT/'assets/animations'/f'{name}.png',optimize=True)
 counts[name]=len(frames)
 # Contact sheet on the same background as the game, for visual QA.
 contact=Image.new('RGBA',(160*len(frames),160),(224,232,207,255))
 for i,f in enumerate(frames):contact.alpha_composite(f,(160*i,0))
 contact.convert('RGB').save(ROOT/'tests'/f'frames-{name}.jpg',quality=90)

farm=Image.open(ROOT/'assets/source/farm-atlas.png').convert('RGBA')
# Only top-down crops/ground are accepted. Oblique buildings are deliberately excluded.
tiles={'ground':(957,13,1069,122),'soil':(1075,13,1185,122),'seed':(1193,13,1302,122),'sprout':(1306,13,1412,122),'leaves':(1420,13,1531,122),'carrot-2':(957,129,1069,241),'grass-2':(1075,129,1185,241),'wheat-2':(1193,129,1302,241),'rice-1':(1420,129,1531,241)}
for name,r in tiles.items():
 im=farm.crop(r).resize((160,160),Image.Resampling.LANCZOS)
 im.save(ROOT/'assets/tiles'/f'{name}.png',optimize=True)
# Early stages use the generated common seed/seedling tiles, not new hand-drawn assets.
for crop in ['carrot','wheat','grass']:
 for stage,src in [(0,'sprout'),(1,'leaves')]:
  Image.open(ROOT/'assets/tiles'/f'{src}.png').save(ROOT/'assets/tiles'/f'{crop}-{stage}.png',optimize=True)
# Rice stage 0 / 2 stay on the accurate existing SVG until proper rice artwork is approved.
import json
(ROOT/'assets/asset-manifest.json').write_text(json.dumps({'generator':'Image tool in this conversation','workerFrames':counts,'workerRuntimeSize':[160,160],'tileRuntimeSize':[160,160],'buildings':'Existing strict-top-down SVG retained. Newly generated oblique building artwork is not used.','rice':'Only stage 1 uses generated paddy; other stages use prior top-down SVG.','license':'Community-inspired fan design; redistribution/commercial clearance not established.'},ensure_ascii=False,indent=2))
print('Assets prepared:',counts)
