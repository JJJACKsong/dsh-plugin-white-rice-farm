"""Placement actions, cancellation, and keyboard recovery in real Chromium.

Ordinary new game only; frozen clock and an isolated memory storage adapter.
This is standalone browser evidence, not official DSH or a physical touchscreen.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import traceback

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = Path(os.environ.get('FARM_HTML_PATH', ROOT / 'index.html'))
OUT = Path(os.environ.get('FARM_ARTIFACT_DIR', ROOT / 'tests/placement-artifacts'))
OUT.mkdir(parents=True, exist_ok=True)
HTML = HTML_PATH.read_text(encoding='utf-8')
HASH = lambda value: hashlib.sha256(value).hexdigest()
SCRIPTS = re.findall(r'<script>(.*?)</script>', HTML, re.S)
REPORT = {'host': 'Standalone Chromium, page.set_content, memory storage adapter; not official DSH',
          'setup': 'Ordinary 4x4 new game, 100 coins, no workers; frozen Date.now; no state injection',
          'html_sha256': HASH(HTML_PATH.read_bytes()),
          'source_sha256': {name: HASH(next(code for code in SCRIPTS if code.startswith(prefix)).encode())
                            for name, prefix in {'ui.js': '/* UI controller.', 'engine.js': '/* 大白饭庄园',
                                                 'map-view.js': '/* Small map viewport helper'}.items()},
          'checks': [], 'browser_errors': [], 'screenshots': []}
BOOT = '''<script>window.FARM_TEST_MODE=true;window.FARM_EMBEDDED=true;
window.__store={};window.__testNow=Date.now();Date.now=()=>window.__testNow;
window.FARM_STORAGE={getItem:k=>window.__store[k]||null,setItem:(k,v)=>window.__store[k]=String(v)};
</script>'''

with sync_playwright() as playwright:
    exe = os.environ.get('CHROMIUM_PATH') or ('/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None)
    browser = playwright.chromium.launch(executable_path=exe, headless=True, args=['--no-sandbox'])
    REPORT['chromium'] = browser.version

    def new_page(width, height):
        page = browser.new_page(viewport={'width': width, 'height': height}, has_touch=True, reduced_motion='reduce')
        page.on('pageerror', lambda error: REPORT['browser_errors'].append(str(error)))
        page.set_content(HTML.replace('<head>', '<head>' + BOOT), wait_until='load')
        page.wait_for_function('!!window.FarmTest')
        page.evaluate('FarmTest.assetsReady()')
        assert page.evaluate('FarmTest.getState().gold') == 100
        return page

    def state(page):
        return page.evaluate('FarmTest.getState()')

    def select_build(page):
        page.locator('.farm-actions [data-open="build"]').click()
        page.locator('[data-build="kitchen"]').click()

    def capture(page, name, description):
        page.evaluate('new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
        page.wait_for_timeout(550)
        path = OUT / (name + '.png')
        page.screenshot(path=str(path), animations='disabled')
        REPORT['screenshots'].append({'file': path.name, 'viewport': page.viewport_size, 'state': description,
                                      'html_sha256': REPORT['html_sha256'], 'sha256': HASH(path.read_bytes())})

    def focused_control(page, selector):
        info = page.locator(selector).evaluate('''el=>{
          const r=el.getBoundingClientRect(),v=el.dataset.tile===undefined?null:document.getElementById('board-scroll').getBoundingClientRect();
          const clip={left:Math.max(0,v?.left||0),top:Math.max(0,v?.top||0),
            right:Math.min(innerWidth,v?.right??innerWidth),bottom:Math.min(innerHeight,v?.bottom??innerHeight)};
          const style=getComputedStyle(el);
          return {tag:el.tagName,id:el.id,tile:el.dataset.tile||null,action:el.dataset.action||null,open:el.dataset.open||null,
            focused:document.activeElement===el,focusVisible:el.matches(':focus-visible'),disabled:el.disabled,
            rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height},clip,
            inView:r.width>0&&r.height>0&&r.left>=clip.left-1&&r.top>=clip.top-1&&r.right<=clip.right+1&&r.bottom<=clip.bottom+1,
            outlineStyle:style.outlineStyle,outlineWidth:parseFloat(style.outlineWidth)};
        }''')
        assert info['tag'] == 'BUTTON' and info['focused'] and info['focusVisible'] and not info['disabled'], info
        assert info['inView'] and info['outlineStyle'] != 'none' and info['outlineWidth'] >= 1, info
        return info

    def check(name, fn):
        before = len(REPORT['browser_errors'])
        try:
            detail = fn()
            assert len(REPORT['browser_errors']) == before, REPORT['browser_errors'][before:]
            REPORT['checks'].append({'name': name, 'status': 'pass', 'detail': detail})
            print('PASS', name, flush=True)
        except Exception as error:
            REPORT['checks'].append({'name': name, 'status': 'fail', 'error': str(error),
                                     'traceback': traceback.format_exc()})
            print('FAIL', name, str(error), flush=True)

    for width, height in ((320, 540), (390, 844)):
        def building_cancel(width=width, height=height):
            page = new_page(width, height)
            start = state(page)
            select_build(page)
            label = page.locator('[data-tile="2"]').get_attribute('aria-label')
            assert '小灶台' in label and '80 金币' in label and '开垦并种' not in label
            occupied = page.locator('[data-tile="32"]').get_attribute('aria-label')
            assert '请选空草地建造' in occupied and '收好再种' not in occupied
            assert '80 金币' in page.locator('#placement-hint').inner_text()
            assert state(page) == start, 'Selecting a building must not charge or mutate the farm'
            page.locator('[data-action="cancel-mode"]').click()
            assert page.locator('#placement').is_hidden()
            assert '已取消建造' in page.locator('#notice-text').inner_text()
            assert '萝卜' in page.locator('#notice-text').inner_text()
            assert state(page) == start
            select_build(page)
            page.locator('[data-tile="2"]').focus()
            page.keyboard.press('Escape')
            assert page.evaluate('document.activeElement.dataset.tile') == '2'
            assert '已取消建造' in page.locator('#notice-text').inner_text()
            select_build(page)
            page.locator('#crop-options [data-crop="wheat"]').focus()
            page.keyboard.press('Enter')
            assert page.evaluate('document.activeElement.dataset.crop') == 'wheat'
            page.keyboard.press('Tab')
            assert page.evaluate('document.activeElement.dataset.crop') == 'grass'
            assert page.locator('#placement').is_hidden()
            assert '已取消建造' in page.locator('#notice-text').inner_text()
            assert '小麦' in page.locator('#notice-text').inner_text()
            assert '小麦' in page.locator('[data-tile="2"]').get_attribute('aria-label')
            assert state(page) == start
            capture(page, f'build-canceled-crop-{width}', 'Canceled kitchen by selecting wheat; next tile action is planting')
            page.locator('[data-tile="2"]').tap()
            after = state(page)
            assert after['gold'] == 88 and after['tiles'][2]['crop'] == 'wheat'
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.close()
            return {'buildLabel': label, 'goldAfterOneTouchPlant': after['gold'], 'crop': after['tiles'][2]['crop']}
        check(f'{width}: build labels, button/Escape/crop cancellation, next touch action', building_cancel)

        def relocation_cancel(width=width, height=height):
            page = new_page(width, height)
            select_build(page)
            page.locator('[data-tile="2"]').tap()
            built = state(page)
            assert built['gold'] == 20 and built['tiles'][2]['kind'] == 'kitchen'
            page.locator('[data-tile="2"]').click()
            page.locator('[data-action="move-building"]').click()
            label = page.locator('[data-tile="3"]').get_attribute('aria-label')
            assert '小灶台' in label and '免费' in label and '开垦并种' not in label
            assert '仍须保证稻田有水' not in label
            assert page.locator('#placement-hint').inner_text() == '点虚线框里的空草地，免费搬家并保留进度。'
            assert page.locator('#notice-text').inner_text() == '点空草地搬入小灶台，免费并保留生产进度。'
            occupied = page.locator('[data-tile="32"]').get_attribute('aria-label')
            assert '请选空草地搬家' in occupied and '收好再种' not in occupied
            assert '小灶台' in page.locator('#placement-title').inner_text()
            page.locator('[data-tile="0"]').click()
            assert state(page) == built, 'Invalid destination must preserve the built farm'
            assert page.locator('#placement').is_visible()
            page.locator('[data-action="cancel-mode"]').click()
            assert state(page) == built
            assert '已取消搬家' in page.locator('#notice-text').inner_text()
            assert 'error' not in page.locator('#notice').get_attribute('class').split()
            page.locator('[data-tile="2"]').click()
            page.locator('[data-action="move-building"]').click()
            capture(page, f'move-selected-{width}', 'Free relocation names the selected kitchen and preserves its origin')
            page.locator('[data-tile="3"]').tap()
            moved = state(page)
            assert moved['gold'] == 20 and moved['inventory'] == built['inventory']
            assert moved['tiles'][3] == built['tiles'][2] and moved['tiles'][2]['type'] == 'grass'
            assert page.locator('#placement').is_hidden()
            page.close()
            return {'moveLabel': label, 'goldAfterMove': moved['gold']}
        check(f'{width}: relocation labels, invalid destination, cancel, one free touch move', relocation_cancel)

        def expansion_cancel(width=width, height=height):
            page = new_page(width, height)
            start = state(page)
            page.locator('#expand-button').click()
            assert '60 金币' in page.locator('[data-tile="4"]').get_attribute('aria-label')
            assert '已拥有' in page.locator('[data-tile="2"]').get_attribute('aria-label')
            assert '开垦并种' not in page.locator('[data-tile="2"]').get_attribute('aria-label')
            page.locator('[data-tile="4"]').focus()
            page.keyboard.press('Escape')
            assert page.evaluate('document.activeElement.id') == 'expand-button'
            assert '已取消扩地' in page.locator('#notice-text').inner_text()
            assert state(page) == start
            page.keyboard.press('Enter')
            assert page.locator('#placement').is_visible()
            page.locator('[data-tile="2"]').focus()
            page.keyboard.press('Escape')
            assert page.evaluate('document.activeElement.dataset.tile') == '2'
            page.keyboard.press('ArrowRight')
            assert page.evaluate('document.activeElement.dataset.tile') == '3'
            page.locator('#expand-button').click()
            page.locator('#expand-button').click()
            assert page.locator('#placement').is_hidden()
            assert '已取消扩地' in page.locator('#notice-text').inner_text()
            page.locator('#expand-button').click()
            page.locator('[data-action="cancel-mode"]').click()
            assert page.locator('#placement').is_hidden() and state(page) == start
            capture(page, f'expansion-canceled-{width}', 'Expansion canceled by its banner button without spending; earlier assertions cover Escape from surviving and removed map cells')
            page.locator('#expand-button').click()
            page.locator('[data-tile="4"]').tap()
            after = state(page)
            assert after['gold'] == 40 and sum(t is not None for t in after['tiles']) == 20
            assert page.locator('#placement').is_hidden()
            assert page.locator('[data-tile="4"]').bounding_box()['width'] >= 44
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.close()
            return {'goldAfterOneTouchExpansion': after['gold'], 'owned': 20}
        check(f'{width}: expansion cancellation, surviving/removed focus, one touch purchase', expansion_cancel)

        for mode in ('build', 'move', 'expand'):
            for key in ('Enter', 'Space'):
                def cancel_button_keyboard(width=width, height=height, mode=mode, key=key):
                    page = new_page(width, height)
                    if mode == 'expand':
                        page.locator('#expand-button').click()
                        target = '#expand-button'
                    else:
                        select_build(page)
                        target = '.farm-actions [data-open="build"]'
                        if mode == 'move':
                            page.locator('[data-tile="2"]').click()
                            page.locator('[data-tile="2"]').click()
                            page.locator('[data-action="move-building"]').click()
                            target = '[data-tile="2"]'
                    before = state(page)
                    page.evaluate('''()=>{window.__cancelKeys=[];for(const type of ['keydown','keyup'])
                      document.addEventListener(type,e=>window.__cancelKeys.push({type,key:e.key,trusted:e.isTrusted,
                        action:e.target.dataset?.action||null,id:e.target.id||null}),true);}''')
                    # Normal Tab reaches the visible banner button; after this
                    # setup, the test never focuses or scrolls the return target.
                    page.locator('#expand-button').focus()
                    page.keyboard.press('Tab')
                    cancel_focus = focused_control(page, '[data-action="cancel-mode"]')
                    page.keyboard.press(key)
                    assert page.locator('#placement').is_hidden() and page.locator('#drawer').is_hidden()
                    returned_focus = focused_control(page, target)
                    assert state(page) == before, 'Cancel must not buy, build, move, plant, or consume a batch'
                    input_events = page.evaluate('window.__cancelKeys')
                    expected_key = ' ' if key == 'Space' else 'Enter'
                    assert any(e['key'] == expected_key and e['trusted'] and e['action'] == 'cancel-mode' for e in input_events), input_events
                    capture(page, f'cancel-button-{mode}-{key.lower()}-{width}',
                            f'Tab to visible {mode} cancel button, then {key}; focus returned to the existing entry or source building, before another action')
                    page.keyboard.press('Enter')
                    if mode == 'expand':
                        assert page.locator('#placement').is_visible() and page.locator('#drawer').is_hidden()
                        next_action = 'Enter reopened expansion'
                    else:
                        assert page.locator('#drawer').is_visible() and page.locator('#placement').is_hidden()
                        expected = '[data-build="kitchen"]' if mode == 'build' else '[data-action="move-building"]'
                        assert page.locator('#drawer ' + expected).is_visible()
                        next_action = 'Enter opened construction drawer' if mode == 'build' else 'Enter opened source kitchen detail'
                    page.keyboard.press('Escape')
                    assert page.locator('#placement').is_hidden() and page.locator('#drawer').is_hidden()
                    roundtrip_focus = focused_control(page, target)
                    if mode == 'move':
                        page.keyboard.press('ArrowRight')
                        assert page.evaluate('document.activeElement.dataset.tile') == '3'
                    after = state(page)
                    assert after == before
                    page.close()
                    return {'mode': mode, 'key': key, 'cancelFocus': cancel_focus, 'returnedFocus': returned_focus,
                            'nextKeyboardAction': next_action, 'roundtripFocus': roundtrip_focus,
                            'inputEvents': input_events, 'goldBefore': before['gold'], 'goldAfter': after['gold']}
                check(f'{width}: {mode} cancel button {key}, visible focus and keyboard continuation', cancel_button_keyboard)

        def well_move_condition(width=width, height=height):
            page = new_page(width, height)
            before = state(page)
            page.locator('[data-tile="17"]').click()
            page.locator('[data-action="move-building"]').click()
            label = page.locator('[data-tile="48"]').get_attribute('aria-label')
            title = page.locator('[data-tile="48"]').get_attribute('title')
            hint = page.locator('#placement-hint').inner_text()
            notice = page.locator('#notice-text').inner_text()
            assert all('仍须保证稻田有水' in text for text in (label, title, hint, notice))
            assert '免费' in label and 'placeable' in page.locator('[data-tile="48"]').get_attribute('class').split()
            page.locator('[data-tile="48"]').click()
            assert state(page) == before, 'The rejected well move must preserve the whole ordinary farm'
            assert page.locator('#placement').is_visible()
            assert '这口井还在给水稻供水' in page.locator('#notice-text').inner_text()
            capture(page, f'well-move-rejected-{width}', 'Initial well17 cannot move to grass48; original rice plan remains watered, mode stays available, no charge')
            page.locator('[data-action="cancel-mode"]').tap()
            assert page.locator('#placement').is_hidden() and state(page) == before
            page.locator('[data-tile="17"]').click()
            page.locator('[data-action="move-building"]').click()
            page.locator('[data-tile="3"]').click()
            after = state(page)
            assert after['gold'] == before['gold'] and after['inventory'] == before['inventory']
            assert after['tiles'][17]['type'] == 'grass' and after['tiles'][3] == before['tiles'][17]
            assert after['tiles'][18] == before['tiles'][18]
            assert page.locator('#placement').is_hidden()
            page.close()
            return {'target48Label': label, 'target48Title': title, 'hint': hint, 'entryNotice': notice,
                    'rejectedDestination': 48, 'legalDestination': 3, 'goldBefore': before['gold'], 'goldAfter': after['gold']}
        check(f'{width}: conditional well move, rejected48, touch cancel, legal3', well_move_condition)

    browser.close()

REPORT['counts'] = {'pass': sum(c['status'] == 'pass' for c in REPORT['checks']),
                    'fail': sum(c['status'] == 'fail' for c in REPORT['checks']),
                    'browser_errors': len(REPORT['browser_errors'])}
(OUT / 'placement-ui-report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')
raise SystemExit(1 if REPORT['counts']['fail'] or REPORT['browser_errors'] else 0)
