"""Farm continuation behaviour in real Chromium; isolated in-memory save fixtures.

This is standalone browser evidence, never official DSH or physical-device evidence.
FARM_HTML_PATH selects the built candidate; FARM_ARTIFACT_DIR selects output.
"""
from pathlib import Path
import hashlib,json,os,traceback
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
HTML_PATH=Path(os.environ.get('FARM_HTML_PATH',ROOT/'index.html'))
OUT=Path(os.environ.get('FARM_ARTIFACT_DIR',ROOT/'tests/continuation-artifacts'))
OUT.mkdir(parents=True,exist_ok=True)
HTML=HTML_PATH.read_text(encoding='utf-8')
checks=[]; errors=[]; screenshots=[]
metadata={'host':'standalone Chromium, in-memory save adapter; not official DSH',
          'html_sha256':hashlib.sha256(HTML_PATH.read_bytes()).hexdigest(),
          'source_sha256':{name:hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest() for name in ['engine.js','ui.js','workers.js','map-view.js']},
          'fixtures':'Explicit test states; ordinary new game remains 4x4, 100 coins, 0 workers.'}

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or ('/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None),headless=True,args=['--no-sandbox'])
    metadata['chromium']=browser.version
    def page_new(width=390,height=844,embedded=False,reduced='no-preference'):
        page=browser.new_page(viewport={'width':width,'height':height},reduced_motion=reduced)
        page.on('pageerror',lambda e:errors.append(str(e)))
        boot="window.FARM_TEST_MODE=true;window.__store={};window.__testNow=Date.now();Date.now=()=>window.__testNow;Object.defineProperty(window,'localStorage',{value:{getItem:k=>window.__store[k]||null,setItem:(k,v)=>window.__store[k]=String(v),removeItem:k=>delete window.__store[k]}});"
        if embedded:boot+='window.FARM_EMBEDDED=true;'
        page.set_content(HTML.replace('<head>','<head><script>'+boot+'</script>'),wait_until='load')
        page.wait_for_function('!!window.FarmTest')
        page.evaluate('FarmTest.assetsReady()')
        return page
    def state(page):return page.evaluate('FarmTest.getState()')
    def check(name,fn):
        before=len(errors)
        try:
            detail=fn()
            assert len(errors)==before,errors[before:]
            checks.append({'name':name,'status':'pass','detail':detail});print('PASS',name,flush=True)
        except Exception as e:
            checks.append({'name':name,'status':'fail','error':str(e),'traceback':traceback.format_exc()});print('FAIL',name,str(e),flush=True)
    def capture(page,name,description):
        page.evaluate('new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
        page.wait_for_timeout(550)
        path=OUT/(name+'.png');page.screenshot(path=str(path),full_page=True,animations='disabled')
        screenshots.append({'file':path.name,'viewport':page.viewport_size,'state':description,'html_sha256':metadata['html_sha256']})
    def retired_detail():
        page=page_new()
        page.evaluate("()=>{const s=FarmTest.getState();s.workers=[{id:1,target:null,lastAt:0,status:'idle',handled:0}];s.nextWorkAt=4000;FarmTest.setState(s)}")
        page.locator('#harvest-button').click();page.locator('[data-tile="32"]').click()
        page.locator('[data-action="reclaim-field"]').click()
        page.evaluate('FarmTest.advance(16000)')
        assert state(page)['tiles'][32]['type']=='grass'
        assert '空地腾好了' in page.locator('#drawer-content').inner_text()
        assert page.locator('[data-plan]').count()==0
        assert page.locator('[data-action="reclaim-field"]').count()==0
        capture(page,'retired-field-390','worker harvested retiring field while its detail stayed open')
        page.locator('#drawer-content [data-action="close-drawer"]').click()
        page.locator('[data-tile="32"]').click()
        assert state(page)['tiles'][32]['type']=='field'
        page.close()
    check('田地腾空时详情转换，无异常且可继续种植',retired_detail)

    def order_fixture(page):
        page.evaluate("()=>{const s=FarmTest.getState();s.xp=132;s.gold=500;s.orderRound=5;s.tiles[2]={type:'building',kind:'mill',paused:false,job:null};s.workers=[{id:1,target:null,lastAt:0,status:'idle',handled:0}];s.nextWorkAt=4000;FarmTest.setState(s);FarmTest.open('orders')}")
        assert page.locator('[data-order="0"]').get_attribute('data-order-item')=='carrot'
    def order_level_refresh():
        page=page_new();order_fixture(page)
        page.evaluate('FarmTest.advance(4000)')
        assert page.locator('[data-order="0"]').get_attribute('data-order-item')=='riceflour'
        page.locator('[data-order="0"]').click()
        assert state(page)['activeOrder']['item']=='riceflour'
        page.close()
    check('后台升级后订单卡同步到当前报价',order_level_refresh)
    def order_time_race():
        page=page_new();order_fixture(page)
        # Inject the clock change and activate the old quote in one task, so the
        # real UI timer cannot replace that button between the two operations.
        # This subcase uses DOM activation, not a trusted pointer-input claim.
        page.evaluate('''()=>{const oldButton=document.querySelector('[data-order="0"]');window.__testNow+=4000;oldButton.click()}''')
        assert state(page)['activeOrder'] is None
        assert '订单已更新' in page.locator('#notice-text').inner_text()
        assert page.locator('[data-order="0"]').get_attribute('data-order-item')=='riceflour'
        page.locator('[data-order="0"]').click()
        assert state(page)['activeOrder']['item']=='riceflour'
        page.close()
    check('同任务注入时间并激活旧报价，拒绝误接其他商品（DOM激活）',order_time_race)
    def order_completion():
        page=page_new()
        page.evaluate("()=>{const s=FarmTest.getState();s.inventory.carrot=4;s.options.autoSell=false;s.activeOrder=FarmEngine.clone(FarmEngine.ORDER_POOL[0]);s.workers=[{id:1,target:null,lastAt:0,status:'idle',handled:0}];s.nextWorkAt=4000;FarmTest.setState(s);FarmTest.open('orders')}")
        page.evaluate('FarmTest.advance(4000)')
        assert state(page)['activeOrder'] is None and state(page)['stats']['orders']==1
        assert page.locator('[data-action="cancel-order"]').count()==0
        assert page.locator('[data-order]').count()==3
        page.close()
    check('订单自动交付后面板回到可接订单，不留取消旧单',order_completion)
    def stock_without_rebuild():
        page=page_new()
        page.evaluate("()=>{const s=FarmTest.getState();s.options.autoSell=false;s.workers=[{id:1,target:null,lastAt:0,status:'idle',handled:0}];s.nextWorkAt=4000;FarmTest.setState(s);FarmTest.open('orders')}")
        first=page.locator('[data-order="0"]');first.focus();first.evaluate("e=>e.dataset.retained='yes'")
        page.evaluate('FarmTest.advance(4000)')
        assert page.locator('[data-order="0"]').get_attribute('data-retained')=='yes'
        assert page.evaluate('document.activeElement.dataset.order')=='0'
        assert page.locator('[data-offer-stock="carrot"]').inner_text()=='仓库已有 4 份'
        page.close()
    check('同一批订单只刷新库存，不替换按钮或丢失焦点',stock_without_rebuild)
    def nested_focus():
        page=page_new(width=320,height=540,embedded=True)
        trigger=page.locator('.compact-management [data-open="workshops"]');trigger.click()
        page.locator('#drawer-content [data-open="build"]').click()
        assert page.locator('#drawer-title').inner_text()=='添点新家当'
        page.keyboard.press('Escape')
        assert page.locator('#drawer').is_hidden()
        assert trigger.evaluate('e=>document.activeElement===e')
        page.close()
    check('抽屉内转建造再关闭，焦点回原地图管理入口',nested_focus)
    def choose_rice_closes():
        page=page_new(width=320,height=540,embedded=True)
        page.evaluate("()=>{const s=FarmTest.getState();s.stats.harvests=1;s.tiles[2]={type:'building',kind:'kitchen',paused:false,job:null};s.tiles[18].plan='wheat';FarmTest.setState(s)}")
        page.locator('.compact-management [data-open="overview"]').click()
        page.locator('[data-overview-goal-action]').click()
        assert page.locator('#drawer').is_hidden()
        assert page.locator('[data-crop="rice"]').get_attribute('aria-pressed')=='true'
        assert page.evaluate('document.activeElement.dataset.crop')=='rice'
        assert 'water-eligible' in page.locator('[data-tile="16"]').get_attribute('class')
        page.close()
    check('去种水稻目标带回地图，选中态与键盘焦点一致',choose_rice_closes)
    def optional_bakery_goal():
        page=page_new(width=390,height=844,embedded=True)
        page.evaluate("()=>{const s=FarmTest.getState();s.xp=135;s.stats.harvests=3;s.gold=300;s.tiles[2]={type:'building',kind:'kitchen',paused:false,job:null};s.tiles[3]={type:'building',kind:'mill',paused:false,job:null};s.workers=[{id:1,target:null,lastAt:0,status:'idle',handled:0}];s.nextWorkAt=4000;FarmTest.setState(s)}")
        page.locator('.compact-management [data-open="overview"]').click()
        assert page.locator('[data-overview-goal-action]').get_attribute('data-action')=='quick-bakery'
        capture(page,'bakery-goal-390','Lv3, one worker and mill; optional existing bakery goal')
        before=state(page)
        page.locator('[data-overview-goal-action]').click()
        assert page.locator('#drawer').is_hidden() and page.locator('#placement').is_visible()
        assert state(page)['gold']==before['gold']
        page.locator('[data-action="cancel-mode"]').click()
        assert state(page)['gold']==before['gold']
        page.close()
    check('可选面包房目标复用建造入口，取消不扣款不增持久规则',optional_bakery_goal)
    def operations_feedback():
        page=page_new(width=390,height=844,embedded=True)
        page.evaluate("()=>{const s=FarmTest.getState();s.options.autoSell=false;s.inventory.carrot=160;s.workers=[{id:1,target:null,lastAt:0,status:'idle',handled:0}];s.nextWorkAt=4000;s.tiles[2]={type:'building',kind:'kitchen',paused:false,job:{item:'meal',startedAt:-50000,readyAt:0}};FarmTest.setState(s);FarmTest.open('overview')}")
        assert '等待入库' in page.locator('#workshop-label').inner_text()
        assert '仓库空间不足' in page.locator('[data-overview-crew]').inner_text()
        page.evaluate("FarmTest.open('settings')")
        assert page.locator('[data-tools-reason]').inner_text()==page.evaluate('FarmEngine.toolUpgradeOffer(FarmTest.getState()).message')
        capture(page,'upgrade-reason-390','existing upgrade is disabled with engine reason')
        page.close()
    check('满仓待收与暂停待料反馈、升级不可用原因明确',operations_feedback)
    def narrow_recipe_layout():
        for width in [320,390]:
            page=page_new(width=width,height=540,embedded=True)
            page.evaluate("()=>{const s=FarmTest.getState();s.xp=135;s.gold=1000;s.tiles[2]={type:'building',kind:'mill',paused:false,job:null};s.tiles[3]={type:'building',kind:'bakery',paused:false,job:null};FarmTest.setState(s);FarmTest.open('workshops')}")
            assert '两种路线' in page.locator('.recipe-guide').inner_text()
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert page.locator('.recipe-guide [data-open="orders"]').bounding_box()['height']>=44
            option=page.locator('[data-recipe="2"][data-recipe-item="riceflour"]');option.focus();option.press('Enter')
            assert option.get_attribute('aria-pressed')=='true'
            assert page.evaluate('document.activeElement.dataset.recipeItem')=='riceflour'
            assert not page.evaluate("document.getElementById('drawer-content').scrollWidth>document.getElementById('drawer-content').clientWidth")
            capture(page,f'workshops-{width}','Lv3 existing flour/riceflour and bread/ricecake controls, no new system')
            page.close()
    check('320/390工坊引导与配方可读可点，无横向溢出且切换保焦点',narrow_recipe_layout)
    browser.close()

report={'metadata':metadata,'checks':checks,'screenshots':screenshots,'pageerrors':errors,
        'passed':sum(c['status']=='pass' for c in checks),'total':len(checks)}
(OUT/'continuation-ui-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(f"{report['passed']}/{report['total']} continuation UI checks passed")
raise SystemExit(0 if report['passed']==report['total'] and not errors else 1)
