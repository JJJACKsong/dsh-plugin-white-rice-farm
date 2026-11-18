#!/usr/bin/env python3
"""Fresh-origin Chromium regression, not a native DSH desktop certification.

Serve the rebuilt single-file game and a minimal DSH slot harness over loopback.
Use *native* Chromium localStorage, Web Locks, image decoding and downloads.
Screenshots and a machine-readable report are CI artifacts, not substitutes for
viewing the screenshots or installing the plugin in a real DSH desktop.
"""
import json
import os
import threading
import traceback
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests' / 'live-browser-artifacts'
OUT.mkdir(exist_ok=True)
RESULTS, ERRORS, EXTERNAL_REQUESTS = [], [], []
KEY = 'dsh-farm-v03'
PREV_KEY = 'dsh-farm-v02'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def check(name, fn):
    try:
        detail = fn()
        RESULTS.append({'name': name, 'status': 'passed', 'detail': detail or ''})
        print('PASS', name, flush=True)
    except Exception as err:
        RESULTS.append({'name': name, 'status': 'failed', 'error': str(err), 'traceback': traceback.format_exc()})
        print('FAIL', name, err, flush=True)


def track(page):
    page.on('pageerror', lambda error: ERRORS.append(str(error)))
    page.on('request', lambda req: EXTERNAL_REQUESTS.append(req.url)
            if urlsplit(req.url).scheme in ('http', 'https') and
            urlsplit(req.url).hostname not in ('127.0.0.1', 'localhost') else None)


server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
BASE = f'http://127.0.0.1:{server.server_port}'
BROWSER_VERSION = None
try:
    with sync_playwright() as p:
        exe = os.environ.get('CHROMIUM_PATH') or ('/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None)
        browser = p.chromium.launch(executable_path=exe, headless=True, args=['--no-sandbox'])
        BROWSER_VERSION = browser.version
        contexts = []

        def context(**kwargs):
            ctx = browser.new_context(accept_downloads=True, **kwargs)
            ctx.add_init_script('window.FARM_TEST_MODE=true;')
            contexts.append(ctx)
            return ctx

        def open_standalone(ctx):
            page = ctx.new_page()
            track(page)
            page.goto(BASE + '/index.html', wait_until='load')
            page.wait_for_function('!!window.FarmTest')
            return page

        def initial_assets_and_layout():
            ctx = context(viewport={'width': 1440, 'height': 900})
            page = open_standalone(ctx)
            assert page.locator('#board button').count() == 16
            assert page.locator('#gold').inner_text() == '100'
            decoded = page.evaluate('''async () => {
              await FarmTest.assetsReady();
              const a = [...Object.entries(FARM_ASSETS.tiles),
                         ...Object.entries(FARM_ASSETS.buildings),
                         ...Object.entries(FARM_ASSETS.buildingCards)];
              const rows = await Promise.all(a.map(([key, src]) => new Promise(done => {
                const im = new Image(); im.onload=()=>done({key,ok:im.naturalWidth>0});
                im.onerror=()=>done({key,ok:false}); im.src=src;
              })));
              return {rows,failed:FarmTest.tiles().failed};
            }''')
            assert len(decoded['rows']) == 35 and all(r['ok'] for r in decoded['rows']), decoded
            assert not decoded['failed'], decoded['failed']
            for width, height in [(1440, 900), (768, 820), (390, 844), (320, 700)]:
                page.set_viewport_size({'width': width, 'height': height})
                page.wait_for_timeout(180)
                dims = page.evaluate('''() => ({scroll:document.documentElement.scrollWidth,
                                               viewport:innerWidth,board:document.querySelector('#board').getBoundingClientRect().width})''')
                assert dims['scroll'] <= dims['viewport'] + 1, (width, dims)
                if width in (1440, 390):
                    page.screenshot(path=str(OUT / f'standalone-{width}.png'), full_page=True)
            avatar = page.locator('.crew-avatar').first
            assert avatar.get_attribute('src').startswith('data:image/png;base64,')
            assert avatar.evaluate('(img)=>img.naturalWidth>0 && img.naturalHeight>0')
            return '35/35 decoded; desktop/tablet/390/320 no horizontal page overflow; static PNG avatar'

        check('HTTP 初始画面、35 张运行素材解码、桌面与窄屏', initial_assets_and_layout)

        def persistence_and_download():
            ctx = context(viewport={'width': 1280, 'height': 850})
            page = open_standalone(ctx)
            page.locator('#harvest-button').click()
            before = page.evaluate('FarmTest.getState()')
            assert before['stats']['harvests'] == 2 and before['gold'] == 100
            stored = page.evaluate(f'JSON.parse(localStorage.getItem({json.dumps(KEY)}))')
            assert stored['stats']['harvests'] == 2 and stored['gold'] == 100
            page.reload(wait_until='load')
            page.wait_for_function('!!window.FarmTest')
            after = page.evaluate('FarmTest.getState()')
            assert after['stats']['harvests'] == 2 and after['gold'] >= before['gold']
            page.locator('.header-right [data-open="settings"]').click()
            with page.expect_download() as downloaded:
                page.locator('[data-action="export-save"]').click()
            export = downloaded.value
            assert export.suggested_filename.endswith('.json')
            file = OUT / 'native-export-save.json'
            export.save_as(str(file))
            saved = json.loads(file.read_text(encoding='utf-8'))
            assert saved['version'] == 3 and saved['stats']['harvests'] == 2
            page.locator('#import-input').set_input_files(str(file))
            page.wait_for_function("document.getElementById('notice-text').textContent.includes('存档已导入')")
            assert page.evaluate('FarmTest.getState().stats.harvests') == 2
            return 'native localStorage survives reload; browser Blob download/import JSON works'

        check('真实同源 localStorage 续档、浏览器原生导出与导入', persistence_and_download)

        def legacy_v2_migration_and_key_isolation():
            seed_ctx = context(viewport={'width': 390, 'height': 844})
            seed_page = open_standalone(seed_ctx)
            old = seed_page.evaluate("""() => {const s=FarmEngine.initial(Date.now());s.version=2;s.savedAt=Date.now();
              s.options.autoSell=false;s.inventory.carrot=7;delete s.shops;return s;}""")
            seed_ctx.close()
            # Seed v02 in a fresh origin before the app boots: removing v03 from a
            # live page races its 5s autosave and can leave an empty v03 behind.
            ctx = context(viewport={'width': 390, 'height': 844})
            ctx.add_init_script("if(!localStorage.getItem('dsh-farm-v03'))localStorage.setItem('dsh-farm-v02', " + json.dumps(json.dumps(old, ensure_ascii=False)) + ");")
            page = ctx.new_page();track(page)
            page.goto(BASE + '/index.html', wait_until='load');page.wait_for_function('!!window.FarmTest')
            page.locator('#commercial-toggle').click()
            page.wait_for_function("""()=>{const b=document.querySelector('[data-street-action=\"retail\"][data-item=\"carrot\"][data-qty=\"1\"]');return b&&!b.disabled}""",timeout=5000)
            # Click in-page so Playwright's per-second DOM-stability retries cannot
            # stretch past the 20 game-second auto-sale boundary.
            page.evaluate("""()=>document.querySelector('[data-street-action=\"retail\"][data-item=\"carrot\"][data-qty=\"1\"]').click()""")
            migrated=page.evaluate("JSON.parse(localStorage.getItem('dsh-farm-v03'))")
            assert migrated['version']==3 and migrated['shops']['produce']['qty']==1 and migrated['inventory']['carrot']==6,(migrated['shops'],migrated['gold'],migrated['time'])
            # Keep the shelf away from its 20s sale boundary while the next page
            # boots; this check is about key isolation, not sale timing.
            page.evaluate("""()=>{const s=JSON.parse(localStorage.getItem('dsh-farm-v03'));s.shops.produce.nextAt=s.time+1000000;localStorage.setItem('dsh-farm-v03',JSON.stringify(s))}""")
            # An old preview.5 client can still write v02; it must not touch v03.
            page.evaluate("""() => {const s=JSON.parse(localStorage.getItem('dsh-farm-v02'));s.gold=777;localStorage.setItem('dsh-farm-v02',JSON.stringify(s));}""")
            page.reload(wait_until='load');page.wait_for_function('!!window.FarmTest')
            after=page.evaluate("JSON.parse(localStorage.getItem('dsh-farm-v03'))")
            assert after['shops']['produce']['qty']==1 and after['inventory']['carrot']==6 and after['gold']==100,after['shops']
            assert page.evaluate("JSON.parse(localStorage.getItem('dsh-farm-v02')).gold")==777
            ctx.close()
            return 'v2 migrated to v3; later v02 writes leave v03 shelf/gold untouched'

        check('旧 v2 存档迁移到 v3，旧客户端再次保存不覆盖新货架', legacy_v2_migration_and_key_isolation)

        def commercial_street_flow():
            ctx = context(viewport={'width': 390, 'height': 844})
            page = open_standalone(ctx)
            page.evaluate('''() => {const s=FarmTest.getState();s.options.autoSell=false;s.xp=135;
              s.shops.food.open=true;s.inventory.carrot=8;s.inventory.bread=2;FarmTest.setState(s)}''')
            page.locator('#commercial-toggle').click()
            assert page.locator('#commercial-view').is_visible()
            assert page.locator('.street-shop').count() == 2
            geometry = page.evaluate('''() => {const v=document.querySelector('#commercial-view').getBoundingClientRect();
              const a=document.querySelector('.commercial-street').getBoundingClientRect();
              const d=document.querySelector('.commercial-data').getBoundingClientRect();
              return {view:v.height,street:a.height,data:d.height,ratio:a.height/v.height,
                      dataOverflow:document.querySelector('.commercial-data').scrollHeight>document.querySelector('.commercial-data').clientHeight};}''')
            assert .27 <= geometry['ratio'] <= .34, geometry
            assert geometry['data'] > geometry['street'] and geometry['dataOverflow'], geometry
            page.screenshot(path=str(OUT / 'commercial-street-390.png'), full_page=True)
            before = page.evaluate('FarmTest.getState()')
            wholesale = page.locator('[data-street-action="wholesale"][data-item="carrot"]')
            assert wholesale.is_enabled()
            wholesale.click()
            after = page.evaluate('FarmTest.getState()')
            assert after['inventory']['carrot'] == 0 and after['gold'] == before['gold'] + 16
            # Retail listing transfers one unit but does not credit money until the sale event.
            page.evaluate('''() => {const s=FarmTest.getState();s.inventory.carrot=1;FarmTest.setState(s)}''')
            retail = page.locator('[data-street-action="retail"][data-item="carrot"][data-qty="1"]').first
            gold = page.evaluate('FarmTest.getState().gold')
            retail.click()
            listed = page.evaluate('FarmTest.getState()')
            assert listed['inventory']['carrot'] == 0 and listed['shops']['produce']['qty'] == 1
            assert listed['gold'] == gold
            page.locator('[data-street-action="return"][data-shop="produce"]').click()
            returned = page.evaluate('FarmTest.getState()')
            assert returned['inventory']['carrot'] == 1 and returned['shops']['produce']['qty'] == 0
            page.locator('[data-street-action="retail"][data-item="carrot"][data-qty="1"]').first.click()
            frozen = page.evaluate('FarmTest.getState()')
            page.locator('#farm-toggle').click()
            page.locator('#commercial-toggle').click()
            assert page.evaluate('FarmTest.getState()') == frozen
            page.evaluate('FarmTest.advance(20000)')
            sold = page.evaluate('FarmTest.getState()')
            assert sold['gold'] == gold + 3 and sold['shops']['produce']['qty'] == 0
            page.evaluate('''() => {const s=FarmTest.getState();s.options.reducedMotion=true;FarmTest.setState(s)}''')
            assert page.locator('.street-customer').first.evaluate('(e)=>getComputedStyle(e).animationName') == 'none'
            for width, height in [(1440, 900), (320, 700)]:
                page.set_viewport_size({'width': width, 'height': height})
                page.wait_for_timeout(100)
                dims = page.evaluate('''() => ({scroll:document.documentElement.scrollWidth,w:innerWidth,
                  stage:document.querySelector('.commercial-street').getBoundingClientRect().height,
                  view:document.querySelector('#commercial-view').getBoundingClientRect().height})''')
                assert dims['scroll'] <= dims['w'] + 1 and dims['stage'] > 0, (width, dims)
                if width == 1440:
                    page.screenshot(path=str(OUT / 'commercial-street-1440.png'), full_page=True)
            return f"two storefronts; 30/70={geometry['ratio']:.3f}; wholesale, one-unit retail, return, view switch and reduced-motion pass; 390/1440/320 widths"

        check('商业街三七布局、两店画面、批发零售退货与视图无副作用', commercial_street_flow)

        def avatar_and_visibility():
            ctx = context(viewport={'width': 1280, 'height': 850})
            page = open_standalone(ctx)
            page.evaluate('''() => {const s=FarmTest.getState();s.gold=10000;
                               s.inventory.meal=100;s.options.autoSell=false;FarmTest.setState(s)}''')
            page.locator('#crew-recruit [data-action="recruit"]').click()
            avatar = page.locator('.crew-row .crew-avatar').first
            assert avatar.is_visible()
            src = avatar.get_attribute('src')
            assert src.startswith('data:image/png;base64,') and avatar.evaluate('(el)=>el.naturalWidth>0')
            image_a = avatar.screenshot()
            page.wait_for_timeout(600)
            image_b = page.locator('.crew-row .crew-avatar').first.screenshot()
            assert image_a == image_b, 'worker recruitment avatar changed pixels after 600 ms'
            assert page.locator('.farm-actor').count() == 1
            page.locator('.header-right [data-open="settings"]').click()
            page.locator('[data-action="toggle-motion"]').click()
            assert page.evaluate("FarmTest.actors().every(a=>a.src.startsWith('data:image/png'))")
            page.locator('[data-action="close-drawer"]').click()
            # Second tab is blank: do not let two standalone files write the same key.
            other = ctx.new_page()
            other.goto('about:blank')
            other.bring_to_front()
            page.wait_for_timeout(250)
            if page.evaluate('document.hidden'):
                old = page.evaluate('FarmTest.getState().time')
                page.wait_for_timeout(1200)
                assert page.evaluate('FarmTest.getState().time') == old
                assert page.locator('.farm-actor').evaluate_all('(els)=>els.every(el=>el.hidden)')
                page.bring_to_front()
                page.wait_for_function('!document.hidden')
                assert page.evaluate('FarmTest.getState().time') > old
                visibility = 'real tab background: idle; foreground: elapsed time caught up'
            else:
                # Clearly label a synthetic fallback; headless focus support differs.
                page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
                old = page.evaluate('FarmTest.getState().time')
                page.wait_for_timeout(1200)
                assert page.evaluate('FarmTest.getState().time') == old
                assert page.locator('.farm-actor').evaluate_all('(els)=>els.every(el=>el.hidden)')
                page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'))")
                assert page.evaluate('FarmTest.getState().time') > old
                visibility = 'synthetic visibilitychange fallback (headless background not observable)'
            return 'portrait pixel-stable; reduced motion uses PNG; ' + visibility

        check('招募头像稳定、减少动态、后台页面低负担与返回结算', avatar_and_visibility)

        def open_host(ctx):
            page = ctx.new_page()
            track(page)
            page.goto(BASE + '/tests/live-browser-host.html', wait_until='load')
            page.wait_for_selector('iframe', timeout=15000)
            frame_locator = page.frame_locator('iframe')
            frame_locator.locator('#board button').first.wait_for(timeout=15000)
            frame = page.locator('iframe').element_handle().content_frame()
            assert frame is not None
            return page, frame

        def host_native_lock_and_storage():
            ctx = context(viewport={'width': 1280, 'height': 800})
            page, frame = open_host(ctx)
            assert page.evaluate('!!navigator.locks && window.isSecureContext')
            assert page.evaluate('window.registrations.length') == 2
            assert page.locator('iframe').get_attribute('sandbox') == 'allow-scripts allow-downloads'
            assert frame.evaluate("(()=>{try{localStorage.getItem('x');return false}catch{return true}})()")
            frame.locator('#harvest-button').click()
            page.wait_for_function("JSON.parse(localStorage.getItem('dsh-farm-v03')).stats.harvests===2")
            page.screenshot(path=str(OUT / 'plugin-desktop.png'))
            second = ctx.new_page()
            track(second)
            second.goto(BASE + '/tests/live-browser-host.html', wait_until='load')
            second.wait_for_function("document.body.textContent.includes('已经在另一个窗口')", timeout=15000)
            assert second.locator('iframe').count() == 0
            page.close()  # Actual tab closure must release the browser Web Lock.
            second.reload(wait_until='load')
            second.wait_for_selector('iframe', timeout=15000)
            second.frame_locator('iframe').locator('#board button').first.wait_for(timeout=15000)
            frame = second.locator('iframe').element_handle().content_frame()
            assert frame is not None
            assert frame.evaluate('FarmTest.getState().stats.harvests') == 2
            for width, height in [(1280, 800), (760, 650), (390, 700)]:
                second.set_viewport_size({'width': width, 'height': height})
                second.wait_for_timeout(200)
                dims = frame.evaluate('''() => ({horizontal:document.documentElement.scrollWidth,
                                                vertical:document.documentElement.scrollHeight,
                                                w:innerWidth,h:innerHeight})''')
                assert dims['horizontal'] <= dims['w'] + 1 and dims['vertical'] <= dims['h'] + 1, (width, dims)
                if width == 390:
                    frame.locator('[data-open="overview"]').click()
                    assert frame.locator('#drawer-title').inner_text() == '庄园与帮手'
                    frame.locator('[data-action="close-drawer"]').click()
                    second.screenshot(path=str(OUT / 'plugin-narrow.png'))
            assert frame.locator('.crew-avatar').first.get_attribute('src').startswith('data:image/png;base64,')
            return 'real Chromium secure-context Web Locks + localStorage, opaque iframe bridge, lock handoff, responsive panel'

        check('HTTP 模拟槽位 + 真实 Web Locks/存储/隔离 iframe 续档及窄屏', host_native_lock_and_storage)
        check('浏览器没有未捕获 JS 异常和外网请求', lambda: (
            (_ for _ in ()).throw(AssertionError({'js_errors': ERRORS, 'external': EXTERNAL_REQUESTS}))
            if ERRORS or EXTERNAL_REQUESTS else '0 errors; 0 external HTTP requests'))

        for ctx in contexts:
            ctx.close()
        browser.close()
finally:
    server.shutdown()
    server.server_close()

report = {
    'environment': 'Playwright Chromium via 127.0.0.1 HTTP (native browser storage, Web Locks, downloads); minimal test DSH slot harness, NOT real DSH desktop',
    'browser_version': BROWSER_VERSION,
    'passed': sum(row['status'] == 'passed' for row in RESULTS),
    'total': len(RESULTS), 'results': RESULTS,
    'uncaught_js_errors': ERRORS, 'external_http_requests': EXTERNAL_REQUESTS,
}
(OUT / 'live-browser-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f"{report['passed']}/{report['total']} fresh-origin browser regressions passed", flush=True)
if report['passed'] != report['total']:
    raise SystemExit(1)
