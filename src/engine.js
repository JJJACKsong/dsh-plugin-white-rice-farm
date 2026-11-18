/* 大白饭庄园 · v0.6
 * Deterministic, dependency-free simulation. Rendering and persistence live elsewhere.
 * Quantities move in whole batches: a full warehouse never destroys or duplicates goods.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.FarmEngine = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const MAX = 16, STEP = 4000, OFFLINE_CAP = 8 * 3600000, SAVE_VERSION = 3;
  const LEVELS = [
    {level:1,xp:0,reward:0,title:'小小农场'},
    {level:2,xp:45,reward:40,title:'小小庄园',unlock:'mill'},
    {level:3,xp:135,reward:70,title:'丰收庄园',unlock:'bakery'},
    {level:4,xp:270,reward:110,title:'田园庄园',unlock:'cows'},
    {level:5,xp:460,reward:150,title:'热闹庄园',capacity:20},
    {level:6,xp:700,reward:220,title:'富饶庄园',capacity:20},
    {level:7,xp:1000,reward:300,title:'繁盛庄园',capacity:20}
  ];
  const CROPS = {
    carrot: {name:'萝卜',time:15000,yield:2,price:2,color:'#df8a49'},
    wheat: {name:'小麦',time:30000,yield:3,price:3,color:'#d2ad55'},
    grass: {name:'牧草',time:20000,yield:3,price:1,color:'#78a270'},
    rice: {name:'水稻',time:35000,yield:3,price:3,color:'#7ea9aa'}
  };
  const ITEMS = {
    carrot:{name:'萝卜',price:2},wheat:{name:'小麦',price:3},grass:{name:'牧草',price:1},rice:{name:'水稻',price:3},
    flour:{name:'面粉',price:8},riceflour:{name:'米粉',price:8},bread:{name:'面包',price:18},ricecake:{name:'米糕',price:20},milk:{name:'牛奶',price:9},meal:{name:'大白饭',price:12}
  };
  const BUILDINGS = {
    house:{name:'农舍',cost:0,desc:'大肥鱼们在这里吃饭。'},
    store:{name:'仓库',cost:90,desc:'增加 80 格库存。'},
    well:{name:'水井',cost:60,desc:'灌溉周围一圈，可种水稻；作物快 10%。'},
    kitchen:{name:'小灶台',cost:80,recipe:'meal',desc:'水稻 ×2 → 大白饭 ×1 · 50 秒'},
    mill:{name:'磨坊',cost:200,recipe:'flour',unlockLevel:2,desc:'小麦 ×3 → 面粉 ×2 · 45 秒；也可选水稻 ×3 → 米粉 ×2。'},
    bakery:{name:'面包房',cost:300,recipe:'bread',unlockLevel:3,desc:'面粉 ×2 → 面包 ×2 · 90 秒；也可选米粉 ×2 → 米糕 ×2。'},
    cows:{name:'牛棚',cost:220,recipe:'milk',unlockLevel:4,desc:'牧草 ×3 → 牛奶 ×2 · 60 秒'}
  };
  const RECIPES = {
    meal:{input:'rice',amount:2,time:50000,qty:1,building:'kitchen'},
    flour:{input:'wheat',amount:3,time:45000,qty:2,building:'mill'},
    riceflour:{input:'rice',amount:3,time:45000,qty:2,building:'mill',unlockLevel:3},
    bread:{input:'flour',amount:2,time:90000,qty:2,building:'bakery'},
    ricecake:{input:'riceflour',amount:2,time:90000,qty:2,building:'bakery',unlockLevel:3},
    milk:{input:'grass',amount:3,time:60000,qty:2,building:'cows'}
  };
  const RECRUITS = [{gold:200,meal:3},{gold:500,meal:8},{gold:900,meal:15},{gold:1500,meal:25}];
  const BASE_RESERVE = {carrot:0,wheat:12,grass:6,rice:8,flour:4,riceflour:4,bread:0,ricecake:0,milk:0,meal:30};
  const ORDER_POOL = [
    {item:'carrot',qty:8,pay:20},{item:'wheat',qty:12,pay:45},{item:'rice',qty:9,pay:35},
    {item:'grass',qty:18,pay:24},{item:'flour',qty:6,pay:58},{item:'milk',qty:8,pay:85},
    {item:'bread',qty:6,pay:128},{item:'meal',qty:4,pay:60},
    {item:'riceflour',qty:6,pay:58},{item:'ricecake',qty:6,pay:142}
  ];
  const idx=(x,y)=>y*MAX+x;
  const inside=(x,y)=>Number.isInteger(x)&&Number.isInteger(y)&&x>=0&&y>=0&&x<MAX&&y<MAX;
  const coord=i=>[i%MAX,Math.floor(i/MAX)];
  const clone=v=>JSON.parse(JSON.stringify(v));
  const total=s=>Object.values(s.inventory).reduce((a,b)=>a+b,0);
  const count=(s,type,kind)=>s.tiles.filter(t=>t&&t.type===type&&(!kind||t.kind===kind)).length;
  const owned=s=>s.tiles.reduce((n,t)=>n+(t?1:0),0);
  function farmLevel(s){let level=1;for(const row of LEVELS)if((s.xp||0)>=row.xp)level=row.level;else break;return level;}
  function levelProgress(s){const level=farmLevel(s),current=LEVELS[level-1],next=LEVELS[level]||null;return {level,title:current.title,xp:Math.max(0,Math.floor(s.xp||0)),currentXp:current.xp,nextXp:next?.xp??current.xp,remaining:next?Math.max(0,next.xp-(s.xp||0)):0,progress:next?Math.max(0,Math.min(1,((s.xp||0)-current.xp)/(next.xp-current.xp))):1,next};}
  function canBuild(s,kind){const b=BUILDINGS[kind];return !!b&&farmLevel(s)>=(b.unlockLevel||1);}
  function recipesFor(kind){return Object.keys(RECIPES).filter(item=>RECIPES[item].building===kind);}
  function canUseRecipe(state,kind,item){const r=RECIPES[item];return !!r&&r.building===kind&&farmLevel(state)>=(r.unlockLevel||1);}
  function recipeFor(tile){
    if(!tile||tile.type!=='building')return null;const fallback=BUILDINGS[tile.kind]?.recipe;if(!fallback)return null;
    const next=tile.nextRecipe;return next&&RECIPES[next]&&RECIPES[next].building===tile.kind?next:fallback;
  }
  const capacity=s=>80+count(s,'building','store')*80+s.storageLevel*100+Math.max(0,farmLevel(s)-4)*20;
  function gainXp(s,amount){
    const before=farmLevel(s);s.xp=Math.min(1000000,Math.max(0,Math.floor((s.xp||0)+amount)));
    const after=farmLevel(s);if(after<=before)return 0;
    let reward=0;for(let level=before+1;level<=after;level++)reward+=LEVELS[level-1]?.reward||0;
    s.gold+=reward;const unlocks=LEVELS.slice(before,after).map(v=>v.unlock&&BUILDINGS[v.unlock]?.name).filter(Boolean);
    if(s.shops&&after>=3)s.shops.food.open=true;
    s.lastNotice=`庄园升到 Lv.${after}，获得 ${reward} 金币${unlocks.length?`，解锁${unlocks.join('、')}`:''}。`;return after-before;
  }
  function inferLegacyXp(raw,s){
    const stats=raw.stats||{};let xp=Math.floor(num(stats.harvests)*3+num(stats.orders)*12+num(stats.expansions)*8+(s.workers?.length||0)*10+count(s,'building')*8+num(raw.toolLevel)*6+num(raw.storageLevel)*4);
    for(const [kind,level] of [['mill',2],['bakery',3],['cows',4]])if(count(s,'building',kind))xp=Math.max(xp,LEVELS[level-1].xp);
    return Math.min(1000000,xp);
  }
  const ripe=(s,t)=>!!(t&&t.type==='field'&&t.crop&&t.readyAt<=s.time);
  const result=(ok,message,extra={})=>Object.assign({ok,message},extra);
  function initial(wall=Date.now()) {
    const s={version:SAVE_VERSION,time:0,savedAt:wall,gold:100,xp:0,inventory:Object.fromEntries(Object.keys(ITEMS).map(k=>[k,0])),tiles:Array(256).fill(null),workers:[],nextWorkAt:STEP,toolLevel:0,storageLevel:0,legacyJobs:[],activeOrder:null,orderRound:0,shops:{produce:{open:true,item:null,qty:0,nextAt:null},food:{open:false,item:null,qty:0,nextAt:null}},options:{autoSell:true,reducedMotion:false},stats:{harvests:0,goods:0,sold:0,earned:0,orders:0,expansions:0},lastNotice:'点亮的田地已经成熟，点一下就能收好再种。'};
    for(let y=0;y<4;y++)for(let x=0;x<4;x++)s.tiles[idx(x,y)]={type:'grass'};
    s.tiles[idx(0,0)]={type:'building',kind:'house',paused:false,job:null};
    s.tiles[idx(1,0)]={type:'building',kind:'store',paused:false,job:null};
    s.tiles[idx(1,1)]={type:'building',kind:'well',paused:false,job:null};
    for(const [x,y,crop,ready] of [[0,2,'carrot',true],[1,2,'carrot',true],[2,2,'wheat',false],[2,1,'rice',false]]){
      const t={type:'field',plan:crop,crop:null,startedAt:null,readyAt:null};s.tiles[idx(x,y)]=t;
      if(ready){t.crop=crop;t.startedAt=-CROPS[crop].time;t.readyAt=0;}
    }
    return s;
  }
  function irrigated(s,x,y){
    if(!inside(x,y))return false;
    for(let yy=Math.max(0,y-1);yy<=Math.min(15,y+1);yy++)for(let xx=Math.max(0,x-1);xx<=Math.min(15,x+1);xx++)if(s.tiles[idx(xx,yy)]?.kind==='well')return true;
    return false;
  }
  function reserve(s,k){return BASE_RESERVE[k]+(s.activeOrder?.item===k?s.activeOrder.qty:0);}
  function orderLock(s,k){return s.activeOrder?.item===k?s.activeOrder.qty:0;}
  function availableInput(state,recipeItem){const r=RECIPES[recipeItem];return r?Math.max(0,(state.inventory[r.input]||0)-orderLock(state,r.input)):0;}
  function addExact(s,k,qty){if(total(s)+qty>capacity(s))return false;s.inventory[k]+=qty;return true;}
  const WHOLESALE_MIN=6, RETAIL_LIMIT=6, RETAIL_INTERVAL=20000;
  const PRODUCE_ITEMS=new Set(Object.keys(CROPS));
  const FOOD_ITEMS=new Set(Object.keys(ITEMS).filter(k=>!PRODUCE_ITEMS.has(k)));
  function shopForItem(k){return PRODUCE_ITEMS.has(k)?'produce':FOOD_ITEMS.has(k)?'food':null;}
  function sellable(s,k){return Math.max(0,(s.inventory[k]||0)-reserve(s,k));}
  function wholesaleQuote(s,k,requested){
    const shop=shopForItem(k),available=sellable(s,k);
    const qty=requested===undefined?available:Math.min(available,Math.max(0,Math.floor(requested)));
    return {item:k,available,qty,minimum:WHOLESALE_MIN,unitPrice:ITEMS[k]?.price||0,total:qty*(ITEMS[k]?.price||0),ok:!!shop&&qty>=WHOLESALE_MIN};
  }
  function wholesale(s,k,requested,expected){
    const q=wholesaleQuote(s,k,requested);
    if(expected&&(expected.item!==k||expected.qty!==q.qty||expected.unitPrice!==q.unitPrice))return result(false,'报价已变化，请重新确认当前数量与价格。',{quote:q});
    if(!q.ok)return result(false,`${ITEMS[k]?.name||'商品'}不足 ${WHOLESALE_MIN} 份起售量；当前可批发 ${q.available} 份。`,{quote:q});
    s.inventory[k]-=q.qty;s.gold+=q.total;s.stats.sold+=q.qty;s.stats.earned+=q.total;
    return result(true,`批发${ITEMS[k].name} ${q.qty} 份，收入 ${q.total} 金币。`,{quote:q,quantity:q.qty,earned:q.total});
  }
  function retailPrice(k){const item=ITEMS[k];return item?Math.max(item.price+1,Math.ceil(item.price*1.25)):0;}
  function retailShopFor(k){return PRODUCE_ITEMS.has(k)?'produce':FOOD_ITEMS.has(k)?'food':null;}
  function retailQuote(s,shopKey,k,requested){
    const shop=s.shops?.[shopKey],owned=retailShopFor(k)===shopKey,open=!!shop?.open,available=sellable(s,k);
    const shelfUsed=shop?.item===k?Math.max(0,Math.min(RETAIL_LIMIT,Math.floor(Number(shop.qty)||0))):0;
    const free=shop?.item&&shop.item!==k?0:Math.max(0,RETAIL_LIMIT-shelfUsed);
    const qty=Math.min(available,Math.max(0,Math.floor(Number(requested)||0)),free),unitPrice=retailPrice(k);
    let reason='';
    if(!shop||!open)reason='这间店还没有开张。';
    else if(!owned)reason='这间店不能卖这种商品。';
    else if(shop.item&&shop.item!==k)reason=`先卖完或退回货架上的${ITEMS[shop.item].name}，再换商品。`;
    else if(free<1)reason='货架已经满了，先等顾客购买或退回商品。';
    else if(available<1)reason=`${ITEMS[k]?.name||'商品'}没有可上架余货。`;
    const canList=!!shop&&open&&owned&&(!shop.item||shop.item===k)&&free>0&&available>0;
    return {item:k,shop:shopKey,owned,open,available,capacity:RETAIL_LIMIT,free,qty,unitPrice,total:qty*unitPrice,canList,ok:canList&&qty>0,reason};
  }
  function retailReturnQuote(s,shopKey){
    const shop=s.shops?.[shopKey];
    if(!shop||!shop.item||shop.qty<=0)return {shop:shopKey,item:null,qty:0,missing:0,ok:false,reason:'货架上没有未售商品。'};
    const qty=shop.qty,missing=Math.max(0,total(s)+qty-capacity(s));
    return {shop:shopKey,item:shop.item,qty,missing,ok:missing===0,reason:missing?`仓库空间不足，还差 ${missing} 格；货架商品没有改变。`:''};
  }
  function listRetail(s,shopKey,k,requested,expected){
    const shop=s.shops?.[shopKey],quote=retailQuote(s,shopKey,k,requested);
    if(expected&&(expected.item!==k||expected.qty!==quote.qty||expected.unitPrice!==quote.unitPrice))return result(false,'上架报价已变化，请重新确认。',{quote});
    if(!quote.ok){
      const message=quote.reason||(quote.available<1?`${ITEMS[k]?.name||'商品'}没有可上架余货。`:'货架已经满了，先等顾客购买或退回商品。');
      return result(false,message,{quote});
    }
    s.inventory[k]-=quote.qty;shop.item=k;shop.qty+=quote.qty;if(shop.nextAt===null||shop.nextAt===undefined)shop.nextAt=s.time+RETAIL_INTERVAL;
    return result(true,`已将${ITEMS[k].name} ${quote.qty} 份放上${shopKey==='produce'?'农产铺':'食品铺'}，零售价 ${quote.unitPrice} 金币，顾客会自动购买。`,{quote,quantity:quote.qty});
  }
  function returnRetail(s,shopKey){
    const quote=retailReturnQuote(s,shopKey);if(!quote.ok)return result(false,quote.reason,{quote});
    const shop=s.shops[shopKey],k=quote.item,qty=quote.qty;
    s.inventory[k]+=qty;shop.item=null;shop.qty=0;shop.nextAt=null;
    return result(true,`已退回${ITEMS[k].name} ${qty} 份，金币没有变化。`,{quantity:qty,quote});
  }
  function retailSettle(s){
    let sold=0;
    for(const [key,shop] of Object.entries(s.shops||{})){
      if(!shop?.open||!shop.item||shop.qty<=0||shop.nextAt===null||shop.nextAt>s.time)continue;
      const k=shop.item,price=retailPrice(k);
      shop.qty--;s.gold+=price;s.stats.sold++;s.stats.earned+=price;sold++;
      if(shop.qty>0)shop.nextAt+=RETAIL_INTERVAL;else{shop.item=null;shop.nextAt=null;}
    }
    return sold;
  }
  function sellSurplus(s,force=false){
    if(!force&&!s.options.autoSell)return 0;
    let gold=0;
    for(const k of Object.keys(ITEMS)){
      let q=sellable(s,k);
      // Keep a small, explicit listing opportunity for each item that has an open shop.
      if(!force&&s.shops?.[shopForItem(k)]?.open)q=Math.max(0,q-2);
      if(q>=WHOLESALE_MIN){s.inventory[k]-=q;gold+=q*ITEMS[k].price;s.stats.sold+=q;}
    }
    s.gold+=gold;s.stats.earned+=gold;return gold;
  }
  function completeOrder(s){
    const o=s.activeOrder;if(!o||s.inventory[o.item]<o.qty)return false;
    s.inventory[o.item]-=o.qty;s.gold+=o.pay;s.stats.earned+=o.pay;s.stats.orders++;s.orderRound++;s.activeOrder=null;
    s.lastNotice=`订单已自动交付，收入 ${o.pay} 金币。`;gainXp(s,12);return true;
  }
  function plant(s,i,crop){
    const t=s.tiles[i];if(!CROPS[crop]||!t||t.type!=='field'||t.crop)return false;
    const [x,y]=coord(i),water=irrigated(s,x,y);if(crop==='rice'&&!water)return false;
    t.plan=crop;t.crop=crop;t.startedAt=s.time;t.readyAt=s.time+Math.round(CROPS[crop].time*(water?.9:1));return true;
  }
  function collect(s,i,replant=true){
    const t=s.tiles[i];if(!ripe(s,t))return false;
    const crop=t.crop;if(!addExact(s,crop,CROPS[crop].yield))return false;
    s.stats.harvests++;s.stats.goods+=CROPS[crop].yield;gainXp(s,3);t.crop=null;t.startedAt=null;t.readyAt=null;
    if(t.retire){s.tiles[i]={type:'grass'};return true;}
    if(replant)plant(s,i,t.plan||crop);
    return true;
  }
  function finishJobs(s){
    let completed=0;
    for(const t of s.tiles){if(!t?.job||t.job.readyAt>s.time)continue;const r=RECIPES[t.job.item];if(addExact(s,t.job.item,r.qty)){s.stats.goods+=r.qty;gainXp(s,5);t.job=null;completed++;}}
    s.legacyJobs=s.legacyJobs.filter(j=>{if(j.readyAt>s.time)return true;const r=RECIPES[j.item];if(!addExact(s,j.item,r.qty))return true;s.stats.goods+=r.qty;completed++;return false;});
    return completed;
  }
  function startMachines(s){
    // A building owns exactly one production slot. Materials are charged only at start.
    for(const t of s.tiles){if(t?.type!=='building'||t.paused||t.job)continue;
      const fallback=BUILDINGS[t.kind]?.recipe;if(!fallback)continue;
      let item=recipeFor(t);if(!canUseRecipe(s,t.kind,item))item=fallback;
      const r=RECIPES[item];
      if(availableInput(s,item)>=r.amount){s.inventory[r.input]-=r.amount;t.job={item,startedAt:s.time,readyAt:s.time+r.time};}
    }
  }
  function workerSweep(s){
    const tasks=[];
    for(let i=0;i<256;i++){const t=s.tiles[i];if(ripe(s,t))tasks.push({i,at:t.readyAt,priority:0});else if(t?.type==='field'&&!t.crop&&t.plan)tasks.push({i,at:s.time,priority:1});}
    tasks.sort((a,b)=>a.priority-b.priority||a.at-b.at||a.i-b.i);
    const batch=2**(s.toolLevel+1);
    for(const w of s.workers){let done=0;w.status='idle';
      while(tasks.length&&done<batch){const {i}=tasks.shift(),t=s.tiles[i];let ok;
        if(ripe(s,t)){sellSurplus(s);ok=collect(s,i,true);}else ok=plant(s,i,t.plan);
        if(ok){w.target=i;w.lastAt=s.time;w.status='working';w.handled++;done++;completeOrder(s);sellSurplus(s);}
      }
    }
  }
  function settle(s,runWorkers=true){
    // Selling and order delivery can unblock a full output slot without losing a batch.
    completeOrder(s);sellSurplus(s);finishJobs(s);completeOrder(s);sellSurplus(s);retailSettle(s);
    if(runWorkers&&s.workers.length&&s.nextWorkAt<=s.time){workerSweep(s);s.nextWorkAt=s.time+STEP;}
    startMachines(s);
    // Starting a batch, delivering an order, or leveling up can free warehouse
    // space for an already finished batch. Settle those at this logical instant,
    // not at the next browser tick. Every retry retires at least one existing
    // job; newly started jobs finish strictly later. Workers run only once above.
    for(let remaining=s.tiles.length+s.legacyJobs.length;remaining>0;remaining--){
      if(!finishJobs(s))break;
      completeOrder(s);sellSurplus(s);retailSettle(s);startMachines(s);
    }
  }
  function advance(s,elapsed){
    if(!Number.isFinite(elapsed)||elapsed<0)throw new Error('时间增量必须是非负有限数。');
    const target=s.time+Math.min(elapsed,OFFLINE_CAP);settle(s);
    let loops=0;
    while(s.time<target){
      let next=target;
      if(s.workers.length&&s.nextWorkAt>s.time)next=Math.min(next,s.nextWorkAt);
      for(const shop of Object.values(s.shops||{}))if(shop?.item&&shop.qty>0&&shop.nextAt>s.time)next=Math.min(next,shop.nextAt);
      for(const t of s.tiles)if(t?.job?.readyAt>s.time)next=Math.min(next,t.job.readyAt);
      for(const j of s.legacyJobs)if(j.readyAt>s.time)next=Math.min(next,j.readyAt);
      if(next<=s.time)throw new Error('模拟时钟未前进。');
      s.time=next;settle(s);if(++loops>100000)throw new Error('模拟事件过多。');
    }
    return s;
  }
  function tend(s,i,chosen='carrot'){
    if(!Number.isInteger(i)||i<0||i>=256||!CROPS[chosen])return result(false,'请选择农场内的地块。');
    const t=s.tiles[i];if(!t)return result(false,'这里还没有开垦，点「扩地」购买相邻土地。');
    if(t.type==='building')return result(true,'building',{open:i});
    if(ripe(s,t)){sellSurplus(s);if(!collect(s,i,true))return result(false,'仓库装不下整批收成。出售余粮或扩容后再收，不会丢失作物。');settle(s,false);return result(true,'已经收好，按原来的计划补种。',{harvested:1});}
    if(t.type==='field'&&t.crop)return result(true,'field',{open:i});
    const crop=chosen,[x,y]=coord(i);
    if(crop==='rice'&&!irrigated(s,x,y))return result(false,'水稻要种在水井旁边，浅蓝色标记的格子都可以。');
    if(t.type==='grass'){if(s.gold<12)return result(false,'新开一块田需要 12 金币，现有田地补种免费。');s.gold-=12;s.tiles[i]={type:'field',plan:crop,crop:null,startedAt:null,readyAt:null};}
    plant(s,i,crop);settle(s,false);return result(true,`已种下${CROPS[crop].name}，成熟后点一下就能收好再种。`);
  }
  function tendAll(s){
    let harvested=0,planted=0,blocked=0;sellSurplus(s);
    for(let i=0;i<256;i++){const t=s.tiles[i];if(ripe(s,t)){if(collect(s,i,true)){harvested++;completeOrder(s);sellSurplus(s);}else blocked++;}
      else if(t?.type==='field'&&!t.crop&&t.plan&&plant(s,i,t.plan))planted++;
    }
    settle(s,false);return result(harvested+planted>0,blocked?`收好并补种 ${harvested} 块田；另有 ${blocked} 块因满仓暂存田里。`:`收好并补种 ${harvested} 块田${planted?`，补种空田 ${planted} 块`:''}。`,{harvested,planted,blocked});
  }
  function changePlan(s,i,crop){
    const t=s.tiles[i];if(!t||t.type!=='field'||!CROPS[crop])return result(false,'请选择一种作物。');
    if(crop==='rice'&&!irrigated(s,...coord(i)))return result(false,'这块田不在水井旁边，暂时不能种水稻。');
    t.plan=crop;delete t.retire;if(!t.crop)plant(s,i,crop);return result(true,t.crop!==crop?`这轮不浪费，下轮改种${CROPS[crop].name}。`:`这块田继续种${CROPS[crop].name}。`);
  }
  function reclaim(s,i){
    const t=s.tiles[i];if(!t||t.type!=='field')return result(false,'请选择一块田。');
    if(t.crop){t.retire=true;return result(true,'这轮收获后自动腾成空地，现有作物不会浪费。');}
    s.tiles[i]={type:'grass'};return result(true,'已经腾成空地，可以摆放建筑。');
  }
  function build(s,i,kind){
    if(!BUILDINGS[kind]||kind==='house')return result(false,'不能建造这个建筑。');
    if(!Number.isInteger(i)||i<0||i>=256||s.tiles[i]?.type!=='grass')return result(false,'请把建筑放在空草地上。');
    const b=BUILDINGS[kind];if(!canBuild(s,kind))return result(false,`${b.name}需要庄园等级 Lv.${b.unlockLevel||1}。`);if(s.gold<b.cost)return result(false,`还差 ${b.cost-s.gold} 金币。`);
    s.gold-=b.cost;s.tiles[i]={type:'building',kind,paused:false,job:null};gainXp(s,8);settle(s,false);
    return result(true,`${b.name}建好了${b.recipe?'，有原料就会自动开工':''}。`);
  }
  function expansionCost(s){return 60+Math.max(0,Math.floor(owned(s)/4)-4)*20;}
  function eligibleChunks(s){
    const list=[];
    for(let y=0;y<16;y+=2)for(let x=0;x<16;x+=2){
      let empty=true,touch=false;
      for(let dy=0;dy<2;dy++)for(let dx=0;dx<2;dx++){if(s.tiles[idx(x+dx,y+dy)])empty=false;
        for(const [ax,ay] of [[-1,0],[1,0],[0,-1],[0,1]]){const xx=x+dx+ax,yy=y+dy+ay;if(inside(xx,yy)&&s.tiles[idx(xx,yy)])touch=true;}
      }
      if(empty&&touch)list.push({x,y});
    }
    return list;
  }
  function expand(s,x,y){
    if(!eligibleChunks(s).some(c=>c.x===x&&c.y===y))return result(false,'请选择高亮的相邻 2×2 土地。');
    const cost=expansionCost(s);if(s.gold<cost)return result(false,`扩地需要 ${cost} 金币，还差 ${cost-s.gold}。`);
    s.gold-=cost;for(let dy=0;dy<2;dy++)for(let dx=0;dx<2;dx++)s.tiles[idx(x+dx,y+dy)]={type:'grass'};
    s.stats.expansions++;gainXp(s,8);return result(true,'多了 4 格土地，选一种作物就能直接种下。');
  }
  function recruit(s){
    const n=s.workers.length;if(n>=4)return result(false,'四只大肥鱼都到齐了。');
    const r=RECRUITS[n];if(s.gold<r.gold||s.inventory.meal<r.meal)return result(false,`招募需要 ${r.gold} 金币和 ${r.meal} 碗大白饭。`);
    s.gold-=r.gold;s.inventory.meal-=r.meal;s.workers.push({id:n+1,target:null,lastAt:s.time,status:'idle',handled:0});gainXp(s,10);
    s.nextWorkAt=Math.min(s.nextWorkAt,s.time);settle(s);return result(true,`第 ${n+1} 只大肥鱼到岗，收获和补种交给她了。`);
  }
  function toolUpgradeOffer(s){
    const cost=[180,600,1600][s.toolLevel]??null;
    const message=cost===null?'农具已经升满。':!s.workers.length?'先招来第一位帮手。':s.gold<cost?`升级农具需要 ${cost} 金币。`:'';
    return {cost,ok:!message,message};
  }
  function storageUpgradeOffer(s){const cost=120+s.storageLevel*100,message=s.gold<cost?`仓库扩容需要 ${cost} 金币。`:'';return {cost,ok:!message,message};}
  function upgradeTools(s){const offer=toolUpgradeOffer(s);if(!offer.ok)return result(false,offer.message);s.gold-=offer.cost;s.toolLevel++;gainXp(s,6);return result(true,`每位工人每轮最多照料 ${2**(s.toolLevel+1)} 块田。`);}
  function upgradeStorage(s){const offer=storageUpgradeOffer(s);if(!offer.ok)return result(false,offer.message);s.gold-=offer.cost;s.storageLevel++;gainXp(s,6);settle(s,false);return result(true,'仓库多了 100 格，不占新土地。');}
  function availableOrders(s){
    const eligible=ORDER_POOL.filter(o=>{
      if(o.item==='meal')return s.workers.length===4;
      const r=RECIPES[o.item];if(!r)return true;
      if(!count(s,'building',r.building)||farmLevel(s)<(r.unlockLevel||1))return false;
      // The new ricecake order needs both workshops in its processing chain.
      return o.item!=='ricecake'||count(s,'building','mill')>0;
    });
    return Array.from({length:Math.min(3,eligible.length)},(_,i)=>clone(eligible[(s.orderRound+i)%eligible.length]));
  }
  function acceptOrder(s,index,expected){
    if(s.activeOrder)return result(false,'先完成手上的订单。');const o=availableOrders(s)[index];
    // A background level-up can change which quote occupies a visible index.
    if(expected!==undefined&&(!o||o.item!==expected?.item||o.qty!==expected?.qty||o.pay!==expected?.pay))return result(false,'订单已更新，请重新选择。');
    if(!o)return result(false,'订单不存在。');s.activeOrder=o;settle(s,false);return result(true,`已经接单，${ITEMS[o.item].name}会优先留给订单，凑齐后自动交付。`);
  }
  function cancelOrder(s){s.activeOrder=null;settle(s,false);return result(true,'已取消订单，没有扣款。');}
  function toggleMachine(s,i){const t=s.tiles[i];if(!t||!BUILDINGS[t.kind]?.recipe)return result(false,'这不是加工建筑。');t.paused=!t.paused;settle(s,false);return result(true,t.paused?(t.job?'当前这一批完成后停工。':'已暂停，恢复后才开工。'):'已恢复自动加工。');}
  function changeRecipe(s,i,item){
    const t=s.tiles[i];if(!t||t.type!=='building'||!BUILDINGS[t.kind]?.recipe)return result(false,'这里不是可切换产品的工坊。');
    if(!canUseRecipe(s,t.kind,item))return result(false,`${BUILDINGS[t.kind].name}不能制作这个产品，或庄园等级不足。`);
    if(recipeFor(t)===item&&t.nextRecipe===item)return result(true,`下一批继续做${ITEMS[item].name}。`);
    t.nextRecipe=item;startMachines(s);return result(true,`下一批改为${ITEMS[item].name}；当前在制的一批按原配方完成。`);
  }
  function toggleSale(s){s.options.autoSell=!s.options.autoSell;settle(s,false);return result(true,s.options.autoSell?'自动售货已开启，会保留原料和大白饭。':'已暂停自动售货，收成会留在仓库。');}
  function unlockFoodShop(s){const shop=s.shops.food;if(farmLevel(s)>=3)shop.open=true;return shop.open;}
  function move(s,from,to){
    const t=s.tiles[from];if(!t||s.tiles[to]?.type!=='grass')return result(false,'请移动到空草地。');
    if(t.type!=='building')return result(false,'只需要搬建筑，田地可直接调整下轮作物。');
    // A moved well must not strand an existing rice plan.
    s.tiles[to]=t;s.tiles[from]={type:'grass'};
    for(let i=0;i<256;i++)if(s.tiles[i]?.type==='field'&&(s.tiles[i].crop==='rice'||s.tiles[i].plan==='rice')&&!irrigated(s,...coord(i))){s.tiles[from]=t;s.tiles[to]={type:'grass'};return result(false,'这口井还在给水稻供水，先补一口井或调整稻田。');}
    return result(true,'已经搬好，生产进度保留，不收搬家费。');
  }
  const num=(v,min=0,max=1e12)=>typeof v==='number'&&Number.isFinite(v)?Math.max(min,Math.min(max,v)):min;
  function restore(raw,wall=Date.now()){
    if(!raw||typeof raw!=='object'||!((raw.version===2||raw.version===SAVE_VERSION)||raw.ver===1))throw new Error('这不是可识别的庄园存档。');
    if(raw.ver===1)return migrate(raw,wall);
    if(!Array.isArray(raw.tiles)||raw.tiles.length!==256)throw new Error('存档地图格式不正确。');
    const s=initial(wall);s.time=num(raw.time);s.savedAt=num(raw.savedAt,0,wall);s.gold=num(raw.gold);s.toolLevel=Math.floor(num(raw.toolLevel,0,3));s.storageLevel=Math.floor(num(raw.storageLevel,0,100));
    for(const k of Object.keys(ITEMS))s.inventory[k]=Math.floor(num(raw.inventory?.[k],0,1e8));
    s.tiles=raw.tiles.map(t=>{
      if(t===null)return null;if(!t||!['grass','field','building'].includes(t.type))throw new Error('存档含有无法识别的地块。');
      if(t.type==='grass')return {type:'grass'};
      if(t.type==='field'){const crop=CROPS[t.crop]?t.crop:null,plan=CROPS[t.plan]?t.plan:crop||'carrot';return {type:'field',plan,crop,startedAt:crop?num(t.startedAt,-1e12):null,readyAt:crop?num(t.readyAt):null,...(t.retire?{retire:true}:{})};}
      if(!BUILDINGS[t.kind])throw new Error('存档含有未知建筑。');
      const nextRecipe=typeof t.nextRecipe==='string'&&RECIPES[t.nextRecipe]&&RECIPES[t.nextRecipe].building===t.kind?t.nextRecipe:undefined;
      let job=null;if(t.job&&RECIPES[t.job.item]&&RECIPES[t.job.item].building===t.kind)job={item:t.job.item,startedAt:num(t.job.startedAt,-1e12),readyAt:num(t.job.readyAt)};
      return {type:'building',kind:t.kind,paused:!!t.paused,job,...(nextRecipe?{nextRecipe}:{})};
    });
    if(owned(s)<4||count(s,'building','house')<1)throw new Error('存档缺少农舍或土地。');
    // Imported v0.1 maps may not follow 2×2 boundaries; normalize the containing chunks.
    alignOwned(s);
    s.workers=Array.from({length:Math.min(4,Array.isArray(raw.workers)?raw.workers.length:0)},(_,i)=>({id:i+1,target:null,lastAt:s.time,status:'idle',handled:num(raw.workers[i]?.handled)}));
    s.nextWorkAt=Math.max(s.time,num(raw.nextWorkAt));
    s.options={autoSell:raw.options?.autoSell!==false,reducedMotion:!!raw.options?.reducedMotion};
    if(raw.shops&&typeof raw.shops==='object')for(const key of ['produce','food']){const old=raw.shops[key],shop=s.shops[key];if(!old||typeof old!=='object')continue;const allowed=key==='produce'?PRODUCE_ITEMS:FOOD_ITEMS;const item=allowed.has(old.item)?old.item:null;const qty=item?Math.min(RETAIL_LIMIT,Math.floor(num(old.qty,0,RETAIL_LIMIT))):0;shop.open=key==='produce'?true:!!old.open&&farmLevel(s)>=3;shop.item=qty?item:null;shop.qty=qty;shop.nextAt=qty?(Number.isFinite(old.nextAt)?Math.max(s.time,num(old.nextAt)):s.time+RETAIL_INTERVAL):null;}
    for(const k of Object.keys(s.stats))s.stats[k]=num(raw.stats?.[k]);s.orderRound=Math.floor(num(raw.orderRound,0,1e6));
    s.xp=Number.isFinite(raw.xp)?Math.floor(num(raw.xp,0,1000000)):inferLegacyXp(raw,s);
    unlockFoodShop(s);
    for(const t of s.tiles){
      if(t?.type!=='building')continue;const fallback=BUILDINGS[t.kind]?.recipe;
      if(!fallback||!t.nextRecipe||t.nextRecipe===fallback||!canUseRecipe(s,t.kind,t.nextRecipe))delete t.nextRecipe;
    }
    const o=raw.activeOrder;if(o&&ORDER_POOL.some(p=>p.item===o.item&&p.qty===o.qty&&p.pay===o.pay))s.activeOrder=clone(o);
    s.legacyJobs=Array.isArray(raw.legacyJobs)?raw.legacyJobs.filter(j=>RECIPES[j?.item]).slice(0,500).map(j=>({item:j.item,readyAt:num(j.readyAt)})):[];
    if(total(s)>capacity(s))s.storageLevel+=Math.ceil((total(s)-capacity(s))/100);
    return s;
  }
  function alignOwned(s){for(let y=0;y<16;y+=2)for(let x=0;x<16;x+=2){const ids=[idx(x,y),idx(x+1,y),idx(x,y+1),idx(x+1,y+1)];if(ids.some(i=>s.tiles[i]))for(const i of ids)if(!s.tiles[i])s.tiles[i]={type:'grass'};}}
  function migrate(raw,wall){
    const s=initial(wall),oldAt=num(raw.last,0,wall);s.gold=num(raw.gold);s.options.autoSell=false;
    for(const k of Object.keys(ITEMS))s.inventory[k]=Math.floor(num(raw.inventory?.[k],0,1e8));
    s.tiles=Array(256).fill(null);
    for(const [key,t] of Object.entries(raw.tiles||{})){const i=Number(key);if(!Number.isInteger(i)||i<0||i>=256)continue;
      if(t.type==='building'&&BUILDINGS[t.kind])s.tiles[i]={type:'building',kind:t.kind,paused:false,job:null};
      else if(t.type==='field'){const crop=CROPS[t.crop]?t.crop:null,remaining=num((t.readyAt||oldAt)-oldAt);s.tiles[i]={type:'field',plan:crop||'carrot',crop,readyAt:crop?remaining:null,startedAt:crop?remaining-CROPS[crop].time:null};}
      else s.tiles[i]={type:'grass'};
    }
    if(owned(s)<4||!count(s,'building','house'))throw new Error('旧存档不完整。');alignOwned(s);
    s.workers=Array.from({length:Math.min(4,raw.workers?.length||0)},(_,i)=>({id:i+1,target:null,lastAt:0,status:'idle',handled:0}));
    s.legacyJobs=(raw.jobs||[]).filter(j=>RECIPES[j.item]).slice(0,500).map(j=>({item:j.item,readyAt:num(j.readyAt-oldAt)}));
    s.savedAt=oldAt;s.stats.orders=num(raw.completed);s.xp=inferLegacyXp(raw,s);unlockFoodShop(s);if(total(s)>capacity(s))s.storageLevel=Math.ceil((total(s)-capacity(s))/100);
    s.lastNotice='旧存档已复制到新版；为保护库存，自动售货暂时关闭。原存档没有改动。';return s;
  }
  return {MAX,STEP,OFFLINE_CAP,SAVE_VERSION,CROPS,ITEMS,BUILDINGS,RECIPES,RECRUITS,LEVELS,BASE_RESERVE,ORDER_POOL,WHOLESALE_MIN,RETAIL_LIMIT,RETAIL_INTERVAL,idx,coord,clone,total,count,owned,capacity,farmLevel,levelProgress,canBuild,recipesFor,canUseRecipe,recipeFor,ripe,initial,irrigated,reserve,availableInput,addExact,sellable,retailPrice,retailShopFor,retailQuote,retailReturnQuote,wholesaleQuote,wholesale,listRetail,returnRetail,retailSettle,sellSurplus,plant,collect,settle,advance,tend,tendAll,changePlan,reclaim,build,expansionCost,eligibleChunks,expand,recruit,toolUpgradeOffer,storageUpgradeOffer,upgradeTools,upgradeStorage,availableOrders,acceptOrder,cancelOrder,toggleMachine,changeRecipe,toggleSale,move,restore,migrate};
});
