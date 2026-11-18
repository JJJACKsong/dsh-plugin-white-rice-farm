/* UI controller. No network, accounts, analytics, model calls, or external dependencies. */
(function(){
'use strict';
const Store=window.FARM_STORAGE||{getItem:k=>window.localStorage.getItem(k),setItem:(k,v)=>window.localStorage.setItem(k,v)};
const E=window.FarmEngine, $=id=>document.getElementById(id), KEY='dsh-farm-v03', PREV_KEY='dsh-farm-v02', OLD_KEY='dsh-farm-v01';
const fmt=n=>Math.floor(n).toLocaleString('zh-CN');
const paths={
 sprout:'M12 21V11M12 15C4 16 3 10 3 6c6 0 10 3 9 9ZM12 11C12 4 16 2 21 3c0 5-3 8-9 8Z',
 leaf:'M5 19C1 10 8 3 20 4c1 12-6 17-15 15Zm0 0L16 8',
 coin:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM14 8h-3a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4h-3M12 6v12',
 meal:'M3 12h18c-.8 6-4 8-9 8s-8.2-2-9-8ZM5 12a4 4 0 0 1 4-5 4 4 0 0 1 6-1 4 4 0 0 1 4 6M8 22h8',
 settings:'m10 3-.7 2.4-2 .8L5 5.1 3.1 8l1.7 1.8-.2 2.2-2 1.5.9 3.2 2.5.3 1.4 1.8-.2 2.5 3.3 1.1 1.6-1.9 2.3-.2 1.8 1.6 2.8-2-1-2.4.9-2 2.3-.8V11l-2.3-.8-.9-2 1-2.4-2.8-2-1.8 1.6-2.3-.2L13 3h-3ZM15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
 hammer:'m4 20 9-9m-1-8 8 8-3 3-8-8 3-3ZM2 19l3 3 8-9-2-2-9 8Z',
 expand:'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M8 8h8v8H8Z',
 basket:'M3 10h18l-2 11H5L3 10Zm3 0L10 3m8 7-4-7M9 14v4m6-4v4',
 pointer:'m6 2 1 18 5-5 5 6 3-2-5-6 7-1L6 2Z',
 box:'m3 7 9-5 9 5v12l-9 4-9-4V7Zm0 0 9 5 9-5M12 12v11M7.5 4.5l9 5',
 mill:'M7 21h10l-2-12H9L7 21ZM12 9V2m0 7 8-4m-8 4 7 5m-7-5-7 5m7-5L4 4M10 21v-5h4v5',
 order:'M8 4H5v18h14V4h-3M8 2h8v5H8V2Zm0 9h8m-8 4h8m-8 4h5',
 arrow:'m9 5 7 7-7 7',close:'m6 6 12 12M18 6 6 18',
 cart:'M3 5h3l3 11h10l2-8H7M10 20h.01M18 20h.01',
 carrot:'M8 8 18 12 4 22 8 8Zm4 2 3-7m0 0 4 1m-4-1-3-2m3 9 7-4M9 12l3 2m-5 2 2 1',
 wheat:'M12 22V3M12 7C8 7 6 4 6 2c4 0 6 2 6 5Zm0 5c-5 0-7-3-7-5 4 0 7 2 7 5Zm0 5c-5 0-7-3-7-5 4 0 7 2 7 5Zm0-8c5 0 7-3 7-5-4 0-7 2-7 5Zm0 6c5 0 7-3 7-5-4 0-7 2-7 5Z',
 grass:'M12 22C8 12 3 7 3 7c0 8 4 14 9 15Zm0 0C7 10 9 3 10 2c4 8 5 12 2 20Zm0 0c0-8 5-15 9-17 0 9-4 14-9 17Z',
 rice:'M4 20c4 2 12 2 16 0M12 19V4M7 18 5 7m7 8 6-7M12 5c3-4 7-2 7 2m-1 2c3-1 4 1 3 3M12 9c-4-5-7-3-7 0',
 flour:'M8 3h8l-1 4c5 5 6 13 2 14H7c-4-1-3-9 2-14L8 3Zm1 4h6M12 12v6m-3-4 3 2 3-2',
 bread:'M4 20h16V9c3-2 0-7-3-6-3-3-9-2-10 0C3 2 0 7 4 9v11Zm4-12 1-2m3 2 1-3m3 3 1-2',
 milk:'M9 2h6v5l3 4v10H6V11l3-4V2Zm0 5h6M6 13h12',
 water:'M12 2C9 7 5 10 5 15a7 7 0 0 0 14 0c0-5-4-8-7-13Zm-3 12c-1 2 0 4 2 4',
 save:'M4 3h14l3 3v15H3V3h1Zm3 0v7h10V3M7 21v-7h10v7',
 download:'M12 2v13m-5-5 5 5 5-5M4 16v5h16v-5'
};
paths.riceflour=paths.flour;paths.ricecake=paths.meal;
function icon(k,cls=''){return `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[k]||paths.sprout}"/></svg>`;}
function hydrate(scope=document){scope.querySelectorAll('[data-icon]').forEach(el=>{if(!el.firstChild)el.innerHTML=icon(el.dataset.icon);});}
function art(kind,purpose='map'){
 const src=(purpose==='card'?FARM_ASSETS.buildingCards?.[kind]:null)||FARM_ASSETS.buildings?.[kind]||FARM_ASSETS.tiles?.[kind];
 if(src)return `<img class="tile-art handpainted" src="${src}" alt="" draggable="false">`;
 return `<svg class="tile-art" viewBox="0 0 100 100" aria-hidden="true"><use href="#art-${kind}"/></svg>`;
}
function buildArt(){
 const sprout=(x,y,scale=1,color='#527b45')=>`<g transform="translate(${x} ${y}) scale(${scale})"><path d="M0 7V-2" stroke="#547341" stroke-width="2"/><ellipse cx="-4" cy="-3" rx="6" ry="3" fill="${color}" transform="rotate(32 -4 -3)"/><ellipse cx="4" cy="-4" rx="6" ry="3" fill="${color}" transform="rotate(-33 4 -4)"/></g>`;
 let defs=`<symbol id="art-ground" viewBox="0 0 100 100"><path d="m20 30-2-4m2 4 3-5M74 76l-3-4m3 4 3-5M50 22l2-4M19 81l3-4M76 27l3 4" stroke="#718e50" stroke-width="1.3" opacity=".5"/><circle cx="71" cy="53" r="1" fill="#d6dfbc"/><circle cx="33" cy="62" r="1.4" fill="#bace9c"/></symbol>`;
 for(const [crop,c]of Object.entries(E.CROPS))for(let stage=0;stage<3;stage++){
   let a='';if(crop==='rice')a+='<path d="M4 22q16-6 30 0t32 0t30 0M4 48q16-6 30 0t32 0t30 0M4 75q16-6 30 0t32 0t30 0" fill="none" stroke="#d1e2d0" stroke-width="2" opacity=".65"/>';
   else a+='<path d="M8 18H92M8 46H92M8 74H92" fill="none" stroke="#896c4e" stroke-width="3" opacity=".4"/>';
   for(let row=0;row<3;row++)for(let col=0;col<3;col++){
    const x=22+col*28+(row%2)*2,y=24+row*26;
    if(stage===0){a+=sprout(x,y,.65);continue;}
    if(crop==='carrot'){if(stage===2)a+=`<ellipse cx="${x}" cy="${y+4}" rx="5" ry="7" fill="#de8a4b" stroke="#b2703f" stroke-width="1"/>`;a+=sprout(x,y,stage===2?1.12:.9,'#4f7845');}
    else if(crop==='wheat'){a+=`<g transform="translate(${x} ${y})"><path d="M0 10V-11m-4 20-4-18m11 19 5-15" stroke="${stage===2?'#a88a37':'#6e8246'}" stroke-width="1.7"/>`;for(let j=0;j<4;j++)a+=`<ellipse cx="${j%2?-2:2}" cy="${-10+j*4}" rx="2.8" ry="4" transform="rotate(${j%2?-30:30} ${j%2?-2:2} ${-10+j*4})" fill="${stage===2?'#e8c368':'#8fa456'}"/>`;a+='</g>';}
    else if(crop==='grass'){a+=`<g transform="translate(${x} ${y})"><path d="M0 9Q-14-1-9-11Q-1-7 0 9ZM0 9Q-4-8 3-14Q7-4 0 9ZM0 9Q3-8 13-8Q12 3 0 9Z" fill="${stage===2?'#537e43':'#799758'}" stroke="#4b723c" stroke-width=".7"/></g>`;}
    else{a+=`<g transform="translate(${x} ${y})"><path d="M0 9V-12M-1 9Q-8 1-7-9M1 9Q7 0 9-6" stroke="#547f50" stroke-width="1.7" fill="none"/>${stage===2?'<path d="M0-10q8-5 11 2M4-11l1 5m3-4 1 5m3-3v4" fill="none" stroke="#d5bb69" stroke-width="2"/>':''}</g>`;}
   }
   defs+=`<symbol id="art-${crop}-${stage}" viewBox="0 0 100 100">${a}</symbol>`;
 }
 const roof=(fill,extra='')=>`<rect x="13" y="17" width="76" height="71" rx="5" fill="#707b4b" opacity=".25"/><rect x="13" y="12" width="72" height="72" rx="3" fill="#e4d5ae" stroke="#8b7c5a" stroke-width="2"/><path d="M9 15h80v62H9Z" fill="${fill}" stroke="#626e62" stroke-width="2"/><path d="M49 15v62" stroke="#4f5c58" stroke-width="3"/><path d="M10 27h38m3 0h37M10 40h38m3 0h37M10 53h38m3 0h37M10 66h38m3 0h37" stroke="#f0efcf" stroke-width="1.2" opacity=".35"/><path d="M18 15v12m11 0v13m-11 0v13m11 0v13m-11 0v11M61 15v12m12 0v13M61 40v13m12 0v13M61 66v11" stroke="#f0efcf" stroke-width="1" opacity=".25"/><rect x="38" y="79" width="21" height="9" rx="2" fill="#ad9269"/>${extra}`;
 defs+=`<symbol id="art-house" viewBox="0 0 100 100">${roof('#82969d','<rect x="65" y="23" width="13" height="14" fill="#d5c0a0" stroke="#6c6e5c" stroke-width="2"/><rect x="68" y="26" width="7" height="8" fill="#625e50"/><circle cx="83" cy="87" r="6" fill="#71904d"/>')}</symbol>`;
 defs+=`<symbol id="art-store" viewBox="0 0 100 100">${roof('#b9a375','<rect x="15" y="80" width="16" height="14" fill="#c4a16a" stroke="#897044"/><path d="m15 80 16 14m0-14-16 14" stroke="#897044"/><rect x="66" y="80" width="16" height="14" fill="#c4a16a" stroke="#897044"/>')}</symbol>`;
 defs+=`<symbol id="art-kitchen" viewBox="0 0 100 100">${roof('#b98367','<rect x="66" y="22" width="13" height="14" fill="#d2c5a9" stroke="#716555" stroke-width="2"/><rect x="69" y="25" width="7" height="8" fill="#61584c"/><circle cx="28" cy="44" r="13" fill="#eee7cd" stroke="#b4a587"/><path d="M17 43h22q-1 12-11 12T17 43Z" fill="#f9f6e9" stroke="#87988c"/><path d="M18 43q10-13 20 0" fill="#fffdf5" stroke="#d7d7c3"/>')}</symbol>`;
 defs+=`<symbol id="art-bakery" viewBox="0 0 100 100">${roof('#b69068','<ellipse cx="28" cy="43" rx="13" ry="9" fill="#e8bc70" stroke="#ad8149"/><path d="m22 38 2 7m4-9 2 9m4-8 2 7" stroke="#bd904e" stroke-width="2"/>')}</symbol>`;
 defs+=`<symbol id="art-well" viewBox="0 0 100 100"><circle cx="50" cy="54" r="29" fill="#7d8864" opacity=".25"/><circle cx="48" cy="49" r="28" fill="#d2c9ab" stroke="#8f8e76" stroke-width="2"/><circle cx="48" cy="49" r="17" fill="#6f9ca1" stroke="#7a8a78" stroke-width="3"/><path d="m48 21 0 11m20-3-8 9m16 11H66m2 20-8-9M48 77V66M29 69l8-9M20 49h11m-3-20 8 9" stroke="#a6a38d" stroke-width="2"/><path d="M27 16v66m42-66v66M24 25h48" stroke="#866e4b" stroke-width="5"/><path d="M48 25v22" stroke="#c4ac79" stroke-width="2"/><rect x="40" y="39" width="14" height="13" rx="3" fill="#b89a6a" stroke="#746b52"/></symbol>`;
 defs+=`<symbol id="art-mill" viewBox="0 0 100 100"><circle cx="52" cy="56" r="32" fill="#7d8864" opacity=".25"/><circle cx="49" cy="48" r="32" fill="#d7c69e" stroke="#8c8061" stroke-width="2"/><path d="M49 16 81 48 49 80 17 48Z" fill="#b1a083" stroke="#8c8061"/><path d="M49 17v62M18 48h62" stroke="#d7c69e" stroke-width="2"/><g transform="rotate(35 49 48)"><path d="M46 5h8v86h-8Z" fill="#aa8452" stroke="#7f684b"/><path d="M7 44h85v8H7Z" fill="#aa8452" stroke="#7f684b"/><path d="M39 5h14v24H39ZM68 38h24v14H68ZM46 67h14v24H46ZM7 45h24v14H7Z" fill="#e5d9b6" stroke="#997a50" stroke-width="2"/></g><circle cx="49" cy="48" r="6" fill="#92734f"/></symbol>`;
 defs+=`<symbol id="art-cows" viewBox="0 0 100 100"><rect x="9" y="9" width="82" height="82" rx="5" fill="#b8b285" stroke="#8b7653" stroke-width="3"/><path d="M18 11v78M82 11v78M11 18h78M11 82h78" stroke="#d4bd90" stroke-width="4"/><rect x="21" y="19" width="58" height="24" fill="#b59469" stroke="#8e754f"/><path d="M22 26h56m-56 9h56" stroke="#dec69c"/><ellipse cx="50" cy="62" rx="19" ry="12" fill="#f7f1df" stroke="#9c9477" stroke-width="1.5"/><ellipse cx="39" cy="59" rx="7" ry="6" fill="#777063"/><ellipse cx="54" cy="68" rx="6" ry="5" fill="#777063"/><ellipse cx="71" cy="60" rx="8" ry="7" fill="#f7f1df" stroke="#9c9477"/><path d="m69 54-3-5m9 5 4-4M31 62l-6 5" stroke="#8d806b" stroke-width="2"/><circle cx="28" cy="75" r="5" fill="#d7b76f"/></symbol>`;
 $('art-defs').innerHTML=`<svg xmlns="http://www.w3.org/2000/svg"><defs>${defs}</defs></svg>`;
}
const ui={crop:'carrot',mode:null,building:null,moveFrom:null,drawer:null,tile:null,cols:0,confirmReset:false,focusReturn:null,goal:null,lastCrewKey:'',lastRender:0,storageOK:true,saveWarned:false,view:'farm'};
let s, storageError='', bootMessage='',lastWall=Date.now(),lastSave=0;
try{
 const stored=Store.getItem(KEY),prev=Store.getItem(PREV_KEY),old=Store.getItem(OLD_KEY);
 if(stored){try{s=E.restore(JSON.parse(stored),lastWall);}catch(err){Store.setItem(KEY+'-recovery-'+lastWall,stored);s=E.initial(lastWall);bootMessage='存档格式有误，已备份原数据并新建农场；可在设置里导出当前进度。';}}
 else if(prev){try{s=E.restore(JSON.parse(prev),lastWall);bootMessage='已从旧版 v2 存档迁移到当前版本；原存档保留，不会覆盖新货架。';}catch(err){Store.setItem(KEY+'-recovery-'+lastWall,prev);s=E.initial(lastWall);bootMessage='旧版 v2 存档格式有误，已备份原数据并新建农场；可在设置里导出当前进度。';}}
 else if(old){s=E.restore(JSON.parse(old),lastWall);bootMessage=s.lastNotice;}
 else s=E.initial(lastWall);
}catch(err){ui.storageOK=false;storageError='当前浏览器限制了本地存档，请在设置中导出备份。';s=E.initial(lastWall);}
const tiles=createFarmTiles({assets:FARM_ASSETS,reducedMotion:()=>s.options.reducedMotion});
const actors=createFarmActors({layer:$('actors'),board:$('board'),getState:()=>s,assets:FARM_ASSETS.animations});
const mapView=createFarmMapView({viewport:$('board-scroll'),board:$('board'),onChange:()=>{actors.sync(mapView.tileSize());renderMapLegend();}});
const elapsed=Math.max(0,lastWall-s.savedAt);
if(elapsed>0){const before={gold:s.gold,harvests:s.stats.harvests};E.advance(s,Math.min(elapsed,E.OFFLINE_CAP));if(elapsed>5000&&!bootMessage)bootMessage=`离开了 ${Math.max(1,Math.floor(elapsed/60000))} 分钟，农场推进 ${Math.round(Math.min(elapsed,E.OFFLINE_CAP)/60000)} 分钟：收了 ${s.stats.harvests-before.harvests} 块田，收入 ${fmt(s.gold-before.gold)} 金币${elapsed>E.OFFLINE_CAP?'（离线最多结算 8 小时）':''}。`;}
function save(){s.savedAt=Date.now();try{Store.setItem(KEY,JSON.stringify(s));ui.storageOK=true;lastSave=Date.now();}catch(err){ui.storageOK=false;lastSave=Date.now();}updateSaveStatus();}
function saveOK(){return window.FARM_STORAGE?.available===false?false:ui.storageOK;}
function saveStatusDetail(ok=saveOK()){return ok?'本地存档正常：操作后会立即写入当前浏览器，并每 5 秒补存一次。':'本地存档受限：当前浏览器没有成功写入，进度可能只在当前页面保留。请现在导出存档备份。';}
function updateSaveStatus(){
 const ok=saveOK();ui.storageOK=ok;
 const el=$('save-status'),label=$('save-status-text');
 if(el){el.classList.toggle('is-error',!ok);const aria=ok?'存档状态：自动存档。打开设置可查看存档详情或导出备份。':'存档状态：存档受限。打开设置查看详情并导出备份。';if(el.getAttribute('aria-label')!==aria)el.setAttribute('aria-label',aria);}
 if(label&&label.textContent!==(ok?'自动存档':'存档受限'))label.textContent=ok?'自动存档':'存档受限';
 document.querySelectorAll('[data-save-detail]').forEach(e=>{const text=saveStatusDetail(ok);if(e.textContent!==text)e.textContent=text;});
 if(!ok&&!ui.saveWarned){ui.saveWarned=true;tell('本地存档受限，进度可能只在当前页面保留；请在设置里导出备份。',true);}
 else if(ok)ui.saveWarned=false;
}
function tickTime(notify=true){const before=E.farmLevel(s),t=Date.now(),dt=Math.max(0,t-lastWall);if(dt)E.advance(s,Math.min(dt,E.OFFLINE_CAP));lastWall=t;const after=E.farmLevel(s);if(notify&&after>before)tell(`庄园升到 Lv.${after}，新建筑与成长奖励已经解锁。`);}
function tell(message,error=false){$('notice-text').textContent=message;$('notice').classList.toggle('error',error);}
function apply(fn,{close=false}={}){const before=E.farmLevel(s);tickTime(false);const afterTime=E.farmLevel(s),r=fn(),after=E.farmLevel(s),levelMessages=[];if(afterTime>before)levelMessages.push(`庄园升到 Lv.${afterTime}。`);if(after>afterTime)levelMessages.push(`庄园升到 Lv.${after}，新建筑与成长奖励已经解锁。`);const message=[r?.message,...levelMessages].filter(Boolean).join(' ');if(message)tell(message,r?.ok===false);if(close)closeDrawer();save();render();if(ui.drawer)renderDrawer();return r;}
function getExtent(){let n=4;for(let i=0;i<256;i++)if(s.tiles[i])n=Math.max(n,...E.coord(i).map(v=>v+1));if(ui.mode==='expand')for(const c of E.eligibleChunks(s))n=Math.max(n,c.x+2,c.y+2);return Math.min(16,n);}
function fieldText(t){if(t?.type!=='field')return '这轮已收完，空地腾好了。';if(!t.crop)return `空田，计划种${E.CROPS[t.plan].name}`;return `${E.CROPS[t.crop].name} · ${E.ripe(s,t)?'已成熟，点一下收好再种':`还需 ${Math.max(0,Math.ceil((t.readyAt-s.time)/1000))} 秒`}`;}
function renderMapLegend(){
 $('garden-legend').innerHTML=mapView.isOverview()?'全景 · 点地块放大':ui.mode==='expand'?`一次买 4 格 · 本次 ${fmt(E.expansionCost(s))} 金币`:'<span class="legend-ready"></span>浅金色边框 = 可以收了';
}
function renderBoard(){
 const n=getExtent(),board=$('board'),placing=E.BUILDINGS[ui.building];
 let focusedTile=null;
 if(ui.cols!==n){const active=document.activeElement,anchor=ui.cols?mapView.anchor():null;focusedTile=board.contains(active)?active.dataset.tile:null;ui.cols=n;board.style.setProperty('--cols',n);let html='';for(let y=0;y<n;y++)for(let x=0;x<n;x++)html+=`<button type="button" class="tile" data-tile="${E.idx(x,y)}"></button>`;board.innerHTML=html;tiles.prune();mapView.sync(n,anchor);}
 else mapView.sync(n);
 const eligible=new Set(E.eligibleChunks(s).flatMap(c=>[E.idx(c.x,c.y),E.idx(c.x+1,c.y),E.idx(c.x,c.y+1),E.idx(c.x+1,c.y+1)]));
 for(const el of board.children){
  const i=+el.dataset.tile,t=s.tiles[i],[x,y]=E.coord(i);
  let className='tile '+(t?.type||'outside'),label='',key=null,ready=false,progress=null,plus=false;
  if(!t){if(ui.mode==='expand'&&eligible.has(i)){className+=' eligible';plus=true;label=`购买这块 2×2 土地，${E.expansionCost(s)} 金币`;}else label='未开垦土地';}
  else if(t.type==='grass'){key='ground';label=`空地，开垦并种${E.CROPS[ui.crop].name}需 12 金币`;if(!ui.mode&&ui.crop==='rice'&&E.irrigated(s,x,y))className+=' water-eligible';}
  else if(t.type==='building'){
   key=t.kind;label=E.BUILDINGS[t.kind].name;
   if(t.job){progress=100*(s.time-t.job.startedAt)/E.RECIPES[t.job.item].time;label+=t.job.readyAt<=s.time?' · 等待仓库空间':` · ${Math.ceil((t.job.readyAt-s.time)/1000)} 秒`;}
  }else{
   label=fieldText(t);
   if(t.crop){ready=E.ripe(s,t);const pct=Math.min(1,Math.max(0,(s.time-t.startedAt)/(t.readyAt-t.startedAt)));key=t.crop+'-'+FarmCropStage(pct,ready);if(t.crop==='rice')className+=' rice';if(ready)className+=' ready';else progress=pct*100;}
   else key=t.plan==='rice'?'paddy':'soil';
  }
  if(t&&(ui.mode==='build'||ui.mode==='move')){
   const free=t.type==='grass';className+=free?' placeable':' unplaceable';
   label=free?(ui.mode==='build'?`在空地建${placing.name}，${fmt(placing.cost)} 金币`:ui.building==='well'?`仍须保证稻田有水，才能把${placing.name}免费搬到这里`:`把${placing.name}搬到这块空地，免费`):`${t.type==='building'?E.BUILDINGS[t.kind].name:'田地'}占用此处；请选空草地${ui.mode==='build'?'建造':'搬家'}`;
  }
  if(t&&ui.mode==='expand'){className+=' unplaceable';label='已拥有的土地，请选高亮的相邻土地扩地';}
  if(el.className!==className){const transitioning=el.classList.contains('tile-transitioning');el.className=className;if(transitioning)el.classList.add('tile-transitioning');}
  tiles.paint(el,{art:key,canFade:t?.type==='field',ready,progress,building:t?.type==='building',label:t?label:'',plus});
  el.setAttribute('aria-label',`第 ${x+1} 列第 ${y+1} 行，${label}`);el.title=label;
 }
 $('land-count').textContent=`${E.owned(s)} 格土地`;
 renderMapLegend();
 $('placement').hidden=!ui.mode;
 if(ui.mode){$('placement-title').textContent=ui.mode==='build'?`正在摆放：${placing.name}`:ui.mode==='move'?`正在搬家：${placing.name}`:'把农场再扩大一点';$('placement-hint').textContent=ui.mode==='expand'?'点高亮的任一格，买下整片 2×2 土地。':ui.mode==='build'?`点虚线框里的空草地，花 ${fmt(placing.cost)} 金币建好。`:ui.building==='well'?'点虚线框里的空草地尝试免费搬家；仍须保证稻田有水。':'点虚线框里的空草地，免费搬家并保留进度。';}
 $('expand-button').disabled=E.owned(s)>=256;
 actors.sync(mapView.tileSize());
 if(focusedTile!==null)(board.querySelector(`[data-tile="${focusedTile}"]`)||$('expand-button')).focus({preventScroll:true});
}

function goal(){
 const n=s.workers.length,kitchen=E.count(s,'building','kitchen');
 if(!s.stats.harvests)return {title:'先收一轮萝卜',desc:'两块田已经熟了。收获后会补种，余粮直接变成金币。',p:0,label:'成熟的田地已经用浅金色标出来了',button:'收好，再种一轮',action:'tend-all'};
 if(!kitchen)return {title:'架起一口小灶台',desc:'种水稻，蒸大白饭。饭做好了，帮你干活的大肥鱼才会来。',p:Math.min(1,s.gold/80),label:`${fmt(s.gold)} / 80 金币`,button:'建一口小灶台',action:'quick-kitchen',disabled:s.gold<80};
 if(n===0){const rice=s.tiles.some(t=>t?.type==='field'&&(t.crop==='rice'||t.plan==='rice'));if(!rice)return {title:'给白饭找一片稻田',desc:'水井旁边才能种水稻。选水稻后，点带浅蓝标记的空地。',p:0,label:'水稻 35 秒 · 大白饭 50 秒',button:'选水稻，去种田',action:'choose-rice'};
  const r=E.RECRUITS[0];return {title:s.inventory.meal<3?'先蒸三碗大白饭':'招来第一只大肥鱼',desc:'小灶台会自动煮饭。招到帮手后，收割和补种就不用你点了。',p:(Math.min(1,s.gold/r.gold)+Math.min(1,s.inventory.meal/r.meal))/2,label:`${fmt(s.gold)} / 200 金币 · ${s.inventory.meal} / 3 碗饭`,button:'招来吃白饭的',action:'recruit',disabled:s.gold<r.gold||s.inventory.meal<3};}
 if(!E.count(s,'building','mill')&&!E.canBuild(s,'mill')){const p=E.levelProgress(s);return {title:'先让庄园长大一点',desc:'收获、加工、扩地和完成订单都会积累声望。达到 Lv.2 就能建磨坊。',p:p.progress,label:`庄园 Lv.${p.level} · 声望 ${p.xp} / ${p.nextXp}`,button:'查看庄园成长',action:'open-growth'};}
 if(!E.count(s,'building','mill'))return {title:'让小麦多赚一点',desc:'田里的事有人照看了。建一座磨坊，试试第一条加工链。',p:Math.min(1,s.gold/200),label:`${fmt(s.gold)} / 200 金币`,button:'建一座磨坊',action:'quick-mill',disabled:s.gold<200};
 if(E.canBuild(s,'bakery')&&!E.count(s,'building','bakery')){const cost=E.BUILDINGS.bakery.cost;return {title:'让面粉接着变成面包',desc:'面包房已经解锁。也可以让磨坊做米粉，再由面包房做米糕；选好以后都会自动接着做。',p:Math.min(1,s.gold/cost),label:`${fmt(s.gold)} / ${cost} 金币 · 也可先招工或扩地`,button:'添一间面包房',action:'quick-bakery',disabled:s.gold<cost};}
 if(n<4){const r=E.RECRUITS[n];return {title:`再请第 ${n+1} 位帮手`,desc:'不分职业，也不排班。多一位帮手，就能同时照料更多田地。',p:(Math.min(1,s.gold/r.gold)+Math.min(1,s.inventory.meal/r.meal))/2,label:`${fmt(s.gold)} / ${r.gold} 金币 · ${s.inventory.meal} / ${r.meal} 碗饭`,button:'招来吃白饭的',action:'recruit',disabled:s.gold<r.gold||s.inventory.meal<r.meal};}
 return {title:E.owned(s)>=256?'农场忙，你歇着':'四只大肥鱼，都齐了',desc:E.owned(s)>=256?'土地已经开垦到 16×16。接下来慢慢调整种植和加工，或者看她们吃白饭。':'扩点地、换换作物，或者添一间工坊。重复劳动就交给她们。',p:Math.min(1,E.owned(s)/256),label:`${E.owned(s)} / 256 格土地`,button:E.owned(s)>=256?'看看农场账本':'再扩一片土地',action:E.owned(s)>=256?'open-inventory':'expand-mode'};
}
function renderCrew(){
 $('crew-count').textContent=`${s.workers.length} / 4`;
 const ripe=s.tiles.filter(t=>E.ripe(s,t)),free=E.capacity(s)-E.total(s);
 const idleText=ripe.some(t=>E.CROPS[t.crop].yield>free)?'仓库空间不足，收成还在田里':ripe.length?'等下一轮照料田地':'田地长着，先吃口饭';
 const key=s.workers.map(w=>`${w.id}-${w.status==='working'&&s.time-w.lastAt<3500?'working':idleText}`).join(',');
 if(ui.lastCrewKey!==key||!$('crew-body').innerHTML){ui.lastCrewKey=key;const avatar=FARM_ASSETS.poster;
  $('crew-body').innerHTML=s.workers.length?s.workers.map(w=>`<div class="crew-row"><img class="crew-avatar" src="${avatar}" alt="DeepSeek 娘头像"><div><strong>大肥鱼 #${w.id}</strong><small>${w.status==='working'&&s.time-w.lastAt<3500?'正在照料田地':idleText}</small></div><span class="worker-dot ${w.status==='working'&&s.time-w.lastAt<3500?'':'idle'}"></span></div>`).join(''):`<div class="crew-empty"><img class="crew-avatar" src="${avatar}" alt="DeepSeek 娘头像"><div><strong>人还没来，饭先做好。</strong><p>招来就帮忙。<br>不用排班，也不用天天喂饭。</p></div></div>`;
 }
 const {n,r,disabled}=recruitOffer();
 if(r){const html=`${n?`<p class="recruit-title">下一位帮手</p>`:''}<div class="cost-line"><strong data-recruit-gold class="${s.gold>=r.gold?'cost-ok':''}">${r.gold} 金币</strong><span>+</span><strong data-recruit-meal class="${s.inventory.meal>=r.meal?'cost-ok':''}">${r.meal} 碗大白饭</strong></div><button class="button ${disabled?'soft':'primary'} wide" data-action="recruit" data-recruit-button ${disabled?'disabled':''}>${n?'再招一只':'招来吃白饭的'}</button>`;if(ui.recruitHTML!==html){$('crew-recruit').innerHTML=html;ui.recruitHTML=html;}}
 else $('crew-recruit').innerHTML='<p class="drawer-intro" style="margin:12px 0 0;font-size:10px">四位都到齐了。招工时才扣饭，吃饭动画不扣库存。</p>';
}
function commercialFocusKey(el){return el?.dataset?.streetFocus||null;}
function commercialControlVisible(el){
 const data=$('commercial-data')?.getBoundingClientRect(),r=el.getBoundingClientRect();
 return !data||(r.top>=data.top-2&&r.bottom<=data.bottom+2&&r.left>=data.left-2&&r.right<=data.right+2);
}
function restoreCommercialFocus(key,wasVisible){
 const view=$('commercial-view');if(!view||!key)return;
 let target=view.querySelector(`[data-street-focus="${key}"]:not(:disabled)`);
 if(!target&&key){
  const [,shop,item]=key.split('|');
  if(item){const row=view.querySelector(`.goods-row [data-item="${item}"]`)?.closest('.goods-row');target=row?.querySelector('button[data-street-action]:not(:disabled)')||null;}
  if(!target&&shop)target=view.querySelector(`[data-street-action="return"][data-shop="${shop}"]:not(:disabled)`);
 }
 if(!target)target=view.querySelector('#street-sale-toggle:not(:disabled)')||$('farm-toggle');
 if(!target)return;
 target.focus({preventScroll:!wasVisible||commercialControlVisible(target)});
}
function renderCommercial(){
 const view=$('commercial-view');if(!view||ui.view!=='street')return;
 // Preserve the pressed node and quote until release; the engine clock still advances.
 if(view.querySelector('[data-street-action]:active'))return;
 const active=document.activeElement,focusKey=view.contains(active)?commercialFocusKey(active):null,wasVisible=!!focusKey&&commercialControlVisible(active);
 $('street-gold').textContent=fmt(s.gold);$('street-storage').textContent=`${fmt(E.total(s))} / ${fmt(E.capacity(s))}`;$('street-sold').textContent=`${fmt(s.stats.sold)} 份`;$('street-sale-toggle').setAttribute('aria-pressed',s.options.autoSell?'true':'false');$('street-sale-label').textContent=s.options.autoSell?'已开启':'已暂停';
 const shelf=(key)=>{const shop=s.shops[key],back=E.retailReturnQuote(s,key);if(!shop.open)return `<div class="shelf-line">尚未开张 · 庄园 Lv.3 解锁</div>`;if(!back.item)return `<div class="shelf-line">货架空着 · 有货就能上架</div>`;const left=Math.max(0,Math.ceil((shop.nextAt-s.time)/1000));return `<div class="shelf-line">货架：${E.ITEMS[back.item].name} ×${back.qty} · 下次成交 ${left} 秒 <button class="button small" data-street-action="return" data-street-focus="return|${key}||" data-shop="${key}" ${!back.ok?'disabled':''}>退回未售货</button>${back.missing?`<small class="return-blocked">仓库还差 ${back.missing} 格，暂时无法退回</small>`:''}</div>`;};
 $('shop-status-grid').innerHTML=`<section class="shop-status"><div class="shop-status-head"><strong>田园农产铺</strong><small>已开张 · 自动营业</small></div><p>出售萝卜、小麦、牧草和水稻。批发满 6 份即时结算。</p>${shelf('produce')}</section><section class="shop-status ${s.shops.food.open?'':'locked'}"><div class="shop-status-head"><strong>大白食品铺</strong><small>${s.shops.food.open?'已开张 · 自动营业':'庄园 Lv.3 解锁'}</small></div><p>出售面粉、米粉、面包、米糕、牛奶和大白饭。</p>${shelf('food')}</section>`;
 const section=(key,title)=>`<section class="goods-section"><h3>${title}<small>${key==='produce'?'原农产':'加工与食品'}</small></h3>${Object.keys(E.ITEMS).filter(k=>E.retailShopFor(k)===key).map(k=>{
  const item=E.ITEMS[k],w=E.wholesaleQuote(s,k),one=E.retailQuote(s,key,k,1),max=E.retailQuote(s,key,k,E.RETAIL_LIMIT);
  return `<div class="goods-row"><div class="goods-name"><strong>${item.name}</strong><small>批发 ${w.unitPrice} · 零售 ${one.unitPrice} 金币</small></div><div class="goods-stock"><strong>${s.inventory[k]} 份</strong><small>可分配 ${one.available} 份</small></div><div class="goods-actions"><button class="button" data-street-action="wholesale" data-street-focus="wholesale|${key}|${k}|" data-item="${k}" data-qty="${w.qty}" data-price="${w.unitPrice}" ${!w.ok?'disabled':''}>批发 ${w.ok?w.qty+'份':'未满6份'}</button><button class="button retail" data-street-action="retail" data-street-focus="retail|${key}|${k}|one" data-shop="${key}" data-item="${k}" data-qty="1" data-price="${one.unitPrice}" ${!one.ok?'disabled':''}>上架1份</button><button class="button retail" data-street-action="retail" data-street-focus="retail|${key}|${k}|max" data-shop="${key}" data-item="${k}" data-qty="${max.qty}" data-price="${max.unitPrice}" ${!max.ok?'disabled':''}>尽量上架${max.qty||''}</button></div></div>`;
 }).join('')}</section>`;
 $('commercial-goods').innerHTML=section('produce','农产商品')+section('food','食品商品');
 restoreCommercialFocus(focusKey,wasVisible);
}
function render(){
 $('gold').textContent=fmt(s.gold);$('meal').textContent=fmt(s.inventory.meal);const growth=E.levelProgress(s);$('farm-level').textContent=`庄园 Lv.${growth.level}`;$('farm-level').title=`${growth.title} · 声望 ${growth.xp}${growth.next?` / ${growth.nextXp}`:' · 已满级'}`;$('storage-label').textContent=`${fmt(E.total(s))} / ${fmt(E.capacity(s))} · 原料会自动留存`;
 const machines=s.tiles.filter(t=>t?.type==='building'&&E.BUILDINGS[t.kind].recipe),phases={};
 for(const t of machines){const phase=t.job?(t.job.readyAt<=s.time?'等待入库':'加工中'):t.paused?'已暂停':'等原料';phases[phase]=(phases[phase]||0)+1;}
 $('workshop-label').textContent=machines.length?Object.entries(phases).map(([phase,n])=>`${n} 间${phase}`).join(' · '):'建好就会自动加工';
 $('order-label').textContent=s.activeOrder?`${E.ITEMS[s.activeOrder.item].name} ${s.inventory[s.activeOrder.item]} / ${s.activeOrder.qty} · 凑齐自动交付`:'顺手多赚一点，不做也没关系';
 $('farm-status').textContent=(s.workers.length?`${s.workers.length} 位帮手正在照看，收割后自动补种。`:'先自己收一轮，大肥鱼随后就来。')+` · 声望 ${growth.xp}${growth.next?` / ${growth.nextXp}`:' · 已满级'}`;
 $('sale-toggle').setAttribute('aria-pressed',s.options.autoSell?'true':'false');$('sale-title').textContent=s.options.autoSell?'余粮自动出售':'余粮暂存在仓库';
 const cropHTML=Object.entries(E.CROPS).map(([k,c])=>`<button class="crop-chip ${ui.crop===k?'active':''}" data-crop="${k}" aria-pressed="${ui.crop===k}" title="选${c.name}，点空地就种">${icon(k)}<span>${c.name}</span><small>${c.time/1000}秒</small></button>`).join('');if(ui.cropHTML!==cropHTML){$('crop-options').innerHTML=cropHTML;ui.cropHTML=cropHTML;}
 const mature=s.tiles.filter(t=>E.ripe(s,t)).length,empty=s.tiles.filter(t=>t?.type==='field'&&!t.crop).length;
 $('harvest-count').textContent=mature||empty;$('harvest-count').hidden=mature+empty===0;
 $('harvest-label').textContent=mature?'收好再种':empty?'把空田补种好':'都在好好长着';$('harvest-button').disabled=mature+empty===0;
 $('context-hint').textContent=ui.crop==='rice'?'水井周围一圈可以种水稻；拖动地图查看，点击地块操作。':'拖动地图查看；点击成熟田收好再种，点空地种植。';
 const g=goal();ui.goal=g;$('goal-title').textContent=g.title;$('goal-desc').textContent=g.desc;$('goal-progress').style.width=(100*g.p)+'%';$('goal-progress-label').textContent=g.label;$('goal-button').textContent=g.button;$('goal-button').dataset.action=g.action;$('goal-button').disabled=!!g.disabled;
 document.body.classList.toggle('no-motion',s.options.reducedMotion);document.body.classList.toggle('commercial-mode',ui.view==='street');document.querySelector('.farm-card')?.classList.toggle('commercial-mode',ui.view==='street');$('commercial-view').hidden=ui.view!=='street';$('commercial-toggle').hidden=ui.view==='street';$('farm-toggle').hidden=ui.view!=='street';$('farm-view-title').textContent=ui.view==='street'?'庄园商业街':'我的农场';$('farm-status').textContent=ui.view==='street'?'上方街景只作演示；商品库存、金币和顾客成交沿用同一经营时钟。':(s.workers.length?`${s.workers.length} 位帮手正在照看，收割后自动补种。`:'先自己收一轮，大肥鱼随后就来。')+` · 声望 ${growth.xp}${growth.next?` / ${growth.nextXp}`:' · 已满级'}`;renderCrew();if(ui.view==='farm')renderBoard();else renderCommercial();updateSaveStatus();updateDrawerLive();hydrate();
}
function closeDrawer(){ui.drawer=null;$('drawer').hidden=true;$('drawer-backdrop').hidden=true;document.body.style.overflow='';if(ui.focusReturn?.isConnected)ui.focusReturn.focus();ui.focusReturn=null;}
function openDrawer(kind,tile=null){if(!ui.drawer)ui.focusReturn=document.activeElement;ui.drawer=kind;ui.tile=tile;ui.confirmReset=false;$('drawer').hidden=false;$('drawer-backdrop').hidden=false;document.body.style.overflow='hidden';renderDrawer();$('drawer').querySelector('[data-action="close-drawer"]').focus();}
function prepareBuild(kind){ui.mode='build';ui.building=kind;closeDrawer();const b=E.BUILDINGS[kind];tell(`点空草地建${b.name}，放下时花 ${fmt(b.cost)} 金币。`);render();$('garden').scrollIntoView({block:'nearest',behavior:s.options.reducedMotion?'instant':'smooth'});}
function cancelPlacement(){
 const mode=ui.mode,from=ui.moveFrom,restoreFocus=$('placement').contains(document.activeElement);ui.mode=null;ui.building=null;ui.moveFrom=null;
 if(mode)tell(`已取消${mode==='build'?'建造':mode==='move'?'搬家':'扩地'}，回到种田。点空地种${E.CROPS[ui.crop].name}。`);
 if(mode&&restoreFocus){
  // Removing the banner changes the viewport; focus against its final geometry.
  $('placement').hidden=true;
  const target=mode==='move'?$('board').querySelector(`[data-tile="${from}"]`):mode==='expand'?$('expand-button'):document.querySelector('.farm-actions [data-open="build"]');
  target?.focus();if(mode==='move')mapView.revealTile(from);
 }
}
function machineToggleLabel(t){return t.paused?(t.job?'取消完成后暂停':'恢复生产'):t.job?'做完这批后暂停':'暂停生产';}
function storageUpgrade(){const {cost,ok}=E.storageUpgradeOffer(s);return {cost,disabled:!ok};}
function storageButtonHTML(prefix='扩容 100 格'){const u=storageUpgrade();return `<button class="button wide" data-action="upgrade-storage" data-storage-upgrade data-storage-prefix="${prefix}" ${u.disabled?'disabled':''}>${prefix} · ${u.cost} 金币</button>`;}
function toolsUpgrade(){const {cost,ok,message}=E.toolUpgradeOffer(s);return {disabled:!ok,label:cost===null?'农具已升满':`农具升级 · ${cost} 金币`,reason:ok?'':message};}
function toolsButtonHTML(){const u=toolsUpgrade();return `<button class="button wide" data-action="upgrade-tools" data-tools-upgrade ${u.disabled?'disabled':''}>${u.label}</button><p class="action-reason" data-tools-reason ${u.reason?'':'hidden'}>${u.reason}</p>`;}
function recruitOffer(){const n=s.workers.length;if(n>=4)return {n,r:null,disabled:true};const r=E.RECRUITS[n];return {n,r,disabled:s.gold<r.gold||s.inventory.meal<r.meal};}
function recipeInputText(t,item){
 const r=E.RECIPES[item];if(!r)return '';
 const input=E.ITEMS[r.input].name,have=s.inventory[r.input]||0,avail=E.availableInput(s,item);
 const locked=s.activeOrder?.item===r.input?Math.min(have,s.activeOrder.qty):0;
 let text=`可用 ${input} ${avail}/${r.amount}（库存 ${have}`;
 if(locked)text+=` · 订单保留 ${locked}`;
 text+='）';if(avail<r.amount){
  text+=` · 还差 ${r.amount-avail}`;
  const source=E.RECIPES[r.input]?.building;
  if(source&&!E.count(s,'building',source))text+=` · 可先建${E.BUILDINGS[source].name}来加工${input}`;
 }
 return text;
}
function recipePanel(t,i){
 const selected=E.recipeFor(t);
 let h=`<div class="recipe-panel" role="group" aria-label="选择下一批产品"><div class="recipe-panel-head"><strong>下一批</strong><span data-recipe-status="${i}">${machineStatus(t)}</span></div><div class="recipe-options">`;
 for(const item of E.recipesFor(t.kind)){
  const r=E.RECIPES[item],unlocked=E.canUseRecipe(s,t.kind,item),active=selected===item;
  const meta=unlocked?`${E.ITEMS[r.input].name} ×${r.amount} → ${r.qty} 份 · ${r.time/1000} 秒`:`Lv.${r.unlockLevel||1} 解锁`;
  const title=unlocked?`下一批做${E.ITEMS[item].name}：${E.ITEMS[r.input].name} ×${r.amount} → ${E.ITEMS[item].name} ×${r.qty}`:`${E.ITEMS[item].name}需要庄园 Lv.${r.unlockLevel||1}`;
  h+=`<button type="button" class="recipe-chip${active?' active':''}" data-recipe="${i}" data-recipe-item="${item}" aria-pressed="${active}" ${unlocked?'':'disabled'} title="${title}">${icon(item)}<span class="recipe-name">${E.ITEMS[item].name}<small>${meta}</small></span></button>`;
 }
 return h+`</div><p class="recipe-input" data-recipe-input="${i}">${recipeInputText(t,selected)}</p></div>`;
}
function machineStatus(t){
 if(t.job){
  const ready=t.job.readyAt<=s.time;
  let text=ready?`本批 ${E.ITEMS[t.job.item].name} 已做好，等待仓库空间`:`本批 ${E.ITEMS[t.job.item].name} · 还需 ${Math.ceil((t.job.readyAt-s.time)/1000)} 秒`;
  if(t.paused)text+=ready?' · 入库后暂停':' · 完成后暂停';return text;
 }
 const next=E.recipeFor(t)||E.BUILDINGS[t.kind].recipe;
 if(t.paused)return `已暂停 · 下一批 ${E.ITEMS[next].name}`;
 const r=E.RECIPES[next],avail=E.availableInput(s,next);
 const locked=s.activeOrder?.item===r.input?Math.min(s.inventory[r.input]||0,s.activeOrder.qty):0;
 if(avail<r.amount)return `下一批 ${E.ITEMS[next].name} · 等${E.ITEMS[r.input].name}（可用 ${avail}/${r.amount}${locked?` · 订单保留 ${locked}`:''}）`;
 return `下一批 ${E.ITEMS[next].name} · 可开工`;
}
function orderKey(o){return `${o.item}:${o.qty}:${o.pay}`;}
function drawerStructureKey(){
 if(ui.drawer==='orders')return s.activeOrder?'active:'+orderKey(s.activeOrder):'offers:'+E.availableOrders(s).map(orderKey).join('|');
 if(ui.drawer==='field')return 'field:'+ui.tile+':'+s.tiles[ui.tile]?.type;
 return ui.drawer;
}
function drawerControlKey(el){
 if(!el?.dataset)return null;const d=el.dataset;
 if(d.order!==undefined)return `order:${d.orderItem}:${d.orderQty}:${d.orderPay}`;
 if(d.recipe!==undefined)return `recipe:${d.recipe}:${d.recipeItem}`;
 for(const key of ['action','open','build','plan','toggleMachine'])if(d[key]!==undefined)return key+':'+d[key];
 return null;
}
function renderDrawer(){
 if(!ui.drawer)return;
 const active=document.activeElement,focusKey=$('drawer-content').contains(active)?drawerControlKey(active):null;
 const kind=ui.drawer,t=ui.tile!==null?s.tiles[ui.tile]:null;
 const titles={overview:'庄园与帮手',growth:'庄园成长',build:'添点新家当',inventory:'庄园仓库',workshops:'让工坊自己忙',orders:'顺手接个订单',settings:'庄园设置',help:'三件事，就会玩',field:'这块田怎么种',building:t?.kind?E.BUILDINGS[t.kind].name:'建筑'};
 $('drawer-title').textContent=titles[kind]||'庄园';let h='';
 if(kind==='overview'){const g=goal();h=`<div class="drawer-section"><h3 data-overview-goal="title">${g.title}</h3><p data-overview-goal="desc">${g.desc}</p><p data-overview-goal="label">${g.label}</p><button class="button primary wide" data-overview-goal-action data-action="${g.action}" ${g.disabled?'disabled':''}>${g.button}</button></div><div class="drawer-section"><h3 data-recruit-title>招来吃白饭的 · ${s.workers.length} / 4</h3><div data-overview-crew>${$('crew-body').innerHTML}</div>${$('crew-recruit').innerHTML}</div>`;
 }else if(kind==='growth'){
  const p=E.levelProgress(s);h=`<div class="estate-level-card"><div class="estate-level-top"><span>当前庄园等级</span><strong data-growth-level>Lv.${p.level} · ${p.title}</strong></div><div class="progress-track"><i data-growth-bar style="width:${p.progress*100}%"></i></div><p data-growth-label>${p.next?`声望 ${p.xp} / ${p.nextXp} · 距离下一级还差 ${p.remaining}`:`声望 ${p.xp} · 已达到当前最高等级`}</p></div><p class="drawer-intro">声望会在正常经营中自动积累，不需要额外打卡或领取。收获、加工、建造、扩地、招募和完成订单都会让庄园成长。</p>`;
  h+='<div class="milestone-list">'+E.LEVELS.slice(1).map(v=>{const unlocked=p.level>=v.level,active=p.level+1===v.level;let unlock=v.unlock?`解锁${E.BUILDINGS[v.unlock].name}`:v.capacity?`仓库容量 +${v.capacity}`:'庄园发展奖励';if(v.level===3)unlock+='，米食配方（米粉、米糕）';const status=unlocked?'已解锁':active?`还差 ${Math.max(0,v.xp-p.xp)} 声望`:`需要 Lv.${v.level-1}`;return `<div class="milestone-row ${unlocked?'done':active?'current':''}"><b>Lv.${v.level}</b><div><strong>${v.title}</strong><small>${unlock} · 升级奖励 ${v.reward} 金币</small></div><span data-level-status="${v.level}">${status}</span></div>`;}).join('')+'</div>';
 }else if(kind==='build'){
  h='<p class="drawer-intro">选建筑，再点空草地摆下。都是 1 格占地；加工建筑原料够就自动开工，不用重复点生产。庄园成长会逐步解锁新工坊。</p>';
  for(const k of ['kitchen','well','mill','bakery','cows','store']){const b=E.BUILDINGS[k],locked=!E.canBuild(s,k),costLabel=locked?`庄园 Lv.${b.unlockLevel||1} 解锁`:`${b.cost} 金币`;h+=`<div class="build-item ${locked?'locked':''}"><div class="building-thumb">${art(k,'card')}</div><div class="info"><h3>${b.name}</h3><p>${b.desc}</p></div><button class="button small" data-build="${k}" ${locked||s.gold<b.cost?'disabled':''}>${costLabel}</button></div>`;}
  h+='<div class="drawer-section"><h3>不小心放错了？</h3><p>点建筑，再点「免费搬家」。建筑进度保留；水井搬动不能让已有稻田断水。</p></div>';
 }else if(kind==='inventory'){
  h=`<p class="drawer-intro">当前 <b data-live="storage">${E.total(s)} / ${E.capacity(s)}</b>。售货只卖超过保留量的余粮，大白饭默认保留 30 碗，足够一次招募。</p>`;
  for(const[k,item]of Object.entries(E.ITEMS))h+=`<div class="inventory-row">${icon(k)}<div class="info"><strong>${item.name}</strong><small data-reserve="${k}">保留 ${E.reserve(s,k)} · 单价 ${item.price} 金币</small></div><b data-stock="${k}">${s.inventory[k]}</b></div>`;
  h+=`<div class="drawer-actions"><button class="button primary wide" data-action="sell-surplus">只卖余粮，不动保留量</button>${storageButtonHTML('扩容 100 格')}</div><p class="drawer-intro">满仓时，作物留在田里，做好的整批产品留在工坊里。不会少收，也不会丢掉。</p>`;
 }else if(kind==='workshops'){
  h='<p class="drawer-intro">一间工坊一次做一批，做完自动接下一批。无需生产队列，也不用给工人分配岗位。</p>';let n=0;
  if(E.farmLevel(s)>=3)h+='<div class="drawer-section recipe-guide"><h3>同一间工坊，两种路线</h3><p>小麦 → 面粉 → 面包；水稻 → 米粉 → 米糕。磨坊选面粉或米粉，面包房选对应的面包或米糕。切换只影响下一批，当前这一批不会浪费。</p><p>水稻也会送去小灶台蒸饭；你可以自由搭配，选好后自动继续。</p><button class="text-button" data-open="orders">看看现有订单</button></div>';
  s.tiles.forEach((t,i)=>{if(t?.type!=='building'||!E.BUILDINGS[t.kind].recipe)return;n++;const pick=E.recipesFor(t.kind).length>1;h+=`<div class="drawer-section"><h3>${E.BUILDINGS[t.kind].name} <span class="dim">· ${E.coord(i).map(v=>v+1).join(', ')}</span></h3>${pick?recipePanel(t,i):`<p data-machine="${i}">${machineStatus(t)}</p>`}<p>${E.BUILDINGS[t.kind].desc}</p><button class="text-button" data-toggle-machine="${i}">${machineToggleLabel(t)}</button></div>`;});
  if(!n)h+='<div class="drawer-section"><h3>先架起小灶台</h3><p>水稻收进仓库后，就会自己变成大白饭。</p></div><button class="button primary wide" data-open="build">去建造</button>';
 }else if(kind==='orders'){
  h='<p class="drawer-intro">订单不是日常任务，不接也没有损失。接下以后，会留足指定物资，凑齐自动交付；大白饭订单等四位工人到齐才出现。</p>';
  if(s.activeOrder){const o=s.activeOrder;h+=`<div class="order-card"><h3>${E.ITEMS[o.item].name} ×${o.qty}<span>+${o.pay} 金币</span></h3><p data-live="order">${s.inventory[o.item]} / ${o.qty} · 正在准备，凑齐自动交付</p><button class="button small" data-action="cancel-order">取消，不扣款</button></div>`;}
  else E.availableOrders(s).forEach((o,i)=>{h+=`<div class="order-card"><h3>${E.ITEMS[o.item].name} ×${o.qty}<span>+${o.pay} 金币</span></h3><p data-offer-stock="${o.item}">仓库已有 ${s.inventory[o.item]} 份</p><button class="button wide" data-order="${i}" data-order-item="${o.item}" data-order-qty="${o.qty}" data-order-pay="${o.pay}">接下，剩下的交给农场</button></div>`;});
 }else if(kind==='field'&&t?.type==='field'){
  h=`<p class="drawer-intro" data-field-live="${ui.tile}">${fieldText(t)}</p><div class="drawer-section"><h3>${t.retire?'这轮收完就腾空':'下一轮种什么？'}</h3><p>改计划不会铲掉这一轮。收获后，工人会按这里的选择继续种。</p></div><div class="field-choices">${Object.entries(E.CROPS).map(([k,c])=>`<button class="crop-chip ${t.plan===k?'active':''}" data-plan="${k}">${icon(k)}<span>${c.name}</span></button>`).join('')}</div><p class="drawer-intro" style="margin-top:20px">${E.irrigated(s,...E.coord(ui.tile))?'有水井灌溉：生长快 10%，可以种水稻。':'没有水井灌溉：普通作物照常生长，水稻需要水井。'}</p><button class="button wide" data-action="reclaim-field" ${t.retire?'disabled':''}>${t.retire?'已安排收完后腾空':'这轮收完后腾出空地'}</button>`;
 }else if(kind==='field'){
  $('drawer-title').textContent='这片空地';h='<div class="drawer-section"><h3>这轮已收完，空地腾好了。</h3><p>收成已经按原来的规则入库或出售。现在可以重新选作物，或放一座建筑。</p><button class="button wide" data-action="close-drawer">回到地图</button></div>';
 }else if(kind==='building'&&t?.type==='building'){
  const b=E.BUILDINGS[t.kind];h=`<div class="building-thumb" style="width:100px;height:100px;margin:0 auto 20px">${art(t.kind,'card')}</div><p class="drawer-intro">${b.desc}</p>`;
  if(b.recipe)h+=`<div class="drawer-section"><h3>本批与下一批</h3><p>每间工坊只占一个生产位。原料消耗一次，产物只结算一次；切换只影响下一批。</p>${E.recipesFor(t.kind).length>1?recipePanel(t,ui.tile):`<p data-machine="${ui.tile}">${machineStatus(t)}</p>`}<button class="text-button" data-toggle-machine="${ui.tile}">${machineToggleLabel(t)}</button></div>`;
  if(t.kind==='store')h+=storageButtonHTML('仓库扩容 100 格');
  if(t.kind==='house')h+=`<div class="drawer-section"><h3 data-tools-level>农具等级 ${s.toolLevel+1} / 4</h3><p>每位工人每 4 秒最多照料 ${2**(s.toolLevel+1)} 块田。农具升级后，四位帮手也能照看更大的庄园。</p><div style="margin-top:10px">${toolsButtonHTML()}</div></div>`;
  h+='<div class="drawer-actions"><button class="button wide" data-action="move-building">免费搬家</button></div>';
 }else if(kind==='settings'){
  h='<p class="drawer-intro">本地单机，不需要账号。关闭页面后最多结算 8 小时；没有工人时，只推进已经在生长和加工的内容。</p>';
  h+=`<div class="drawer-section save-detail"><h3>存档与备份</h3><p data-save-detail>${saveStatusDetail()}</p><p>存档只保存在当前浏览器，不会上传。换浏览器、移动 HTML 文件或清理浏览器前，请先导出下方的 JSON 备份。</p></div>`;
  h+=`<div class="settings-row"><div><strong>自动批发</strong><small>按单品起售量自动批发；已开店商品额外保留 2 份零售机会。</small></div><button class="toggle" data-action="toggle-sale" aria-label="自动售货" aria-pressed="${s.options.autoSell}"><i></i></button></div><div class="settings-row"><div><strong>减少动态</strong><small>小人、头像和作物过渡都静下来，生产照常。</small></div><button class="toggle" data-action="toggle-motion" aria-label="减少动态" aria-pressed="${s.options.reducedMotion}"><i></i></button></div>`;
  h+=`<div class="drawer-section"><h3 data-tools-level>农具等级 ${s.toolLevel+1} / 4</h3><p>每位工人每轮照料 ${2**(s.toolLevel+1)} 块田。招工或升级农具都能提高照料能力。</p><div style="margin-top:10px">${toolsButtonHTML()}</div></div>`;
  h+='<div class="drawer-actions"><button class="button" data-action="export-save">导出存档</button><button class="button" data-action="import-save">导入存档</button><button class="button" data-action="import-old">尝试复制同一浏览器的旧版存档</button></div><p class="drawer-intro">换浏览器、移动 HTML 文件或清理浏览器前，先导出一份。不同文件路径可能不会共享存档。</p>';
  h+=ui.confirmReset?'<div class="drawer-section"><h3>要重新开一座农场吗？</h3><p>当前进度会先在本浏览器内备份，然后重开；仍建议先导出文件。</p><button class="button danger wide" style="margin-top:10px" data-action="confirm-reset">确认重开</button></div>':'<button class="text-button" data-action="request-reset">重新开一座农场…</button>';
 }else if(kind==='help'){
  h='<div class="help-step"><b>1</b><div><strong>选作物，点空地。</strong><p>新开田花 12 金币。成熟田点一下，收好并按原计划补种。也可以用「收好再种」一次处理全部田地。</p></div></div><div class="help-step"><b>2</b><div><strong>建工坊，然后不用管。</strong><p>有原料就自动开工，余粮自动出售。水井旁种水稻，灶台蒸大白饭；饭会留下，不会被卖光。</p></div></div><div class="help-step"><b>3</b><div><strong>用饭招来大肥鱼。</strong><p>最多四位，招来就照料田地，不用选职业。饭只扣一次，后面不饿肚子、不罢工。</p></div></div><div class="drawer-section"><h3>经营还由你决定</h3><p>种什么、在哪里种、先建哪条加工链、先扩地还是招人。省掉的是重复点击，不是这些选择。</p></div><div class="drawer-section"><h3>关于这一版</h3><p>这是 0.6 米食加工版，沿用轻操作玩法。作物状态使用两张图片同步交叉叠化；四位工人的地图形象加大。庄园声望会随着正常经营自动累积，逐步解锁磨坊、面包房和牛棚，并提供金币与仓库容量奖励。Lv.3 后可在磨坊、面包房选择米粉、米糕；切换只影响下一批。随时可以离开，回来接着种；记得在更换浏览器前导出存档。</p></div>';
 }
 ui.drawerKey=drawerStructureKey();$('drawer-content').innerHTML=h;hydrate($('drawer'));updateDrawerLive();
 if(focusKey){const next=Array.from($('drawer-content').querySelectorAll('button')).find(el=>!el.disabled&&drawerControlKey(el)===focusKey);(next||$('drawer').querySelector('[data-action="close-drawer"]')).focus({preventScroll:true});}
}
function updateDrawerLive(){
 if(!ui.drawer)return;
 if(ui.drawerKey!==drawerStructureKey()){renderDrawer();return;}
 const drawer=$('drawer');
 if(ui.drawer==='overview'){
  const g=goal();drawer.querySelectorAll('[data-overview-goal]').forEach(e=>e.textContent=g[e.dataset.overviewGoal]);
  drawer.querySelectorAll('[data-overview-goal-action]').forEach(e=>{e.textContent=g.button;e.dataset.action=g.action;e.disabled=!!g.disabled;});
  const crew=drawer.querySelector('[data-overview-crew]');if(crew&&crew.innerHTML!==$('crew-body').innerHTML)crew.innerHTML=$('crew-body').innerHTML;
 }
 document.querySelectorAll('[data-stock]').forEach(e=>e.textContent=s.inventory[e.dataset.stock]);
 const storage=storageUpgrade();
 drawer.querySelectorAll('[data-storage-upgrade]').forEach(e=>{e.disabled=storage.disabled;e.textContent=`${e.dataset.storagePrefix||'扩容 100 格'} · ${storage.cost} 金币`;});
 const tools=toolsUpgrade();
 drawer.querySelectorAll('[data-tools-upgrade]').forEach(e=>{e.disabled=tools.disabled;e.textContent=tools.label;});
 drawer.querySelectorAll('[data-tools-reason]').forEach(e=>{e.textContent=tools.reason;e.hidden=!tools.reason;});
 drawer.querySelectorAll('[data-tools-level]').forEach(e=>e.textContent=`农具等级 ${s.toolLevel+1} / 4`);
 const offer=recruitOffer();
 drawer.querySelectorAll('[data-recruit-title]').forEach(e=>e.textContent=`招来吃白饭的 · ${offer.n} / 4`);
 if(offer.r){
  drawer.querySelectorAll('[data-recruit-gold]').forEach(e=>{e.textContent=`${offer.r.gold} 金币`;e.classList.toggle('cost-ok',s.gold>=offer.r.gold);});
  drawer.querySelectorAll('[data-recruit-meal]').forEach(e=>{e.textContent=`${offer.r.meal} 碗大白饭`;e.classList.toggle('cost-ok',s.inventory.meal>=offer.r.meal);});
  drawer.querySelectorAll('[data-recruit-button]').forEach(e=>{e.disabled=offer.disabled;e.classList.toggle('soft',offer.disabled);e.classList.toggle('primary',!offer.disabled);const label=offer.n?'再招一只':'招来吃白饭的';if(e.textContent!==label)e.textContent=label;});
 }else drawer.querySelectorAll('[data-recruit-button]').forEach(e=>{e.disabled=true;e.textContent='四位都到齐了';});
 drawer.querySelectorAll('[data-toggle-machine]').forEach(e=>{const t=s.tiles[+e.dataset.toggleMachine];if(t)e.textContent=machineToggleLabel(t);});
 drawer.querySelectorAll('[data-reserve]').forEach(e=>{const k=e.dataset.reserve,item=E.ITEMS[k];if(item)e.textContent=`保留 ${E.reserve(s,k)} · 单价 ${item.price} 金币`;});
 document.querySelectorAll('[data-machine]').forEach(e=>{const t=s.tiles[+e.dataset.machine];if(t)e.textContent=machineStatus(t);});
 document.querySelectorAll('[data-recipe-status]').forEach(e=>{const t=s.tiles[+e.dataset.recipeStatus];if(t)e.textContent=machineStatus(t);});
 document.querySelectorAll('[data-recipe-input]').forEach(e=>{const t=s.tiles[+e.dataset.recipeInput];if(t)e.textContent=recipeInputText(t,E.recipeFor(t));});
 document.querySelectorAll('[data-recipe]').forEach(el=>{const t=s.tiles[+el.dataset.recipe],item=el.dataset.recipeItem;if(!t||!E.RECIPES[item])return;const r=E.RECIPES[item],unlocked=E.canUseRecipe(s,t.kind,item),active=E.recipeFor(t)===item;el.disabled=!unlocked;el.classList.toggle('active',active);el.setAttribute('aria-pressed',active?'true':'false');const small=el.querySelector('small');if(small){const meta=unlocked?`${E.ITEMS[r.input].name} ×${r.amount} → ${r.qty} 份 · ${r.time/1000} 秒`:`Lv.${r.unlockLevel||1} 解锁`;if(small.textContent!==meta)small.textContent=meta;}});
 document.querySelectorAll('[data-field-live]').forEach(e=>{const t=s.tiles[+e.dataset.fieldLive];if(t)e.textContent=fieldText(t);});
 document.querySelectorAll('[data-live="storage"]').forEach(e=>e.textContent=`${E.total(s)} / ${E.capacity(s)}`);
 drawer.querySelectorAll('[data-offer-stock]').forEach(e=>e.textContent=`仓库已有 ${s.inventory[e.dataset.offerStock]} 份`);
 document.querySelectorAll('[data-live="order"]').forEach(e=>{if(s.activeOrder)e.textContent=`${s.inventory[s.activeOrder.item]} / ${s.activeOrder.qty} · 凑齐自动交付`;else e.textContent='已经自动交付，金币已到账。';});
 if(ui.drawer==='build')document.querySelectorAll('[data-build]').forEach(el=>{const b=E.BUILDINGS[el.dataset.build],locked=!E.canBuild(s,el.dataset.build);el.disabled=locked||s.gold<b.cost;el.textContent=locked?`庄园 Lv.${b.unlockLevel||1} 解锁`:`${b.cost} 金币`;el.closest('.build-item')?.classList.toggle('locked',locked);});
 if(ui.drawer==='growth'){const p=E.levelProgress(s);document.querySelectorAll('[data-growth-level]').forEach(el=>el.textContent=`Lv.${p.level} · ${p.title}`);document.querySelectorAll('[data-growth-bar]').forEach(el=>el.style.width=(p.progress*100)+'%');document.querySelectorAll('[data-growth-label]').forEach(el=>el.textContent=p.next?`声望 ${p.xp} / ${p.nextXp} · 距离下一级还差 ${p.remaining}`:`声望 ${p.xp} · 已达到当前最高等级`);document.querySelectorAll('[data-level-status]').forEach(el=>{const level=+el.dataset.levelStatus,row=E.LEVELS[level-1],unlocked=p.level>=level,active=p.level+1===level;el.textContent=unlocked?'已解锁':active?`还差 ${Math.max(0,row.xp-p.xp)} 声望`:`需要 Lv.${level-1}`;el.closest('.milestone-row')?.classList.toggle('done',unlocked);el.closest('.milestone-row')?.classList.toggle('current',!unlocked&&active);});}
}
function actTile(i){
 const t=s.tiles[i];
 if(ui.mode==='build'){const r=apply(()=>E.build(s,i,ui.building));if(r.ok){ui.mode=null;render();}return;}
 if(ui.mode==='move'){const r=apply(()=>E.move(s,ui.moveFrom,i));if(r.ok){ui.mode=null;render();}return;}
 if(ui.mode==='expand'){const [x,y]=E.coord(i);const r=apply(()=>E.expand(s,Math.floor(x/2)*2,Math.floor(y/2)*2));if(r.ok){ui.mode=null;render();mapView.revealTile(i);}return;}
 if(t?.type==='building'){openDrawer('building',i);return;}
 if(t?.type==='field'&&t.crop&&!E.ripe(s,t)){openDrawer('field',i);return;}
 apply(()=>E.tend(s,i,ui.crop));
}
function action(a){
 if(a==='open-commercial'){ui.view='street';ui.mode=null;closeDrawer();render();$('farm-toggle').focus({preventScroll:true});tell('已进入商业街。街景只作演示，经营结算照常进行。');return;}
 if(a==='open-farm'){ui.view='farm';render();$('commercial-toggle').focus({preventScroll:true});tell('已返回农场，商业街经营会继续按同一逻辑时钟结算。');return;}
 if(a==='tend-all')return apply(()=>E.tendAll(s));
 if(a==='recruit')return apply(()=>E.recruit(s));
 if(a==='toggle-sale')return apply(()=>E.toggleSale(s));
 if(a==='upgrade-storage')return apply(()=>E.upgradeStorage(s));
 if(a==='upgrade-tools')return apply(()=>E.upgradeTools(s));
 if(a==='sell-surplus')return apply(()=>({ok:true,message:`卖出余粮，收入 ${E.sellSurplus(s,true)} 金币。保留的物资没有动。`}));
 if(a==='reclaim-field')return apply(()=>E.reclaim(s,ui.tile));
 if(a==='cancel-order')return apply(()=>E.cancelOrder(s));
 if(a==='expand-mode'){if(ui.mode==='expand')cancelPlacement();else{ui.mode='expand';tell('点高亮的相邻土地，一次买 4 格。');}closeDrawer();render();return;}
 if(a==='cancel-mode'){cancelPlacement();render();return;}
 if(a==='close-drawer'){closeDrawer();return;}
 if(a==='quick-kitchen'){prepareBuild('kitchen');return;}
 if(a==='quick-mill'){prepareBuild('mill');return;}
 if(a==='quick-bakery'){prepareBuild('bakery');return;}
 if(a==='choose-rice'){ui.crop='rice';cancelPlacement();closeDrawer();render();$('garden').scrollIntoView({block:'nearest'});$('crop-options').querySelector('[data-crop="rice"]')?.focus({preventScroll:true});tell('水井旁带浅蓝标记的空地，可以种水稻。');return;}
 if(a==='open-inventory'){openDrawer('inventory');return;}
 if(a==='open-growth'){openDrawer('growth');return;}
 if(a==='move-building'){ui.moveFrom=ui.tile;ui.building=s.tiles[ui.moveFrom].kind;ui.mode='move';closeDrawer();tell(`点空草地搬入${E.BUILDINGS[ui.building].name}，免费${ui.building==='well'?'；仍须保证稻田有水':'并保留生产进度'}。`);render();return;}
 if(a==='toggle-motion')return apply(()=>{s.options.reducedMotion=!s.options.reducedMotion;return {ok:true,message:s.options.reducedMotion?'已减少地图与头像动态，生产照常。':'已恢复地图与头像动画。'};});
 if(a==='export-save'){tickTime();save();const blob=new Blob([JSON.stringify(s,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='大白饭庄园-存档-'+new Date().toISOString().slice(0,10)+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);tell('已发起存档下载，请保管好 JSON 文件。');return;}
 if(a==='import-save'){$('import-input').click();return;}
 if(a==='import-old'){
  try{const source=[PREV_KEY,OLD_KEY].find(k=>Store.getItem(k)),old=source?Store.getItem(source):null;if(!old){tell('这个文件路径下没有找到旧存档；旧版农场没有被更改。',true);return;}const imported=E.restore(JSON.parse(old));backupCurrent();s=imported;lastWall=Date.now();E.advance(s,Math.min(E.OFFLINE_CAP,Math.max(0,lastWall-s.savedAt)));ui.mode=null;ui.lastCrewKey='';save();render();renderDrawer();tell(`旧版存档已复制，原存档没有改动。自动售货${s.options.autoSell?'已开启':'已暂停'}。`);}catch(e){tell('没有成功导入：'+e.message,true);}return;
 }
 if(a==='request-reset'){ui.confirmReset=true;renderDrawer();return;}
 if(a==='confirm-reset'){backupCurrent();s=E.initial();lastWall=Date.now();ui.mode=null;ui.lastCrewKey='';closeDrawer();save();render();tell('新农场准备好了。上一份进度已尽力备份在本浏览器内。');return;}
}
function backupCurrent(){try{Store.setItem(KEY+'-backup',JSON.stringify(s));return true;}catch(e){return false;}}
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b||b.disabled)return;
 if(b.dataset.streetAction){const kind=b.dataset.streetAction,shop=b.dataset.shop,item=b.dataset.item,qty=Number(b.dataset.qty),price=Number(b.dataset.price);
  if(kind==='wholesale'){apply(()=>E.wholesale(s,item,undefined,{item,qty,unitPrice:price}));return;}
  if(kind==='retail'){apply(()=>E.listRetail(s,shop,item,qty,{item,qty,unitPrice:price}));return;}
  if(kind==='return'){apply(()=>E.returnRetail(s,shop));return;}
 }
 if(b.dataset.tile!==undefined){actTile(+b.dataset.tile);return;}
 if(b.dataset.open){openDrawer(b.dataset.open);return;}
 if(b.dataset.crop){ui.crop=b.dataset.crop;cancelPlacement();render();$('crop-options').querySelector(`[data-crop="${ui.crop}"]`)?.focus({preventScroll:true});return;}
 if(b.dataset.build){prepareBuild(b.dataset.build);return;}
 if(b.dataset.plan){apply(()=>E.changePlan(s,ui.tile,b.dataset.plan));return;}
 if(b.dataset.recipe!==undefined){const i=+b.dataset.recipe,item=b.dataset.recipeItem;apply(()=>E.changeRecipe(s,i,item));const next=$('drawer').querySelector(`[data-recipe="${i}"][data-recipe-item="${item}"]`);if(next)next.focus();return;}
 if(b.dataset.toggleMachine!==undefined){apply(()=>E.toggleMachine(s,+b.dataset.toggleMachine));return;}
 if(b.dataset.order!==undefined){const quote={item:b.dataset.orderItem,qty:Number(b.dataset.orderQty),pay:Number(b.dataset.orderPay)};apply(()=>E.acceptOrder(s,+b.dataset.order,quote));return;}
 if(b.dataset.action)action(b.dataset.action);
});
$('drawer-backdrop').addEventListener('click',closeDrawer);
document.addEventListener('keydown',e=>{
 if(e.target.classList?.contains('tile')&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){
  const i=+e.target.dataset.tile,[x,y]=E.coord(i),nx=x+(e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0),ny=y+(e.key==='ArrowDown'?1:e.key==='ArrowUp'?-1:0);
  if(nx>=0&&ny>=0&&nx<ui.cols&&ny<ui.cols){const next=$('board').querySelector(`[data-tile="${E.idx(nx,ny)}"]`);if(next){e.preventDefault();next.focus({preventScroll:true});mapView.revealTile(E.idx(nx,ny));}}
  return;
 }
 if(e.key==='Escape'){if(ui.drawer)closeDrawer();else if(ui.mode){cancelPlacement();render();}}
 if(e.key==='Tab'&&ui.drawer){const els=Array.from($('drawer').querySelectorAll('button:not(:disabled),a[href],input:not([hidden])')).filter(el=>el.offsetParent!==null);if(!els.length)return;const first=els[0],last=els.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}
});
$('import-input').addEventListener('change',async e=>{
 const file=e.target.files?.[0];e.target.value='';if(!file)return;if(file.size>2*1024*1024){tell('存档超过 2 MB，未导入。',true);return;}
 try{const candidate=E.restore(JSON.parse(await file.text()));backupCurrent();s=candidate;lastWall=Date.now();E.advance(s,Math.min(E.OFFLINE_CAP,Math.max(0,lastWall-s.savedAt)));ui.mode=null;ui.lastCrewKey='';save();render();renderDrawer();tell('存档已导入，原进度已尽力在本地备份。');}catch(err){tell('导入失败，当前农场没有改变：'+err.message,true);}
});
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(renderBoard,100);});
window.addEventListener('pagehide',()=>{tickTime();save();mapView.dispose();actors.dispose();tiles.dispose();});
document.addEventListener('visibilitychange',()=>{tickTime();save();if(!document.hidden)render();else renderCrew();});
if(window.FARM_EMBEDDED)document.body.classList.add('embedded');
buildArt();hydrate();render();save();if(bootMessage)tell(bootMessage);else if(storageError)tell(storageError,true);
setInterval(()=>{if(document.hidden)return;tickTime();render();if(Date.now()-lastSave>=5000)save();},1000);
window.FarmFlush=()=>{tickTime();save();};
if(window.FARM_TEST_MODE)window.FarmTest={tiles:()=>tiles.snapshot(),assetsReady:()=>tiles.ready(),actors:()=>actors.snapshot(),getState:()=>E.clone(s),setState:v=>{s=E.restore(v);lastWall=Date.now();ui.lastCrewKey='';render();},advance:ms=>{E.advance(s,ms);lastWall=Date.now();render();},save,render,open:openDrawer};
})();
