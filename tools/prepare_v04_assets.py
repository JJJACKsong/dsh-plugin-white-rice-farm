"""Deterministic slicing/matting of supplied Image atlases, not fresh image generation.

The building sheet is oblique, despite its printed caption. Full cutouts are
used on the map and in cards as requested. Square-grid interaction is unchanged;
no roof-only reconstruction, perspective rectification or AI redrawing is used.
"""
from pathlib import Path
import json, hashlib
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

R=Path(__file__).resolve().parents[1]
A=R/'assets'
for d in ['tiles','buildings','building-cards']:(A/d).mkdir(exist_ok=True)
C=Image.open(A/'source/crop-stages-v04.png').convert('RGB').resize((1408,1056),Image.Resampling.LANCZOS)
B=Image.open(A/'source/buildings-v04.png').convert('RGB').resize((1408,1056),Image.Resampling.LANCZOS)
S=224
records=[]

def matte(im):
    """Flood-fill only connected warm paper. Do not remove white rice/smoke."""
    rgb=np.asarray(im.convert('RGB')).astype(np.int16)
    r,g,b=rgb[...,0],rgb[...,1],rgb[...,2]
    paper=(r>215)&(g>182)&(b>140)&((r-b)>15)&((g-b)>6)&((r-g)<55)
    n,labels,stats,_=cv2.connectedComponentsWithStats(paper.astype('uint8'),8)
    touching=np.unique(np.r_[labels[0,:],labels[-1,:],labels[:,0],labels[:,-1]])
    bg=np.isin(labels,touching[touching!=0])
    fg=(~bg).astype('uint8')
    # Keep the main connected artwork, including internal pale details.
    n,lab,stats,_=cv2.connectedComponentsWithStats(fg,8)
    if n>1:
        largest=1+np.argmax(stats[1:,cv2.CC_STAT_AREA]);fg=(lab==largest).astype('uint8')
    # Fill any enclosed background in the object. Shared sprite edge stays anti-aliased.
    contours,_=cv2.findContours(fg,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    mask=np.zeros_like(fg)
    cv2.drawContours(mask,contours,-1,255,cv2.FILLED)
    alpha=Image.fromarray(mask).filter(ImageFilter.GaussianBlur(.35))
    out=im.convert('RGBA');out.putalpha(alpha)
    box=out.getbbox()
    if not box:raise ValueError('Empty sprite')
    return out.crop(box)

def fit(im,size=S,pad=6,stretch=False):
    out=Image.new('RGBA',(size,size))
    if stretch:
        im=im.resize((size-2*pad,size-2*pad),Image.Resampling.LANCZOS)
    else:
        im=im.copy();im.thumbnail((size-2*pad,size-2*pad),Image.Resampling.LANCZOS)
    out.alpha_composite(im,((size-im.width)//2,(size-im.height)//2));return out

def save(im,group,name,source,**meta):
    p=A/group/(name+'.png');im.save(p,optimize=True)
    records.append({'id':group+'/'+name,'file':str(p.relative_to(R)),'size':list(im.size),'source':source,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),**meta})
    return im

# Remove only superseded tile files; worker assets are untouched.
for p in (A/'tiles').glob('*.png'):p.unlink()
base={'ground':(352,77,550,238),'soil':(701,77,897,238),'paddy':(1041,77,1245,239)}
for key,box in base.items():
    save(fit(matte(C.crop(box)),stretch=True),'tiles',key,'crop-stages-v04.png',crop=list(box),usage='map')
rows={
 'carrot':[(306,296,506,441),(583,296,785,441),(863,295,1066,442),(1143,295,1358,442)],
 'wheat':[(305,490,506,626),(583,490,785,626),(863,489,1068,627),(1143,489,1358,627)],
 'grass':[(304,678,506,800),(583,678,785,801),(863,678,1068,802),(1143,678,1358,802)],
 'rice':[(303,852,506,1002),(582,852,785,1002),(861,852,1068,1003),(1142,851,1360,1003)],
}
for crop,boxes in rows.items():
    for stage,box in enumerate(boxes):
        # One footprint and baseline per stage. Unequal sheet cells are normalized.
        im=fit(matte(C.crop(box)),stretch=True)
        save(im,'tiles',f'{crop}-{stage}','crop-stages-v04.png',crop=list(box),stage=stage,usage='map')

cards={
 'house':(43,77,398,414),'store':(415,123,705,414),'well':(709,125,1002,414),'market':(1015,120,1374,414),
 'mill':(40,480,349,804),'bakery':(359,479,679,804),'cows':(704,514,1006,804),'kitchen':(1021,479,1377,804),
}
for k,box in cards.items():
    save(fit(matte(B.crop(box)),320,8),'building-cards',k,'buildings-v04.png',crop=list(box),usage='panel: full original oblique illustration; also source for map')

# 0.4.1: Preserve the full source building, not just a rectified roof.
# Map interaction remains orthogonal. These are oblique illustration sprites
# deliberately reused at the same footprint; no projection or parts collage.
for key in cards:
    image=Image.open(A/'building-cards'/(key+'.png')).convert('RGBA')
    image=image.resize((S,S),Image.Resampling.LANCZOS)
    save(image,'buildings',key,'buildings-v04.png',
         usage='map: full original oblique building, proportionally scaled',
         sourceCard='assets/building-cards/'+key+'.png',
         projection='square-grid map with oblique building illustration')

# Review contact sheets. Text is QA labelling, never part of runtime images.
fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=ImageFont.truetype(fontpath,16)
def contact(group,names,dest,columns=4,cell=204):
    rows=(len(names)+columns-1)//columns
    im=Image.new('RGB',(columns*cell,rows*(cell+28)),(239,241,230));draw=ImageDraw.Draw(im)
    for i,name in enumerate(names):
        x=(i%columns)*cell;y=(i//columns)*(cell+28)
        # alternating dark/light checks make halos and alpha errors obvious
        for yy in range(0,cell,12):
            for xx in range(0,cell,12):
                color=(229,235,221) if (xx//12+yy//12)%2==0 else (200,212,190)
                draw.rectangle((x+xx,y+yy,x+xx+11,y+yy+11),fill=color)
        a=Image.open(A/group/(name+'.png')).convert('RGBA');a.thumbnail((cell-10,cell-10),Image.Resampling.LANCZOS)
        im.paste(a,(x+(cell-a.width)//2,y+(cell-a.height)//2),a)
        draw.text((x+8,y+cell+4),name,font=font,fill=(32,47,35))
    im.save(R/'tests'/dest)
contact('tiles',[f'{crop}-{i}' for crop in rows for i in range(4)],'asset-crops-v04.png')
contact('buildings',list(cards),'asset-map-buildings-v04.png')
contact('building-cards',list(cards),'asset-building-cards-v04.png')
manifest={
 'version':'0.4.1','generator':'Existing Image outputs supplied in this conversation; isolated full buildings and proportional scaling only',
 'cropStates':{k:4 for k in rows},'stageThresholds':[0,.20,.60,1],
 'mapBuildingKeys':list(cards),'activeBuildingKeys':['house','store','well','kitchen','mill','bakery','cows'],
 'reservedBuildingKeys':['market'],
 'mapSize':[S,S],'cardSize':[320,320],
 'projectionNote':'Square-grid map with full original oblique building illustrations. Both map and cards preserve doors, walls, shop goods, animals and surrounding garden details; no strict overhead projection is claimed.',
 'runtimeRecords':records,'workers':'Existing 0.3 animation assets retained, not regenerated or newly licensed.',
 'rights':'Community-inspired fan design. Technical usability does not establish third-party rights or redistribution/commercial clearance.'}
# Lightweight runtime copies; editable/source PNGs remain lossless.
for row in records:
    dest=A/'runtime'/Path(row['id']+'.webp');dest.parent.mkdir(parents=True,exist_ok=True)
    Image.open(R/row['file']).save(dest,'WEBP',quality=93,method=6,exact=True)
    row['runtimeFile']=str(dest.relative_to(R))
    row['runtimeSha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
(A/'asset-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('Prepared',len(records),'runtime PNGs; preserved worker animations.')
