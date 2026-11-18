'use strict';
const assert=require('node:assert/strict');
const E=require('../src/engine.js');
let passed=0;const results=[];
function test(name,fn){try{fn();passed++;results.push({name,pass:true});console.log('PASS',name);}catch(e){results.push({name,pass:false,error:e.message});console.error('FAIL',name,e);process.exitCode=1;}}
const fresh=()=>E.initial(1000);
function clear(s){s.options.autoSell=false;s.inventory=Object.fromEntries(Object.keys(E.ITEMS).map(k=>[k,0]));}
function worker(s,n=1){s.workers=Array.from({length:n},(_,i)=>({id:i+1,status:'idle',lastAt:0,target:null,handled:0}));s.nextWorkAt=s.time+E.STEP;}
function rich(){const s=fresh();s.gold=100000;s.inventory.meal=100;s.xp=E.LEVELS.at(-1).xp;return s;}

test('4×4 起步，上限坐标 16×16',()=>{const s=fresh();assert.equal(E.owned(s),16);assert.equal(s.tiles.length,256);assert.equal(E.count(s,'field'),4);assert.equal(s.workers.length,0);});
test('一键收获后补种，空田按计划播种',()=>{const s=fresh();const r=E.tendAll(s);assert.equal(r.harvested,2);assert.equal(r.planted,2);assert.equal(s.gold,100);assert.equal(s.tiles[E.idx(0,2)].crop,'carrot');assert.equal(s.tiles[E.idx(2,1)].crop,'rice');});
test('满仓收获不丢失任何作物',()=>{const s=fresh();clear(s);s.inventory.wheat=E.capacity(s)-1;const t=s.tiles[E.idx(0,2)];const old=JSON.stringify(t);assert.equal(E.collect(s,E.idx(0,2)),false);assert.equal(s.inventory.carrot,0);assert.equal(JSON.stringify(t),old);});
test('成熟作物一次只计一批，不会重复收取',()=>{const s=fresh();clear(s);assert.equal(E.collect(s,E.idx(0,2)),true);assert.equal(E.collect(s,E.idx(0,2)),false);assert.equal(s.inventory.carrot,2);});
test('水稻必须邻水；失败不扣开垦费用',()=>{const s=fresh();const gold=s.gold;assert.equal(E.tend(s,E.idx(3,3),'rice').ok,false);assert.equal(s.gold,gold);assert.equal(s.tiles[E.idx(3,3)].type,'grass');assert.equal(E.tend(s,E.idx(0,1),'rice').ok,true);assert.equal(s.gold,gold-12);});
test('长着的作物可以改下轮计划，不销毁当前收成',()=>{const s=fresh();E.tendAll(s);const i=E.idx(0,2),old=s.tiles[i].readyAt;assert.equal(E.changePlan(s,i,'wheat').ok,true);assert.equal(s.tiles[i].crop,'carrot');assert.equal(s.tiles[i].readyAt,old);E.advance(s,14000);E.collect(s,i);assert.equal(s.tiles[i].crop,'wheat');});
test('灶台自动开工，一座建筑只占一个生产位',()=>{const s=rich();clear(s);s.inventory.rice=10;assert.ok(E.build(s,E.idx(2,0),'kitchen').ok);for(let n=0;n<20;n++)E.settle(s);assert.equal(s.inventory.rice,8);assert.equal(s.inventory.meal,0);E.advance(s,49999);assert.equal(s.inventory.meal,0);E.advance(s,1);assert.equal(s.inventory.meal,1);assert.equal(s.inventory.rice,6);});
test('工坊整批产出：满仓等待，腾出空间后只入库一次',()=>{const s=rich();clear(s);s.inventory.grass=3;E.build(s,E.idx(2,0),'cows');s.inventory.wheat=E.capacity(s)-1;E.advance(s,60000);assert.equal(s.inventory.milk,0);assert.ok(s.tiles[E.idx(2,0)].job);for(let n=0;n<12;n++)E.settle(s);assert.equal(s.inventory.milk,0);s.inventory.wheat-=2;E.settle(s);assert.equal(s.inventory.milk,2);assert.equal(s.tiles[E.idx(2,0)].job,null);E.settle(s);assert.equal(s.inventory.milk,2);});
test('自动批发保护大白饭、加工原料与每种商品两份上架机会',()=>{const s=fresh();s.inventory.meal=35;s.inventory.rice=20;s.inventory.wheat=25;s.inventory.carrot=10;E.sellSurplus(s);assert.equal(s.inventory.meal,35);assert.equal(s.inventory.rice,10);assert.equal(s.inventory.wheat,14);assert.equal(s.inventory.carrot,2);});
test('招工消耗一次白饭，招来后自动工作',()=>{const s=rich();s.inventory.meal=3;const gold=s.gold;assert.equal(E.recruit(s).ok,true);assert.equal(s.inventory.meal,0);assert.equal(s.workers.length,1);assert.equal(s.gold,gold-200);assert.ok(s.stats.harvests>0);E.advance(s,300000);assert.equal(s.inventory.meal,0);assert.ok(s.stats.harvests>5);});
test('工人最多四位，多次点击不能超招',()=>{const s=rich();s.options.autoSell=false;for(let i=0;i<4;i++)assert.ok(E.recruit(s).ok);const gold=s.gold,meal=s.inventory.meal;assert.equal(E.recruit(s).ok,false);assert.equal(s.workers.length,4);assert.equal(s.gold,gold);assert.equal(s.inventory.meal,meal);});
test('扩地只能买正交相邻 2×2，不允许斜对角和行坐标绕回',()=>{const s=rich();assert.equal(E.expand(s,4,4).ok,false);assert.equal(E.expand(s,16,0).ok,false);assert.equal(E.expand(s,-2,2).ok,false);assert.equal(E.expand(s,4,0).ok,true);assert.equal(E.owned(s),20);assert.equal(E.expand(s,4,0).ok,false);});
test('可以完整扩至 16×16，绝不会越界',()=>{const s=rich();s.gold=1e8;for(let n=0;n<100;n++){const c=E.eligibleChunks(s)[0];if(!c)break;assert.ok(E.expand(s,c.x,c.y).ok);}assert.equal(E.owned(s),256);assert.equal(E.eligibleChunks(s).length,0);assert.equal(s.tiles.length,256);});
test('离线推进与同时间逐秒在线推进一致',()=>{const a=rich();E.tendAll(a);E.build(a,E.idx(2,0),'kitchen');E.build(a,E.idx(3,0),'mill');worker(a,2);const b=E.clone(a);E.advance(a,600000);for(let n=0;n<600;n++)E.advance(b,1000);assert.deepEqual(a,b);});
test('离线单次最多推进八小时',()=>{const s=fresh();E.advance(s,24*3600000);assert.equal(s.time,E.OFFLINE_CAP);});
test('没有工人不会在离线期间自动收割补种',()=>{const s=fresh();E.tendAll(s);const harvested=s.stats.harvests;E.advance(s,600000);assert.equal(s.stats.harvests,harvested);assert.ok(s.tiles.filter(t=>E.ripe(s,t)).length);});
test('订单自动交付，只结算一次',()=>{const s=fresh();clear(s);E.acceptOrder(s,0);s.inventory.carrot=8;const gold=s.gold;E.settle(s);assert.equal(s.activeOrder,null);assert.equal(s.gold,gold+20);assert.equal(s.stats.orders,1);E.settle(s);assert.equal(s.stats.orders,1);});
test('接下的原料订单不被加工抢走',()=>{const s=rich();clear(s);E.build(s,E.idx(2,0),'kitchen');s.activeOrder={item:'rice',qty:9,pay:35};s.inventory.rice=8;E.settle(s);assert.equal(s.inventory.rice,8);assert.equal(s.tiles[E.idx(2,0)].job,null);s.inventory.rice=9;E.settle(s);assert.equal(s.activeOrder,null);assert.equal(s.inventory.rice,0);});
test('水井搬家不能使稻田断水，失败完整回滚',()=>{const s=rich();E.tendAll(s);const before=JSON.stringify(s.tiles);assert.equal(E.move(s,E.idx(1,1),E.idx(3,3)).ok,false);assert.equal(JSON.stringify(s.tiles),before);});
test('复制旧版存档，保留在途产品，不改原对象',()=>{const old={ver:1,gold:233,inventory:{meal:7,rice:8},last:1000,tiles:{0:{type:'building',kind:'house'},1:{type:'building',kind:'store'},2:{type:'building',kind:'kitchen'},16:{type:'field',crop:'carrot',readyAt:6000}},workers:[{role:'field'}],jobs:[{item:'meal',readyAt:4000}],completed:4};const before=JSON.stringify(old),s=E.restore(old,5000);assert.equal(s.gold,233);assert.equal(s.inventory.meal,7);assert.equal(s.workers.length,1);assert.equal(s.options.autoSell,false);assert.equal(s.legacyJobs.length,1);E.advance(s,3000);assert.equal(s.inventory.meal,8);assert.equal(JSON.stringify(old),before);});
test('新存档校验、往返与未知字段清理',()=>{const a=fresh();E.tendAll(a);assert.equal(a.version,E.SAVE_VERSION);const b=E.restore(JSON.parse(JSON.stringify(a)),1000);assert.equal(b.version,E.SAVE_VERSION);assert.equal(b.gold,a.gold);assert.deepEqual(b.tiles,a.tiles);assert.throws(()=>E.restore({version:2,tiles:[]}));assert.throws(()=>E.restore({version:99,tiles:Array(256).fill(null)}));const raw=E.clone(a);raw.tiles[0].kind='<script>';assert.throws(()=>E.restore(raw));});

test('庄园声望升级只奖励一次，并逐步解锁磨坊、面包房和牛棚',()=>{
 const s=fresh();assert.equal(E.farmLevel(s),1);assert.equal(E.canBuild(s,'mill'),false);assert.equal(E.canBuild(s,'kitchen'),true);
 s.xp=E.LEVELS[1].xp-3;const gold=s.gold;assert.ok(E.collect(s,E.idx(0,2)));assert.equal(E.farmLevel(s),2);assert.equal(s.gold,gold+40);assert.equal(E.canBuild(s,'mill'),true);assert.equal(E.canBuild(s,'bakery'),false);
 const saved=E.restore(JSON.parse(JSON.stringify(s)),2000);assert.equal(saved.xp,s.xp);assert.equal(saved.gold,s.gold);assert.equal(E.farmLevel(saved),2);
 saved.xp=E.LEVELS[2].xp;assert.equal(E.farmLevel(saved),3);assert.equal(E.canBuild(saved,'bakery'),true);saved.xp=E.LEVELS[3].xp;assert.equal(E.canBuild(saved,'cows'),true);
});
test('庄园等级提升提供仓库容量，旧版存档自动补算成长进度',()=>{
 const s=fresh();const base=E.capacity(s);s.xp=E.LEVELS[4].xp-1;assert.equal(E.capacity(s),base);E.collect(s,E.idx(0,2));assert.equal(E.farmLevel(s),5);assert.equal(E.capacity(s),base+20);
 const old=E.clone(s);delete old.xp;old.stats.harvests=100;const oldGold=old.gold,restored=E.restore(old,2000);assert.ok(restored.xp>=E.LEVELS[3].xp);assert.ok(E.farmLevel(restored)>=4);assert.equal(restored.gold,oldGold);
});
test('未达到庄园等级不能提前建造高阶工坊',()=>{const s=fresh();s.gold=10000;assert.equal(E.build(s,E.idx(2,0),'mill').ok,false);assert.equal(s.tiles[E.idx(2,0)].type,'grass');s.xp=E.LEVELS[1].xp;assert.equal(E.build(s,E.idx(2,0),'mill').ok,true);});
test('农具升级提升处理量，不超过四名工人',()=>{const s=rich();worker(s,4);assert.ok(E.upgradeTools(s).ok);assert.equal(s.toolLevel,1);assert.equal(s.workers.length,4);});
test('腾地保留当前收成，收完后变空草地',()=>{const s=fresh();clear(s);const i=E.idx(0,2);assert.ok(E.reclaim(s,i).ok);assert.equal(s.tiles[i].crop,'carrot');assert.ok(E.collect(s,i));assert.equal(s.inventory.carrot,2);assert.equal(s.tiles[i].type,'grass');});
test('修改计划可以取消腾地，存档保留腾地状态',()=>{const s=fresh();E.reclaim(s,32);const copy=E.restore(JSON.parse(JSON.stringify(s)),1000);assert.equal(copy.tiles[32].retire,true);E.changePlan(copy,32,'wheat');assert.equal(copy.tiles[32].retire,undefined);});
test('米食配方 Lv.3 解锁；错误建筑与无效配方不改变状态',()=>{
 const s=fresh();clear(s);s.gold=10000;s.xp=E.LEVELS[1].xp;assert.ok(E.build(s,E.idx(2,0),'mill').ok);const mill=E.idx(2,0);
 assert.equal(E.canUseRecipe(s,'mill','riceflour'),false);const before=JSON.stringify(s);assert.equal(E.changeRecipe(s,mill,'riceflour').ok,false);assert.equal(JSON.stringify(s),before);
 s.xp=E.LEVELS[2].xp;assert.equal(E.canUseRecipe(s,'mill','riceflour'),true);
 assert.equal(E.changeRecipe(s,E.idx(0,0),'riceflour').ok,false);assert.equal(E.changeRecipe(s,mill,'ricecake').ok,false);assert.equal(E.changeRecipe(s,mill,'nope').ok,false);
 assert.equal(E.recipeFor(s.tiles[mill]),'flour');
});
test('忙碌时换下批保留当前批次，下一批原料只扣一次',()=>{
 const s=rich();clear(s);s.inventory.wheat=6;s.inventory.rice=6;assert.ok(E.build(s,E.idx(2,0),'mill').ok);const i=E.idx(2,0);E.settle(s);
 const t=s.tiles[i];assert.equal(t.job.item,'flour');const job=JSON.stringify(t.job),wheat=s.inventory.wheat,rice=s.inventory.rice;
 assert.ok(E.changeRecipe(s,i,'riceflour').ok);assert.equal(JSON.stringify(t.job),job);assert.equal(s.inventory.wheat,wheat);assert.equal(s.inventory.rice,rice);
 E.advance(s,45000);assert.equal(t.job.item,'riceflour');assert.equal(s.inventory.rice,rice-3);assert.equal(s.inventory.flour,2);assert.equal(s.inventory.wheat,wheat);
});
test('满仓时当前批次保留，腾出空间后只入库一次',()=>{
 const s=rich();clear(s);s.inventory.wheat=3;assert.ok(E.build(s,E.idx(2,0),'mill').ok);const t=s.tiles[E.idx(2,0)];assert.equal(t.job.item,'flour');
 s.inventory.carrot=E.capacity(s)-E.total(s);assert.equal(E.total(s),E.capacity(s));
 E.advance(s,45000);assert.equal(s.inventory.flour,0);assert.ok(t.job);assert.ok(t.job.readyAt<=s.time);
 const pending=E.clone(t.job);E.changeRecipe(s,E.idx(2,0),'riceflour');assert.deepEqual(t.job,pending);assert.equal(E.recipeFor(t),'riceflour');
 s.inventory.carrot-=2;E.settle(s);assert.equal(s.inventory.flour,2);assert.equal(t.job,null);
});
test('暂停记住下一批选择，恢复后才开工',()=>{
 const s=rich();clear(s);s.inventory.rice=6;assert.ok(E.build(s,E.idx(2,0),'mill').ok);const i=E.idx(2,0);assert.ok(E.toggleMachine(s,i).ok);
 assert.ok(E.changeRecipe(s,i,'riceflour').ok);assert.equal(E.recipeFor(s.tiles[i]),'riceflour');assert.equal(s.tiles[i].job,null);assert.equal(s.inventory.rice,6);
 E.advance(s,100000);assert.equal(s.tiles[i].job,null);assert.equal(s.inventory.rice,6);
 assert.ok(E.toggleMachine(s,i).ok);assert.equal(s.tiles[i].job.item,'riceflour');assert.equal(s.inventory.rice,3);
});
test('旧档缺新物品补零，默认与无效下一批配方安全回退',()=>{
 const s=rich();clear(s);E.build(s,E.idx(2,0),'mill');const i=E.idx(2,0);const raw=JSON.parse(JSON.stringify(s));
 delete raw.inventory.riceflour;delete raw.inventory.ricecake;delete raw.tiles[i].nextRecipe;
 const a=E.restore(raw,1000);assert.equal(a.inventory.riceflour,0);assert.equal(a.inventory.ricecake,0);assert.equal(E.recipeFor(a.tiles[i]),'flour');
 raw.tiles[i].nextRecipe='ricecake';const b=E.restore(raw,1000);assert.equal(E.recipeFor(b.tiles[i]),'flour');
 raw.tiles[i].nextRecipe='riceflour';raw.xp=E.LEVELS[1].xp;const c=E.restore(raw,1000);assert.equal(E.recipeFor(c.tiles[i]),'flour');
});
test('当前在制品与下一批选择可分别恢复',()=>{
 const s=rich();clear(s);s.inventory.wheat=3;s.inventory.rice=6;E.build(s,E.idx(2,0),'mill');const i=E.idx(2,0);assert.equal(s.tiles[i].job.item,'flour');
 assert.ok(E.changeRecipe(s,i,'riceflour').ok);const r=E.restore(JSON.parse(JSON.stringify(s)),2000),rt=r.tiles[i];
 assert.equal(rt.job.item,'flour');assert.equal(E.recipeFor(rt),'riceflour');
 E.advance(r,45000);assert.equal(rt.job.item,'riceflour');assert.equal(r.inventory.flour,2);assert.equal(r.inventory.rice,3);
});
test('米食订单只在 Lv3 且对应工坊存在时进入轮换',()=>{
 const s=rich();clear(s);E.build(s,E.idx(2,0),'mill');
 const items=()=>{const set=new Set();for(let round=0;round<20;round++){s.orderRound=round;for(const o of E.availableOrders(s))set.add(o.item);}return set;};
 assert.ok(items().has('riceflour'));assert.equal(items().has('ricecake'),false);E.build(s,E.idx(3,0),'bakery');assert.ok(items().has('ricecake'));
 s.xp=E.LEVELS[1].xp;const low=items();assert.equal(low.has('riceflour'),false);assert.equal(low.has('ricecake'),false);
});
test('米糕订单等磨坊与面包房齐全后出现，原有面包单规则不变',()=>{
 const s=rich();clear(s);E.build(s,2,'bakery');
 const offered=()=>{const all=new Set();for(let n=0;n<20;n++){s.orderRound=n;E.availableOrders(s).forEach(o=>all.add(o.item));}return all;};
 assert.equal(offered().has('ricecake'),false);assert.equal(offered().has('bread'),true);
 E.build(s,3,'mill');assert.equal(offered().has('ricecake'),true);
});
test('新加工品订单保护与自动售货保留',()=>{
 const s=rich();clear(s);s.options.autoSell=true;E.build(s,E.idx(2,0),'mill');E.build(s,E.idx(3,0),'bakery');
 s.inventory.riceflour=6;s.inventory.ricecake=6;s.activeOrder={item:'riceflour',qty:6,pay:58};E.sellSurplus(s);
 assert.equal(s.inventory.riceflour,6);assert.equal(s.inventory.ricecake,0);
 s.activeOrder={item:'rice',qty:9,pay:35};s.inventory.rice=8;assert.equal(E.availableInput(s,'riceflour'),0);
});
test('含米食加工链的离线推进与逐秒在线推进一致',()=>{
 const a=rich();clear(a);a.inventory.rice=200;a.inventory.wheat=50;E.build(a,E.idx(2,0),'mill');E.build(a,E.idx(3,0),'bakery');
 assert.ok(E.changeRecipe(a,E.idx(2,0),'riceflour').ok);assert.ok(E.changeRecipe(a,E.idx(3,0),'ricecake').ok);
 const b=E.clone(a);E.advance(a,600000);for(let n=0;n<600;n++)E.advance(b,1000);assert.deepEqual(a,b);
});
test('米粉在制时改回面粉，搬家与读档不丢已扣原料的一批',()=>{
 const s=rich();clear(s);s.inventory.wheat=3;s.inventory.rice=6;E.build(s,2,'mill');E.advance(s,45000);
 E.changeRecipe(s,2,'riceflour');const job=E.clone(s.tiles[2].job);assert.equal(job.item,'riceflour');
 E.changeRecipe(s,2,'flour');assert.deepEqual(s.tiles[2].job,job);assert.ok(E.move(s,2,3).ok);
 const restored=E.restore(JSON.parse(JSON.stringify(s)),2000);assert.deepEqual(restored.tiles[3].job,job);assert.equal(E.recipeFor(restored.tiles[3]),'flour');
 E.advance(restored,45000);assert.equal(restored.inventory.riceflour,2);assert.equal(restored.inventory.rice,3);assert.equal(restored.inventory.flour,2);
 E.settle(restored);assert.equal(restored.inventory.riceflour,2);
});
test('米糕订单自动交付一次，保留旧订单轮换前缀',()=>{
 const s=rich();clear(s);E.build(s,2,'mill');E.build(s,3,'bakery');
 assert.equal(E.ORDER_POOL[7].item,'meal');let choice=-1;
 for(let round=0;round<E.ORDER_POOL.length&&choice<0;round++){s.orderRound=round;choice=E.availableOrders(s).findIndex(o=>o.item==='ricecake');}
 assert.ok(choice>=0);assert.ok(E.acceptOrder(s,choice).ok);const before=s.gold;
 s.inventory.ricecake=6;E.settle(s,false);assert.equal(s.gold,before+142);assert.equal(s.inventory.ricecake,0);assert.equal(s.stats.orders,1);
 E.settle(s,false);assert.equal(s.gold,before+142);assert.equal(s.stats.orders,1);
});
// Ordinary Lv.3, two workshops and a nearly full 160-slot warehouse. Seeded
// inventory stands for harvests accumulated while automatic selling is paused.
function nearFullChain(){
 const s=fresh();clear(s);s.xp=135;s.gold=1000;s.inventory.wheat=9;s.inventory.flour=2;
 assert.ok(E.build(s,2,'mill').ok);assert.ok(E.build(s,3,'bakery').ok);
 s.inventory.carrot=E.capacity(s)-E.total(s)-2;return s;
}
test('近满仓耗料腾位在同一时刻接收待入库成品，在线离线一致',()=>{
 const a=nearFullChain(),b=E.clone(a);E.advance(a,180000);for(let n=0;n<180;n++)E.advance(b,1000);
 assert.deepEqual(a,b);assert.equal(a.inventory.bread,4);assert.equal(a.stats.goods,10);
 assert.equal(a.tiles[3].job.startedAt,180000);assert.equal(a.tiles[3].job.readyAt,270000);
});
test('满仓工坊同刻稳定后零时间推进不再补发产品或扣料',()=>{
 const s=nearFullChain();E.advance(s,90000);
 assert.equal(s.inventory.bread,2);assert.equal(s.tiles[3].job.startedAt,90000);
 const stable=E.clone(s);for(let n=0;n<10;n++)E.advance(s,0);assert.deepEqual(s,stable);
});
test('近满仓链路中途存档恢复，下一批与暂停不丢失',()=>{
 const s=nearFullChain();E.changeRecipe(s,2,'riceflour');E.toggleMachine(s,3);E.advance(s,45000);
 const restored=E.restore(E.clone(s),1000);const project=x=>({time:x.time,gold:x.gold,xp:x.xp,inventory:x.inventory,tiles:x.tiles,stats:x.stats});
 E.advance(s,135000);for(let n=0;n<135;n++)E.advance(restored,1000);
 assert.deepEqual(project(s),project(restored));assert.equal(restored.tiles[3].paused,true);
 assert.equal(E.recipeFor(restored.tiles[2]),'riceflour');
});
test('近满仓精确结算点存档后继续，与整段推进的经营结果一致',()=>{
 const uninterrupted=nearFullChain(),saved=E.clone(uninterrupted);E.advance(saved,90000);
 const restored=E.restore(E.clone(saved),1000);E.advance(uninterrupted,180000);E.advance(restored,90000);
 for(const key of ['time','gold','xp','inventory','tiles','stats','activeOrder','orderRound'])assert.deepEqual(restored[key],uninterrupted[key],key);
});
test('加工升级增加容量后，同刻收下遍历较早的满仓批次',()=>{
 const s=fresh();clear(s);s.gold=1000;s.xp=E.LEVELS[3].xp;s.inventory.rice=2;s.inventory.wheat=3;
 assert.ok(E.build(s,3,'kitchen').ok);E.advance(s,5000);assert.ok(E.build(s,2,'mill').ok);
 s.xp=E.LEVELS[4].xp-5;s.inventory.carrot=E.capacity(s)-E.total(s)-1;E.advance(s,45000);
 assert.equal(E.farmLevel(s),5);assert.equal(s.inventory.meal,1);assert.equal(s.inventory.flour,2);
 assert.equal(s.tiles[2].job,null);assert.equal(s.tiles[3].job,null);const stable=E.clone(s);E.advance(s,0);assert.deepEqual(s,stable);
});
test('工人同一逻辑时刻只工作一次，工坊稳定化不加跑工人',()=>{
 const s=nearFullChain();worker(s);s.nextWorkAt=90000;E.advance(s,90000);
 assert.equal(s.workers[0].handled,2);assert.equal(s.nextWorkAt,94000);
 const stable=E.clone(s);E.advance(s,0);assert.deepEqual(s,stable);
});
test('订单列表解锁后旧报价不误接另一种货物，兼容原索引调用',()=>{
 const s=fresh();clear(s);s.gold=1000;s.xp=E.LEVELS[1].xp;E.build(s,2,'mill');s.orderRound=5;
 const shown=E.availableOrders(s)[0];assert.equal(shown.item,'carrot');
 s.xp=E.LEVELS[2].xp;assert.equal(E.availableOrders(s)[0].item,'riceflour');
 const before=E.clone(s),rejected=E.acceptOrder(s,0,shown);assert.equal(rejected.ok,false);
 assert.equal(rejected.message,'订单已更新，请重新选择。');assert.deepEqual(s,before);
 const current=E.availableOrders(s)[0];assert.equal(E.acceptOrder(s,0,current).ok,true);
 assert.deepEqual(s.activeOrder,current);E.cancelOrder(s);assert.equal(E.acceptOrder(s,0).ok,true);
});
test('订单报价校验含数量与报酬，重复接单不覆盖当前订单',()=>{
 const s=fresh();clear(s);const quote=E.availableOrders(s)[0],before=E.clone(s);
 for(const altered of [{...quote,qty:quote.qty+1},{...quote,pay:quote.pay+1},null]){
  assert.equal(E.acceptOrder(s,0,altered).ok,false);assert.deepEqual(s,before);
 }
 assert.equal(E.acceptOrder(s,0,quote).ok,true);const active=E.clone(s);
 assert.equal(E.acceptOrder(s,1,E.availableOrders(s)[1]).ok,false);assert.deepEqual(s,active);
});
// A repeatable opening: harvest all every 15 seconds, build the stove immediately,
// and add two carrot plots. This is a simulated pacing check, not a human playtest.
test('开局模拟能在 8 分钟以内招到第一位工人',()=>{const s=fresh();E.tendAll(s);E.build(s,E.idx(2,0),'kitchen');E.tend(s,E.idx(3,1),'carrot');E.tend(s,E.idx(3,2),'carrot');let seconds=0;while(seconds<480){E.advance(s,15000);seconds+=15;E.tendAll(s);if(s.gold>=200&&s.inventory.meal>=3)break;}assert.ok(seconds<480,`花费 ${seconds} 秒`);assert.ok(E.recruit(s).ok);console.log('PACING: first worker at',seconds,'seconds');});

test('批发按单品六份门槛结算，少一份不动库存、混合商品不合并',()=>{
 const s=fresh();clear(s);s.inventory.carrot=5;s.inventory.wheat=1;
 const before=s.gold;assert.equal(E.wholesale(s,'carrot',5).ok,false);assert.equal(E.wholesale(s,'wheat',1).ok,false);
 assert.equal(s.inventory.carrot,5);assert.equal(s.inventory.wheat,1);assert.equal(s.gold,before);
 s.inventory.carrot=6;const q=E.wholesaleQuote(s,'carrot',6);assert.equal(q.total,12);assert.equal(E.wholesale(s,'carrot',6,{item:'carrot',qty:6,unitPrice:2}).ok,true);
 assert.equal(s.inventory.carrot,0);assert.equal(s.gold,before+12);
});
test('自动批发先留两份零售机会，凑满六份才出售',()=>{
 const s=fresh();s.inventory.carrot=7;E.sellSurplus(s);assert.equal(s.inventory.carrot,7);
 s.inventory.carrot=8;const gold=s.gold;E.sellSurplus(s);assert.equal(s.inventory.carrot,2);assert.equal(s.gold,gold+12);
});
test('零售允许单件上架，转移时不入账，20秒后逐件成交',()=>{
 const s=fresh();clear(s);s.inventory.carrot=1;const before=s.gold;
 const r=E.listRetail(s,'produce','carrot',1);assert.equal(r.ok,true);assert.equal(r.quote.unitPrice,3);
 assert.equal(s.inventory.carrot,0);assert.equal(s.shops.produce.qty,1);assert.equal(s.gold,before);
 E.advance(s,E.RETAIL_INTERVAL-1);assert.equal(s.gold,before);assert.equal(s.shops.produce.qty,1);
 E.advance(s,1);assert.equal(s.gold,before+3);assert.equal(s.shops.produce.qty,0);assert.equal(s.shops.produce.item,null);
});
test('店铺每20秒一件、单架六件、不同商品不覆盖',()=>{
 const s=fresh();clear(s);s.inventory.carrot=8;s.inventory.wheat=8;
 assert.equal(E.listRetail(s,'produce','carrot',6).quote.qty,6);assert.equal(E.listRetail(s,'produce','wheat',1).ok,false);
 E.advance(s,60000);assert.equal(s.gold,109);assert.equal(s.shops.produce.qty,3);assert.equal(s.inventory.carrot,2);
});
test('退回未售商品原子执行，仓库满时不改变货架',()=>{
 const s=fresh();clear(s);s.inventory.carrot=4;assert.ok(E.listRetail(s,'produce','carrot',4).ok);
 s.inventory.wheat=E.capacity(s)-E.total(s);const shelf=E.clone(s.shops.produce),gold=s.gold;
 const failed=E.returnRetail(s,'produce');assert.equal(failed.ok,false);assert.deepEqual(s.shops.produce,shelf);assert.equal(s.gold,gold);
 s.inventory.wheat-=4;assert.equal(E.returnRetail(s,'produce').ok,true);assert.equal(s.inventory.carrot,4);assert.equal(s.shops.produce.qty,0);
});
test('同一商品货架隔离仓库批发，避免重复扣货',()=>{
 const s=fresh();clear(s);s.inventory.carrot=12;assert.ok(E.listRetail(s,'produce','carrot',1).ok);
 const q=E.wholesaleQuote(s,'carrot');assert.equal(q.available,11);assert.equal(q.qty,11);assert.equal(E.wholesale(s,'carrot',11).ok,true);
 assert.equal(s.inventory.carrot,0);assert.equal(s.shops.produce.qty,1);
});
test('零售逐步推进、一次推进和成交点存档恢复结果守恒',()=>{
 const a=fresh();clear(a);a.inventory.carrot=6;a.inventory.wheat=7;E.listRetail(a,'produce','carrot',6);
 const b=E.clone(a),c=E.clone(a);E.advance(a,120000);for(let i=0;i<120;i++)E.advance(b,1000);
 E.advance(c,40000);const restored=E.restore(E.clone(c),2000);E.advance(c,80000);E.advance(restored,80000);
 const project=x=>({time:x.time,gold:x.gold,inventory:x.inventory,shops:x.shops,stats:x.stats});
 assert.deepEqual(project(a),project(b));assert.deepEqual(project(c),project(restored));assert.equal(a.shops.produce.qty,0);
});
test('新字段缺失的v1/v2旧档安全迁移，货架默认空且不改变旧库存金币',()=>{
 const s=fresh();s.gold=345;s.inventory.carrot=7;const raw=E.clone(s);raw.version=2;delete raw.shops;
 const r=E.restore(raw,2000);assert.equal(r.version,E.SAVE_VERSION);assert.equal(r.gold,345);assert.equal(r.inventory.carrot,7);assert.equal(r.shops.produce.open,true);assert.equal(r.shops.produce.qty,0);assert.equal(r.shops.food.open,false);
 const old={ver:1,gold:233,inventory:{carrot:9},last:1000,tiles:{0:{type:'building',kind:'house'},1:{type:'building',kind:'store'},2:{type:'field',crop:'carrot',readyAt:6000},3:{type:'grass'}}};
 const m=E.restore(old,2000);assert.equal(m.version,E.SAVE_VERSION);assert.equal(m.gold,233);assert.equal(m.inventory.carrot,9);assert.equal(m.shops.produce.qty,0);
});
test('v1迁移推定Lv.3时同步解锁食品铺，迁移完成即可上架面包',()=>{
 const old={ver:1,gold:233,inventory:{bread:1},last:1000,tiles:{0:{type:'building',kind:'house'},1:{type:'building',kind:'store'},2:{type:'building',kind:'bakery'},3:{type:'grass'}}};
 const s=E.restore(old,2000);assert.equal(E.farmLevel(s),3);assert.equal(s.xp,135);assert.equal(s.shops.food.open,true);
 const quote=E.retailQuote(s,'food','bread',1);assert.equal(quote.ok,true);assert.equal(quote.unitPrice,23);const gold=s.gold;
 const listed=E.listRetail(s,'food','bread',1,{item:'bread',qty:1,unitPrice:quote.unitPrice});
 assert.equal(listed.ok,true);assert.equal(s.inventory.bread,0);assert.equal(s.shops.food.qty,1);assert.equal(s.gold,gold);
 E.advance(s,E.RETAIL_INTERVAL);assert.equal(s.gold,gold+quote.unitPrice);assert.equal(s.shops.food.qty,0);
});
test('零售报价/归属/可放数由引擎集中计算，动作复用同一结果并保持过期报价拒绝',()=>{
 const s=fresh();clear(s);s.xp=135;s.shops.food.open=true;s.inventory.bread=8;s.inventory.carrot=2;
 assert.equal(E.retailShopFor('carrot'),'produce');assert.equal(E.retailShopFor('bread'),'food');assert.equal(E.retailShopFor('meal'),'food');assert.equal(E.retailShopFor('unknown'),null);
 const before=JSON.stringify(s),one=E.retailQuote(s,'food','bread',1),max=E.retailQuote(s,'food','bread',E.RETAIL_LIMIT);
 assert.equal(JSON.stringify(s),before);assert.equal(one.unitPrice,23);assert.equal(one.qty,1);assert.equal(one.free,6);assert.equal(one.ok,true);assert.equal(max.qty,6);
 assert.equal(E.retailQuote(s,'produce','bread',1).reason,'这间店不能卖这种商品。');
 assert.equal(E.listRetail(s,'food','bread',6,{item:'bread',qty:6,unitPrice:23}).ok,true);
 assert.equal(s.shops.food.qty,6);assert.equal(s.shops.food.item,'bread');
 const full=E.retailQuote(s,'food','bread',1);assert.equal(full.qty,0);assert.equal(full.ok,false);assert.equal(full.reason,'货架已经满了，先等顾客购买或退回商品。');
 const stable=JSON.stringify(s);const stale=E.listRetail(s,'food','bread',1,{item:'bread',qty:1,unitPrice:22});assert.equal(stale.ok,false);assert.equal(JSON.stringify(s),stable);
 const back=E.retailReturnQuote(s,'food');assert.equal(back.ok,true);assert.equal(back.qty,6);assert.equal(back.missing,0);
 s.inventory.carrot+=E.capacity(s)-E.total(s);const blocked=E.retailReturnQuote(s,'food');assert.equal(blocked.ok,false);assert.equal(blocked.missing,6);assert.match(blocked.reason,/仓库空间不足/);
});
test('食品铺在Lv.3解锁，减少动态不参与经营状态',()=>{
 const s=fresh();assert.equal(s.shops.food.open,false);s.xp=E.LEVELS[2].xp-1;E.collect(s,E.idx(0,2));assert.equal(s.shops.food.open,true);
 s.inventory.bread=1;assert.ok(E.listRetail(s,'food','bread',1).ok);const copy=E.restore(E.clone(s),2000);E.advance(s,20000);E.advance(copy,20000);
 assert.deepEqual(copy.shops,s.shops);assert.equal(copy.gold,s.gold);
});


test('零售周期中途存档保留原成交点，短返回与连续推进一致',()=>{
 const project=s=>({time:s.time,gold:s.gold,inventory:s.inventory,shops:s.shops,stats:s.stats});
 for(const elapsed of [1,5000,19999,20000,20001,99999]){
  const a=fresh();a.inventory.carrot=6;assert.ok(E.listRetail(a,'produce','carrot',6).ok);E.advance(a,elapsed);
  const b=E.restore(E.clone(a),2000);assert.deepEqual(b.shops,a.shops,`restored at ${elapsed}`);
  for(const delta of [1,19999,40000]){E.advance(a,delta);E.advance(b,delta);assert.deepEqual(project(b),project(a),`restored at ${elapsed}, advanced ${delta}`);}
 }
 const raw=fresh();raw.inventory.carrot=1;E.listRetail(raw,'produce','carrot',1);E.advance(raw,5000);delete raw.shops.produce.nextAt;
 const partial=E.restore(raw,2000);assert.equal(partial.shops.produce.nextAt,partial.time+E.RETAIL_INTERVAL);
});

test('正常新档可完成批发、单件零售、大白饭招工并自然解锁磨坊',()=>{
 const s=E.initial();
 E.tendAll(s);E.advance(s,15000);E.tendAll(s);
 assert.equal(s.gold,112);assert.equal(s.inventory.carrot,2);assert.equal(s.stats.sold,6);
 assert.ok(E.listRetail(s,'produce','carrot',1).ok);const beforeRetail=s.gold;E.advance(s,E.RETAIL_INTERVAL);assert.equal(s.gold,beforeRetail+3);
 assert.ok(E.build(s,E.idx(0,1),'kitchen').ok);
 for(let i=0;i<20;i++){E.advance(s,15000);E.tendAll(s);}
 assert.ok(s.gold>=E.RECRUITS[0].gold);assert.ok(s.inventory.meal>=E.RECRUITS[0].meal);
 assert.ok(E.farmLevel(s)>=3);assert.ok(E.canBuild(s,'mill'));assert.equal(s.shops.food.open,true);
 assert.ok(E.recruit(s).ok);assert.equal(s.workers.length,1);assert.ok(E.canBuild(s,'mill'));
});

const report={generated_at_utc:new Date().toISOString(),passed,total:results.length,results};require('node:fs').writeFileSync(__dirname+'/engine-results.json',JSON.stringify(report,null,2));console.log(`\n${passed}/${results.length} tests passed`);
