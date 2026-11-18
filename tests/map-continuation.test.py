"""Map continuation regressions using the actual built game and Chromium input.

The in-memory storage adapter and explicit state setup are test fixtures. These
checks do not claim official DSH Web, native App, or physical touch-device coverage.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = Path(os.environ.get('FARM_HTML_PATH', ROOT / 'index.html'))
OUT = Path(os.environ.get('FARM_ARTIFACT_DIR', ROOT / 'tests/map-continuation-artifacts'))
OUT.mkdir(parents=True, exist_ok=True)
HTML = HTML_PATH.read_text(encoding='utf-8')
BOOT = '''<script>window.FARM_TEST_MODE=true;window.FARM_EMBEDDED=true;
window.__store={};Object.defineProperty(window,'localStorage',{value:{
getItem:k=>window.__store[k]||null,setItem:(k,v)=>window.__store[k]=String(v)}});</script>'''
RESULTS = []
ERRORS = []
REPORT = {
    'time_utc': datetime.now(timezone.utc).isoformat(),
    'environment': 'Real headless Chromium input; built game in page.set_content; in-memory storage adapter; explicit economy fixtures. Not official DSH or native App.',
    'html_path': str(HTML_PATH),
    'html_sha256': hashlib.sha256(HTML_PATH.read_bytes()).hexdigest(),
    'test_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ['src/map-view.js', 'src/ui.js', 'src/engine.js']},
    'results': RESULTS,
    'uncaught_errors': ERRORS,
}


def run_case(name, fn):
    before_errors = len(ERRORS)
    try:
        fn()
        assert len(ERRORS) == before_errors, ERRORS[before_errors:]
        RESULTS.append({'name': name, 'pass': True})
        print('PASS', name, flush=True)
    except Exception as exc:
        RESULTS.append({'name': name, 'pass': False, 'error': str(exc)})
        print('FAIL', name, str(exc), flush=True)


def settled(page):
    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    page.wait_for_timeout(150)


def center(page, selector):
    element = page.locator(selector).first
    element.scroll_into_view_if_needed()
    box = element.bounding_box()
    assert box is not None
    return {'x': box['x'] + box['width'] / 2, 'y': box['y'] + box['height'] / 2}


def state(page):
    return page.evaluate('FarmTest.getState()')


def save_report():
    REPORT['passed'] = sum(row['pass'] for row in RESULTS)
    REPORT['total'] = len(RESULTS)
    (OUT / 'map-continuation-results.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')


try:
    with sync_playwright() as playwright:
        exe = os.environ.get('CHROMIUM_PATH') or ('/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None)
        browser = playwright.chromium.launch(executable_path=exe, headless=True, args=['--no-sandbox'])
        REPORT['browser_version'] = browser.version

        def new_page(touch=False, width=390, height=844):
            page = browser.new_page(viewport={'width': width, 'height': height}, has_touch=touch)
            page.on('pageerror', lambda error: ERRORS.append(str(error)))
            page.set_content(HTML.replace('<head>', '<head>' + BOOT), wait_until='load')
            page.wait_for_function('!!window.FarmTest')
            return page

        def threshold():
            observations = []
            for distance in (7, 8, 9):
                page = new_page()
                point = center(page, '[data-tile="49"]')
                before = state(page)
                page.mouse.move(point['x'], point['y'])
                page.mouse.down()
                page.mouse.move(point['x'] + distance, point['y'])
                page.mouse.up()
                settled(page)
                after = state(page)
                expected = distance <= 8
                assert (after['tiles'][49].get('crop') == 'carrot') == expected, (distance, after['tiles'][49])
                assert after['gold'] == before['gold'] - (12 if expected else 0), (distance, before['gold'], after['gold'])
                assert page.locator('#drawer').is_hidden()
                observations.append({'distance_css_px': distance, 'gold_delta': after['gold'] - before['gold']})
                page.close()
            (OUT / 'threshold-observations.json').write_text(json.dumps(observations, indent=2))

        run_case('8px 阈值：7/8px 轻抖只点击一次，9px 拖动不种植', threshold)

        def multitouch(second):
            observed_firsts = set()
            for release_case in ('A', 'B'):
                page = new_page(touch=True)
                page.evaluate('''() => {window.inputEvents=[];
                  for(const type of ['pointerdown','pointerup','pointercancel','click'])
                    document.addEventListener(type,e=>inputEvents.push({type,id:e.pointerId,
                      primary:e.isPrimary, trusted:e.isTrusted,
                      target:e.target.id, tile:e.target.closest('[data-tile]')?.dataset.tile}),true);
                }''')
                a = center(page, '[data-tile="49"]')
                other = {'inside': '[data-tile="50"]', 'toolbar': '[data-map-action="fit"]', 'outside': '[data-open="settings"]'}[second]
                c = center(page, other)
                a['id'], c['id'] = 1, 2
                before = state(page)
                client = page.context.new_cdp_session(page)
                client.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [a]})
                client.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [a, c]})
                # Keep both input sequences; derive their actual release order
                # from browser pointer events instead of inferring it from CDP.
                client.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': [c if release_case == 'A' else a]})
                client.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                page.wait_for_timeout(400)
                after = state(page)
                events = page.evaluate('inputEvents')
                releases = [event for event in events if event['type'] == 'pointerup']
                release_order = ['primary' if event['primary'] else 'secondary' for event in releases]
                details = {'second': second, 'release_case': release_case, 'observed_release_order': release_order, 'before_gold': before['gold'], 'after_gold': after['gold'], 'tile49': after['tiles'][49], 'events': events}
                artifact = OUT / f'multitouch-{second}-case-{release_case}.json'
                artifact.write_text(json.dumps(details, ensure_ascii=False, indent=2))
                assert release_order in (['primary', 'secondary'], ['secondary', 'primary']), details
                assert all(event['trusted'] for event in releases), details
                observed_firsts.add(release_order[0])
                assert after['gold'] == before['gold'] and after['tiles'][49].get('crop') is None, details
                assert page.locator('#drawer').is_hidden(), details
                point = center(page, '[data-tile="49"]')
                page.touchscreen.tap(point['x'], point['y'])
                page.wait_for_function("FarmTest.getState().tiles[49].crop==='carrot'")
                page.wait_for_timeout(400)
                details['next_single_tap_gold'] = state(page)['gold']
                artifact.write_text(json.dumps(details, ensure_ascii=False, indent=2))
                assert details['next_single_tap_gold'] == before['gold'] - 12
                assert page.locator('#drawer').is_hidden()
                page.close()
            assert observed_firsts == {'primary', 'secondary'}, (second, observed_firsts)

        run_case('双指都在地图内时取消操作，下一次单指轻触恢复', lambda: multitouch('inside'))
        run_case('第二指落在地图工具栏时仍取消本次地图操作', lambda: multitouch('toolbar'))
        run_case('第二指落在地图之外时仍取消本次地图操作', lambda: multitouch('outside'))

        def blur_cancel():
            page = new_page()
            point = center(page, '[data-tile="49"]')
            before = state(page)
            page.mouse.move(point['x'], point['y'])
            page.mouse.down()
            # Deliberately synthetic blur to exercise the actual registered cleanup;
            # pointer input before and after is native browser input.
            page.evaluate("window.dispatchEvent(new Event('blur'))")
            page.mouse.up()
            settled(page)
            assert state(page)['gold'] == before['gold']
            assert state(page)['tiles'][49].get('crop') is None
            page.locator('[data-tile="49"]').click()
            assert state(page)['gold'] == before['gold'] - 12
            assert not page.locator('#board-scroll').evaluate("e=>e.classList.contains('is-panning')")
            page.close()

        run_case('按下后 blur 取消（明确注入事件），释放不误种且下一次点击可用', blur_cancel)

        def keyboard_far_corner():
            page = new_page(width=320, height=540)
            page.evaluate('''() => {const s=FarmTest.getState();s.gold=1e7;
              while(FarmEngine.eligibleChunks(s).length){const c=FarmEngine.eligibleChunks(s)[0];FarmEngine.expand(s,c.x,c.y)}
              FarmEngine.move(s,0,255);FarmTest.setState(s);
            }''')
            page.locator('[data-map-action="fit"]').click()
            page.locator('[data-tile="255"]').focus()
            before = state(page)
            page.keyboard.press('Enter')
            assert page.locator('[data-map-action="fit"]').get_attribute('aria-pressed') == 'false'
            assert page.locator('#drawer').is_hidden()
            assert state(page)['gold'] == before['gold']
            assert page.evaluate('document.activeElement.dataset.tile') == '255'
            scroll_before = page.locator('#board-scroll').evaluate('(v)=>({left:v.scrollLeft,top:v.scrollTop})')
            page.keyboard.press('Enter')
            page.locator('#drawer').wait_for(state='visible')
            page.keyboard.press('Escape')
            assert page.locator('#drawer').is_hidden()
            assert page.evaluate('document.activeElement.dataset.tile') == '255'
            assert page.locator('#board-scroll').evaluate('(v)=>({left:v.scrollLeft,top:v.scrollTop})') == scroll_before
            page.keyboard.press('ArrowLeft')
            assert page.evaluate('document.activeElement.dataset.tile') == '254'
            settled(page)
            page.screenshot(path=str(OUT / 'keyboard-corner-320x540.png'))
            geometry = page.locator('[data-tile="254"]').bounding_box()
            assert geometry['width'] >= 44
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            (OUT / 'keyboard-corner-320x540.json').write_text(json.dumps({'viewport': {'width': 320, 'height': 540}, 'state': '16x16 fixture; house moved to index255; keyboard overview locate/open/close/arrow-left', 'tile254': geometry, 'source_sha256': REPORT['source_sha256']}, ensure_ascii=False, indent=2))
            page.close()

        run_case('320×540 远角全景键盘只定位；详情退出后保持焦点和视野', keyboard_far_corner)
        browser.close()
except Exception as exc:
    REPORT['environment_error'] = str(exc)
    print('ENVIRONMENT_ERROR', str(exc), flush=True)
finally:
    save_report()

print(f"{REPORT['passed']}/{REPORT['total']} map continuation tests passed")
if REPORT.get('environment_error') or REPORT['passed'] != REPORT['total'] or ERRORS:
    raise SystemExit(1)
