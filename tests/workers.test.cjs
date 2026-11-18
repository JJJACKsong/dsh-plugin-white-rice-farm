'use strict';
// Real cosmetic worker module with bounded DOM/clock adapters. This checks
// scheduling and cleanup contracts, not pixels, GIF decoding, or host behavior.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),crypto=require('node:crypto');
const source=fs.readFileSync(path.join(__dirname,'../src/workers.js'),'utf8');
const results=[];
function test(name,fn){try{fn();results.push({name,pass:true});console.log('PASS',name);}catch(e){results.push({name,pass:false,error:e.message});console.error('FAIL',name,e.message);process.exitCode=1;}}
function environment({osReduced=false,gameReduced=false,workers=1}={}){
 let serial=0;const timers=new Map(),documentListeners=new Map(),motionListeners=new Set();
 class Element{
  constructor(){this.children=[];this.dataset={};this.style={setProperty(){}};this.offsetLeft=0;this.offsetTop=0;this.offsetWidth=44;this.offsetHeight=44;this.hidden=false;}
  setAttribute(){} removeAttribute(k){delete this[k];} append(...xs){this.children.push(...xs);for(const x of xs)x.parent=this;} remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);}
 }
 const document={hidden:false,createElement:()=>new Element(),addEventListener(k,fn){if(!documentListeners.has(k))documentListeners.set(k,new Set());documentListeners.get(k).add(fn);},removeEventListener(k,fn){documentListeners.get(k)?.delete(fn);}};
 const media={matches:osReduced,addEventListener:(kind,fn)=>{assert.equal(kind,'change');motionListeners.add(fn);},removeEventListener:(kind,fn)=>{assert.equal(kind,'change');motionListeners.delete(fn);}};
 const context={window:{},document,matchMedia:query=>{assert.equal(query,'(prefers-reduced-motion: reduce)');return media;},performance:{now:()=>0},setInterval:(fn,ms)=>{const id=++serial;timers.set(id,{fn,ms});return id;},clearInterval:id=>timers.delete(id)};
 vm.runInNewContext(source,context,{timeout:1000});
 const state={tiles:Array(256).fill(null),workers:Array.from({length:workers},(_,i)=>({id:i+1,target:null,lastAt:0,status:'idle',handled:0})),options:{reducedMotion:gameReduced}};
 state.tiles[0]={type:'building',kind:'house'};for(let i=1;i<16;i++)state.tiles[i]={type:'grass'};
 const layer=new Element(),board=new Element();board.querySelector=()=>new Element();
 const actors=context.window.createFarmActors({layer,board,getState:()=>state,assets:{idle:'idle.gif',idlePoster:'idle.png'}});
 return {actors,state,layer,document,timers,documentListeners,motionListeners,
  visibility(hidden){document.hidden=hidden;for(const fn of [...documentListeners.get('visibilitychange')||[]])fn();},
  motion(reduced){media.matches=reduced;for(const fn of [...motionListeners])fn({matches:reduced});},
  assertStopped(){assert.equal(timers.size,0);},
  assertRunning(){assert.equal(timers.size,1);assert.equal([...timers.values()][0].ms,120);},
  assertPoster(){assert.ok(actors.snapshot().every(a=>a.src==='idle.png'));}
 };
}
test('系统减少动态在初次显示时使用静态图且不开启工人轮询',()=>{const e=environment({osReduced:true});e.actors.sync(44);e.assertStopped();e.assertPoster();e.actors.dispose();});
test('系统减少动态运行时切换会立即停表并在解除后恢复单一计时器',()=>{const e=environment();e.actors.sync(44);e.assertRunning();e.motion(true);e.assertStopped();e.assertPoster();e.motion(false);e.assertRunning();e.actors.sync(44);e.assertRunning();assert.equal(e.actors.snapshot()[0].src,'idle.gif');e.actors.dispose();});
test('隐藏停止轮询并隐藏角色，恢复后沿用当前系统偏好',()=>{const e=environment();e.actors.sync(44);e.visibility(true);e.assertStopped();assert.ok(e.layer.children.every(a=>a.hidden));e.assertPoster();e.motion(true);e.visibility(false);e.assertStopped();e.assertPoster();assert.ok(e.layer.children.every(a=>!a.hidden));e.motion(false);e.assertRunning();e.actors.dispose();});
test('游戏内减少动态与系统偏好共同决定工人调度',()=>{const e=environment();e.actors.sync(44);e.state.options.reducedMotion=true;e.actors.sync(44);e.assertStopped();e.assertPoster();e.motion(true);e.state.options.reducedMotion=false;e.actors.sync(44);e.assertStopped();e.motion(false);e.assertRunning();e.actors.dispose();});
test('没有工人时不轮询，招到工人后只建立一个计时器',()=>{const e=environment({workers:0});e.actors.sync(44);e.assertStopped();e.state.workers.push({id:1,target:null,lastAt:0,status:'idle',handled:0});e.actors.sync(44);e.assertRunning();e.actors.sync(44);e.assertRunning();e.actors.dispose();});
test('销毁清除计时器、角色和可见性及系统偏好监听器',()=>{const e=environment();e.actors.sync(44);e.assertRunning();e.actors.dispose();e.assertStopped();assert.equal(e.layer.children.length,0);assert.equal(e.documentListeners.get('visibilitychange')?.size||0,0);assert.equal(e.motionListeners.size,0);e.motion(true);e.visibility(false);e.assertStopped();});
const report={passed:results.filter(r=>r.pass).length,total:results.length,source_sha256:crypto.createHash('sha256').update(source).digest('hex'),environment:'Node vm executing real src/workers.js with DOM/clock/media-query adapters; not a browser or official DSH runtime',results};
fs.writeFileSync(path.join(__dirname,'workers-results.json'),JSON.stringify(report,null,2));console.log(`${report.passed}/${report.total} worker lifecycle tests passed`);
