/* Stable two-layer crop cross-dissolve painter.
 * Both crop states stay visible during the blend: outgoing 1 -> 0 and
 * incoming 0 -> 1 on the same linear timeline. New requests are queued while
 * a blend is running, avoiding mid-transition snaps and third image layers.
 */
(function(root){
'use strict';
const DURATION=420;
root.FarmCropStage=function(progress,ready){return ready?3:progress<.20?0:progress<.60?1:2;};
root.createFarmTiles=function({assets,reducedMotion}){
 const records=new Map(),decoded=new Map();let disposed=false;const failed=new Set();
 const urls={...(assets.tiles||{}),...(assets.buildings||{})};
 function load(key){
  if(decoded.has(key))return decoded.get(key);
  const src=urls[key];
  const p=new Promise(resolve=>{
   if(!src){failed.add(key);resolve(false);return;}
   const img=new Image();img.onload=()=>resolve(true);img.onerror=()=>{failed.add(key);resolve(false);};img.src=src;
   if(img.complete&&img.naturalWidth)resolve(true);
  });decoded.set(key,p);return p;
 }
 Object.keys(urls).forEach(load);
 function stopped(){return disposed||document.hidden||root.FARM_SUSPENDED||reducedMotion()||matchMedia('(prefers-reduced-motion: reduce)').matches;}
 function cancel(r){if(r.frame)cancelAnimationFrame(r.frame);r.frame=0;if(r.timer)clearTimeout(r.timer);r.timer=0;}
 function commit(r,key){
  cancel(r);r.seq++;r.layers.forEach((img,j)=>{img.style.transition='none';img.style.opacity=j===r.front?'1':'0';});
  const img=r.layers[r.front];if(key&&urls[key]){img.src=urls[key];img.dataset.art=key;}
  r.key=key||null;r.target=key||null;r.fromKey=null;r.toKey=null;r.queued=null;r.active=false;r.element.classList.remove('tile-transitioning');
 }
 function create(el){
  const surface=document.createElement('span');surface.className='tile-surface';surface.setAttribute('aria-hidden','true');
  const layers=[0,1].map(()=>{const img=document.createElement('img');img.className='tile-art handpainted tile-image';img.alt='';img.draggable=false;img.style.opacity='0';surface.append(img);return img;});
  const ready=document.createElement('span');ready.className='ready-dot';ready.textContent='✓';ready.hidden=true;ready.setAttribute('aria-hidden','true');
  const progress=document.createElement('span');progress.className='tile-progress';progress.hidden=true;progress.setAttribute('aria-hidden','true');const bar=document.createElement('i');progress.append(bar);
  const label=document.createElement('span');label.className='tile-label';label.setAttribute('aria-hidden','true');
  const plus=document.createElement('span');plus.className='chunk-plus';plus.textContent='+';plus.hidden=true;plus.setAttribute('aria-hidden','true');
  el.replaceChildren(surface,progress,ready,plus,label);
  const r={element:el,surface,layers,progress,bar,ready,label,plus,key:null,target:null,fromKey:null,toKey:null,queued:null,front:0,seq:0,frame:0,timer:0,active:false};records.set(el,r);return r;
 }
 function finish(r,seq){
  if(disposed||seq!==r.seq||!r.active)return;
  const completed=r.toKey,queued=r.queued;commit(r,completed);
  if(queued&&queued!==completed){r.target=queued;request(r);}
 }
 function begin(r,key,seq){
  const old=r.front,next=1-old,outgoing=r.layers[old],incoming=r.layers[next];
  incoming.style.transition='none';incoming.style.opacity='0';incoming.src=urls[key];incoming.dataset.art=key;
  outgoing.style.transition='none';outgoing.style.opacity='1';
  r.fromKey=r.key;r.toKey=key;r.key=key;r.front=next;r.active=true;r.element.classList.add('tile-transitioning');
  // Force a single layout read so both layers start at their exact endpoints.
  void incoming.offsetWidth;
  r.frame=requestAnimationFrame(()=>{
   r.frame=0;if(disposed||seq!==r.seq)return;
   if(stopped()){commit(r,key);return;}
   outgoing.style.transition=`opacity ${DURATION}ms linear`;
   incoming.style.transition=`opacity ${DURATION}ms linear`;
   // Reciprocal opacity ramps create a true cross-dissolve, not fade-out then fade-in.
   outgoing.style.opacity='0';incoming.style.opacity='1';
   r.timer=setTimeout(()=>finish(r,seq),DURATION+40);
  });
 }
 function request(r){
  if(disposed||!r.target)return;
  if(stopped()){commit(r,r.target);return;}
  if(r.active){r.queued=r.target===r.toKey?null:r.target;return;}
  const key=r.target;if(key===r.key)return;
  const seq=++r.seq;
  load(key).then(ok=>{
   if(!ok||disposed||seq!==r.seq||!r.element.isConnected)return;
   // If the requested art changed while decoding, discard this stale decode.
   if(r.target!==key){request(r);return;}
   if(key===r.key)return;
   if(!r.key){commit(r,key);return;}
   begin(r,key,seq);
  });
 }
 function paint(el,{art,canFade=false,ready=false,progress=null,building=false,label='',plus=false}){
  if(disposed)return;const r=records.get(el)||create(el);
  r.label.textContent=label;r.ready.hidden=!ready;r.plus.hidden=!plus;r.progress.hidden=progress===null;
  r.progress.classList.toggle('building-progress',building);
  if(progress!==null)r.bar.style.width=Math.max(0,Math.min(100,progress))+'%';
  if(!art){cancel(r);r.seq++;r.key=r.target=r.fromKey=r.toKey=r.queued=null;r.surface.hidden=true;r.active=false;r.element.classList.remove('tile-transitioning');return;}
  r.surface.hidden=false;
  if(art===r.target){if(r.active&&stopped())commit(r,art);return;}
  r.target=art;
  if(!canFade||!r.key||stopped()){commit(r,art);return;}
  request(r);
 }
 function settle(){for(const r of records.values())if(r.active||r.target!==r.key)commit(r,r.target||r.toKey||r.key);}
 function prune(){for(const [el,r]of records)if(!el.isConnected){cancel(r);r.seq++;records.delete(el);}}
 function visibility(){if(document.hidden)settle();}
 const mq=matchMedia('(prefers-reduced-motion: reduce)');const motion=()=>{if(mq.matches)settle();};
 document.addEventListener('visibilitychange',visibility);mq.addEventListener?.('change',motion);
 return {paint,prune,settle,ready:()=>Promise.all(Object.keys(urls).map(load)),
  snapshot:()=>({duration:DURATION,failed:[...failed],active:[...records.values()].filter(r=>r.active).length,tiles:[...records.values()].map(r=>({index:+r.element.dataset.tile,key:r.key,target:r.target,active:r.active,queued:r.queued,layers:r.layers.map(i=>({key:i.dataset.art||null,opacity:getComputedStyle(i).opacity,loaded:!!i.naturalWidth}))}))}),
  dispose(){disposed=true;for(const r of records.values()){cancel(r);r.seq++;}records.clear();document.removeEventListener('visibilitychange',visibility);mq.removeEventListener?.('change',motion);}
 };
};
})(window);
