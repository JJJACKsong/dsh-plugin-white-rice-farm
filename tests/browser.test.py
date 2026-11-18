import os
"""Headless local UI checks. Uses Playwright, a self-contained document, and a
memory localStorage adapter because the test browser blocks navigation to file://.
It does not pretend to validate a user's native filesystem/localStorage policy.
"""
from pathlib import Path
import json, time
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
KEY='dsh-farm-v03'
PREV_KEY='dsh-farm-v02'
OLD_KEY='dsh-farm-v01'
HTML_PATH=Path(os.environ.get('FARM_HTML_PATH',ROOT/'index.html'))
ARTIFACTS=Path(os.environ.get('FARM_ARTIFACT_DIR',ROOT/'tests'))
ARTIFACTS.mkdir(parents=True,exist_ok=True)
HTML=HTML_PATH.read_text(encoding='utf-8')
RESULTS=[]
ERRORS=[]

def bootstrap(store=None, adapter=True, wall=None):
    js='window.FARM_TEST_MODE=true;'
    if wall is not None:
        js+='Date.now=()=>'+json.dumps(wall)+';'
    if adapter:
        js+='window.__store='+json.dumps(store or {},ensure_ascii=False)+';'
        js+="Object.defineProperty(window,'localStorage',{value:{getItem:k=>window.__store[k]||null,setItem:(k,v)=>window.__store[k]=String(v),removeItem:k=>delete window.__store[k]}});"
    return '<script>'+js+'</script>'

with sync_playwright() as p:
    exe=os.environ.get('CHROMIUM_PATH') or ('/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None)
    browser=p.chromium.launch(executable_path=exe,headless=True,args=['--no-sandbox'])
    def page_new(store=None,width=1280,adapter=True,height=1050,touch=False,wall=None):
        page=browser.new_page(viewport={'width':width,'height':height},has_touch=touch)
        page.on('pageerror',lambda e:ERRORS.append(str(e)))
        page.set_content(HTML.replace('<head>','<head>'+bootstrap(store,adapter,wall)),wait_until='load')
        page.wait_for_function('!!window.FarmTest')
        return page
    def state(page):return page.evaluate('FarmTest.getState()')
    def test(name,fn):
        try:
            fn();RESULTS.append({'name':name,'pass':True});print('PASS',name,flush=True)
        except Exception as exc:
            RESULTS.append({'name':name,'pass':False,'error':str(exc)});print('FAIL',name,str(exc),flush=True)
    def first():
        page=page_new();assert page.locator('#board button').count()==16
        assert page.locator('#gold').inner_text()=='100'
        assert page.locator('#drawer').is_hidden()
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        page.close()
    test('初次加载：4×4 地图，主界面无弹窗、无横向溢出',first)
    def all_harvest():
        page=page_new();page.locator('#harvest-button').click()
        s=state(page);assert s['stats']['harvests']==2;assert s['gold']==100
        assert all(s['tiles'][i]['crop'] for i in [32,33,34,18])
        page.close()
    test('一次点击完成全田收获与补种',all_harvest)
    def point_plant():
        page=page_new();page.locator('#crop-options [data-crop="wheat"]').click();page.locator('[data-tile="51"]').click()
        s=state(page);assert s['tiles'][51]['crop']=='wheat';assert s['gold']==88
        assert page.locator('#drawer').is_hidden(),'种完以后不应多弹一次检查面板'
        page.close()
    test('选作物后直接点空地，只扣一次开垦费',point_plant)
    def rice():
        page=page_new();page.locator('#crop-options [data-crop="rice"]').click();page.locator('[data-tile="51"]').click()
        assert state(page)['gold']==100;assert '水井' in page.locator('#notice-text').inner_text()
        page.locator('[data-tile="16"]').click();assert state(page)['tiles'][16]['crop']=='rice'
        page.close()
    test('水稻放置反馈明确，失败不扣款',rice)
    def drag():
        page=page_new();before=state(page);boxes=[page.locator(f'[data-tile="{i}"]').bounding_box() for i in [48,49,50]]
        centers=[(b['x']+b['width']/2,b['y']+b['height']/2) for b in boxes]
        page.mouse.move(*centers[0]);page.mouse.down();page.mouse.move(*centers[1],steps=8);page.mouse.move(*centers[2],steps=8);page.mouse.up()
        s=state(page)
        assert s['gold']==before['gold'],'拖动不能种植扣款'
        assert all(s['tiles'][i].get('crop') is None for i in [48,49,50]),'拖动过的空地不能连种'
        assert page.locator('#drawer').is_hidden()
        page.locator('[data-tile="51"]').click();assert state(page)['tiles'][51]['crop']=='carrot'
        page.close()
    test('拖动地图不操作地块；单击仍可种植',drag)
    def build():
        page=page_new();page.evaluate("(()=>{let s=FarmTest.getState();s.inventory.rice=8;FarmTest.setState(s)})()")
        page.locator('.farm-actions [data-open="build"]').click();page.locator('[data-build="kitchen"]').click()
        assert page.locator('#placement').is_visible();page.locator('[data-tile="2"]').click()
        s=state(page);assert s['gold']==20;assert s['inventory']['rice']==6;assert s['tiles'][2]['job'] is not None
        assert page.locator('#placement').is_hidden();assert page.locator('#drawer').is_hidden()
        page.evaluate('FarmTest.advance(50000)');assert state(page)['inventory']['meal']==1
        page.close()
    test('灶台两步放置，自动加工，完成后自动接下一批',build)
    def expand():
        page=page_new();page.locator('#expand-button').click();assert page.locator('#board button').count()==36
        page.locator('[data-tile="4"]').click();s=state(page);assert sum(t is not None for t in s['tiles'])==20;assert s['gold']==40
        assert page.locator('#placement').is_hidden();page.close()
    test('点扩地后选一片高亮区域，准确新增四格',expand)
    def recruit():
        page=page_new();page.evaluate("(()=>{let s=FarmTest.getState();s.gold=300;s.inventory.meal=3;FarmTest.setState(s)})()")
        page.locator('#crew-recruit [data-action="recruit"]').click();s=state(page)
        assert len(s['workers'])==1;assert s['inventory']['meal']==0;assert s['stats']['harvests']==2
        assert page.locator('select').count()==0
        page.evaluate('FarmTest.advance(60000)');assert state(page)['stats']['harvests']>2
        page.close()
    test('招工后自动上岗，完全不需要分配职业',recruit)
    def plans():
        page=page_new();page.locator('#harvest-button').click();page.locator('[data-tile="32"]').click()
        assert page.locator('#drawer').is_visible();page.locator('[data-plan="wheat"]').click()
        s=state(page);assert s['tiles'][32]['crop']=='carrot';assert s['tiles'][32]['plan']=='wheat'
        page.keyboard.press('Escape');assert page.locator('#drawer').is_hidden();page.close()
    test('修改下一轮作物，不铲掉当前作物；Escape 关闭',plans)

    def growth():
        page=page_new();s=state(page);s['xp']=45;s['gold']=1000;page.evaluate('(v)=>FarmTest.setState(v)',s)
        assert page.locator('#farm-level').inner_text()=='庄园 Lv.2'
        page.locator('#farm-level').click();assert page.locator('#drawer-title').inner_text()=='庄园成长'
        assert '磨坊' in page.locator('#drawer-content').inner_text()
        page.locator('[data-action="close-drawer"]').click()
        page.locator('.farm-actions [data-open="build"]').click()
        assert not page.locator('[data-build="mill"]').is_disabled()
        assert page.locator('[data-build="bakery"]').is_disabled()
        page.close()
    test('庄园声望显示、成长面板和高阶建筑解锁状态一致',growth)

    def rice_recipe_controls():
        page=page_new(width=390)
        page.evaluate("""()=>{const s=FarmTest.getState();s.xp=45;s.gold=1000;s.options.autoSell=false;s.inventory.wheat=6;s.inventory.rice=12;FarmEngine.build(s,2,'mill');FarmTest.setState(s)}""")
        page.locator('[data-tile="2"]').click()
        option=page.locator('button[data-recipe-item="riceflour"]')
        assert option.is_disabled()
        page.evaluate('(()=>{const s=FarmTest.getState();s.xp=135;FarmTest.setState(s)})()')
        assert not option.is_disabled()
        option.focus();page.wait_for_timeout(1300)
        assert page.evaluate('document.activeElement.dataset.recipeItem')=='riceflour'
        before=state(page)['tiles'][2]['job']
        option.press('Enter')
        assert state(page)['tiles'][2]['nextRecipe']=='riceflour'
        assert state(page)['tiles'][2]['job']==before
        assert page.evaluate('document.activeElement.dataset.recipeItem')=='riceflour'
        assert page.locator('button[data-recipe-item="riceflour"]').get_attribute('aria-pressed')=='true'
        page.close()
    test('米食配方等级即时解锁，键盘切换保留在制品和焦点',rice_recipe_controls)

    def live_storage_upgrade():
        page=page_new()
        page.evaluate("""()=>{const s=FarmTest.getState();s.gold=0;s.inventory.carrot=80;s.options.autoSell=true;FarmTest.setState(s);FarmTest.open('inventory')}""")
        button=page.locator('#drawer-content [data-storage-upgrade]')
        assert button.is_disabled();assert '120' in button.inner_text()
        page.evaluate('FarmTest.advance(1000)')
        assert not button.is_disabled();assert '120' in button.inner_text()
        button.focus();page.evaluate('FarmTest.advance(1000)')
        assert page.evaluate("document.activeElement.dataset.storageUpgrade!==undefined")
        page.evaluate("FarmTest.open('building',1)")
        store=page.locator('#drawer-content [data-storage-upgrade]')
        assert not store.is_disabled();assert '仓库扩容 100 格' in store.inner_text()
        page.close()
    test('仓库扩容随实际收入启用，库存与仓库入口一致且焦点保留',live_storage_upgrade)

    def live_tools_upgrade():
        page=page_new()
        page.evaluate("""()=>{const s=FarmTest.getState();s.gold=200;s.inventory.meal=3;FarmEngine.recruit(s);s.gold=20;s.inventory.carrot=82;s.options.autoSell=true;FarmTest.setState(s);FarmTest.open('building',0)}""")
        button=page.locator('#drawer-content [data-tools-upgrade]')
        assert button.is_disabled();assert '180' in button.inner_text()
        page.evaluate('FarmTest.advance(1000)')
        assert not button.is_disabled()
        button.focus();page.evaluate('FarmTest.advance(1000)')
        assert page.evaluate("document.activeElement.dataset.toolsUpgrade!==undefined")
        page.evaluate("FarmTest.open('settings')")
        settings=page.locator('#drawer-content [data-tools-upgrade]')
        assert not settings.is_disabled()
        page.evaluate("""()=>{const s=FarmTest.getState();s.toolLevel=3;FarmTest.setState(s)}""")
        assert settings.is_disabled();assert '农具已升满' in settings.inner_text()
        assert '4 / 4' in page.locator('#drawer-content [data-tools-level]').inner_text()
        page.evaluate("""()=>{const s=FarmTest.getState();s.toolLevel=0;s.workers=[];s.gold=1000;FarmTest.setState(s)}""")
        assert settings.is_disabled();assert '180' in settings.inner_text()
        page.close()
    test('农具升级统一资金/招工/满级条件，房屋与设置入口同步',live_tools_upgrade)

    def live_recruit_offer():
        page=page_new()
        page.evaluate("""()=>{const s=FarmTest.getState();s.gold=1000;FarmEngine.build(s,2,'kitchen');s.stats.harvests=1;s.gold=40;s.inventory.meal=3;s.inventory.carrot=82;s.options.autoSell=true;FarmTest.setState(s);FarmTest.open('overview')}""")
        button=page.locator('#drawer-content [data-recruit-button]')
        goal=page.locator('#drawer-content [data-overview-goal-action]')
        assert goal.get_attribute('data-action')=='recruit' and goal.is_disabled()
        need=page.evaluate('FarmEngine.RECRUITS[0].gold')
        assert button.is_disabled();assert str(need) in page.locator('#drawer-content [data-recruit-gold]').inner_text()
        page.evaluate('FarmTest.advance(1000)')
        assert not button.is_disabled()
        assert goal.is_enabled()
        button.focus();page.evaluate('FarmTest.advance(1000)')
        assert page.evaluate("document.activeElement.dataset.recruitButton!==undefined")
        page.evaluate("""()=>{const s=FarmTest.getState();FarmEngine.recruit(s);FarmTest.setState(s)}""")
        assert '1 / 4' in page.locator('#drawer-content [data-recruit-title]').inner_text()
        assert button.inner_text()=='再招一只'
        assert button.is_disabled()
        next_gold=page.evaluate('FarmEngine.RECRUITS[FarmTest.getState().workers.length].gold')
        next_meal=page.evaluate('FarmEngine.RECRUITS[FarmTest.getState().workers.length].meal')
        assert str(next_gold) in page.locator('#drawer-content [data-recruit-gold]').inner_text()
        assert str(next_meal) in page.locator('#drawer-content [data-recruit-meal]').inner_text()
        assert goal.get_attribute('data-action')=='open-growth'
        page.close()
    test('概览招工卡随金币/白饭/人数更新，焦点不在计时刷新中丢失',live_recruit_offer)

    def live_machine_toggle_label():
        page=page_new()
        page.evaluate("""()=>{const s=FarmTest.getState();s.xp=45;s.gold=1000;s.options.autoSell=false;s.inventory.wheat=6;FarmEngine.build(s,2,'mill');FarmTest.setState(s);FarmTest.open('building',2)}""")
        button=page.locator('#drawer-content [data-toggle-machine="2"]')
        assert button.inner_text()=='做完这批后暂停'
        button.click()
        button=page.locator('#drawer-content [data-toggle-machine="2"]')
        assert button.inner_text()=='取消完成后暂停'
        page.evaluate('FarmTest.advance(45000)')
        assert button.inner_text()=='恢复生产'
        page.close()
    test('暂停工坊完成当前批后，toggle 文案自动回到恢复生产',live_machine_toggle_label)

    def live_growth_level_title():
        page=page_new()
        page.evaluate("""()=>{const s=FarmTest.getState();s.gold=1000;s.xp=44;FarmTest.setState(s);FarmTest.open('growth')}""")
        top=page.locator('#drawer-content [data-growth-level]')
        assert 'Lv.1' in top.inner_text()
        page.locator('#drawer [data-action="close-drawer"]').focus()
        page.evaluate("""()=>{const s=FarmTest.getState();const r=FarmEngine.build(s,3,'well');if(!r.ok)throw Error(r.message);FarmTest.setState(s)}""")
        assert 'Lv.2' in top.inner_text()
        title=page.evaluate('FarmEngine.levelProgress(FarmTest.getState()).title')
        assert title in top.inner_text()
        assert page.evaluate("document.activeElement.dataset.action")=='close-drawer'
        page.close()
    test('成长面板顶部等级与称号随升级同步，焦点保留',live_growth_level_title)

    def levelup_notice():
        page=page_new();s=state(page);s['xp']=42;page.evaluate('(v)=>FarmTest.setState(v)',s)
        page.locator('#harvest-button').click()
        assert page.locator('#farm-level').inner_text()=='庄园 Lv.2'
        assert '庄园升到 Lv.2' in page.locator('#notice-text').inner_text()
        page.close()
    test('庄园升级即时反馈，经营操作与等级奖励同步结算',levelup_notice)

    def live_unlock():
        page=page_new();s=state(page);s['gold']=1000;page.evaluate('(v)=>FarmTest.setState(v)',s)
        page.locator('.farm-actions [data-open="build"]').click()
        mill=page.locator('[data-build="mill"]');assert mill.is_disabled();assert 'Lv.2' in mill.inner_text()
        s=state(page);s['xp']=45;page.evaluate('(v)=>FarmTest.setState(v)',s)
        assert not mill.is_disabled();assert mill.inner_text()=='200 金币'
        page.close()
    test('建造面板打开时庄园升级，锁定状态与造价即时刷新',live_unlock)
    def legacy_import_feedback():
        results=[]
        for enabled in [True,False]:
            page=page_new()
            page.evaluate("""enabled=>{const old=FarmEngine.initial(Date.now());old.version=2;delete old.shops;old.options.autoSell=enabled;old.gold=233;localStorage.setItem('dsh-farm-v02',JSON.stringify(old))}""",enabled)
            raw=page.evaluate("localStorage.getItem('dsh-farm-v02')")
            page.locator('.header-right [data-open="settings"]').click();page.locator('[data-action="import-old"]').click()
            current=state(page);notice=page.locator('#notice-text').inner_text()
            assert current['gold']==233 and current['options']['autoSell'] is enabled
            assert ('已开启' if enabled else '已暂停') in notice,notice
            assert page.evaluate("localStorage.getItem('dsh-farm-v02')")==raw
            results.append({'enabled':enabled,'notice':notice});page.close()
        return results
    test('手动导入v2保留售货设置，反馈与开启/暂停实际状态一致',legacy_import_feedback)
    def export():
        page=page_new();page.evaluate("HTMLAnchorElement.prototype.click=function(){window.__export={url:this.href,name:this.download}}")
        page.locator('.header-right [data-open="settings"]').click();page.locator('[data-action="export-save"]').click()
        data=page.evaluate("async()=>({name:__export.name,data:await (await fetch(__export.url)).json()})")
        assert data['data']['version']==3;assert data['name'].endswith('.json');page.close()
    test('导出按钮生成可解析的 JSON 存档 Blob',export)
    def import_file():
        page=page_new();s=state(page);s['gold']=9876
        page.locator('#import-input').set_input_files({'name':'farm.json','mimeType':'application/json','buffer':json.dumps(s).encode()})
        page.wait_for_function('FarmTest.getState().gold===9876')
        page.locator('#import-input').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{not-json}'})
        page.wait_for_function("document.getElementById('notice-text').textContent.includes('导入失败')")
        assert state(page)['gold']==9876;page.close()
    test('导入存档成功；损坏文件不覆盖当前农场',import_file)
    def persistence():
        page=page_new();page.locator('#harvest-button').click();page.evaluate('FarmTest.save()');saved=page.evaluate('window.__store');before=state(page);page.close()
        again=page_new(saved);after=state(again);assert after['gold']==before['gold'];assert after['stats']['harvests']==before['stats']['harvests'];again.close()
    test('保存再加载恢复进度，不重复发放收获（存储适配器）',persistence)
    def return_time_boundaries():
        # Fixed wall-clock inputs isolate boot settlement; this uses the existing
        # storage adapter and is not native navigation / official DSH evidence.
        wall=1800000000000
        oracle=page_new(wall=wall)
        seed=oracle.evaluate('''wall=>{const s=FarmEngine.initial(wall);s.xp=140;s.gold=800;s.options.autoSell=false;s.inventory.wheat=5;s.inventory.rice=3;if(!FarmEngine.build(s,2,'mill').ok||!FarmEngine.changeRecipe(s,2,'riceflour').ok)throw Error('Fixture actions failed');FarmEngine.advance(s,42000);return s;}''',wall)
        cap=oracle.evaluate('FarmEngine.OFFLINE_CAP')
        cases=[('v3',seed,elapsed,KEY) for elapsed in [0,1,4000,5000,5001,cap-1,cap,cap+1]]
        paused=json.loads(json.dumps(seed));paused['tiles'][2]['paused']=True
        cases.append(('paused-next-batch',paused,4000,KEY))
        old_v2=json.loads(json.dumps(seed));old_v2['version']=2;old_v2.pop('xp');old_v2['tiles'][2].pop('nextRecipe')
        cases.append(('old-v2-defaults',old_v2,4000,PREV_KEY))
        old_client=json.loads(json.dumps(seed));old_client['version']=2;old_client.pop('shops')
        cases.append(('old-v2-no-shops',old_client,4000,PREV_KEY))
        old_v1={'ver':1,'gold':233,'inventory':{'meal':7},'last':wall,'tiles':{'0':{'type':'building','kind':'house'},'1':{'type':'building','kind':'store'},'16':{'type':'field','crop':'wheat','readyAt':wall+2000},'17':{'type':'grass'}},'workers':[],'jobs':[],'completed':2}
        cases.append(('v1-migration',old_v1,4000,OLD_KEY))
        try:
            for label,raw,elapsed,key in cases:
                expected=oracle.evaluate('''({raw,elapsed,wall})=>{const s=FarmEngine.restore(raw,wall+elapsed);if(elapsed)FarmEngine.advance(s,elapsed);s.savedAt=wall+elapsed;return s;}''',{'raw':raw,'elapsed':elapsed,'wall':wall})
                saved=json.dumps(raw)
                page=page_new({key:saved},wall=wall+elapsed)
                try:
                    after=state(page)
                    assert after==expected,(label,elapsed,after,expected)
                    assert page.evaluate("JSON.parse(localStorage.getItem('dsh-farm-v03'))")==expected
                    if key in (PREV_KEY,OLD_KEY):
                        assert page.evaluate('(k)=>localStorage.getItem(k)',key)==saved
                    if label=='v3' and elapsed<=5000:
                        assert '离开了' not in page.locator('#notice-text').inner_text()
                finally:
                    page.close()
        finally:
            oracle.close()
    test('短返与八小时边界按同一引擎结算，保留暂停/下一批与旧档（时钟及存储适配器）',return_time_boundaries)
    def legacy_key_isolation():
        # preview.5 只写 v02 且不认识 shops；preview.7 只读 v03，旧版再次保存不能覆盖新货架。
        wall=1800000000000
        oracle=page_new(wall=wall)
        old=oracle.evaluate("""wall=>{const s=FarmEngine.initial(wall);s.version=2;s.savedAt=wall;s.options.autoSell=false;s.inventory.carrot=7;delete s.shops;return s}""",wall)
        oracle.close()
        page=page_new({PREV_KEY:json.dumps(old)},wall=wall)
        page.evaluate("""()=>{const s=FarmTest.getState();if(!FarmEngine.listRetail(s,'produce','carrot',1).ok)throw Error('migration shelf setup failed');FarmTest.setState(s);FarmTest.save()}""")
        assert state(page)['shops']['produce']['qty']==1
        overwritten=json.loads(json.dumps(old));overwritten['gold']=777
        page.evaluate('(v)=>localStorage.setItem("dsh-farm-v02",v)',json.dumps(overwritten))
        stored=page.evaluate('window.__store');page.close()
        again=page_new(stored,wall=wall+1000)
        after=state(again)
        assert after['shops']['produce']['qty']==1 and after['inventory']['carrot']==6 and after['gold']==100,after
        assert json.loads(stored['dsh-farm-v02'])['gold']==777
        assert json.loads(stored[KEY])['shops']['produce']['qty']==1
        again.close()
    test('旧版 v02 再次保存不会覆盖新键 v03 的货架和金币',legacy_key_isolation)
    def old_import():
        page=page_new();page.evaluate("(()=>{const old={ver:1,gold:233,inventory:{meal:7},last:Date.now(),tiles:{0:{type:'building',kind:'house'},1:{type:'building',kind:'store'},16:{type:'field',crop:null},17:{type:'grass'}},workers:[],jobs:[],completed:2};localStorage.setItem('dsh-farm-v01',JSON.stringify(old));})()")
        page.locator('.header-right [data-open="settings"]').click();page.locator('[data-action="import-old"]').click()
        s=state(page);assert s['gold']==233;assert s['inventory']['meal']==7;assert s['options']['autoSell'] is False
        assert page.evaluate("JSON.parse(localStorage.getItem('dsh-farm-v01')).gold")==233;page.close()
    test('旧版存档复制到新版，原数据保持不变',old_import)
    def storage_disabled():
        page=page_new(adapter=False);assert '存档受限' in page.locator('#save-status').inner_text()
        page.locator('#harvest-button').click();assert state(page)['gold']==100;page.close()
    test('浏览器禁止存档时仍可玩，并显示限制提示',storage_disabled)
    def keyboard_focus():
        page=page_new();page.locator('#crop-options [data-crop="carrot"]').focus();page.wait_for_timeout(1300)
        assert page.evaluate("document.activeElement.dataset.crop==='carrot'")
        page.close()
    test('每秒更新不会把键盘焦点从作物按钮上移走',keyboard_focus)
    def responsive():
        page=page_new(width=1440);page.screenshot(path=str(ARTIFACTS/'desktop-initial.png'),full_page=True)
        for width in [768,390,320]:
            page.set_viewport_size({'width':width,'height':844});page.wait_for_timeout(170)
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),width
            if width==390:page.screenshot(path=str(ARTIFACTS/'mobile-initial.png'),full_page=True)
        page.close()
    test('1440 / 768 / 390 / 320 像素布局不横向溢出',responsive)

    def narrow_initial():
        for width in (390,320):
            page=page_new(width=width)
            m=page.evaluate("""()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect();return {tile:t.width,scroll:[v.scrollWidth,v.scrollHeight],client:[v.clientWidth,v.clientHeight],body:document.body.scrollWidth,inner:innerWidth}}""")
            assert m['tile']>=44,m
            assert m['scroll'][0]<=m['client'][0]+1 and m['scroll'][1]<=m['client'][1]+1,m
            assert m['body']<=m['inner']
            page.close()
    test('390/320 窄屏初始 4×4 自然适配且地块≥44',narrow_initial)

    def full_map(page):
        page.evaluate("""()=>{let s=FarmTest.getState();s.gold=1e7;while(FarmEngine.eligibleChunks(s).length){let c=FarmEngine.eligibleChunks(s)[0];FarmEngine.expand(s,c.x,c.y)}FarmTest.setState(s)}""")
    def map_view_and_overview():
        page=page_new();full_map(page)
        m=page.evaluate("""()=>{const b=document.querySelector('#board'),v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect();return {tile:t.width,scroll:[v.scrollWidth,v.scrollHeight],client:[v.clientWidth,v.clientHeight],body:document.body.scrollWidth,inner:innerWidth}}""")
        assert m['tile']>=44,m
        assert m['scroll'][0]>m['client'][0] and m['scroll'][1]>m['client'][1],m
        assert m['body']<=m['inner']
        page.locator('[data-map-action="fit"]').click();page.wait_for_timeout(50)
        fit=page.evaluate("""()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect(),b=document.querySelector('[data-map-action="fit"]');return {tile:t.width,scroll:[v.scrollWidth,v.scrollHeight],client:[v.clientWidth,v.clientHeight],pressed:b.getAttribute('aria-pressed')}}""")
        assert fit['tile']<44,fit
        assert fit['pressed']=='true'
        assert fit['scroll'][0]<=fit['client'][0]+1 and fit['scroll'][1]<=fit['client'][1]+1,fit
        colors=page.locator('[data-map-action="fit"]').evaluate("""e=>{const s=getComputedStyle(e),rgb=v=>v.match(/[\\d.]+/g).slice(0,3).map(Number);return {fg:rgb(s.color),bg:rgb(s.backgroundColor)}}""")
        def luminance(rgb):
            channels=[v/255/12.92 if v/255<=.04045 else ((v/255+.055)/1.055)**2.4 for v in rgb]
            return sum(c*w for c,w in zip(channels,[.2126,.7152,.0722]))
        lights=sorted([luminance(colors['fg']),luminance(colors['bg'])])
        assert (lights[1]+.05)/(lights[0]+.05)>=4.5,colors
        page.locator('[data-map-action="fit"]').click();page.wait_for_timeout(40)
        back=page.evaluate("""()=>{const t=document.querySelector('.tile').getBoundingClientRect();return {tile:t.width,pressed:document.querySelector('[data-map-action="fit"]').getAttribute('aria-pressed')}}""")
        assert back['tile']>=44 and back['pressed']=='false',back
        page.locator('[data-map-action="fit"]').click();page.wait_for_timeout(40)
        before=state(page);page.locator('[data-tile="255"]').click();page.wait_for_timeout(60)
        locate=state(page)
        assert locate['gold']==before['gold'] and locate['tiles'][255].get('crop') is None,'全景点击不能操作地块'
        assert page.locator('[data-tile="255"]').bounding_box()['width']>=44
        assert page.locator('[data-map-action="fit"]').get_attribute('aria-pressed')=='false'
        assert page.locator('[data-tile="255"]').is_visible()
        page.locator('[data-tile="255"]').click();assert state(page)['tiles'][255]['crop']=='carrot'
        page.close()
    test('全景只定位；扩展地图正常视图地块≥44且两轴可滚动',map_view_and_overview)

    def pan_then_hit():
        page=page_new();full_map(page)
        page.evaluate("()=>{const v=document.querySelector('#board-scroll');v.scrollLeft=0;v.scrollTop=0}")
        before=state(page);box=page.locator('[data-tile="32"]').bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-130,y-110,steps=8);page.mouse.up();page.wait_for_timeout(40)
        after=state(page);scroll=page.evaluate("()=>{const v=document.querySelector('#board-scroll');return [v.scrollLeft,v.scrollTop]}")
        assert scroll[0]>0 and scroll[1]>0,scroll
        assert after['gold']==before['gold'] and after['stats']['harvests']==before['stats']['harvests']
        assert after['tiles'][32]['crop']=='carrot'
        assert page.locator('#drawer').is_hidden()
        page.locator('[data-tile="32"]').click()
        hit=state(page);assert hit['stats']['harvests']==before['stats']['harvests']+1,hit['stats']['harvests']
        page.close()
    test('拖动只平移，平移到远角后点击命中实际地块',pan_then_hit)

    def drag_modes():
        page=page_new();page.evaluate("()=>{const s=FarmTest.getState();s.gold=1000;FarmTest.setState(s)}")
        page.locator('.farm-actions [data-open="build"]').click();page.locator('[data-build="kitchen"]').click()
        assert page.locator('#placement').is_visible()
        before=state(page);box=page.locator('[data-tile="51"]').bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+45,y-45,steps=8);page.mouse.up();page.wait_for_timeout(30)
        mid=state(page);assert mid['gold']==before['gold'] and mid['tiles'][51]['type']=='grass';assert page.locator('#placement').is_visible()
        page.locator('[data-tile="51"]').click();assert state(page)['tiles'][51]['type']=='building'
        page.close()

        page=page_new();page.evaluate("()=>{const s=FarmTest.getState();s.gold=1000;FarmTest.setState(s)}")
        page.locator('#expand-button').click();eligible=page.locator('#board .eligible').first;assert page.locator('#board .eligible').count()>0
        target=int(eligible.get_attribute('data-tile'))
        before=state(page);owned_before=sum(t is not None for t in before['tiles']);box=eligible.bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-35,y+35,steps=8);page.mouse.up();page.wait_for_timeout(30)
        mid=state(page);assert mid['gold']==before['gold'] and sum(t is not None for t in mid['tiles'])==owned_before;assert page.locator('#placement').is_visible()
        page.locator('#board .eligible').first.click();after=state(page)
        assert after['gold']<before['gold'] and sum(t is not None for t in after['tiles'])==owned_before+4
        assert page.locator('#placement').is_hidden()
        assert page.locator(f'[data-tile="{target}"]').is_visible(),'刚买的土地应在视口内'
        page.close()

        page=page_new();page.locator('[data-tile="0"]').click();page.locator('[data-action="move-building"]').click()
        assert page.locator('#placement').is_visible()
        box=page.locator('[data-tile="51"]').bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+40,y-40,steps=8);page.mouse.up();page.wait_for_timeout(30)
        mid=state(page);assert mid['tiles'][0]['type']=='building' and mid['tiles'][51]['type']=='grass'
        page.locator('[data-tile="51"]').click();assert state(page)['tiles'][0]['type']=='grass' and state(page)['tiles'][51]['type']=='building'
        page.close()
    test('建造、扩地与搬家模式拖动不扣款不落建筑',drag_modes)

    def touch_cancel_and_keyboard():
        page=page_new(touch=True)
        page.evaluate("""()=>{window.touchEvents=[];for(const type of ['pointerdown','pointerup','pointercancel','click'])document.addEventListener(type,e=>{touchEvents.push({type,id:e.pointerId,primary:e.isPrimary,detail:e.detail,tile:e.target.closest('[data-tile]')?.dataset.tile});if(touchEvents.length>30)touchEvents.shift()},true)}""")
        page.evaluate("""()=>{const t=document.querySelector('[data-tile="48"]'),v=document.querySelector('#board-scroll'),r=t.getBoundingClientRect();const o={bubbles:true,cancelable:true,pointerId:91,pointerType:'touch',isPrimary:true,button:0,buttons:1,clientX:r.left+r.width/2,clientY:r.top+r.height/2};t.dispatchEvent(new PointerEvent('pointerdown',o));v.dispatchEvent(new PointerEvent('pointermove',Object.assign({},o,{clientX:o.clientX+70,clientY:o.clientY+20})));v.dispatchEvent(new PointerEvent('pointercancel',o));}""")
        assert state(page)['tiles'][48].get('crop') is None
        box=page.locator('[data-tile="50"]').bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
        client=page.context.new_cdp_session(page)
        client.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
        for i in range(1,6):client.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+10*i,'y':y-8*i}]})
        client.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(60)
        assert state(page)['tiles'][50].get('crop') is None,'真实触摸拖动不能误种'
        gold=state(page)['gold']
        box=page.locator('[data-tile="49"]').bounding_box();page.touchscreen.tap(box['x']+box['width']/2,box['y']+box['height']/2)
        try:
            page.wait_for_function("FarmTest.getState().tiles[49].crop==='carrot'",timeout=3000)
        except Exception as exc:
            raise AssertionError({'phase':'tap_after_touch_drag','tile':state(page)['tiles'][49],'events':page.evaluate('touchEvents')}) from exc
        page.wait_for_timeout(400)  # Also allow any delayed native compatibility click.
        assert state(page)['gold']==gold-12 and page.locator('#drawer').is_hidden(),'一次轻触只种植一次，不补开详情'
        harvested=state(page)['stats']['harvests']
        box=page.locator('[data-tile="32"]').bounding_box();page.touchscreen.tap(box['x']+box['width']/2,box['y']+box['height']/2)
        page.wait_for_function('(n)=>FarmTest.getState().stats.harvests===n+1',arg=harvested,timeout=3000)
        page.wait_for_timeout(400)
        assert state(page)['stats']['harvests']==harvested+1 and page.locator('#drawer').is_hidden(),'轻触收获一次，不重复触发'
        gold=state(page)['gold']
        page.evaluate("""()=>{
         for(const [i,id] of [[48,101],[51,102]]){const t=document.querySelector(`[data-tile="${i}"]`),r=t.getBoundingClientRect(),o={bubbles:true,pointerId:id,pointerType:'touch',isPrimary:true,button:0,clientX:r.left+r.width/2,clientY:r.top+r.height/2};t.dispatchEvent(new PointerEvent('pointerdown',{...o,buttons:1}));t.dispatchEvent(new PointerEvent('pointerup',{...o,buttons:0}));}
         for(const [i,id] of [[48,101],[51,102]])document.querySelector(`[data-tile="${i}"]`).dispatchEvent(new PointerEvent('click',{bubbles:true,pointerId:id,pointerType:'touch',detail:1}));
        }""")
        assert state(page)['gold']==gold-24 and page.locator('#drawer').is_hidden(),'连续轻触后分别补发的点击不能重复操作'
        box=page.locator('[data-tile="0"]').bounding_box();page.touchscreen.tap(box['x']+box['width']/2,box['y']+box['height']/2)
        page.locator('#drawer').wait_for(state='visible')
        page.wait_for_timeout(400)
        assert page.locator('#drawer').is_visible(),'补发的触摸点击不能落到遮罩并关掉刚打开的建筑详情'
        page.close()

        page=page_new();box=page.locator('[data-tile="50"]').bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+60,y,steps=8);page.mouse.up();page.wait_for_timeout(20)
        page.locator('[data-tile="48"]').focus();page.keyboard.press('Enter')
        assert state(page)['tiles'][48].get('crop')=='carrot','拖动后第一次键盘 Enter 应种植 48'
        page.keyboard.press('ArrowRight');assert page.evaluate('document.activeElement.dataset.tile')=='49'
        page.keyboard.press('Enter');assert state(page)['tiles'][49].get('crop')=='carrot','方向键定位后 Enter 应种植 49'
        page.close()
    test('触摸取消不误种，拖动后键盘 Enter/方向键仍可操作',touch_cancel_and_keyboard)

    def tick_resize_keeps_view():
        page=page_new();full_map(page)
        page.locator('[data-tile="51"]').click();assert state(page)['tiles'][51].get('crop')=='carrot'
        page.locator('[data-map-action="zoom-out"]').click();page.locator('[data-map-action="zoom-out"]').click();page.wait_for_timeout(30)
        page.evaluate("()=>{const v=document.querySelector('#board-scroll');v.scrollLeft=280;v.scrollTop=260}")
        panel_before=page.evaluate("()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect();return {scroll:[v.scrollLeft,v.scrollTop],tile:t.width}}")
        page.locator('#farm-level').click();assert page.locator('#drawer').is_visible();page.locator('#drawer [data-action="close-drawer"]').click()
        panel_after=page.evaluate("()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect();return {scroll:[v.scrollLeft,v.scrollTop],tile:t.width}}")
        assert panel_after==panel_before,panel_after
        before=page.evaluate("()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect();return {scroll:[v.scrollLeft,v.scrollTop],tile:t.width}}")
        page.evaluate('FarmTest.advance(1000)');page.wait_for_timeout(20)
        after=page.evaluate("()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect();return {scroll:[v.scrollLeft,v.scrollTop],tile:t.width}}")
        assert after==before,after
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(180)
        resized=page.evaluate("()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect();return {scroll:[v.scrollLeft,v.scrollTop],tile:t.width,body:document.body.scrollWidth,inner:innerWidth}}")
        assert resized['tile']>=44 and resized['body']<=resized['inner'],resized
        assert resized['scroll'][0]>0 and resized['scroll'][1]>0,resized
        page.close()
    test('计时刷新与窗口缩放不重置地图视野',tick_resize_keeps_view)

    def short_overview_roundtrip():
        page=page_new(width=320)
        page.evaluate("document.body.classList.add('embedded')")
        page.set_viewport_size({'width':320,'height':540});page.wait_for_timeout(180)
        full_map(page)
        page.evaluate("()=>{const v=document.querySelector('#board-scroll');v.scrollLeft=200;v.scrollTop=240}")
        before=page.locator('#board-scroll').evaluate('(v)=>({left:v.scrollLeft,top:v.scrollTop})')
        fit=page.locator('[data-map-action="fit"]');fit.click()
        dims=page.evaluate("""()=>{const b=document.querySelector('#board').getBoundingClientRect(),v=document.querySelector('#board-scroll');return {board:[b.width,b.height],viewport:[v.clientWidth,v.clientHeight]}}""")
        assert dims['board'][0]<=dims['viewport'][0]+1 and dims['board'][1]<=dims['viewport'][1]+1,dims
        assert '点地块放大' in page.locator('#garden-legend').inner_text()
        fit.click()
        after=page.locator('#board-scroll').evaluate('(v)=>({left:v.scrollLeft,top:v.scrollTop})')
        assert after==before,(before,after)
        page.close()
    test('低矮窗口全景完整适配，全景往返保留原视野',short_overview_roundtrip)

    def release_outside_iframe():
        page=browser.new_page(viewport={'width':1280,'height':800})
        page.on('pageerror',lambda e:ERRORS.append(str(e)))
        page.set_content('<iframe id="farm" sandbox="allow-scripts" style="position:absolute;left:80px;top:80px;width:600px;height:550px;border:0"></iframe>')
        doc=HTML.replace('<head>','<head>'+bootstrap()+'<script>window.FARM_EMBEDDED=true;</script>')
        page.locator('#farm').evaluate('(el,doc)=>el.srcdoc=doc',doc)
        frame=page.locator('#farm').element_handle().content_frame()
        frame.wait_for_function('!!window.FarmTest',timeout=15000)
        frame.evaluate("""()=>{const s=FarmTest.getState();s.gold=1e7;while(FarmEngine.eligibleChunks(s).length){const c=FarmEngine.eligibleChunks(s)[0];FarmEngine.expand(s,c.x,c.y)}FarmTest.setState(s)}""")
        viewport=frame.locator('#board-scroll');r=viewport.bounding_box()
        before=viewport.evaluate('(v)=>({left:v.scrollLeft,top:v.scrollTop})')
        page.mouse.move(r['x']+2,r['y']+20);page.mouse.down()
        page.mouse.move(r['x']+2,70);page.mouse.up()
        page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2)
        assert not viewport.evaluate('(v)=>v.classList.contains("is-panning")')
        assert viewport.evaluate('(v)=>({left:v.scrollLeft,top:v.scrollTop})')==before
        frame.locator('[data-tile="48"]').click()
        assert frame.evaluate('FarmTest.getState().tiles[48].crop')=='carrot'
        page.close()
    test('离开隔离面板再松手不留下拖动，返回后的首次点击可用',release_outside_iframe)

    def endgame():
        page=page_new();page.evaluate("(()=>{let s=FarmTest.getState();s.gold=1e7;while(FarmEngine.eligibleChunks(s).length){let c=FarmEngine.eligibleChunks(s)[0];FarmEngine.expand(s,c.x,c.y)}s.inventory.meal=100;s.options.autoSell=false;for(let i=0;i<4;i++)FarmEngine.recruit(s);s.toolLevel=3;FarmTest.setState(s)})()")
        assert page.locator('#board button').count()==256;assert page.locator('#expand-button').is_disabled()
        assert '4 / 4' in page.locator('#crew-count').inner_text()
        m=page.evaluate("""()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect(),b=document.querySelector('#board').getBoundingClientRect(),a=document.querySelector('#actors').getBoundingClientRect();return {tile:t.width,scroll:[v.scrollWidth,v.scrollHeight],client:[v.clientWidth,v.clientHeight],board:[b.left,b.top,b.width,b.height],actors:[a.left,a.top,a.width,a.height],actorCount:document.querySelectorAll('.farm-actor').length}}""")
        assert m['tile']>=44 and m['scroll'][0]>m['client'][0] and m['scroll'][1]>m['client'][1],m
        assert m['actorCount']==4
        assert abs(m['board'][0]-m['actors'][0])<1 and abs(m['board'][1]-m['actors'][1])<1 and abs(m['board'][2]-m['actors'][2])<1 and abs(m['board'][3]-m['actors'][3])<1,m
        page.screenshot(path=str(ARTIFACTS/'desktop-16x16.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(170)
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        narrow=page.evaluate("""()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect();return {tile:t.width,scroll:[v.scrollWidth,v.scrollHeight],client:[v.clientWidth,v.clientHeight]}}""")
        assert narrow['tile']>=44 and narrow['scroll'][0]>narrow['client'][0] and narrow['scroll'][1]>narrow['client'][1],narrow
        page.locator('[data-map-action="fit"]').click();page.wait_for_timeout(50)
        fit=page.evaluate("""()=>{const v=document.querySelector('#board-scroll'),t=document.querySelector('.tile').getBoundingClientRect();return {tile:t.width,scroll:[v.scrollWidth,v.scrollHeight],client:[v.clientWidth,v.clientHeight],pressed:document.querySelector('[data-map-action="fit"]').getAttribute('aria-pressed')}}""")
        assert fit['tile']<44 and fit['pressed']=='true',fit
        assert fit['scroll'][0]<=fit['client'][0]+1 and fit['scroll'][1]<=fit['client'][1]+1,fit
        page.close()
    test('16×16 地块≥44、两轴可达；全景适配且工人层对齐',endgame)
    test('浏览器运行无未捕获 JavaScript 异常',lambda:(_ for _ in ()).throw(AssertionError(ERRORS)) if ERRORS else None)
report={'date':'2026-11-18','environment':'Headless Chromium; page.set_content; in-memory localStorage adapter except fallback test. No native file:// policy verification.','passed':sum(r['pass'] for r in RESULTS),'total':len(RESULTS),'results':RESULTS,'uncaught_errors':ERRORS}
(ARTIFACTS/'browser-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(f"\n{report['passed']}/{report['total']} browser tests passed")
if report['passed']!=report['total']:raise SystemExit(1)
