"""Check actual sliced pixels and browser transitions; no mocked image decoder."""
from pathlib import Path
import hashlib,json,os
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1]
results=[];errors=[];requests=[]
def test(name,fn):
    try:fn();results.append({'name':name,'pass':True});print('PASS',name,flush=True)
    except Exception as e:results.append({'name':name,'pass':False,'error':str(e)});print('FAIL',name,str(e),flush=True)
def check_asset(row):
    path=R/row['file'];im=Image.open(path);im.load();assert im.mode=='RGBA';assert list(im.size)==row['size']
    a=np.array(im)[:,:,3];assert a.max()==255
    assert a[0].max()==a[-1].max()==a[:,0].max()==a[:,-1].max()==0,'opaque pixel hits sprite boundary'
    assert .1<(a>128).mean()<.98
    assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    w=Image.open(R/row['runtimeFile']);w.load();assert w.size==im.size and w.mode=='RGBA'
    assert np.array_equal(np.array(w)[:,:,3],a),'runtime alpha changed'
    assert hashlib.sha256((R/row['runtimeFile']).read_bytes()).hexdigest()==row['runtimeSha256']
M=json.loads((R/'assets/asset-manifest.json').read_text())
for row in M['runtimeRecords']:test('素材解码/透明边缘/尺寸/哈希：'+row['id'],lambda row=row:check_asset(row))
def stages():
    for crop in ['rice','carrot','wheat','grass']:
        hashes=[]
        for i in range(4):hashes.append(hashlib.sha256((R/f'assets/tiles/{crop}-{i}.png').read_bytes()).hexdigest())
        assert len(set(hashes))==4
    assert len(M['runtimeRecords'])==35
    assert len(M['activeBuildingKeys'])==7 and M['reservedBuildingKeys']==['market']
test('四种作物各四幅独立图片；七种在用建筑与一套预留摊位齐全',stages)
html=(R/'index.html').read_text()
boot='''<script>window.FARM_TEST_MODE=true;window.__store={};window.__testNow=Date.now();Date.now=()=>window.__testNow;
Object.defineProperty(window,'localStorage',{value:{getItem:k=>__store[k]||null,setItem:(k,v)=>__store[k]=String(v),removeItem:k=>delete __store[k]}});</script>'''
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,headless=True,args=['--no-sandbox'])
    ctx=browser.new_context(viewport={'width':1440,'height':1050})
    page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda req:requests.append(req.url) if req.url.startswith(('http:','https:')) else None)
    page.set_content(html.replace('<head>','<head>'+boot),wait_until='load')
    page.wait_for_function('!!window.FarmTest');page.evaluate('FarmTest.assetsReady()')
    page.wait_for_timeout(80)
    def snap(i=18):return next(t for t in page.evaluate('FarmTest.tiles().tiles') if t['index']==i)
    def reset(crop='rice',progress=0,reduced=False):
        page.evaluate('''({crop,progress,reduced})=>{let s=FarmEngine.initial(Date.now());s.time=100000;s.options.autoSell=false;s.options.reducedMotion=reduced;s.workers=[];s.gold=4000;
        s.tiles[18]={type:'field',crop,plan:crop,startedAt:s.time-progress*30000,readyAt:s.time+(1-progress)*30000};FarmTest.setState(s)}''',{'crop':crop,'progress':progress,'reduced':reduced})
        page.wait_for_function("()=>{const t=FarmTest.tiles().tiles.find(t=>t.index===18);return !!t&&!t.active}",timeout=3000)
    def decoded():
        values=page.evaluate('''async()=>{const a=[...Object.entries(FARM_ASSETS.tiles),...Object.entries(FARM_ASSETS.buildings),...Object.entries(FARM_ASSETS.buildingCards)];return await Promise.all(a.map(([k,src])=>new Promise(resolve=>{let im=new Image;im.onload=()=>resolve({k,w:im.naturalWidth,h:im.naturalHeight});im.onerror=()=>resolve({k,w:0,h:0});im.src=src;})));}''')
        assert len(values)==35 and all(v['w']>0 and v['h']>0 for v in values),values
        assert not page.evaluate('FarmTest.tiles().failed')
    test('Chromium 解码全部 35 份运行素材，不依赖 SVG 回退',decoded)
    def initial():
        assert page.evaluate('FarmTest.tiles().active')==0
        assert page.locator('#board .tile-image').count()==32
        assert page.locator('#board svg').count()==0
    test('初次显示直接落到当前状态，没有从空白淡入或旧图闪回',initial)
    def boundaries():
        stages=page.evaluate('[0,.1999,.2,.5999,.6,.9999].map(x=>FarmCropStage(x,false)).concat(FarmCropStage(1,true))')
        assert stages==[0,0,1,1,2,2,3]
    test('生长阶段切点正确，成熟贴图仅在真正成熟后出现',boundaries)
    def stable():
        reset()
        # Drain any layout-driven board rebuild before taking node identities.
        page.evaluate('FarmTest.render()');page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        page.evaluate("window.__layers=[...document.querySelectorAll('[data-tile=\"18\"] .tile-image')];FarmTest.advance(1000);FarmTest.render();FarmTest.render()")
        detail=page.evaluate("""()=>({same:__layers.every((el,i)=>el===document.querySelectorAll('[data-tile=\"18\"] .tile-image')[i]),
          connected:__layers.map(el=>el.isConnected),before:__layers.map(el=>el.dataset.art||null),
          after:[...document.querySelectorAll('[data-tile=\"18\"] .tile-image')].map(el=>el.dataset.art||null),
          board:document.querySelectorAll('#board .tile').length,active:FarmTest.tiles().active,tile:FarmTest.getState().tiles[18]})""")
        assert detail['same'],detail
        assert not snap()['active']
    test('倒计时/进度更新保留同一组图片节点，不反复触发动画',stable)
    def fade():
        reset(progress=.19);page.evaluate('FarmTest.advance(1000)')
        # Wait for the actual reciprocal ramp instead of a fixed RAF-delay sleep.
        page.wait_for_function("""()=>{const r=FarmTest.tiles().tiles.find(t=>t.index===18);if(!r?.active)return false;
          const o=r.layers.map(l=>parseFloat(l.opacity));return o.every(v=>v>0&&v<1)&&Math.abs(o[0]+o[1]-1)<.08}""",timeout=3000)
        row=snap();assert row['target']=='rice-1' and row['active'],row
        assert all(0<float(l['opacity'])<1 for l in row['layers']),row
        assert abs(sum(float(l['opacity']) for l in row['layers'])-1)<.08,row
        assert all(l['loaded'] for l in row['layers'])
        page.screenshot(path=str(R/'tests/crossfade-mid.png'))
        page.wait_for_function("""()=>{const r=FarmTest.tiles().tiles.find(t=>t.index===18);return !r.active&&r.key==='rice-1'}""",timeout=3000)
        row=snap();assert not row['active'] and row['key']=='rice-1';assert sorted(float(l['opacity']) for l in row['layers'])==[0,1]
    test('水稻生长使用真正交叉叠化：新旧两层同时可见且透明度互补',fade)
    def grow():
        reset(progress=.59);page.evaluate('FarmTest.advance(1000)')
        page.wait_for_function("""()=>{const r=FarmTest.tiles().tiles.find(t=>t.index===18);return r.key==='rice-2'&&!r.active}""",timeout=3000)
        assert snap()['key']=='rice-2'
        page.evaluate('FarmTest.advance(16000)')
        page.wait_for_function("""()=>{const r=FarmTest.tiles().tiles.find(t=>t.index===18);return r.key==='rice-3'&&!r.active}""",timeout=3000)
        assert snap()['key']=='rice-3'
        assert page.locator('[data-tile="18"] .ready-dot').is_visible()
    test('水稻生长期与成熟期均使用新素材，成熟标识一致',grow)
    def harvest():
        reset(progress=1);before=page.evaluate('FarmTest.getState().inventory.rice')
        page.locator('[data-tile="18"]').click()
        page.wait_for_function("""()=>{const r=FarmTest.tiles().tiles.find(t=>t.index===18);return r.key==='rice-0'&&r.active&&new Set(r.layers.map(l=>l.key)).size===2}""",timeout=3000)
        row=snap();assert row['key']=='rice-0' and row['active'],row
        assert set(l['key'] for l in row['layers'])=={'rice-3','rice-0'}
        assert page.evaluate('FarmTest.getState().inventory.rice')==before+3
        page.wait_for_function("""()=>!FarmTest.tiles().tiles.find(t=>t.index===18).active""",timeout=3000)
        assert not snap()['active']
    test('收获自动补种以成熟→播种交叉淡化，库存只增加一次',harvest)
    def crop_swap():
        reset(progress=1);page.evaluate("(()=>{let s=FarmTest.getState();s.tiles[18].plan='wheat';FarmTest.setState(s)})()")
        page.locator('[data-tile="18"]').click()
        page.wait_for_function("""()=>{const r=FarmTest.tiles().tiles.find(t=>t.index===18);return r.key==='wheat-0'&&r.active}""",timeout=3000)
        row=snap();assert row['key']=='wheat-0' and row['active'],row
        page.wait_for_function("""()=>!FarmTest.tiles().tiles.find(t=>t.index===18).active""",timeout=3000)
        assert not snap()['active']
    test('跨作物换种也淡化，水面与普通耕地不会残留',crop_swap)
    def rapid():
        reset(progress=.19);page.evaluate('FarmTest.advance(1000)');page.wait_for_timeout(40)
        page.evaluate('FarmTest.advance(13000)');page.wait_for_timeout(40)
        page.evaluate('FarmTest.advance(20000)')
        page.wait_for_function("""()=>{const r=FarmTest.tiles().tiles.find(t=>t.index===18);return r.key==='rice-3'&&!r.active}""",timeout=3000)
        row=snap();assert row['key']=='rice-3' and not row['active'],row
        assert page.locator('[data-tile="18"] .tile-image').count()==2
        assert sorted(float(l['opacity']) for l in row['layers'])==[0,1]
    test('短时间连续切换以最新状态为准，始终最多两层图片',rapid)
    def reduced():
        reset(progress=.19,reduced=True);page.evaluate('FarmTest.advance(1000)');page.wait_for_timeout(45)
        row=snap();assert row['key']=='rice-1' and not row['active'];assert sorted(float(l['opacity']) for l in row['layers'])==[0,1]
    test('减少动态模式跳过淡化，生产时间与收成不变',reduced)
    def reduce_mid():
        reset(progress=.19);page.evaluate('FarmTest.advance(1000)');page.wait_for_timeout(80)
        page.evaluate('(()=>{let s=FarmTest.getState();s.options.reducedMotion=true;FarmTest.setState(s)})()');page.wait_for_timeout(30)
        assert not snap()['active'] and snap()['key']=='rice-1'
    test('正在淡化时开启减少动态，立即稳定在新状态',reduce_mid)
    def os_motion():
        reset(progress=.19);page.emulate_media(reduced_motion='reduce');page.evaluate('FarmTest.advance(1000)');page.wait_for_timeout(50)
        assert not snap()['active'] and snap()['key']=='rice-1'
        page.emulate_media(reduced_motion='no-preference')
    test('遵守操作系统减少动态偏好',os_motion)
    def hidden():
        reset(progress=.19);page.evaluate('FarmTest.advance(1000)');page.wait_for_timeout(60)
        page.evaluate("Object.defineProperty(document,'hidden',{value:true,configurable:true});document.dispatchEvent(new Event('visibilitychange'))")
        assert not snap()['active']
        page.evaluate("Object.defineProperty(document,'hidden',{value:false,configurable:true});document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_timeout(80);assert snap()['key']=='rice-1'
    test('隐藏页面时终止淡化，返回后不重播历史阶段',hidden)
    def expansion():
        reset(progress=.19);page.evaluate('FarmTest.advance(1000)');page.wait_for_timeout(40)
        page.locator('#expand-button').click();page.locator('[data-tile="4"]').click();page.wait_for_timeout(480)
        assert page.locator('#board .tile').count()==36
        assert len(page.evaluate('FarmTest.tiles().tiles'))==36
        assert snap()['key']=='rice-1'
    test('扩地重排时清理旧动画，不留幽灵图片或已移除格子',expansion)
    def show_all():
        page.evaluate('''(()=>{let s=FarmEngine.initial(Date.now());s.time=100000;s.gold=2860;s.options.autoSell=false;
        const keys=['house','store','well','kitchen','mill','bakery','cows'];
        for(let y=0;y<8;y++)for(let x=0;x<8;x++)s.tiles[y*16+x]={type:'grass'};
        keys.forEach((k,i)=>{s.tiles[i]={type:'building',kind:k,paused:false,job:null}});
        for(let y=2;y<7;y++)for(let x=0;x<8;x++){let crop=['carrot','wheat','grass','rice'][Math.floor(x/2)],p=[0,.3,.75,1][(x+y)%4];s.tiles[y*16+x]={type:'field',crop,plan:crop,startedAt:s.time-p*30000,readyAt:s.time+(1-p)*30000};}
        for(let y of [1,3,5,7])s.tiles[y*16+6]={type:'building',kind:'well',paused:false,job:null};
        s.stats.harvests=36;s.stats.earned=3000;s.inventory.meal=19;s.inventory.wheat=24;s.inventory.rice=8;s.inventory.grass=9;
        // QA fixture, not a player save. Workers have valid idle records.
        s.workers=[1,2,3,4].map(id=>({id,status:'idle',lastAt:0,target:null,handled:0}));
        s.options.reducedMotion=true;FarmTest.setState(s);
        })()''');page.wait_for_timeout(450);page.evaluate('FarmTest.assetsReady()')
        for i,key in enumerate(M['activeBuildingKeys']):
            # Engine dictionary order and fixture order differ: inspect by key, not list index.
            rows=page.evaluate('FarmTest.tiles().tiles');assert any(r['key']==key for r in rows)
        assert page.locator('#board svg').count()==0
        page.mouse.move(5,5);page.screenshot(path=str(R/'tests/art-farm-8x8.png'),full_page=True)
        page.locator('.farm-actions [data-open="build"]').click();page.wait_for_timeout(100)
        assert page.locator('#drawer-content img').count()==6
        assert page.locator('#drawer-content img').evaluate_all('(els)=>els.every(i=>i.complete&&i.naturalWidth===320)')
        page.screenshot(path=str(R/'tests/art-build-menu.png'),full_page=True)
        page.locator('[data-action="close-drawer"]').click()
    test('全部现有建筑使用地图贴图，建造菜单使用完整透明插画',show_all)
    def endgame():
        page.evaluate('''(()=>{let s=FarmTest.getState();s.gold=1e8;while(FarmEngine.eligibleChunks(s).length){let c=FarmEngine.eligibleChunks(s)[0];FarmEngine.expand(s,c.x,c.y)};
        for(let i=0;i<256;i++)if(s.tiles[i]?.type==='grass'){let crop=['carrot','wheat','grass','rice'][i%4],p=[.1,.3,.75,1][Math.floor(i/16)%4];s.tiles[i]={type:'field',crop,plan:crop,startedAt:s.time-p*30000,readyAt:s.time+(1-p)*30000};}FarmTest.setState(s)})()''')
        page.wait_for_timeout(450);assert page.locator('#board .tile-image').count()==512
        assert len(page.evaluate('FarmTest.tiles().tiles'))==256
        assert not page.evaluate('FarmTest.tiles().failed')
        page.screenshot(path=str(R/'tests/art-farm-16x16.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        page.screenshot(path=str(R/'tests/art-mobile.png'),full_page=True)
    test('256 格完整素材地图每格固定双层，不叠加图片或整页溢出',endgame)
    def mass_fade():
        page.set_viewport_size({'width':1440,'height':1050});page.wait_for_timeout(130)
        page.evaluate("(()=>{let s=FarmTest.getState();s.workers=[];s.options.reducedMotion=false;s.options.autoSell=false;for(let t of s.tiles)if(t?.type==='field'){t.startedAt=s.time-5700;t.readyAt=s.time+24300;}FarmTest.setState(s)})()")
        page.wait_for_function("()=>{const t=FarmTest.tiles().tiles.find(t=>t.index===18);return !!t&&!t.active}",timeout=3000);page.evaluate('FarmTest.advance(1000)');page.wait_for_timeout(130)
        snapshot=page.evaluate('FarmTest.tiles()');fields=page.evaluate("FarmTest.getState().tiles.filter(t=>t?.type==='field').length")
        assert snapshot['active']==fields and fields>240,(snapshot['active'],fields)
        assert page.locator('#board .tile-image').count()==512
        page.wait_for_timeout(460);assert page.evaluate('FarmTest.tiles().active')==0
    test('满地图二百余块田同时淡化，固定双层并全部正确收尾',mass_fade)
    test('所有操作均无外部网络请求' ,lambda:(_ for _ in ()).throw(AssertionError(requests)) if requests else None)
    test('素材与淡化检查无未捕获脚本异常',lambda:(_ for _ in ()).throw(AssertionError(errors)) if errors else None)
    browser.close()
report={'version':'0.5.0','passed':sum(r['pass'] for r in results),'total':len(results),'results':results,'errors':errors,'httpRequests':requests,'environment':'Actual Chromium decoder/CSS transitions; set_content; fixed wall clock and in-memory save adapter. Test fixtures are synthetic and are not shipped as a player save.'}
(R/'tests/art-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(f"{report['passed']} / {report['total']}",flush=True)
if report['passed']!=report['total']:raise SystemExit(1)
