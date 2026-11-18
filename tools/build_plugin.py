from pathlib import Path
import json, shutil
R=Path(__file__).resolve().parents[1];P=R; (P/'lib').mkdir(parents=True,exist_ok=True)
html=(R/'index.html').read_text()
source=(R/'src/plugin-client.js').read_text()
(P/'lib/client.js').write_text(source.replace('/*__GAME_HTML_JSON__*/',json.dumps(html,ensure_ascii=False)))
(P/'lib/index.js').write_text('// No host tools, services, timers, RPC, or workspace access.\nexport function apply() {}\n')
# Root package.json is source-controlled and holds npm scripts; do not overwrite it.
(P/'cordis.patch.yml').write_text('- insert:\n    - id: dsh-white-rice-farm\n      name: dsh-plugin-white-rice-farm\n')
(P/'icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect x="4" y="4" width="56" height="56" rx="15" fill="#e7eedc"/><path d="M14 34h36c-2 15-11 20-18 20s-16-5-18-20" fill="#fffdf5" stroke="#526f49" stroke-width="3"/><path d="M18 33c0-11 7-17 14-17s14 6 14 17" fill="#fffdf5" stroke="#526f49" stroke-width="3"/><path d="M25 11c-2-4 2-5 1-9m10 10c-2-4 2-5 1-9" fill="none" stroke="#82966c" stroke-width="2"/></svg>')
print('Built plugin',P)
