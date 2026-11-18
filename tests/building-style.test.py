"""Regression: full source illustration is reused, not a roof-only reconstruction."""
from pathlib import Path
import os, json, hashlib
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1]
M=json.loads((R/'assets/asset-manifest.json').read_text())
BASE=json.loads((R/'tests/baseline-v04.json').read_text())
results=[]
def test(name,fn):
    try: fn(); results.append({'name':name,'pass':True}); print('PASS',name,flush=True)
    except Exception as err: results.append({'name':name,'pass':False,'error':str(err)}); print('FAIL',name,str(err),flush=True)
def full(key):
    expected=Image.open(R/f'assets/building-cards/{key}.png').convert('RGBA').resize((224,224),Image.Resampling.LANCZOS)
    actual=Image.open(R/f'assets/buildings/{key}.png').convert('RGBA')
    assert np.array_equal(np.array(expected),np.array(actual)), 'map is not the full proportionally resized illustration'
for key in M['mapBuildingKeys']:test('地图保留完整插画：'+key,lambda key=key:full(key))
def crop_unchanged():
    for name,expected in BASE['cropHashes'].items():
        assert hashlib.sha256((R/name).read_bytes()).hexdigest()==expected,name
    assert len(BASE['cropHashes'])==19

def code_unchanged():
    for name,expected in BASE['sourceHashes'].items():
        assert hashlib.sha256((R/name).read_bytes()).hexdigest()==expected,name

test('19张作物/地块与V0.4逐字节一致',crop_unchanged)
errors=[]
boot="""<script>window.FARM_TEST_MODE=true;window.__store={};window.__now=Date.now();Date.now=()=>__now;Object.defineProperty(window,'localStorage',{value:{getItem:k=>__store[k]||null,setItem:(k,v)=>__store[k]=String(v),removeItem:k=>delete __store[k]}});</script>"""
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1280,'height':900})
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.set_content((R/'index.html').read_text().replace('<head>','<head>'+boot),wait_until='load')
    page.wait_for_function('!!window.FarmTest')
    page.evaluate('FarmTest.assetsReady()')
    def full_sprite_hitboxes():
        page.evaluate('''(()=>{let s=FarmEngine.initial();s.options.reducedMotion=true;s.options.autoSell=false;s.gold=2860;let keys=['house','store','well','kitchen','mill','bakery','cows'];window.__buildings=keys.map((key,j)=>({key,index:j<4?j:12+j}));for(let {key,index} of __buildings)s.tiles[index]={type:'building',kind:key,job:null,paused:true};FarmTest.setState(s)})()''')
        page.wait_for_timeout(100)
        measurements=page.locator('#board .tile.building').evaluate_all('''els=>els.map(el=>{const b=el.getBoundingClientRect(), imgs=[...el.querySelectorAll('.tile-image')];return {within:imgs.every(i=>{const r=i.getBoundingClientRect();return r.left>=b.left-1&&r.right<=b.right+1&&r.top>=b.top-1&&r.bottom<=b.bottom+1}),pointer:imgs.every(i=>getComputedStyle(i).pointerEvents==='none')}})''')
        assert len(measurements)==7 and all(r['within'] and r['pointer'] for r in measurements),measurements
        for record in page.evaluate('__buildings'):
            page.locator(f'[data-tile="{record["index"]}"]').click()
            expected=page.evaluate('(key)=>FarmEngine.BUILDINGS[key].name',record['key'])
            assert page.locator('#drawer-title').inner_text()==expected
            page.locator('[data-action="close-drawer"]').click()
        page.screenshot(path=str(R/'tests/full-building-playtest.png'),full_page=True)
        page.locator('.farm-card').screenshot(path=str(R/'tests/full-building-map-detail.png'))
    test('七种完整建筑不越格、不挡相邻操作，点击均打开正确详情',full_sprite_hitboxes)
    test('完整建筑点击检查无脚本异常',lambda: (_ for _ in ()).throw(AssertionError(errors)) if errors else None)
    browser.close()
report={'version':'0.5.0','passed':sum(r['pass'] for r in results),'total':len(results),'results':results,'environment':'Pillow exact-pixel comparison + Chromium. Fixed-clock test scene with simulated storage, not actual DSH.'}
(R/'tests/building-style-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(f'{report["passed"]}/{report["total"]}')
if report['passed']!=report['total']:raise SystemExit(1)
