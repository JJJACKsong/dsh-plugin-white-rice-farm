/* Cosmetic actors only: economic outcomes are owned by engine.js, never by GIF frames. */
(function(root){
'use strict';
const STATES=['idle','walk','work','harvest','carry'];
root.createFarmActors=function({layer,board,getState,assets}){
 const actors=new Map(),motion=matchMedia('(prefers-reduced-motion: reduce)');let timer=0,disposed=false,lastSize=60;
 const canAnimate=s=>!disposed&&!document.hidden&&!root.FARM_SUSPENDED&&!s.options.reducedMotion&&!motion.matches&&s.workers.length>0;
 const position=i=>{const b=board.querySelector(`[data-tile="${i}"]`);return b?{x:b.offsetLeft+b.offsetWidth/2,y:b.offsetTop+b.offsetHeight*.79}:null;};
 function route(start,end,s){
  if(start===end)return [start];const q=[start],previous=new Map([[start,null]]);
  for(let at=0;at<q.length;at++){const i=q[at],x=i%16,y=Math.floor(i/16);
   for(const [xx,yy] of [[x+1,y],[x-1,y],[x,y+1],[x,y-1]]){if(xx<0||yy<0||xx>15||yy>15)continue;const j=yy*16+xx,t=s.tiles[j];if(!t||previous.has(j)||(t.type==='building'&&j!==end))continue;previous.set(j,i);q.push(j);if(j===end){const p=[j];let c=i;while(c!==null){p.unshift(c);c=previous.get(c);}return p;}}
  }
  // Enclosed fields still work: absence of a visual route never stops the simulation.
  return [end];
 }
 function home(s,id){const house=s.tiles.findIndex(t=>t?.kind==='house');const candidates=s.tiles.map((t,i)=>t&&t.type!=='building'?i:null).filter(i=>i!==null).sort((a,b)=>Math.abs(a%16-house%16)+Math.abs(Math.floor(a/16)-Math.floor(house/16))-Math.abs(b%16-house%16)-Math.abs(Math.floor(b/16)-Math.floor(house/16))||a-b);return candidates[(id-1)%Math.max(1,candidates.length)]??house;}
 function pose(a,state,staticOnly){const src=assets[staticOnly?state+'Poster':state]||assets.idlePoster;if(a.src!==src){a.img.src=src;a.src=src;}a.el.dataset.state=state;}
 function pointAlong(path,p){if(path.length===1)return position(path[0]);const f=Math.max(0,Math.min(.999999,p))*(path.length-1),k=Math.floor(f),u=f-k,a=position(path[k]),b=position(path[k+1]);return a&&b?{x:a.x+(b.x-a.x)*u,y:a.y+(b.y-a.y)*u}:a||b;}
 function update(){
  if(disposed)return;const s=getState();const hidden=document.hidden||root.FARM_SUSPENDED;
  const still=s.options.reducedMotion||motion.matches||hidden;
  const now=performance.now();
  for(const w of s.workers){let a=actors.get(w.id);if(!a){const el=document.createElement('div'),img=document.createElement('img'),badge=document.createElement('b');el.className='farm-actor';el.setAttribute('aria-hidden','true');img.alt='';img.draggable=false;badge.textContent=w.id;el.append(img,badge);layer.append(el);a={el,img,src:'',key:null,at:home(s,w.id),start:0,path:[],phase:'idle'};actors.set(w.id,a);}
   const key=w.status==='working'&&w.target!==null?w.lastAt+':'+w.target:null;
   if(key!==null&&key!==a.key){a.key=key;a.path=route(a.at,w.target,s);a.start=now;a.phase='walk';a.target=w.target;}
   let pt,state='idle',flip=false;const age=now-a.start;
   if(a.phase!=='idle'&&age<850){state='walk';pt=pointAlong(a.path,age/850);if(a.path.length>1)flip=(a.path.at(-1)%16)<(a.path[0]%16);}
   else if(a.phase!=='idle'&&age<1700){state='work';pt=position(a.target);}
   else if(a.phase!=='idle'&&age<2350){state='harvest';pt=position(a.target);}
   else if(a.phase!=='idle'&&age<3250){state='carry';pt=position(a.target);}
   else{if(a.phase!=='idle'){a.at=a.target;a.phase='idle';}pt=position(a.at)||position(home(s,w.id));}
   if(still){state='idle';pt=position(w.target??home(s,w.id));}
   pose(a,state,still);a.el.hidden=hidden;
   if(pt){a.el.style.left=pt.x+'px';a.el.style.top=pt.y+'px';a.el.style.zIndex=String(10+Math.floor(pt.y));}
   a.img.style.transform=flip?'scaleX(-1)':'';const actorSize=Math.max(8,Math.min(88,lastSize*.98));a.el.style.width=actorSize+'px';a.el.style.setProperty('--actor-badge-size',Math.max(7,Math.min(15,actorSize*.22))+'px');
  }
  for(const [id,a] of actors)if(!s.workers.some(w=>w.id===id)){a.el.remove();actors.delete(id);}
 }
 function scheduling(){clearInterval(timer);timer=0;if(disposed)return;update();if(canAnimate(getState()))timer=setInterval(update,120);}
 const visibility=()=>scheduling();document.addEventListener('visibilitychange',visibility);
 motion.addEventListener?.('change',scheduling);
 return {sync(size){if(disposed)return;lastSize=size||lastSize;const s=getState();layer.style.width=board.offsetWidth+'px';layer.style.height=board.offsetHeight+'px';update();const active=canAnimate(s);if(active&&!timer)timer=setInterval(update,120);if(!active&&timer){clearInterval(timer);timer=0;}},dispose(){disposed=true;clearInterval(timer);timer=0;document.removeEventListener('visibilitychange',visibility);motion.removeEventListener?.('change',scheduling);for(const a of actors.values()){a.img.removeAttribute('src');a.el.remove();}actors.clear();},snapshot(){return Array.from(actors.values(),a=>({state:a.el.dataset.state,src:a.src,x:a.el.style.left,y:a.el.style.top}));}};
};
})(window);
