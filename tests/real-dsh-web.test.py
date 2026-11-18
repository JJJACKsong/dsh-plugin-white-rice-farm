#!/usr/bin/env python3
"""Actual official DSH Web CLI integration: no fake slots, no providers, no messages."""
import hashlib, json, os, re, signal, socket, subprocess, sys, time, traceback
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests/real-dsh-web-artifacts'
OUT.mkdir(exist_ok=True)
checks=[]; browser_errors=[]; network_errors=[]; console=[]
metadata={'dsh_package':'@deepseek-ai/dsh@0.2.2-rc.1',
 'source_commit':os.environ.get('GITHUB_SHA'),'host':'official DSH Web, not Electron',
 'package_version':json.loads((ROOT/'package.json').read_text())['version'],
 'test_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'html_sha256':hashlib.sha256((ROOT/'index.html').read_bytes()).hexdigest(),
 'source_sha256':{name:hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest() for name in ['engine.js','ui.js','map-view.js','workers.js']},
 'model_messages_sent':0,'native_OS_hide_tested':False,'physical_performance_tested':False}
proc=None; pw=None; browser=None; ctx=None; page=None; frame=None; auth_url=None
server_logs=[]; host_exits=[]

def redact(value):
 return re.sub(r'(token=)[^&#\s]+',r'\1[REDACTED]',str(value))

def observe_tab(tab):
 tab.on('pageerror',lambda e:browser_errors.append(redact(str(e)[:1600])))
 tab.on('requestfailed',lambda r:network_errors.append({'url':redact(r.url[:300]),'failure':r.failure}))
 tab.on('console',lambda m:console.append(redact(m.type+': '+m.text[:300])))

def check(name,fn):
 try:
  result=fn();checks.append({'name':name,'status':'pass','detail':result})
  print('PASS',name,result or '',flush=True);return True
 except Exception as e:
  checks.append({'name':name,'status':'fail','error':redact(e),'traceback':redact(traceback.format_exc()[-5000:])})
  print('FAIL',name,redact(e),flush=True);return False

def skip(name,reason):
 checks.append({'name':name,'status':'skip','reason':reason});print('SKIP',name,reason,flush=True)

def capture(tag,tab=None):
 current=tab if tab is not None else page
 if current is None or current.is_closed():return
 try:
  current.screenshot(path=str(OUT/(tag+'.png')),full_page=True,timeout=15000,animations='disabled')
  data=current.evaluate('''() => ({
   title:document.title,href:location.href,
   text:(document.body?.innerText||'').slice(0,15000),
   buttons:[...document.querySelectorAll('button')].slice(0,100).map(e=>({title:e.title,text:e.innerText.slice(0,80),aria:e.getAttribute('aria-label')})),
   frames:[...document.querySelectorAll('iframe')].map(e=>({title:e.title,sandbox:e.getAttribute('sandbox'),src:e.getAttribute('src'),srcdocBytes:e.getAttribute('srcdoc')?.length||0}))
  })''')
  data['href']=redact(data['href'])
  (OUT/(tag+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2))
 except Exception as e:console.append('capture:'+redact(e))

def launch(phase='initial',reuse_port=False):
 global proc,auth_url
 for key in ('DSH_HOME','DSH_AGENTS_HOME','DSH_TEST_WORKSPACE','DSH_BIN'):
  if not os.environ.get(key):raise AssertionError('missing isolated '+key)
 assert len({os.environ[x] for x in ('DSH_HOME','DSH_AGENTS_HOME','DSH_TEST_WORKSPACE')})==3
 assert not any(os.environ.get(k) for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY'))
 assert os.environ.get('DSH_TELEMETRY_DISABLED')=='1'
 if reuse_port:
  assert proc is None or proc.poll() is not None,'previous test-host process still alive'
  port=int(metadata['address'].split(':')[1])
 else:
  with socket.socket() as sock:
   sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  metadata['address']=f'127.0.0.1:{port}'
 args=[os.environ['DSH_BIN'],'web','--no-open','--host','127.0.0.1','--port',str(port)]
 logpath=OUT/('dsh-web-'+phase+'.log')
 server_logs.append(logpath)
 log=open(logpath,'w')
 proc=subprocess.Popen(args,cwd=os.environ['DSH_TEST_WORKSPACE'],stdin=subprocess.DEVNULL,
  stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 log.close()
 for _ in range(200):
  body=logpath.read_text(errors='replace')
  match=re.search(r'dsh web:\s+(http://127\.0\.0\.1:'+str(port)+r'/\?token=[^\s]+)',body)
  if match:
   auth_url=match.group(1)
   metadata['auth_mode']='official loopback token URL; token redacted in artifacts'
   return 'official DSH Web startup URL emitted with temporary access token'
  if proc.poll() is not None:
   raise RuntimeError('official DSH exited '+str(proc.returncode)+':'+re.sub(r'(token=)[^\s]+',r'\1[REDACTED]',body[-6000:]))
  time.sleep(0.5)
 raise TimeoutError('official DSH did not print its startup URL within 100 sec')

def dismiss_onboarding(tab=None):
 """Only close official informational/sign-in prompts. Never log in or add keys."""
 target=tab if tab is not None else page
 for _ in range(6):
  preview=target.get_by_role('button',name=re.compile(r'^(Continue|继续)$'))
  if preview.count() and preview.is_visible():
   preview.click(timeout=12000)
   try:target.get_by_role('button',name=re.compile(r'^(Close|关闭)$')).wait_for(state='visible',timeout=9000)
   except Exception:pass
   continue
  get_started=target.get_by_text(re.compile(r'^(Get started|开始使用)$'))
  close=target.get_by_role('button',name=re.compile(r'^(Close|关闭)$'))
  if get_started.count() and get_started.is_visible() and close.count() and close.is_visible():
   close.click(timeout=12000)
   target.wait_for_timeout(300)
   continue
  target.wait_for_timeout(450)
  # At most a very short fade remains after the close action.
  mask=target.locator('._mask_14mp3_18')
  if not mask.count() or not mask.is_visible():break
 mask=target.locator('._mask_14mp3_18')
 if mask.count():mask.wait_for(state='hidden',timeout=9000)

def open_ui():
 global pw,browser,ctx,page
 pw=sync_playwright().start()
 browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,
  headless=True,args=['--no-sandbox'])
 metadata['chromium']=browser.version
 ctx=browser.new_context(viewport={'width':1280,'height':800},accept_downloads=True)
 ctx.add_init_script('window.FARM_TEST_MODE = true;')
 page=ctx.new_page()
 observe_tab(page)
 page.goto(auth_url,wait_until='domcontentloaded',timeout=30000)
 try:page.get_by_text('大白饭庄园',exact=True).first.wait_for(state='visible',timeout=40000)
 finally:capture('official-home-before-opening')
 dismiss_onboarding()
 capture('official-home-after-no-account-dismiss')
 return 'Official DSH sidebar label appeared; both onboarding dialogs closed without account action'

def mount_farm():
 global frame
 page.get_by_role('button',name='大白饭庄园',exact=True).click(timeout=12000)
 iframe=page.locator('iframe[title="大白饭庄园"]').first
 iframe.wait_for(state='attached',timeout=25000)
 frame=iframe.element_handle().content_frame()
 assert frame is not None
 frame.locator('#board button').first.wait_for(timeout=15000)
 frame.wait_for_function("typeof window.FarmTest?.getState==='function'",timeout=15000)
 capture('official-farm-desktop')
 assert frame.locator('#board button').count()==16
 assert frame.locator('#gold').inner_text()=='100'
 return 'Clicked real sidebar -> game iframe, initial 4x4 and 100 coins'

def verify_assets():
 assert page.locator('iframe[title="大白饭庄园"]').first.get_attribute('sandbox')=='allow-scripts allow-downloads'
 state=frame.evaluate('''async()=>{await FarmTest.assetsReady();
  let all=[...Object.values(FARM_ASSETS.tiles),...Object.values(FARM_ASSETS.buildings),...Object.values(FARM_ASSETS.buildingCards)];
  let ok=await Promise.all(all.map(src=>new Promise(done=>{let im=new Image;im.onload=()=>done(im.naturalWidth>0);im.onerror=()=>done(false);im.src=src})));
  let blocked=false;try{localStorage.getItem('x')}catch(e){blocked=true}
  return {total:all.length,ok:ok.filter(Boolean).length,failed:FarmTest.tiles().failed,
   blocked,avatar:[...document.querySelectorAll('.crew-avatar')].every(im=>im.naturalWidth>0&&im.src.startsWith('data:image/png')),
   csp:document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content||''}}''')
 assert state['total']==state['ok']==35 and not state['failed'],state
 assert state['blocked'] and state['avatar'],state
 assert "connect-src 'none'" in state['csp'],state
 return '35 native decoded assets, PNG avatar, opaque iframe, app CSP'

def save_reload():
 global frame
 frame.locator('#harvest-button').click()
 page.wait_for_function("""()=>{try{let s=JSON.parse(localStorage.getItem('dsh-farm-v03'));return s?.gold=== 100&&s?.stats?.harvests===2}catch(e){return false}}""",timeout=12000)
 page.reload(wait_until='domcontentloaded',timeout=30000)
 page.get_by_role('button',name='大白饭庄园',exact=True).wait_for(timeout=40000)
 dismiss_onboarding()
 page.get_by_role('button',name='大白饭庄园',exact=True).click(timeout=12000)
 iframe=page.locator('iframe[title="大白饭庄园"]').first
 iframe.wait_for(state='attached',timeout=25000)
 frame=iframe.element_handle().content_frame()
 frame.locator('#board button').first.wait_for(timeout=20000)
 frame.wait_for_function("typeof window.FarmTest?.getState==='function'",timeout=15000)
 state=frame.evaluate('FarmTest.getState()')
 assert state['stats']['harvests']==2 and state['gold']>=100,state
 capture('official-farm-after-reload')
 return 'real DSH Web host persisted farm state across browser reload'

def narrow():
 measurements=[]
 for width,height in [(1280,800),(390,700),(320,640)]:
  page.set_viewport_size({'width':width,'height':height})
  page.wait_for_timeout(350)
  dims=frame.evaluate("""()=>{
   const rect=e=>{const r=e.getBoundingClientRect();return {w:r.width,h:r.height,x:r.x,y:r.y}};
   const selectors=['.header-right [data-open="settings"]','.farm-actions .button',
    '.compact-management .button','#farm-level','.crop-chip','#harvest-button'];
   return {w:innerWidth,h:innerHeight,sw:document.documentElement.scrollWidth,sh:document.documentElement.scrollHeight,
    save:rect(document.querySelector('#save-status')),saveCount:document.querySelectorAll('#save-status').length,
    board:rect(document.querySelector('#board')),viewport:rect(document.querySelector('#board-scroll')),
    tile:rect(document.querySelector('#board .tile')),garden:rect(document.querySelector('.garden')),
    controls:selectors.flatMap(selector=>[...document.querySelectorAll(selector)].map(e=>({selector,text:e.textContent.trim(),...rect(e)})))}
  }""")
  assert dims['sw']<=dims['w']+1 and dims['sh']<=dims['h']+1,dims
  assert dims['saveCount']==1 and dims['save']['w']>0 and dims['save']['h']>0,dims
  assert 0<=dims['save']['y'] and dims['save']['y']+dims['save']['h']<=dims['h'],dims
  if width<=390:
   # New commercial entry adds a visible compact control; the hidden desktop
   # duplicates still exist in the DOM, so count visible controls explicitly.
   visible=[c for c in dims['controls'] if c['w']>0 and c['h']>0]
   assert len(dims['controls'])==16,dims
   assert len(visible)==14,(len(visible),dims)
   for control in visible:
    assert control['w']>=39.5 and control['h']>=39.5,control
    assert control['x']>=-1 and control['x']+control['w']<=dims['w']+1,control
    assert control['y']>=-1 and control['y']+control['h']<=dims['h']+1,control
  assert dims['viewport']['w']>150 and dims['viewport']['h']>=80,dims
  assert dims['tile']['w']>=43.5 and dims['tile']['h']>=43.5,dims
  for start,size in [('x','w'),('y','h')]:
   assert dims['viewport'][start]>=dims['garden'][start]-1,dims
   assert dims['viewport'][start]+dims['viewport'][size]<=dims['garden'][start]+dims['garden'][size]+1,dims
  measurements.append(dims)
  capture('official-farm-'+str(width))
 original=frame.evaluate('FarmTest.getState()')
 try:
  frame.evaluate("""()=>{
   const state=FarmTest.getState();state.gold=1e7;
   while(FarmEngine.eligibleChunks(state).length){const c=FarmEngine.eligibleChunks(state)[0];FarmEngine.expand(state,c.x,c.y)}
   FarmTest.setState(state)
  }""")
  assert frame.locator('#board button').count()==256
  large=frame.evaluate("""()=>{
   const v=document.querySelector('#board-scroll');v.scrollLeft=v.scrollWidth;v.scrollTop=v.scrollHeight;
   const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,w:r.width,h:r.height}};
   return {viewport:rect(v),tile:rect(document.querySelector('[data-tile="255"]')),
    garden:rect(document.querySelector('.garden')),pageWidth:document.documentElement.scrollWidth,width:innerWidth}
  }""")
  assert large['pageWidth']<=large['width']+1,large
  assert large['tile']['w']>=43.5 and large['tile']['h']>=43.5,large
  assert large['tile']['x']>=large['viewport']['x']-1 and large['tile']['right']<=large['viewport']['right']+1,large
  assert large['tile']['y']>=large['viewport']['y']-1 and large['tile']['bottom']<=large['viewport']['bottom']+1,large
  metadata['compact_16x16']=large
  frame.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
  page.wait_for_timeout(150)
  capture('official-farm-16x16-320')
  frame.locator('[data-map-action="fit"]').click()
  fit=frame.evaluate("""()=>{const r=e=>{const b=e.getBoundingClientRect();return {w:b.width,h:b.height}};return {board:r(document.querySelector('#board')),viewport:r(document.querySelector('#board-scroll'))}}""")
  assert fit['board']['w']<=fit['viewport']['w']+1 and fit['board']['h']<=fit['viewport']['h']+1,fit
  metadata['compact_16x16_overview']=fit
  frame.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
  page.wait_for_timeout(150)
  capture('official-map-overview-320')
 finally:
  fit_button=frame.locator('[data-map-action="fit"]')
  if fit_button.get_attribute('aria-pressed')=='true':fit_button.click()
  frame.evaluate('(state)=>{FarmTest.setState(state);FarmTest.save()}',original)
 metadata['compact_ui']=measurements
 return '1280, 390 and 320 layouts fit; save status visible; management controls at least 40px; 16x16 retains 44px tiles and far corner is reachable'

def storage_failure_feedback():
 """Force only farm persistence to fail in this isolated official host."""
 page.set_viewport_size({'width':320,'height':640})
 assert frame.evaluate('window.FARM_STORAGE.available') is True
 initial=frame.evaluate('FarmTest.getState()')
 page.evaluate("""()=>{
  const original=Storage.prototype.setItem;
  window.__farmQuotaFailures=0;
  window.__farmRestoreSetItem=()=>{Storage.prototype.setItem=original;delete window.__farmRestoreSetItem;delete window.__farmQuotaFailures};
  Storage.prototype.setItem=function(k,v){
   if(k==='dsh-farm-v03'){window.__farmQuotaFailures++;throw new DOMException('isolated test quota','QuotaExceededError')}
   return original.call(this,k,v)
  }
 }""")
 try:
  frame.evaluate('FarmTest.save()')
  frame.locator('#save-status').filter(has_text='受限').wait_for(state='visible',timeout=10000)
  failures=page.evaluate('window.__farmQuotaFailures')
  assert failures>=1 and frame.evaluate('window.FARM_STORAGE.available') is False
  frame.locator('.header-right [data-open="settings"]').click()
  frame.locator('#drawer').wait_for(state='visible')
  export=frame.locator('[data-action="export-save"]')
  assert export.is_visible() and export.is_enabled()
  close=frame.locator('[data-action="close-drawer"]')
  rect=close.bounding_box()
  assert rect and rect['width']>=39.5 and rect['height']>=39.5,rect
  with page.expect_download() as pending:
   export.click()
  download=pending.value
  target=OUT/'quota-fallback-export.json'
  download.save_as(str(target))
  backup=json.loads(target.read_text())
  assert backup['version']==3 and backup['stats']['harvests']==initial['stats']['harvests']
  capture('official-storage-limited-settings-320')
  close.click()
  capture('official-storage-limited-main-320')
  metadata['storage_failure_feedback']={'visible_at_320':True,'host_quota_failures':failures,'bridge_unavailable_after_host_error':True,'exported_valid_version3':True,'harvests_preserved':backup['stats']['harvests']}
  return 'host quota failure remains visible at 320px; settings exports a valid farm backup'
 finally:
  page.evaluate('window.__farmRestoreSetItem?.()')

def rice_processing_lifecycle():
 """Exercise new recipes through the real host UI, with a labelled Lv.3 fixture."""
 global frame
 original=frame.evaluate('FarmTest.getState()')
 page.set_viewport_size({'width':390,'height':700})
 try:
  metadata['rice_processing_stage']='fixture'
  frame.evaluate("""()=>{
   const s=FarmTest.getState();s.gold=10000;s.xp=135;s.options.autoSell=false;s.activeOrder=null;
   for(const key of Object.keys(FarmEngine.ITEMS))s.inventory[key]=0;
   s.inventory.wheat=6;s.inventory.rice=30;
   FarmEngine.build(s,2,'mill');FarmEngine.build(s,3,'bakery');FarmTest.setState(s);
  }""")
  before=frame.evaluate('FarmTest.getState()')
  assert before['tiles'][2]['job']['item']=='flour'
  frame.locator('.compact-management [data-open="workshops"]').click()
  frame.locator('button[data-recipe-item="riceflour"]').click()
  frame.locator('button[data-recipe-item="ricecake"]').click()
  selected=frame.evaluate('FarmTest.getState()')
  assert selected['tiles'][2]['job']==before['tiles'][2]['job']
  assert selected['inventory']['rice']==before['inventory']['rice']
  assert selected['tiles'][2]['nextRecipe']=='riceflour' and selected['tiles'][3]['nextRecipe']=='ricecake'
  assert frame.locator('button[data-recipe-item="riceflour"]').get_attribute('aria-pressed')=='true'
  assert frame.locator('button[data-recipe-item="ricecake"]').get_attribute('aria-pressed')=='true'
  frame.evaluate('() => new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
  capture('official-rice-recipes-selected-390')
  metadata['rice_processing_stage']='save-before-reload'
  frame.evaluate('FarmTest.save()')
  page.wait_for_function("""()=>{const s=JSON.parse(localStorage.getItem('dsh-farm-v03')||'null');
   return s?.tiles?.[2]?.nextRecipe==='riceflour'&&s?.tiles?.[3]?.nextRecipe==='ricecake'}""",timeout=10000)
  # The host collapses its navigation at narrow widths; remount through visible desktop navigation.
  page.set_viewport_size({'width':1280,'height':800})
  page.reload(wait_until='domcontentloaded',timeout=30000)
  metadata['rice_processing_stage']='reloaded-waiting-sidebar'
  page.get_by_role('button',name='大白饭庄园',exact=True).wait_for(timeout=40000)
  dismiss_onboarding();frame=mount_in(page)
  page.set_viewport_size({'width':390,'height':700})
  metadata['rice_processing_stage']='restored'
  restored=frame.evaluate('FarmTest.getState()')
  assert restored['tiles'][2]['nextRecipe']=='riceflour' and restored['tiles'][3]['nextRecipe']=='ricecake'
  job=restored['tiles'][2]['job']
  assert (job and job['item']=='flour' and job['readyAt']==before['tiles'][2]['job']['readyAt']) or restored['inventory']['flour']==2
  frame.evaluate('FarmTest.advance(240000)')
  metadata['rice_processing_stage']='advanced'
  produced=frame.evaluate('FarmTest.getState()')
  assert produced['inventory']['flour']==2 and produced['inventory']['ricecake']>=2,produced['inventory']
  frame.locator('.compact-management [data-open="inventory"]').click()
  assert frame.locator('[data-stock="riceflour"]').count()==1 and frame.locator('[data-stock="ricecake"]').count()==1
  capture('official-rice-products-inventory-390')
  frame.locator('[data-action="close-drawer"]').click()
  frame.locator('.compact-management [data-open="workshops"]').click()
  page.set_viewport_size({'width':320,'height':640});page.wait_for_timeout(250)
  dims=frame.evaluate("""()=>({w:innerWidth,sw:document.documentElement.scrollWidth,
   buttons:[...document.querySelectorAll('button[data-recipe]')].map(e=>{const r=e.getBoundingClientRect();return {w:r.width,h:r.height}})})""")
  assert dims['sw']<=dims['w']+1 and dims['buttons']
  assert all(x['w']>=39.5 and x['h']>=39.5 for x in dims['buttons']),dims
  capture('official-rice-workshops-320')
  metadata['rice_processing']={'fixture':'Lv.3 with one mill and bakery; not initial player progress',
   'current_batch_preserved':True,'next_recipes_persisted_after_reload':True,'old_flour_batch_qty':2,
   'ricecake_produced':produced['inventory']['ricecake'],'compact_recipe_buttons':dims['buttons']}
  return 'real UI selects both rice recipes; current flour batch survives reload; ricecake produced; 320px controls fit'
 finally:
  failed=sys.exc_info()[0] is not None
  try:
   if not page.is_closed() and not frame.is_detached():
    if frame.locator('#drawer').is_visible():frame.locator('[data-action="close-drawer"]').click()
    frame.evaluate('(s)=>{FarmTest.setState(s);FarmTest.save()}',original)
  except Exception as err:
   metadata['rice_cleanup_error']=redact(err)
   if not failed:raise

def workshop_waiting_feedback():
 original=frame.evaluate('FarmTest.getState()')
 try:
  frame.evaluate("""()=>{
   const s=FarmTest.getState();s.gold=10000;s.xp=135;s.options.autoSell=false;
   for(const key of Object.keys(FarmEngine.ITEMS))s.inventory[key]=0;
   s.inventory.rice=8;s.activeOrder={item:'rice',qty:9,pay:35};
   FarmEngine.build(s,2,'mill');FarmEngine.changeRecipe(s,2,'riceflour');FarmTest.setState(s);
  }""")
  frame.locator('.compact-management [data-open="workshops"]').click()
  status=frame.locator('[data-recipe-status="2"]').first.inner_text()
  assert '订单' in status and '水稻' in status and '0' in status,status
  frame.evaluate("""()=>{const s=FarmTest.getState();s.activeOrder=null;s.inventory.rice=6;FarmEngine.settle(s,false);FarmTest.setState(s)}""")
  before=frame.evaluate('FarmTest.getState().tiles[2].job')
  frame.locator('[data-toggle-machine="2"]').click()
  frame.locator('[data-recipe-status="2"]').filter(has_text='暂停').first.wait_for(state='visible')
  after=frame.evaluate('FarmTest.getState().tiles[2]')
  assert after['paused'] and after['job']==before
  capture('official-workshop-finishes-then-pauses-320')
  metadata['workshop_waiting_feedback']={'order_protection_visible':True,'pause_keeps_current_batch':True}
  return 'workshop explains protected stock and finishes-current-batch pause state'
 finally:
  if frame.locator('#drawer').is_visible():frame.locator('[data-action="close-drawer"]').click()
  frame.evaluate('(s)=>{FarmTest.setState(s);FarmTest.save()}',original)


def live_panel_feedback():
 original=frame.evaluate('FarmTest.getState()')
 try:
  page.set_viewport_size({'width':390,'height':844})
  frame.evaluate("""()=>{
   const s=FarmEngine.initial();s.gold=10000;s.xp=135;s.options.autoSell=true;
   for(const key of Object.keys(FarmEngine.ITEMS))s.inventory[key]=0;
   s.inventory.flour=2;
   const built=FarmEngine.build(s,2,'bakery');if(!built.ok)throw Error(built.message);
   // Seven existing loaves plus this batch reach six wholesale units after the two-unit retail reserve.
   s.inventory.bread=7;
   s.gold=119;FarmTest.setState(s);
  }""")
  frame.locator('.compact-management [data-open="inventory"]').click()
  upgrade=frame.locator('[data-action="upgrade-storage"]')
  assert upgrade.is_disabled(),'fixture must start below the 120 gold upgrade cost'
  frame.locator('[data-action="sell-surplus"]').focus()
  frame.evaluate('FarmTest.advance(90000)')
  assert frame.evaluate('FarmTest.getState().gold')>=120
  assert upgrade.is_enabled(),'production income should enable the button without reopening the drawer'
  assert frame.locator('#drawer').is_visible()
  assert frame.locator('[data-action="sell-surplus"]').evaluate('(e)=>document.activeElement===e')
  upgrade.click()
  assert '220' in upgrade.inner_text() and upgrade.is_disabled()
  frame.locator('[data-action="close-drawer"]').click()
  frame.locator('.compact-management [data-open="workshops"]').click()
  # The first batch was sold above; start another through the real engine.
  frame.evaluate("""()=>{const s=FarmTest.getState();s.inventory.flour=2;FarmEngine.settle(s,false);FarmTest.setState(s)}""")
  toggle=frame.locator('[data-toggle-machine="2"]')
  toggle.click()
  assert toggle.inner_text()=='取消完成后暂停'
  toggle.focus()
  frame.evaluate('FarmTest.advance(90000)')
  assert toggle.inner_text()=='恢复生产'
  assert toggle.evaluate('(e)=>document.activeElement===e')
  await_paint='()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))'
  frame.evaluate(await_paint)
  capture('official-live-workshop-pause-390')
  metadata['live_panel_feedback']={'fixture':'Lv.3 bakery, 7 loaves plus one new batch cross wholesale minimum while retaining 2; initial gold 119; not initial player progress',
   'upgrade_unlocks_without_reopen':True,'upgrade_cost_updates_after_purchase':True,
   'pause_label_updates_on_completion':True,'focused_controls_preserved':True}
  return 'production income enables warehouse expansion; completed batch updates resume label; drawer and focus remain'
 finally:
  failed=sys.exc_info()[0] is not None
  try:
   if not page.is_closed() and not frame.is_detached():
    if frame.locator('#drawer').is_visible():frame.locator('[data-action="close-drawer"]').click()
    frame.evaluate('(s)=>{FarmTest.setState(s);FarmTest.save()}',original)
  except Exception as err:
   metadata['live_panel_cleanup_error']=redact(err)
   if not failed:raise


def map_navigation():
 original=frame.evaluate('FarmTest.getState()')
 touch=None
 def seed(extent):
  frame.evaluate("""n=>{const s=FarmEngine.initial();s.gold=1e7;s.options.autoSell=false;
   while(true){const c=FarmEngine.eligibleChunks(s).find(c=>c.x<n&&c.y<n);if(!c)break;FarmEngine.expand(s,c.x,c.y)}
   s.gold=10000;FarmTest.setState(s)}""",extent)
 def economy():
  return frame.evaluate("""()=>{const s=FarmTest.getState();return {gold:s.gold,xp:s.xp,inventory:s.inventory,tiles:s.tiles,stats:s.stats}}""")
 def click_tile(index):
  tile=frame.locator(f'[data-tile="{index}"]');tile.scroll_into_view_if_needed()
  r=tile.bounding_box();page.mouse.click(r['x']+r['width']/2,r['y']+r['height']/2)
 def drag_tile(index):
  tile=frame.locator(f'[data-tile="{index}"]');tile.scroll_into_view_if_needed()
  r=tile.bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
  page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-70,y-15,steps=7);page.mouse.up()
 try:
  page.set_viewport_size({'width':320,'height':700})
  seed(16)
  viewport=frame.locator('#board-scroll')
  overview=frame.locator('[data-map-action="fit"]')
  zoom_in=frame.locator('[data-map-action="zoom-in"]')
  zoom_out=frame.locator('[data-map-action="zoom-out"]')
  for button in [overview,zoom_in,zoom_out]:
   r=button.bounding_box();assert r['width']>=39.5 and r['height']>=39.5,r
  width=frame.locator('#board .tile').first.bounding_box()['width']
  assert width>=43.5
  zoom_in.click()
  assert frame.locator('#board .tile').first.bounding_box()['width']>width
  zoom_out.click()
  viewport.evaluate('(v)=>{v.scrollLeft=0;v.scrollTop=0}')
  before=economy();drag_tile(3)
  assert economy()==before,'dragging from grass must not plant, collect or spend'
  assert frame.locator('#drawer').is_hidden()
  scroll=viewport.evaluate('(v)=>({x:v.scrollLeft,y:v.scrollTop})')
  assert scroll['x']>0,scroll
  frame.evaluate('FarmTest.advance(1000)')
  after=viewport.evaluate('(v)=>({x:v.scrollLeft,y:v.scrollTop})')
  assert abs(after['x']-scroll['x'])<2 and abs(after['y']-scroll['y'])<2,(scroll,after)
  overview.click()
  fit=frame.evaluate("""()=>{const r=e=>{const v=e.getBoundingClientRect();return {w:v.width,h:v.height}};return {b:r(document.querySelector('#board')),v:r(document.querySelector('#board-scroll'))}}""")
  assert fit['b']['w']<=fit['v']['w']+1 and fit['b']['h']<=fit['v']['h']+1,fit
  before=economy();click_tile(255)
  assert economy()==before,'overview click must only locate and enlarge'
  assert frame.locator('[data-tile="255"]').bounding_box()['width']>=43.5
  click_tile(255)
  state=frame.evaluate('FarmTest.getState()')
  assert state['tiles'][255]['type']=='field' and state['tiles'][255]['crop']=='carrot'
  assert state['gold']==before['gold']-12
  assert state['tiles'][254]['type']=='grass','actual pointer must hit exactly the selected far-corner cell'

  # Trusted touch move/cancel inside the actual iframe; no synthetic DOM events.
  before=economy();r=viewport.bounding_box();x=r['x']+r['width']*.6;y=r['y']+r['height']*.6
  touch=ctx.new_cdp_session(page)
  touch.send('Emulation.setTouchEmulationEnabled',{'enabled':True,'maxTouchPoints':1})
  touch.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
  touch.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+45,'y':y+30}]})
  touch.send('Input.dispatchTouchEvent',{'type':'touchCancel','touchPoints':[]})
  assert economy()==before,'touch pan/cancel must not operate land'
  tile=frame.locator('[data-tile="254"]');tile.scroll_into_view_if_needed();r=tile.bounding_box()
  touch.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':r['x']+r['width']/2,'y':r['y']+r['height']/2}]})
  touch.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
  frame.wait_for_function("FarmTest.getState().tiles[254].crop==='carrot'",timeout=3000)
  page.wait_for_timeout(400)
  assert frame.evaluate('FarmTest.getState().gold')==before['gold']-12 and frame.locator('#drawer').is_hidden(),'trusted touch tap acts once, without compatibility-click echo'
  house=frame.locator('[data-tile="0"]');house.scroll_into_view_if_needed();r=house.bounding_box()
  touch.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':r['x']+r['width']/2,'y':r['y']+r['height']/2}]})
  touch.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
  frame.locator('#drawer').wait_for(state='visible')
  page.wait_for_timeout(400)
  assert frame.locator('#drawer').is_visible(),'touch compatibility click must not close the newly opened building drawer'
  frame.locator('[data-action="close-drawer"]').click()
  touch.send('Emulation.setTouchEmulationEnabled',{'enabled':False})
  touch.detach();touch=None

  viewport.evaluate('(v)=>{v.scrollLeft=0;v.scrollTop=0}')
  frame.locator('.farm-actions [data-open="build"]').click()
  frame.locator('[data-build="kitchen"]').click()
  before=economy();drag_tile(3)
  assert economy()==before,'drag in placement mode must not place a building or spend'
  frame.locator('[data-action="cancel-mode"]').click()
  seed(8)
  frame.locator('#expand-button').click()
  before=economy();drag_tile(8)
  assert economy()==before,'drag across eligible land must not purchase it'
  count=frame.evaluate('FarmEngine.owned(FarmTest.getState())')
  cost=frame.evaluate('FarmEngine.expansionCost(FarmTest.getState())')
  click_tile(8)
  assert frame.evaluate('FarmEngine.owned(FarmTest.getState())')==count+4
  assert frame.evaluate('FarmTest.getState().gold')==before['gold']-cost
  visible=frame.evaluate("""()=>{const t=document.querySelector('[data-tile="8"]').getBoundingClientRect(),v=document.querySelector('#board-scroll').getBoundingClientRect();return t.x+t.width/2>=v.x&&t.x+t.width/2<=v.right&&t.y+t.height/2>=v.y&&t.y+t.height/2<=v.bottom}""")
  assert visible,'purchased land should remain in view after expansion'
  frame.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
  capture('official-map-expanded-320')
  metadata['map_navigation']={'fixture':'expanded 8x8 and 16x16; no workers; not default progress',
   'tile_min_width':width,'zoom_and_overview':True,'overview_only_locates':True,
   'far_corner_pointer_accurate':True,'pan_keeps_economy':True,'touch_cancel_then_click':True,'trusted_touch_building_drawer':True,
   'placement_pan_no_spend':True,'expansion_pan_no_spend':True,'purchased_land_visible':True,'tick_preserves_scroll':True}
  return '44px targets, zoom/overview, accurate far-corner click, mouse/touch cancel safety, and drag-safe building/expansion verified in official Web'
 finally:
  failed=sys.exc_info()[0] is not None
  try:
   if touch:
    touch.send('Emulation.setTouchEmulationEnabled',{'enabled':False});touch.detach()
   if not page.is_closed() and not frame.is_detached():
    if frame.locator('#drawer').is_visible():frame.locator('[data-action="close-drawer"]').click()
    cancel=frame.locator('[data-action="cancel-mode"]')
    if cancel.is_visible():cancel.click()
    fit_button=frame.locator('[data-map-action="fit"]')
    if fit_button.get_attribute('aria-pressed')=='true':fit_button.click()
    frame.evaluate('(s)=>{FarmTest.setState(s);FarmTest.save()}',original)
  except Exception as err:
   metadata['map_cleanup_error']=redact(err)
   if not failed:raise


def continuation_field_detail():
 original=frame.evaluate('FarmTest.getState()')
 try:
  page.set_viewport_size({'width':390,'height':800})
  frame.evaluate("""()=>{const s=FarmEngine.initial();s.workers=[{id:1,target:null,lastAt:0,status:'idle',handled:0}];s.nextWorkAt=4000;FarmTest.setState(s)}""")
  frame.locator('#harvest-button').click()
  frame.locator('[data-tile="32"]').click()
  frame.locator('[data-action="reclaim-field"]').click()
  frame.evaluate('FarmTest.advance(16000)')
  assert frame.evaluate("FarmTest.getState().tiles[32].type")=='grass'
  assert '空地腾好了' in frame.locator('#drawer-content').inner_text()
  assert frame.locator('[data-plan]').count()==0
  frame.evaluate('()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
  page.wait_for_timeout(200)
  capture('official-continuation-retired-field-390')
  frame.locator('#drawer-content [data-action="close-drawer"]').click()
  frame.locator('[data-tile="32"]').click()
  assert frame.evaluate("FarmTest.getState().tiles[32].type")=='field'
  return 'worker retirement updates the open detail and removes obsolete actions; replant works in official iframe'
 finally:
  if frame.locator('#drawer').is_visible():frame.locator('.drawer-header [data-action="close-drawer"]').click()
  frame.evaluate('(s)=>{FarmTest.setState(s);FarmTest.save()}',original)

def continuation_order_identity():
 original=frame.evaluate('FarmTest.getState()')
 try:
  frame.evaluate("""()=>{const s=FarmEngine.initial();s.xp=132;s.gold=500;s.orderRound=5;s.tiles[2]={type:'building',kind:'mill',paused:false,job:null};s.workers=[{id:1,target:null,lastAt:0,status:'idle',handled:0}];s.nextWorkAt=4000;FarmTest.setState(s)}""")
  frame.locator('.compact-management [data-open="orders"]').click()
  assert frame.locator('[data-order="0"]').get_attribute('data-order-item')=='carrot'
  frame.evaluate('FarmTest.advance(4000)')
  offer=frame.locator('[data-order="0"]')
  shown=offer.get_attribute('data-order-item')
  assert shown=='riceflour'
  offer.click()
  assert frame.evaluate('FarmTest.getState().activeOrder.item')==shown
  capture('official-continuation-order-identity-390')
  metadata['continuation_order_identity']={'fixture':'Lv2 xp132, round5, mill; worker harvest unlocks Lv3','visible_and_accepted_item':shown}
  return 'after background level-up the visible quote and real clicked order match'
 finally:
  if frame.locator('#drawer').is_visible():frame.locator('.drawer-header [data-action="close-drawer"]').click()
  frame.evaluate('(s)=>{FarmTest.setState(s);FarmTest.save()}',original)

def continuation_multitouch():
 original=frame.evaluate('FarmTest.getState()');touch=None;observations=[]
 try:
  page.set_viewport_size({'width':390,'height':800})
  touch=ctx.new_cdp_session(page)
  touch.send('Emulation.setTouchEmulationEnabled',{'enabled':True,'maxTouchPoints':2})
  for selector in ['[data-map-action="fit"]','.header-right [data-open="settings"]']:
   frame.evaluate('()=>FarmTest.setState(FarmEngine.initial())')
   tile=frame.locator('[data-tile="49"]');tile.scroll_into_view_if_needed()
   a=tile.bounding_box();b=frame.locator(selector).bounding_box()
   first={'x':a['x']+a['width']/2,'y':a['y']+a['height']/2,'id':1}
   second={'x':b['x']+b['width']/2,'y':b['y']+b['height']/2,'id':2}
   touch.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[first]})
   touch.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[first,second]})
   touch.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[second]})
   touch.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
   page.wait_for_timeout(350)
   after=frame.evaluate('FarmTest.getState()')
   assert after['gold']==100 and after['tiles'][49]['type']=='grass',(selector,after['gold'],after['tiles'][49])
   assert frame.locator('#drawer').is_hidden()
   touch.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[dict(first,id=3)]})
   touch.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
   frame.wait_for_function("FarmTest.getState().tiles[49].type==='field'")
   page.wait_for_timeout(250)
   assert frame.evaluate('FarmTest.getState().gold')==88
   observations.append({'second_finger':selector,'two_finger_gold':100,'next_single_tap_gold':88})
  frame.evaluate('()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
  page.wait_for_timeout(200)
  capture('official-continuation-multitouch-390')
  metadata['continuation_multitouch']=observations
  return 'trusted two-finger touch with second finger on toolbar/settings cancels map action; next normal tap acts once'
 finally:
  if touch:
   touch.send('Emulation.setTouchEmulationEnabled',{'enabled':False});touch.detach()
  if frame.locator('#drawer').is_visible():frame.locator('.drawer-header [data-action="close-drawer"]').click()
  fit=frame.locator('[data-map-action="fit"]')
  if fit.get_attribute('aria-pressed')=='true':fit.click()
  frame.evaluate('(s)=>{FarmTest.setState(s);FarmTest.save()}',original)


def round2_placement_continuity():
 """Real official iframe inputs; labelled engine fixtures, without clock injection."""
 original=frame.evaluate('FarmTest.getState()');original_viewport=page.viewport_size
 original_crop=frame.locator('#crop-options [aria-pressed="true"]').get_attribute('data-crop')
 observations=[]
 metadata['round2_placement']={'host':'existing real official DSH iframe, not a simulated host',
  'fixture':'4x4 new game; relocation alone uses a labelled Lv3 paused mill built by the engine',
  'clock_injection':False,'official_short_return_tested':False,'cases':observations,'screenshots':[],
  'keyboard_cancellations':[]}
 def state():return frame.evaluate('FarmTest.getState()')
 def economy(value):return {k:v for k,v in value.items() if k not in ('time','savedAt')}
 def fresh():
  frame.evaluate('()=>FarmTest.setState(FarmEngine.initial())')
  frame.locator('#crop-options [data-crop="carrot"]').click()
  return state()
 def select_build():
  frame.locator('.farm-actions [data-open="build"]').click()
  frame.locator('[data-build="kitchen"]').click()
 def capture_placement(tag,description):
  png=OUT/(tag+'.png');detail=OUT/(tag+'.json')
  # Old artifacts cannot satisfy this run, and the generic capture helper's
  # best-effort behavior must not turn missing new screenshots into acceptance.
  png.unlink(missing_ok=True);detail.unlink(missing_ok=True)
  capture(tag)
  assert png.exists() and detail.exists(),'missing required Round2 screenshot or page detail: '+tag
  view=frame.evaluate("""()=>({width:innerWidth,height:innerHeight,
   focus:{id:document.activeElement.id,tile:document.activeElement.dataset.tile||null},
   notice:document.querySelector('#notice-text').textContent})""")
  metadata['round2_placement']['screenshots'].append({'file':png.name,'sha256':hashlib.sha256(png.read_bytes()).hexdigest(),
   'host_viewport':page.viewport_size,'iframe':view,'state_description':description,
   'html_sha256':metadata['html_sha256'],'source_sha256':metadata['source_sha256']})
 def forward_matches(before,after,move=False):
  # The live timer remains real. Compare against the unchanged engine at the
  # observed simulation time, allowing an in-flight batch to finish naturally.
  assert after['time']>=before['time'],(before['time'],after['time'])
  expected=frame.evaluate("""({before,after,move})=>{
   const s=FarmEngine.clone(before);
   if(move){const r=FarmEngine.move(s,2,3);if(!r.ok)throw Error(r.message)}
   FarmEngine.advance(s,after.time-before.time);return s;
  }""",{'before':before,'after':after,'move':move})
  assert {k:v for k,v in after.items() if k!='savedAt'}=={k:v for k,v in expected.items() if k!='savedAt'},(before,after,expected)
 def focused_control(selector):
  info=frame.locator(selector).evaluate("""e=>{
   const r=e.getBoundingClientRect(),viewport=e.dataset.tile===undefined?null:document.querySelector('#board-scroll').getBoundingClientRect();
   const clip={left:Math.max(0,viewport?.left||0),top:Math.max(0,viewport?.top||0),
    right:Math.min(innerWidth,viewport?.right??innerWidth),bottom:Math.min(innerHeight,viewport?.bottom??innerHeight)};
   const style=getComputedStyle(e);
   return {tag:e.tagName,id:e.id,tile:e.dataset.tile||null,action:e.dataset.action||null,open:e.dataset.open||null,
    focused:document.activeElement===e,focus_visible:e.matches(':focus-visible'),disabled:e.disabled,
    rect:{x:r.x,y:r.y,width:r.width,height:r.height},clip,
    in_view:r.width>0&&r.height>0&&r.left>=clip.left-1&&r.top>=clip.top-1&&r.right<=clip.right+1&&r.bottom<=clip.bottom+1,
    outline_style:style.outlineStyle,outline_width:parseFloat(style.outlineWidth)};
  }""")
  assert info['tag']=='BUTTON' and info['focused'] and info['focus_visible'] and not info['disabled'],info
  assert info['in_view'] and info['outline_style']!='none' and info['outline_width']>=1,info
  return info
 def keyboard_cancel(mode,key,target):
  # Set up at an existing entry, then use real Tab to reach the visible cancel
  # button. After activation, never focus/scroll the expected target for the test.
  before=state()
  row={'mode':mode,'key':key,'target':target,'host_viewport':page.viewport_size,'status':'started'}
  metadata['round2_placement']['keyboard_cancellations'].append(row)
  frame.locator('#expand-button').focus();page.keyboard.press('Tab')
  row['cancel_focus']=focused_control('[data-action="cancel-mode"]')
  page.keyboard.press(key)
  assert frame.locator('#placement').is_hidden() and frame.locator('#drawer').is_hidden(),'cancel must not open a drawer or leave placement active'
  row['returned_focus']=focused_control(target)
  canceled=state()
  if mode=='move':forward_matches(before,canceled)
  else:assert economy(canceled)==economy(before),'keyboard cancellation must preserve the farm'
  page.keyboard.press('Enter')
  if mode=='expand':
   assert frame.locator('#placement').is_visible() and frame.locator('#drawer').is_hidden(),'Enter on the returned expansion entry must reopen expansion'
   row['next_keyboard_action']='Enter reopened expansion'
  else:
   assert frame.locator('#drawer').is_visible() and frame.locator('#placement').is_hidden()
   expected='[data-build="kitchen"]' if mode=='build' else '[data-action="move-building"]'
   assert frame.locator(expected).is_visible(),'Enter must open the corresponding construction/building drawer'
   row['next_keyboard_action']='Enter opened construction drawer' if mode=='build' else 'Enter opened original building detail'
  page.keyboard.press('Escape')
  assert frame.locator('#placement').is_hidden() and frame.locator('#drawer').is_hidden()
  row['focus_after_keyboard_roundtrip']=focused_control(target)
  after=state()
  if mode=='move':forward_matches(before,after)
  else:assert economy(after)==economy(before),'reopening and closing an entry must not buy, build, or plant'
  row.update(status='passed',gold_before=before['gold'],gold_after=after['gold'],
   simulation_time_before=before['time'],simulation_time_after=after['time'])
 try:
  assert page.locator('iframe[title="大白饭庄园"]').first.get_attribute('sandbox')=='allow-scripts allow-downloads'
  for width,height in [(320,640),(390,700)]:
   page.set_viewport_size({'width':width,'height':height})
   before=fresh();select_build()
   cost=frame.evaluate('FarmEngine.BUILDINGS.kitchen.cost')
   build_label=frame.locator('[data-tile="2"]').get_attribute('aria-label')
   assert '小灶台' in build_label and f'{cost} 金币' in build_label and '开垦并种' not in build_label,build_label
   assert '请选空草地建造' in frame.locator('[data-tile="32"]').get_attribute('aria-label')
   assert f'{cost} 金币' in frame.locator('#placement-hint').inner_text()
   assert frame.locator('.farm-actions [data-open="build"]').evaluate('(e)=>document.activeElement===e')
   assert economy(state())==economy(before),'choosing construction must not mutate the farm'
   frame.evaluate('()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
   capture_placement(f'official-r2-build-mode-{width}','Kitchen selected on the initial 4x4 farm; placement names the building and price, without spending')
   frame.locator('[data-action="cancel-mode"]').click()
   assert frame.locator('#placement').is_hidden()
   assert '已取消建造' in frame.locator('#notice-text').inner_text()
   assert economy(state())==economy(before),'canceling construction must not spend or build'
   for key in ['Enter','Space']:
    select_build();keyboard_cancel('build',key,'.farm-actions [data-open="build"]')
   select_build();frame.locator('#crop-options [data-crop="wheat"]').click()
   notice=frame.locator('#notice-text').inner_text()
   assert frame.locator('#placement').is_hidden() and '已取消建造' in notice and '小麦' in notice,notice
   assert '小麦' in frame.locator('[data-tile="2"]').get_attribute('aria-label')
   wheat=frame.locator('#crop-options [data-crop="wheat"]')
   assert wheat.evaluate('(e)=>document.activeElement===e'),'selected crop must keep focus after its buttons are rebuilt'
   page.keyboard.press('Enter')
   assert wheat.get_attribute('aria-pressed')=='true' and wheat.evaluate('(e)=>document.activeElement===e')
   page.keyboard.press('Tab')
   assert frame.locator('#crop-options [data-crop="grass"]').evaluate('(e)=>document.activeElement===e'),'Tab must continue from the selected crop'
   assert economy(state())==economy(before)
   frame.locator('[data-tile="2"]').focus();page.keyboard.press('Enter')
   planted=state()
   assert planted['gold']==88 and planted['tiles'][2]['crop']=='wheat',planted['tiles'][2]

   before=fresh();frame.locator('#expand-button').click()
   expansion_cost=frame.evaluate('FarmEngine.expansionCost(FarmTest.getState())')
   assert f'{expansion_cost} 金币' in frame.locator('[data-tile="4"]').get_attribute('aria-label')
   owned_label=frame.locator('[data-tile="2"]').get_attribute('aria-label')
   assert '已拥有' in owned_label and '开垦并种' not in owned_label,owned_label
   frame.locator('[data-tile="2"]').focus();page.keyboard.press('Escape')
   assert frame.locator('#placement').is_hidden()
   assert frame.evaluate('document.activeElement.dataset.tile')=='2','surviving tile lost focus when board shrank'
   page.keyboard.press('ArrowRight')
   assert frame.evaluate('document.activeElement.dataset.tile')=='3','arrow navigation must continue after cancellation'
   frame.locator('#expand-button').click()
   frame.locator('[data-tile="4"]').focus();page.keyboard.press('Escape')
   assert frame.evaluate('document.activeElement.id')=='expand-button','removed tile must return focus to expansion entry'
   assert '已取消扩地' in frame.locator('#notice-text').inner_text()
   assert economy(state())==economy(before)
   frame.evaluate('()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
   capture_placement(f'official-r2-expand-cancel-focus-{width}','Expansion canceled from a removed prospective tile; 100 coins and focus returned to the expansion button')
   page.keyboard.press('Enter')
   assert frame.locator('#placement').is_visible(),'keyboard must reopen expansion from the returned entry'
   frame.locator('#expand-button').click()
   assert frame.locator('#placement').is_hidden() and '已取消扩地' in frame.locator('#notice-text').inner_text()
   frame.locator('#expand-button').click();frame.locator('[data-action="cancel-mode"]').click()
   assert frame.locator('#placement').is_hidden() and economy(state())==economy(before)
   for key in ['Enter','Space']:
    frame.locator('#expand-button').click();keyboard_cancel('expand',key,'#expand-button')
   frame.locator('#expand-button').click();frame.locator('[data-tile="4"]').focus();page.keyboard.press('Enter')
   expanded=state()
   assert expanded['gold']==before['gold']-expansion_cost and sum(t is not None for t in expanded['tiles'])==20
   assert frame.locator('#placement').is_hidden()

   well_before=fresh()
   frame.locator('[data-tile="17"]').click();frame.locator('[data-action="move-building"]').click()
   well_target=frame.locator('[data-tile="48"]')
   well_label=well_target.get_attribute('aria-label')
   for text in [well_label,well_target.get_attribute('title'),frame.locator('#placement-hint').inner_text(),frame.locator('#notice-text').inner_text()]:
    assert '仍须保证稻田有水' in text,text
   well_target.click();well_rejected=state()
   assert economy(well_rejected)==economy(well_before),'refused well relocation must preserve gold, source well, target grass, rice plan and inventory'
   assert frame.locator('#placement').is_visible() and frame.locator('#drawer').is_hidden()
   well_refusal=frame.locator('#notice-text').inner_text()
   assert '供水' in well_refusal and '先补一口井' in well_refusal,well_refusal
   keyboard_cancel('move','Enter','[data-tile="17"]')
   assert economy(state())==economy(well_before)

   frame.evaluate("""()=>{
    const s=FarmEngine.initial();s.xp=140;s.gold=800;s.options.autoSell=false;
    s.inventory.wheat=5;s.inventory.rice=3;
    for(const r of [FarmEngine.build(s,2,'mill'),FarmEngine.changeRecipe(s,2,'riceflour'),FarmEngine.toggleMachine(s,2)])
     if(!r.ok)throw Error(r.message);
    FarmTest.setState(s);
   }""")
   batch=state()['tiles'][2]['job'];assert batch and batch['item']=='flour'
   frame.locator('[data-tile="2"]').click();frame.locator('[data-action="move-building"]').click()
   move_label=frame.locator('[data-tile="3"]').get_attribute('aria-label')
   assert '磨坊' in move_label and '免费' in move_label and '开垦并种' not in move_label,move_label
   assert '请选空草地搬家' in frame.locator('[data-tile="0"]').get_attribute('aria-label')
   assert '磨坊' in frame.locator('#placement-title').inner_text()
   assert '保留进度' in frame.locator('#placement-hint').inner_text()
   before=state();frame.locator('[data-tile="0"]').click();invalid=state()
   forward_matches(before,invalid)
   assert frame.locator('#placement').is_visible(),'an invalid destination must leave relocation available'
   frame.locator('[data-action="cancel-mode"]').click();canceled=state()
   forward_matches(invalid,canceled)
   assert frame.locator('#placement').is_hidden() and '已取消搬家' in frame.locator('#notice-text').inner_text()
   assert 'error' not in frame.locator('#notice').get_attribute('class').split()
   for key in ['Enter','Space']:
    frame.locator('[data-tile="2"]').click();frame.locator('[data-action="move-building"]').click()
    keyboard_cancel('move',key,'[data-tile="2"]')
   frame.locator('[data-tile="2"]').click();frame.locator('[data-action="move-building"]').click()
   frame.evaluate('()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
   capture_placement(f'official-r2-move-mode-{width}','Paused mill selected for free relocation; current flour batch and next riceflour choice follow the real timer')
   before=state();frame.locator('[data-tile="3"]').click();moved=state()
   forward_matches(before,moved,move=True)
   assert moved['gold']==600 and moved['inventory']['wheat']==2 and moved['inventory']['rice']==3
   assert moved['tiles'][2]['type']=='grass' and moved['tiles'][3]['paused'] and moved['tiles'][3]['nextRecipe']=='riceflour'
   if moved['tiles'][3]['job']:assert moved['tiles'][3]['job']==batch
   else:assert moved['inventory']['flour']==2
   assert frame.locator('#placement').is_hidden()
   dims=frame.evaluate("""()=>{const r=document.querySelector('[data-tile="3"]').getBoundingClientRect();return {width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,tileWidth:r.width,tileHeight:r.height}}""")
   assert dims['scrollWidth']<=dims['width']+1 and dims['tileWidth']>=43.5 and dims['tileHeight']>=43.5,dims
   observations.append({'host_viewport':{'width':width,'height':height},'iframe':dims,
    'build_label':build_label,'cancel_then_keyboard_plant_gold':planted['gold'],
    'crop_focus':'wheat -> Enter retains wheat -> Tab grass',
    'surviving_tile_focus':'2 -> ArrowRight -> 3','removed_tile_focus':'expand-button -> Enter reopens',
    'expansion_gold':expanded['gold'],'relocation_label':move_label,'relocation_gold':moved['gold'],
    'well_rejected_move':{'source':17,'destination':48,'gold':well_rejected['gold'],
     'condition_label':well_label,'refusal_notice':well_refusal,'placement_retained_after_refusal':True},
    'batch_before':batch,'batch_after':moved['tiles'][3]['job'],'next_recipe':moved['tiles'][3]['nextRecipe'],
    'simulation_time_before_move':before['time'],'simulation_time_after_move':moved['time']})
  return '320/390 official iframe: mode labels, cancellation, keyboard recovery, one purchase and free paused-workshop relocation preserve the engine economy'
 finally:
  failed=sys.exc_info()[0] is not None
  try:
   if not page.is_closed() and not frame.is_detached():
    if frame.locator('#drawer').is_visible():frame.locator('.drawer-header [data-action="close-drawer"]').click()
    if frame.locator('[data-action="cancel-mode"]').is_visible():frame.locator('[data-action="cancel-mode"]').click()
    frame.locator(f'#crop-options [data-crop="{original_crop}"]').click()
    frame.evaluate('(s)=>{FarmTest.setState(s);FarmTest.save()}',original)
    page.set_viewport_size(original_viewport)
  except Exception as err:
   metadata['round2_placement_cleanup_error']=redact(err)
   if not failed:raise


def stop_host():
 """Stop only the new DSH Web process launched for this CI test."""
 global proc,auth_url
 if proc is not None:
  if proc.poll() is None:
   try:os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=12)
   except Exception:
    if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
  host_exits.append(proc.returncode);proc=None
 auth_url=None

def official_cli(label,*args):
 home=Path(os.environ['DSH_HOME']).resolve()
 runner=Path(os.environ['RUNNER_TEMP']).resolve()
 assert home.is_relative_to(runner),'unsafe DSH_HOME outside isolated CI temporary root'
 result=subprocess.run([os.environ['DSH_BIN'],*args],cwd=str(ROOT),
  env=os.environ.copy(),stdin=subprocess.DEVNULL,text=True,stdout=subprocess.PIPE,
  stderr=subprocess.STDOUT,timeout=180)
 (OUT/(label+'.log')).write_text(redact(result.stdout),encoding='utf-8')
 if result.returncode:raise RuntimeError(label+' exit='+str(result.returncode)+': '+redact(result.stdout[-3500:]))
 return result.stdout

def bundles():
 p=Path(os.environ['DSH_HOME'])/'profiles/web/package.json'
 rows=json.loads(p.read_text())['dsh']['profile']['bundles']
 assert '@deepseek-ai/dsh-web-app' in rows,rows
 return rows

def visit_official_tab(has_game=True):
 tab=ctx.new_page()
 observe_tab(tab)
 tab.goto(auth_url,wait_until='domcontentloaded',timeout=30000)
 tab.get_by_role('button',name=re.compile(r'^(Plugins|插件)$')).first.wait_for(timeout=40000)
 dismiss_onboarding(tab)
 farm=tab.get_by_role('button',name='大白饭庄园',exact=True)
 if has_game:farm.first.wait_for(state='visible',timeout=25000)
 else:
  tab.wait_for_timeout(1200)
  assert farm.count()==0,'removed plugin still appears in official Web sidebar'
 return tab

def mount_in(tab):
 tab.get_by_role('button',name='大白饭庄园',exact=True).first.click(timeout=15000)
 el=tab.locator('iframe[title="大白饭庄园"]').first
 el.wait_for(state='attached',timeout=25000)
 actual=el.element_handle().content_frame()
 assert actual is not None
 actual.locator('#board button').first.wait_for(timeout=20000)
 actual.wait_for_function("typeof window.FarmTest?.getState==='function'",timeout=15000)
 return actual

def saved(tab):
 payload=tab.evaluate("localStorage.getItem('dsh-farm-v03')")
 assert payload is not None,'host farm save missing'
 return json.loads(payload)

def two_real_tabs():
 """Test Web Locks through two true official DSH Web tabs in one Chromium context."""
 global page,frame
 owner=page
 initial=saved(owner)
 assert initial['stats']['harvests']==2 and initial['gold']>=100
 locks=owner.evaluate("""async()=>({secure:isSecureContext,
  held:(await navigator.locks.query()).held.map(x=>({name:x.name,mode:x.mode}))})""")
 assert locks['secure'] and any(x['name']=='dsh-white-rice-farm-save-v2' and x['mode']=='exclusive' for x in locks['held']),locks
 second=visit_official_tab()
 try:
  second.get_by_role('button',name='大白饭庄园',exact=True).click(timeout=15000)
  second.get_by_text('农场已经在另一个窗口打开',exact=False).first.wait_for(timeout=18000)
  assert second.locator('iframe[title="大白饭庄园"]').count()==0
  assert owner.locator('iframe[title="大白饭庄园"]').count()==1
  capture('second-tab-lock-rejected',second)
  owner.close()
  second.get_by_role('button',name='重新打开',exact=True).click(timeout=15000)
  next_frame=second.locator('iframe[title="大白饭庄园"]').first
  next_frame.wait_for(state='attached',timeout=25000)
  actual=next_frame.element_handle().content_frame()
  actual.locator('#board button').first.wait_for(timeout=20000)
  actual.wait_for_function("typeof window.FarmTest?.getState==='function'",timeout=15000)
  restored=actual.evaluate('FarmTest.getState()')
  assert restored['stats']['harvests']==initial['stats']['harvests']
  assert restored['gold']>=initial['gold']
  held_after=second.evaluate("""async()=>(await navigator.locks.query()).held.map(x=>({name:x.name,mode:x.mode}))""")
  assert any(x['name']=='dsh-white-rice-farm-save-v2' and x['mode']=='exclusive' for x in held_after),held_after
  page,frame=second,actual
  capture('second-tab-took-over-after-owner-closed',second)
  metadata['two_real_tabs']={'second_denied':True,'no_second_iframe':True,'owner_closed':True,'exclusive_lock_transferred':True,'harvests_preserved':restored['stats']['harvests']}
  return 'real second tab denied; close owner -> retry acquires exclusive lock and restores save'
 finally:
  if page is not second and not second.is_closed():second.close()

def official_remove_reinstall():
 """Use the official CLI and restart only isolated DSH Web processes on SAME origin."""
 global page,frame
 current=next((t for t in ctx.pages if not t.is_closed()),None)
 if current is None:current=visit_official_tab()
 initial=saved(current)
 assert initial['stats']['harvests']==2 and initial['gold']>=100,initial
 for tab in list(ctx.pages):
  if not tab.is_closed():tab.close()
 stop_host()
 official_cli('official-plugin-remove','plugin','--profile','web','remove','dsh-plugin-white-rice-farm')
 assert 'dsh-plugin-white-rice-farm' not in bundles(),'plugin still in official profile after remove'
 removed_config=official_cli('official-composition-after-remove','--profile','web','--dump-config')
 assert 'dsh-white-rice-farm' not in removed_config,'plugin persists in official effective configuration'
 launch('after-remove',reuse_port=True)
 removed_tab=visit_official_tab(has_game=False)
 try:
  assert saved(removed_tab)['stats']['harvests']==initial['stats']['harvests'],'uninstall removed saved farm'
  capture('official-web-after-plugin-remove',removed_tab)
 finally:removed_tab.close()
 stop_host()
 official_cli('official-plugin-reinstall','plugin','--profile','web','add','.')
 assert 'dsh-plugin-white-rice-farm' in bundles(),'plugin not reinstated in official profile'
 installed_config=official_cli('official-composition-after-reinstall','--profile','web','--dump-config')
 assert 'dsh-white-rice-farm' in installed_config,'plugin absent in official configuration after re-add'
 launch('after-reinstall',reuse_port=True)
 tab=visit_official_tab(has_game=True)
 actual=mount_in(tab)
 restored=actual.evaluate('FarmTest.getState()')
 assert restored['stats']['harvests']==initial['stats']['harvests']==2,restored['stats']
 assert restored['gold']>=initial['gold'],(initial['gold'],restored['gold'])
 assert actual.locator('#board button').count()==16
 page,frame=tab,actual
 metadata['remove_reinstall']={'official_remove':True,'removed_profile_and_config':True,'not_in_official_sidebar':True,'save_still_in_origin_storage':True,'official_add':True,'reinstalled_profile_and_config':True,'reappeared_in_sidebar':True,'save_harvests':restored['stats']['harvests'],'save_gold':restored['gold']}
 capture('official-web-reinstalled-with-original-save',tab)
 return 'official remove/add and Web restart on same origin preserve the original farm save'

try:
 if check('实际官方 CLI 在隔离目录启动 Web 服务',launch):
  if check('实际 DSH Web 页面出现插件侧栏',open_ui):
   if check('实际 DSH 侧栏点击挂载农场面板',mount_farm):
    check('实际宿主资源、CSP、静态头像',verify_assets)
    if check('实际宿主存档与刷新接续',save_reload):
     check('实际宿主窄屏布局',narrow)
     check('官方 DSH Web 两个真实标签页锁排他及关闭持锁页接管',two_real_tabs)
     check('官方插件卸载重装后的存档接续',official_remove_reinstall)
     check('米食配方选择、在制品与刷新接续',rice_processing_lifecycle)
     check('工坊订单原料保护与本批完成后暂停提示',workshop_waiting_feedback)
     check('农场面板随生产收入和本批完成实时更新',live_panel_feedback)
     check('大地图缩放定位、拖动防误触与扩地接续',map_navigation)
     check('田地腾空后打开的详情继续可用',continuation_field_detail)
     check('后台升级后的订单显示与接单身份一致',continuation_order_identity)
     check('第二指落在地图外取消本次操作且单指可接续',continuation_multitouch)
     check('建造搬家扩地的模式提示、取消与键盘接续',round2_placement_continuity)
     check('窄屏存档受限提示与手动导出',storage_failure_feedback)
   else:
    skip('实际宿主资源、CSP、静态头像','iframe not loaded')
    skip('实际宿主存档与刷新接续','iframe not loaded')
  else:
   skip('实际 DSH 侧栏点击挂载农场面板','sidebar absent')
finally:
 capture('official-final')
 try:
  if ctx:ctx.close()
  if browser:browser.close()
  if pw:pw.stop()
 except Exception:pass
 stop_host()
 for logpath in server_logs:
  if logpath.exists():logpath.write_text(redact(logpath.read_text(errors='replace')))
 metadata.update({'passed':sum(x['status']=='pass' for x in checks),
  'failed':sum(x['status']=='fail' for x in checks),
  'skipped':sum(x['status']=='skip' for x in checks),
  'steps':checks,'console_tail':console[-70:],
  'browser_errors':browser_errors,'network_failures':network_errors,
  'process_exit_after_cleanup':host_exits[-1] if host_exits else None,
  'test_host_exits':host_exits,
  'test_scope':'actual official DSH Web: placement mode/cancellation/keyboard continuity, retired-field detail, live order identity, same-document outside-map two-finger cancellation, map navigation and pointer/touch safety, layout, storage failure/export, true two-tab lock, official reinstall, rice recipes, workshop feedback and live panel controls; <=5s real remount is not claimed'})
 (OUT/'official-dsh-web-report.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False))
 print('OFFICIAL DSH RESULT',metadata['passed'],'passed',metadata['failed'],'failed',metadata['skipped'],'skipped')
if metadata['failed']:sys.exit(1)
