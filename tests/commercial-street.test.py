#!/usr/bin/env python3
"""Standalone Chromium regression for the R3 commercial-street view and sales paths."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
ARTIFACTS=ROOT/'tests'/'commercial-street-artifacts'
ARTIFACTS.mkdir(exist_ok=True)
# Economy fixtures advance explicitly; real_boot below retains the ordinary wall clock.
BOOT="""<script>window.FARM_TEST_MODE=true;Date.now=()=>1800000000000;window.__store={};Object.defineProperty(window,'localStorage',{value:{getItem:k=>window.__store[k]||null,setItem:(k,v)=>window.__store[k]=String(v),removeItem:k=>delete window.__store[k]}});</script>"""
KEY='dsh-farm-v03'
checks=[]
def check(name,fn):
    detail=fn();checks.append({'name':name,'pass':True,'detail':detail});print('PASS',name,flush=True)
def real_boot(store):
    return '<script>window.__store='+json.dumps(store,ensure_ascii=False)+""";Object.defineProperty(window,'localStorage',{value:{getItem:k=>window.__store[k]||null,setItem:(k,v)=>window.__store[k]=String(v),removeItem:k=>delete window.__store[k]}});</script>"""

with sync_playwright() as p:
    exe=os.environ.get('CHROMIUM_PATH') or None
    browser=p.chromium.launch(executable_path=exe,headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':390,'height':844})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def new_page(width,height,boot=BOOT):
        tab=browser.new_page(viewport={'width':width,'height':height})
        tab.on('pageerror',lambda e:errors.append(str(e)))
        tab.set_content(HTML.replace('<head>','<head>'+boot),wait_until='load')
        return tab
    page.set_content(HTML.replace('<head>','<head>'+BOOT),wait_until='load')
    page.wait_for_function('!!window.FarmTest')
    def setup():
        page.evaluate("""()=>{const s=FarmTest.getState();s.options.autoSell=false;s.xp=135;s.shops.food.open=true;s.inventory.carrot=8;s.inventory.bread=2;FarmTest.setState(s)}""")
        page.locator('#commercial-toggle').click()
        assert page.locator('#commercial-view').is_visible()
        assert page.locator('.street-shop').count()==2
        assert page.locator('.street-backdrop').evaluate("""async img=>{
            await img.decode();
            return img.src.startsWith('data:image/')&&img.naturalWidth>0;
        }""")
        shops=page.locator('.street-shop img').evaluate_all("""async images=>{
            await Promise.all(images.map(img=>img.decode()));
            const scene=document.querySelector('.commercial-street').getBoundingClientRect();
            return images.map(img=>{
                const box=img.getBoundingClientRect();
                return {
                    embedded:img.src.startsWith('data:image/'),
                    decoded:img.naturalWidth>0&&img.naturalHeight>0,
                    visible:box.width>0&&box.height>0&&box.left>=scene.left&&box.right<=scene.right
                        &&box.top>=scene.top&&box.bottom<=scene.bottom
                };
            });
        }""")
        assert shops==[{'embedded':True,'decoded':True,'visible':True}]*2,shops
        g=page.evaluate("""()=>{const v=document.querySelector('#commercial-view').getBoundingClientRect(),a=document.querySelector('.commercial-street').getBoundingClientRect(),d=document.querySelector('.commercial-data');return {ratio:a.height/v.height,street:a.height,data:d.clientHeight,scroll:d.scrollHeight}}""")
        assert .27<=g['ratio']<=.34 and g['data']>g['street'] and g['scroll']>g['data'],g
        page.screenshot(path=str(ARTIFACTS/'commercial-street-390.png'),full_page=True)
        return g
    geometry=check('三七布局、内嵌街景和店铺、数据区独立滚动',setup)
    def focus_timer_and_actions():
        fixture=page.evaluate("""()=>{const s=FarmEngine.initial(Date.now());s.options.autoSell=false;s.xp=135;s.shops.food.open=true;s.inventory.carrot=8;s.inventory.bread=2;s.savedAt=Date.now();return s}""")
        tab=new_page(320,700,real_boot({KEY:json.dumps(fixture)}))
        assert tab.locator('#commercial-toggle').is_visible()
        tab.locator('#commercial-toggle').click()
        tab.wait_for_timeout(1200)
        initial_focus=tab.evaluate('document.activeElement.id')
        assert initial_focus=='farm-toggle',initial_focus
        target=tab.locator('[data-street-action="retail"][data-item="carrot"][data-qty="1"]').first
        target.scroll_into_view_if_needed();target.focus()
        before=tab.evaluate("""selector=>{const e=document.querySelector(selector),r=e.getBoundingClientRect();return {tag:document.activeElement.tagName,text:e.textContent.trim(),focused:document.activeElement===e,w:r.width,h:r.height}}""",'[data-street-action="retail"][data-item="carrot"][data-qty="1"]')
        assert before['tag']=='BUTTON' and before['focused'] and before['w']>0 and before['h']>0,before
        tab.wait_for_timeout(1300)
        after=tab.evaluate("""()=>{const e=document.activeElement,data=document.querySelector('#commercial-data').getBoundingClientRect(),r=e.getBoundingClientRect();return {tag:e.tagName,action:e.dataset.streetAction||'',item:e.dataset.item||'',inView:!!e.closest('#commercial-view'),visible:r.width>0&&r.height>0&&r.bottom>data.top&&r.top<data.bottom,focus:e.matches(':focus')}}""")
        assert after['tag']=='BUTTON' and after['action']=='retail' and after['item']=='carrot' and after['inView'] and after['visible'] and after['focus'],after
        tab.keyboard.press('Enter');tab.wait_for_timeout(180)
        one=json.loads(tab.evaluate("localStorage.getItem('dsh-farm-v03')"))
        assert one['shops']['produce']['qty']==1 and one['inventory']['carrot']==7,one['shops']
        assert tab.evaluate("()=>document.activeElement.dataset.streetAction==='retail'"),'Enter 后焦点应仍在上架按钮'
        tab.keyboard.press('Space');tab.wait_for_timeout(180)
        two=json.loads(tab.evaluate("localStorage.getItem('dsh-farm-v03')"))
        assert two['shops']['produce']['qty']==2 and two['inventory']['carrot']==6,two['shops']
        tab.keyboard.press('Tab')
        tab_state=tab.evaluate("""()=>({tag:document.activeElement.tagName,inView:!!document.activeElement.closest('#commercial-view')})""")
        assert tab_state['tag']=='BUTTON' and tab_state['inView'],tab_state
        tab.locator('#commercial-data').evaluate('(e)=>e.scrollTop=e.scrollHeight')
        scrolled=tab.locator('#commercial-data').evaluate('(e)=>e.scrollTop')
        assert scrolled>0
        tab.wait_for_timeout(1300)
        scrolled_after=tab.locator('#commercial-data').evaluate('(e)=>e.scrollTop')
        assert abs(scrolled_after-scrolled)<2,'定时刷新不应把玩家主动滚动的数据区拉回旧焦点'
        assert tab.evaluate("document.activeElement.tagName")=='BUTTON'
        target=tab.locator('[data-street-action="retail"][data-item="carrot"][data-qty="1"]').first
        target.scroll_into_view_if_needed();box=target.bounding_box()
        tab.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);tab.mouse.down()
        tab.wait_for_timeout(1300);tab.mouse.up();tab.wait_for_timeout(180)
        pressed=json.loads(tab.evaluate("localStorage.getItem('dsh-farm-v03')"))
        assert pressed['shops']['produce']['qty']==3 and pressed['inventory']['carrot']==5,'跨定时刷新的按下/松开必须只成交一次'
        tab.close()
        return {'refresh_focus':after,'enter_shelf':one['shops']['produce'],'space_shelf':two['shops']['produce'],'tab':tab_state,'data_scroll':{'before':scrolled,'after':scrolled_after},'pointer_across_tick_shelf':pressed['shops']['produce']['qty']}
    check('真实定时刷新保留可见焦点，Enter/Space/Tab 在窄窗可继续操作',focus_timer_and_actions)
    def v1_migration_food_shop():
        old={'ver':1,'gold':233,'inventory':{'bread':1},'last':int(time.time()*1000),'tiles':{'0':{'type':'building','kind':'house'},'1':{'type':'building','kind':'store'},'2':{'type':'building','kind':'bakery'},'3':{'type':'grass'}},'workers':[],'jobs':[],'completed':4}
        raw=json.dumps(old,ensure_ascii=False)
        tab=new_page(390,844,real_boot({'dsh-farm-v01':raw}))
        tab.locator('#commercial-toggle').click()
        food=tab.locator('[data-street-action="retail"][data-item="bread"][data-qty="1"]').first
        assert food.is_enabled(),'v1 迁移推定 Lv.3 后食品铺应已解锁'
        food.click();tab.wait_for_timeout(120)
        migrated=json.loads(tab.evaluate("localStorage.getItem('dsh-farm-v03')"))
        assert migrated['version']==3 and migrated['xp']==135 and migrated['shops']['food']['open'] is True,migrated
        assert migrated['inventory']['bread']==0 and migrated['shops']['food']['qty']==1,migrated['shops']
        assert json.loads(tab.evaluate("localStorage.getItem('dsh-farm-v01')"))['inventory']['bread']==1
        tab.close()
        return {'migrated_version':migrated['version'],'food_shelf':migrated['shops']['food']}
    check('v1 迁移完成立即解锁食品铺并可上架面包',v1_migration_food_shop)
    def wholesale():
        before=page.evaluate('FarmTest.getState()')
        page.locator('[data-street-action="wholesale"][data-item="carrot"]').click()
        after=page.evaluate('FarmTest.getState()')
        assert after['inventory']['carrot']==0 and after['gold']==before['gold']+16
        return {'gold_before':before['gold'],'gold_after':after['gold'],'carrot_remaining':after['inventory']['carrot']}
    check('批发报价与库存扣减/金币入账一致',wholesale)
    def auto_toggle():
        btn=page.locator('#street-sale-toggle');assert btn.get_attribute('aria-pressed')=='false'
        btn.click();assert page.evaluate('FarmTest.getState().options.autoSell') is True
        btn.click();assert page.evaluate('FarmTest.getState().options.autoSell') is False
        return '商业街内可切换自动批发；当前无库存时不改变金币'
    check('自动批发开关在商业街可见且生效',auto_toggle)
    def retail_return():
        page.evaluate("""()=>{const s=FarmTest.getState();s.inventory.carrot=1;FarmTest.setState(s)}""")
        gold=page.evaluate('FarmTest.getState().gold')
        page.locator('[data-street-action="retail"][data-item="carrot"][data-qty="1"]').first.click()
        listed=page.evaluate('FarmTest.getState()')
        assert listed['inventory']['carrot']==0 and listed['shops']['produce']['qty']==1 and listed['gold']==gold
        page.locator('[data-street-action="return"][data-shop="produce"]').click()
        returned=page.evaluate('FarmTest.getState()')
        assert returned['inventory']['carrot']==1 and returned['shops']['produce']['qty']==0
        page.locator('[data-street-action="retail"][data-item="carrot"][data-qty="1"]').first.click()
        return {'before_sale_gold':gold,'shelf':page.evaluate('FarmTest.getState().shops.produce')}
    check('单件上架不提前入账、未售货退回原子执行',retail_return)
    def sale_and_switch():
        frozen=page.evaluate('FarmTest.getState()')
        page.locator('#farm-toggle').click();page.locator('#commercial-toggle').click()
        assert page.evaluate('FarmTest.getState()')==frozen
        page.evaluate('FarmTest.advance(20000)')
        sold=page.evaluate('FarmTest.getState()')
        assert sold['gold']==frozen['gold']+3 and sold['shops']['produce']['qty']==0
        return {'gold_after_sale':sold['gold'],'shelf_qty':sold['shops']['produce']['qty']}
    check('切页不改账、20游戏秒成交一件',sale_and_switch)
    def static_street_and_responsive():
        assert page.locator('.street-customer').count()==0
        for w,h in [(1440,900),(320,700)]:
            page.set_viewport_size({'width':w,'height':h})
            dims=page.locator('.commercial-street').evaluate("""scene=>{
                const street=scene.getBoundingClientRect();
                const backdrop=scene.querySelector('.street-backdrop').getBoundingClientRect();
                const floor=street.top+scene.clientHeight*(1-parseFloat(getComputedStyle(scene).getPropertyValue('--street-floor'))/100);
                return {
                    scroll:document.documentElement.scrollWidth,
                    width:innerWidth,
                    covered:backdrop.left<=street.left+.5&&backdrop.right>=street.right-.5,
                    animations:scene.getAnimations({subtree:true}).length,
                    grounded:[...scene.querySelectorAll('.street-shop')].every(shop=>{
                        const art=shop.querySelector('img').getBoundingClientRect();
                        const sign=shop.querySelector('.shop-signboard').getBoundingClientRect();
                        return Math.abs(art.bottom-floor-2)<=1&&sign.top>=art.bottom&&sign.bottom<=street.bottom;
                    })
                };
            }""")
            assert dims['scroll']<=dims['width']+1 and dims['covered'] and dims['grounded'] and dims['animations']==0,dims
            if w==1440:page.screenshot(path=str(ARTIFACTS/'commercial-street-1440.png'),full_page=True)
        assert not errors,errors
        return '320/1440 无横向溢出；门脸贴地、静态街景铺满横向画布'
    check('静态街景与窄窗/桌面的店铺落地',static_street_and_responsive)
    browser_version=browser.version
    browser.close()

report={'date':datetime.now(timezone.utc).isoformat(timespec='seconds'),'browser':f'Playwright Chromium {browser_version}','passed':len(checks),'total':len(checks),'geometry':geometry,'results':checks}
(ARTIFACTS/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(f"{len(checks)}/{len(checks)} commercial browser checks passed")
