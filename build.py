"""Build a self-contained HTML; Python 3 and Pillow needed only to rebuild assets."""
from pathlib import Path
import base64
import json
ROOT=Path(__file__).resolve().parent

def uri(path: Path, mime: str) -> str:
    return 'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode('ascii')

def image_group(name: str) -> dict:
    folder=ROOT/'assets/runtime'/name
    if folder.is_dir():return {p.stem:uri(p,'image/webp') for p in sorted(folder.glob('*.webp'))}
    return {p.stem:uri(p,'image/png') for p in sorted((ROOT/'assets'/name).glob('*.png'))}

def main() -> None:
    poster=ROOT/'assets/worker-portrait.png'
    if not poster.exists():
        from PIL import Image
        im=Image.open(ROOT/'assets/worker-portrait.gif')
        im.convert('RGB').save(poster)
    assets={'poster':uri(poster,'image/png'),
            'tiles':image_group('tiles'),
            'buildings':image_group('buildings'),
            'buildingCards':image_group('building-cards'),
            'animations':{**{name:uri(ROOT/'assets/animations'/f'{name}.gif','image/gif') for name in ('work','idle','walk','harvest','carry')},**{name+'Poster':uri(ROOT/'assets/animations'/f'{name}.png','image/png') for name in ('walk','idle','work','carry','harvest')}}}
    template=(ROOT/'src/template.html').read_text(encoding='utf-8')
    replacements={
        '/*__CSS__*/':(ROOT/'src/style.css').read_text(encoding='utf-8'),
        '/*__ENGINE__*/':(ROOT/'src/engine.js').read_text(encoding='utf-8'),
        '/*__TILES__*/':(ROOT/'src/tiles.js').read_text(encoding='utf-8'),
        '/*__ACTORS__*/':(ROOT/'src/workers.js').read_text(encoding='utf-8'),
        '/*__MAP_VIEW__*/':(ROOT/'src/map-view.js').read_text(encoding='utf-8'),
        '/*__UI__*/':(ROOT/'src/ui.js').read_text(encoding='utf-8'),
        '/*__ASSETS__*/':json.dumps(assets,ensure_ascii=False),
    }
    for marker,text in replacements.items(): template=template.replace(marker,text)
    (ROOT/'index.html').write_text(template,encoding='utf-8')
    print('Built',ROOT/'index.html',len(template.encode('utf-8')),'bytes')
if __name__=='__main__':main()
