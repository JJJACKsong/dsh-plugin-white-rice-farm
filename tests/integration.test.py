from pathlib import Path
import json, os
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1]
V=R/'tests/vendor'
HARNESS='''<!doctype html><html><head><meta charset="utf-8"><style>html,body,#root{width:100%;height:100%;margin:0;overflow:hidden}</style></head><body><div id="root"></div><script src="/react.js"></script><script src="/react-dom.js"></script><script>
window.registrations=[];window.__ModuleLoader__={load(spec){let def=spec.factory(n=>{if(n==='react')return React;throw Error(n)});def.apply({slots:{inject:(n,fn)=>fn(),register:(o,C)=>{registrations.push({o,C});return()=>{registrations=registrations.filter(r=>r.C!==C)}}}})}};
window.mountFarm=()=>{const C=registrations.find(r=>r.o.name==='main').C;window.panel=ReactDOM.render(React.createElement(C),document.getElementById('root'));};
window.unmountFarm=()=>ReactDOM.unmountComponentAtNode(document.getElementById('root'));
</script><script src="/client.js"></script><script>mountFarm();</script></body></html>'''
# This environment blocks URL/file navigation. All test documents are injected with set_content.
ADAPTER="""<script>window.FARM_TEST_MODE=true;window.__store={};Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>__store[k]||null,setItem:(k,v)=>__store[k]=String(v),removeItem:k=>delete __store[k]}});window.__lease=false;Object.defineProperty(navigator,'locks',{configurable:true,value:{request:async(n,o,fn)=>{if(__lease)return fn(null);__lease=true;try{return await fn({name:n})}finally{__lease=false}}}});</script>"""
def inline_script(path):
 source=path.read_text()
 if path==R/'lib/client.js':
  # Enable test hooks in the srcdoc bootstrap; add_init_script can race that document.
  marker='window.FARM_EMBEDDED=true;'
  assert source.count(marker)==1
  source=source.replace(marker,marker+'window.FARM_TEST_MODE=true;')
 return '<script>'+source.replace('</script','<\\/script')+'</script>'
HARNESS=HARNESS.replace('<head>','<head>'+ADAPTER).replace('<script src="/react.js"></script>',inline_script(V/'react.production.min.js')).replace('<script src="/react-dom.js"></script>',inline_script(V/'react-dom.production.min.js')).replace('<script src="/client.js"></script>',inline_script(R/'lib/client.js'))
RESULTS=[];ERRORS=[]
def test(name,fn):
 try:fn();RESULTS.append({'name':name,'pass':True});print('PASS',name,flush=True)
 except Exception as e:RESULTS.append({'name':name,'pass':False,'error':str(e)});print('FAIL',name,str(e),flush=True)
with sync_playwright() as p:
 exe=os.environ.get('CHROMIUM_PATH') or ('/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None)
 browser=p.chromium.launch(executable_path=exe,headless=True,args=['--no-sandbox'])
 ctx=browser.new_context(viewport={'width':1280,'height':800});ctx.add_init_script('window.FARM_TEST_MODE=true;')
 page=ctx.new_page();page.on('pageerror',lambda e:ERRORS.append(str(e)));page.set_content(HARNESS,wait_until='load');page.wait_for_selector('iframe');frame=page.frames[1];frame.locator('#board button').first.wait_for(state='visible')
 def loaded():
  assert page.evaluate('registrations.length')==2
  assert frame.locator('#board button').count()==16
  assert frame.evaluate('document.body.classList.contains("embedded")')
  assert page.locator('iframe').get_attribute('sandbox')=='allow-scripts allow-downloads'
 test('真实 Chromium 中通过模块加载器/slots 模拟层挂载隔离 iframe',loaded)
 def persisted():
  frame.locator('#harvest-button').click();page.wait_for_function("JSON.parse(localStorage.getItem('dsh-farm-v03')).gold=== 100")
  assert frame.evaluate("(()=>{try{localStorage.getItem('x');return false}catch{return true}})()")
 test('隔离 iframe 不能访问宿主存储，合法消息桥仍可保存收成',persisted)
 def spoof():
  page.evaluate("window.postMessage({kind:'farm-save',channel:panel.channel,key:'dsh-farm-v03',value:'{}'},'*')")
  page.wait_for_timeout(100);assert page.evaluate("JSON.parse(localStorage.getItem('dsh-farm-v03')).gold")==100
 test('伪造来源消息不能覆盖真实存档',spoof)
 def remount():
  global frame
  page.evaluate('unmountFarm()');page.wait_for_selector('iframe',state='detached');page.wait_for_timeout(120)
  page.evaluate('mountFarm()');page.frame_locator('iframe').locator('#board button').first.wait_for(timeout=15000)
  frame=page.locator('iframe').element_handle().content_frame();assert frame is not None
  assert frame.evaluate('FarmTest.getState().gold')==100
 test('面板卸载再挂载恢复进度且不重复发放收成',remount)
 def locking():
  page.evaluate("(()=>{const node=document.createElement('div');node.id='second-root';document.body.append(node);const C=registrations.find(r=>r.o.name==='main').C;window.secondPanel=ReactDOM.render(React.createElement(C),node)})()")
  page.wait_for_function("document.getElementById('second-root').textContent.includes('已经在另一个窗口')")
  assert page.locator('#second-root iframe').count()==0
  page.evaluate("ReactDOM.unmountComponentAtNode(document.getElementById('second-root'));document.getElementById('second-root').remove()")
 test('锁适配器拒绝第二个面板实例，未启动第二个写入者',locking)
 def workers():
  frame.evaluate("(()=>{let s=FarmEngine.initial();s.gold=100000;s.inventory.meal=100;s.options.autoSell=false;for(let i=0;i<256;i++){if(s.tiles[i]?.type==='grass')FarmEngine.tend(s,i,'carrot')}for(let i=0;i<4;i++)FarmEngine.recruit(s);FarmTest.setState(s);FarmTest.advance(16000)})()")
  assert frame.locator('.farm-actor').count()==4
  assert frame.evaluate("[...document.querySelectorAll('.farm-actor')].every(el=>getComputedStyle(el).pointerEvents==='none')")
  frame.wait_for_timeout(1050)
  poses=frame.evaluate('FarmTest.actors()');assert all(x['src'].startswith('data:image/') for x in poses);assert any(x['state']=='work' for x in poses),str([x['state'] for x in poses])
  page.screenshot(path=str(R/'tests/plugin-working.png'))
 test('四名工人以接近一格宽的尺寸出现在地图中，动作层不拦截地块操作',workers)
 def reduced():
  frame.locator('.header-right [data-open="settings"]').click();frame.locator('[data-action="toggle-motion"]').click()
  assert frame.evaluate("FarmTest.actors().every(a=>a.src.startsWith('data:image/png'))")
  frame.locator('[data-action="close-drawer"]').click()
 test('减少动态将地图 GIF 换成静态图片，经济进度继续',reduced)
 def fit():
  for w,h in [(1280,800),(1000,650),(760,650),(390,700)]:
   page.set_viewport_size({'width':w,'height':h});page.wait_for_timeout(150)
   assert not frame.evaluate('document.documentElement.scrollWidth>innerWidth'),(w,h,'horizontal')
   assert not frame.evaluate('document.documentElement.scrollHeight>innerHeight'),(w,h,'vertical')
  frame.locator('[data-open="overview"]').click();assert frame.locator('#drawer-title').inner_text()=='庄园与帮手'
  frame.locator('[data-action="close-drawer"]').click()
  page.screenshot(path=str(R/'tests/plugin-narrow.png'))
 test('嵌入面板在四种窗口尺寸单屏显示，窄屏招工入口仍可达',fit)
 def endgame():
  frame.evaluate("(()=>{let s=FarmTest.getState();s.gold=1e8;while(FarmEngine.eligibleChunks(s).length){let c=FarmEngine.eligibleChunks(s)[0];FarmEngine.expand(s,c.x,c.y)}FarmTest.setState(s)})()")
  assert frame.locator('#board button').count()==256
  m=frame.evaluate("""()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect(),b=document.querySelector('#board').getBoundingClientRect(),a=document.querySelector('#actors').getBoundingClientRect();return {tile:t.width,scroll:[v.scrollWidth,v.scrollHeight],client:[v.clientWidth,v.clientHeight],board:[b.left,b.top,b.width,b.height],actors:[a.left,a.top,a.width,a.height]}}""")
  assert m['tile']>=44 and m['scroll'][0]>m['client'][0] and m['scroll'][1]>m['client'][1],m
  assert abs(m['board'][0]-m['actors'][0])<1 and abs(m['board'][1]-m['actors'][1])<1,m
  assert not frame.evaluate('document.documentElement.scrollWidth>innerWidth')
  assert not frame.evaluate('document.documentElement.scrollHeight>innerHeight')
  frame.evaluate("()=>document.querySelector('[data-tile=\"255\"]').scrollIntoView({block:'nearest',inline:'nearest'})")
  frame.wait_for_timeout(30)
  visible=frame.evaluate("""()=>{const t=document.querySelector('[data-tile="255"]').getBoundingClientRect(),v=document.querySelector('#board-scroll').getBoundingClientRect();return t.left>=v.left-1&&t.right<=v.right+1&&t.top>=v.top-1&&t.bottom<=v.bottom+1}""")
  assert visible,'最远一格应能滚到视口内'
  frame.locator('[data-map-action="fit"]').click();frame.wait_for_timeout(50)
  fit=frame.evaluate("""()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect();return {tile:t.width,scroll:[v.scrollWidth,v.scrollHeight],client:[v.clientWidth,v.clientHeight],pressed:document.querySelector('[data-map-action="fit"]').getAttribute('aria-pressed')}}""")
  assert fit['tile']<44 and fit['pressed']=='true',fit
  assert fit['scroll'][0]<=fit['client'][0]+1 and fit['scroll'][1]<=fit['client'][1]+1,fit
  page.set_viewport_size({'width':1280,'height':800});page.wait_for_timeout(200);page.screenshot(path=str(R/'tests/plugin-16x16.png'))
 test('16×16 地图地块≥44、两轴可达、全景适配且工人层对齐',endgame)
 def hidden():
  frame.evaluate("Object.defineProperty(document,'hidden',{value:true,configurable:true});document.dispatchEvent(new Event('visibilitychange'))")
  t=frame.evaluate('FarmTest.getState().time');frame.wait_for_timeout(1300)
  assert frame.evaluate('FarmTest.getState().time')==t
  assert frame.evaluate("[...document.querySelectorAll('.farm-actor')].every(e=>e.hidden)")
  frame.evaluate("Object.defineProperty(document,'hidden',{value:false,configurable:true});document.dispatchEvent(new Event('visibilitychange'))")
  assert frame.evaluate('FarmTest.getState().time')>t
 test('隐藏时不轮询推进，返回时用同一引擎补结算',hidden)
 test('嵌入浏览器无未捕获 JavaScript 异常',lambda:(_ for _ in ()).throw(AssertionError(ERRORS)) if ERRORS else None)
 browser.close()

report={'date':'2026-11-08','passed':sum(r['pass'] for r in RESULTS),'total':len(RESULTS),'environment':'Actual Chromium set_content + React 16 + mocked DSH slots/module loader, localStorage and Web Locks. Real opaque sandbox iframe/postMessage/CSP. Native navigation and file:// are blocked by environment policy; no real DSH desktop validation.','results':RESULTS,'uncaught_errors':ERRORS}
(R/'tests/integration-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(report['passed'],'/',report['total'])
if report['passed']!=report['total']:raise SystemExit(1)
