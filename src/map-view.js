/* Small map viewport helper: sizing, pan/zoom and overview-to-location only.
 * It never touches game rules or the save; all view state lives in this closure.
 */
(function(root){
'use strict';
const MIN_TILE=44,MAX_TILE=96,OVERVIEW_MIN=1,GAP=3,PAD=8,BORDER=2,THRESHOLD=8,MAX_TOUCH_ECHOES=32;
root.createFarmMapView=function({viewport,board,onChange=()=>{}}){
 const controls=Array.from(document.querySelectorAll('[data-map-action]'));
 const touchClicks=new Set();
 let extent=0,size=0,normalSize=0,normalScroll={left:0,top:0},overview=false,pointer=null,suppressClick=false,disposed=false;
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 function viewportBox(){
  const r=viewport.getBoundingClientRect();
  return {w:Math.max(1,viewport.clientWidth||r.width),h:Math.max(1,viewport.clientHeight||r.height)};
 }
 function fitSize(n){
  const {w,h}=viewportBox(),chrome=2*(PAD+BORDER);
  const byWidth=Math.floor((w-12-chrome-(n-1)*GAP)/n);
  const byHeight=Math.floor((h-12-chrome-(n-1)*GAP)/n);
  return clamp(Math.min(byWidth,byHeight),MIN_TILE,MAX_TILE);
 }
 function overviewSize(n){
  const {w,h}=viewportBox(),chrome=2*(PAD+BORDER);
  const byWidth=Math.floor((w-12-chrome-(n-1)*GAP)/n);
  const byHeight=Math.floor((h-12-chrome-(n-1)*GAP)/n);
  return clamp(Math.min(byWidth,byHeight),OVERVIEW_MIN,MIN_TILE);
 }
 function anchorIndex(){
  if(!extent)return 0;
  const br=board.getBoundingClientRect(),vr=viewport.getBoundingClientRect();
  const x=Math.floor((vr.left+vr.width/2-br.left-PAD-BORDER)/(size+GAP));
  const y=Math.floor((vr.top+vr.height/2-br.top-PAD-BORDER)/(size+GAP));
  return clamp(y,0,extent-1)*16+clamp(x,0,extent-1);
 }
 function centerTile(i){
  const el=board.querySelector(`[data-tile="${i}"]`);
  if(!el)return;
  const vr=viewport.getBoundingClientRect(),tr=el.getBoundingClientRect();
  viewport.scrollLeft+=(tr.left+tr.width/2)-(vr.left+vr.width/2);
  viewport.scrollTop+=(tr.top+tr.height/2)-(vr.top+vr.height/2);
 }
 function setSize(next,min=MIN_TILE){
  size=clamp(next,min,MAX_TILE);
  board.style.setProperty('--tile-size',size+'px');
 }
 function updateControls(){
  for(const b of controls){
   const a=b.dataset.mapAction;
   if(a==='zoom-out')b.disabled=overview||size<=MIN_TILE;
   else if(a==='zoom-in')b.disabled=overview||size>=MAX_TILE;
   else if(a==='fit'){
    b.setAttribute('aria-pressed',overview?'true':'false');
    b.title=overview?'返回正常视图':'查看全图并定位';
    b.setAttribute('aria-label',overview?'返回正常视图':'查看全图并定位');
   }
  }
 }
 function setOverview(want){
  if(disposed||want===overview)return;
  if(want){
   normalSize=size;normalScroll={left:viewport.scrollLeft,top:viewport.scrollTop};
   overview=true;setSize(overviewSize(extent),OVERVIEW_MIN);
   viewport.scrollLeft=0;viewport.scrollTop=0;
  }else{
   overview=false;setSize(normalSize||fitSize(extent));
   viewport.scrollLeft=normalScroll.left;viewport.scrollTop=normalScroll.top;
  }
  updateControls();onChange();
 }
 function zoom(direction){
  if(disposed||overview)return;
  const anchor=anchorIndex(),next=clamp(size+direction*12,MIN_TILE,MAX_TILE);
  if(next===size)return;
  normalSize=next;setSize(next);centerTile(anchor);updateControls();onChange();
 }
 function focusTile(i){
  if(disposed)return;
  if(overview){
   overview=false;setSize(normalSize||fitSize(extent));updateControls();onChange();
  }
  centerTile(i);
 }
 function revealTile(i){
  if(disposed||overview)return;
  const el=board.querySelector(`[data-tile="${i}"]`);
  if(!el)return;
  const vr=viewport.getBoundingClientRect(),tr=el.getBoundingClientRect(),margin=12;
  if(tr.left<vr.left+margin||tr.right>vr.right-margin||tr.top<vr.top+margin||tr.bottom>vr.bottom-margin)centerTile(i);
 }
 function endGesture(){
  const p=pointer;pointer=null;
  if(p&&viewport.hasPointerCapture?.(p.id)){try{viewport.releasePointerCapture(p.id);}catch(e){}}
  viewport.classList.remove('is-panning');
 }
 function cancelGesture(){
  if(pointer)suppressClick=true;
  endGesture();
 }
 function onPointerDown(e){
  // A second finger cancels the map gesture even when it lands on the toolbar
  // or elsewhere in this document. Do not prevent native pinch zoom.
  if(pointer){cancelGesture();return;}
  if(!viewport.contains(e.target)||e.target.closest('[data-map-action]'))return;
  if(!e.isPrimary||e.button!==0)return;
  suppressClick=false;
  pointer={id:e.pointerId,x:e.clientX,y:e.clientY,left:viewport.scrollLeft,top:viewport.scrollTop,dragging:false,tile:e.target.closest('[data-tile]')};
 }
 function onPointerMove(e){
  if(!pointer||pointer.id!==e.pointerId)return;
  if(pointer&&e.pointerType==='mouse'&&!(e.buttons&1)){cancelGesture();return;}
  const dx=e.clientX-pointer.x,dy=e.clientY-pointer.y;
  if(!pointer.dragging){
   if(dx*dx+dy*dy<=THRESHOLD*THRESHOLD)return;
   pointer.dragging=true;suppressClick=true;
   try{viewport.setPointerCapture(e.pointerId);}catch(err){}
   viewport.classList.add('is-panning');
  }
  e.preventDefault();
  viewport.scrollLeft=pointer.left-dx;
  viewport.scrollTop=pointer.top-dy;
 }
 function onPointerUp(e){
  if(!pointer||pointer.id!==e.pointerId)return;
  const dx=e.clientX-pointer.x,dy=e.clientY-pointer.y,moved=pointer.dragging||dx*dx+dy*dy>THRESHOLD*THRESHOLD;
  const touch=e.pointerType==='touch',pressed=pointer.tile;
  const hit=touch&&!moved?document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-tile]'):null;
  const tap=touch&&!moved&&pressed&&pressed===hit&&board.contains(pressed);
  if(moved){viewport.scrollLeft=pointer.left-dx;viewport.scrollTop=pointer.top-dy;suppressClick=true;}
  endGesture();
  // Touch compatibility clicks can be absent after panning, or arrive later.
  // Route a valid tap through the same button action, then suppress that echo.
  if(touch){
   touchClicks.add(e.pointerId);
   if(touchClicks.size>MAX_TOUCH_ECHOES)touchClicks.delete(touchClicks.values().next().value);
   if(tap){suppressClick=false;pressed.click();}
   suppressClick=true;
  }
 }
 function onPointerCancel(e){
  if(!pointer||pointer.id!==e.pointerId)return;
  cancelGesture();
 }
 function onLostCapture(e){
  if(pointer&&pointer.id===e.pointerId)cancelGesture();
 }
 function onPointerLeave(){if(pointer&&!pointer.dragging)cancelGesture();}
 function onTouchEcho(e){
  // Opening a drawer can retarget the native echo outside the map viewport.
  if(touchClicks.delete(e.pointerId)){e.preventDefault();e.stopPropagation();}
 }
 function onClick(e){
  if(disposed||!viewport.contains(e.target))return;
  if(suppressClick){
   const pointerClick=e.detail>0;
   suppressClick=false;
   if(pointerClick){e.preventDefault();e.stopPropagation();return;}
  }
  if(overview){
   const tile=e.target.closest('[data-tile]');
   if(tile){e.preventDefault();e.stopPropagation();focusTile(+tile.dataset.tile);}
  }
 }
 function onControl(e){
  const a=e.currentTarget.dataset.mapAction;
  if(a==='zoom-out')zoom(-1);
  else if(a==='zoom-in')zoom(1);
  else if(a==='fit')setOverview(!overview);
  e.preventDefault();
 }
 document.addEventListener('pointerdown',onPointerDown,true);
 window.addEventListener('pointermove',onPointerMove,{passive:false});
 window.addEventListener('pointerup',onPointerUp);
 window.addEventListener('pointercancel',onPointerCancel);
 viewport.addEventListener('lostpointercapture',onLostCapture);
 viewport.addEventListener('pointerleave',onPointerLeave);
 viewport.addEventListener('click',onClick,true);
 document.addEventListener('click',onTouchEcho,true);
 window.addEventListener('blur',cancelGesture);
 for(const b of controls)b.addEventListener('click',onControl);
 function onVisibility(){if(document.hidden)cancelGesture();}
 document.addEventListener('visibilitychange',onVisibility);
 return {
  sync(n,anchor){
   if(disposed)return;
   const first=!extent,changed=extent!==n,beforeSize=size,beforeOverview=overview;extent=n;
   if(first){setSize(fitSize(n));normalSize=size;}
   else if(overview){const next=overviewSize(n);if(next!==size)setSize(next,OVERVIEW_MIN);}
   else if(changed&&size<MIN_TILE){setSize(MIN_TILE);normalSize=size;}
   if(first){viewport.scrollLeft=0;viewport.scrollTop=0;}
   else if(anchor!==undefined&&anchor!==null)centerTile(anchor);
   updateControls();
   if(size!==beforeSize||overview!==beforeOverview)onChange();
  },
  anchor:anchorIndex,
  tileSize:()=>size,
  isOverview:()=>overview,
  focusTile,
  revealTile,
  dispose(){
   disposed=true;endGesture();touchClicks.clear();
   document.removeEventListener('pointerdown',onPointerDown,true);
   window.removeEventListener('pointermove',onPointerMove);
   window.removeEventListener('pointerup',onPointerUp);
   window.removeEventListener('pointercancel',onPointerCancel);
   viewport.removeEventListener('lostpointercapture',onLostCapture);
   viewport.removeEventListener('pointerleave',onPointerLeave);
   viewport.removeEventListener('click',onClick,true);
   document.removeEventListener('click',onTouchEcho,true);
   window.removeEventListener('blur',cancelGesture);
   document.removeEventListener('visibilitychange',onVisibility);
   for(const b of controls)b.removeEventListener('click',onControl);
  }
 };
};
})(window);
