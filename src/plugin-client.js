/* DSH entrypoint. Only React is required from the host's module loader.
 * No HTTP handlers, tools, model calls, shell access, or workspace mutations.
 */
window.__ModuleLoader__.load({
 id:'dsh-plugin-white-rice-farm',
 factory(require){
  'use strict';
  const React=require('react'),h=React.createElement,ID='dsh-white-rice-farm',KEY='dsh-farm-v03',PREV='dsh-farm-v02',OLD='dsh-farm-v01';
  const GAME_HTML=/*__GAME_HTML_JSON__*/;
  const LIMIT=2*1024*1024,LOCK='dsh-white-rice-farm-save-v2';
  const safeJSON=x=>JSON.stringify(x).replace(/</g,'\\u003c');
  function Icon(){return h('span',{'aria-label':'大白饭庄园',style:{fontSize:16}},'田');}
  function allowedKey(k){return k===KEY||k===KEY+'-backup'||new RegExp('^'+KEY+'-recovery-\\d+$').test(k);}
  function validSnapshot(text){if(typeof text!=='string'||text.length>LIMIT)return false;try{const x=JSON.parse(text);return x?.version===3&&Array.isArray(x.tiles)&&x.tiles.length===256&&Number.isFinite(x.gold)&&Number.isFinite(x.time)&&Array.isArray(x.workers)&&x.workers.length<=4;}catch{return false;}}
  function makeDocument(channel,cache,available){
   const boot=`<script>window.FARM_EMBEDDED=true;window.FARM_STORAGE=(function(){const cache=${safeJSON(cache)},channel=${safeJSON(channel)};const api={available:${available},getItem:k=>Object.prototype.hasOwnProperty.call(cache,k)?cache[k]:null,setItem(k,v){if(!api.available)throw new Error('Host storage unavailable');v=String(v);cache[k]=v;parent.postMessage({kind:'farm-save',channel,key:k,value:v},'*');}};addEventListener('message',e=>{if(e.source!==parent||e.data?.channel!==channel)return;if(e.data.kind==='farm-save-error')api.available=false;if(e.data.kind==='farm-flush'&&window.FarmFlush)window.FarmFlush();});return api;})();<\/script>`;
   const csp=`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'; base-uri 'none'; form-action 'none'">`;
   return GAME_HTML.replace('<head>','<head>'+csp+boot);
  }
  class Panel extends React.Component{
   constructor(props){super(props);this.state={document:null,message:'正在打开农场…'};this.frame={current:null};this.closed=false;this.release=null;this.fallback=false;this.onMessage=this.onMessage.bind(this);}
   componentDidMount(){this.open();}
   async open(){
    if(this.closed)return;
    if(navigator.locks?.request){
     try{await navigator.locks.request(LOCK,{mode:'exclusive',ifAvailable:true},async lock=>{
      if(this.closed)return;if(!lock){this.setState({message:'农场已经在另一个窗口打开。请先关闭那一处，再点重新打开。'});return;}
      const hold=new Promise(resolve=>{this.release=resolve;});this.boot();await hold;
     });}catch(err){if(!this.closed)this.setState({message:'无法取得安全存档锁，未启动农场：'+err.message});}
    }else{
     // Fail closed: starting two writers would silently overwrite the player's progress.
     this.setState({message:'当前宿主没有提供 Web Locks，暂不启动可写农场。请先用单文件版试玩，或在支持该接口的新版宿主中测试。'});
    }
   }
   boot(){
    if(this.closed)return;const cache={};let available=true;
    try{for(const k of [KEY,PREV,OLD]){const v=localStorage.getItem(k);if(v&&v.length<=LIMIT)cache[k]=v;}const k=KEY+'-probe';localStorage.setItem(k,'1');localStorage.removeItem(k);}catch{available=false;}
    this.channel=(crypto.randomUUID?crypto.randomUUID():String(Date.now())+'-'+Math.random());
    window.addEventListener('message',this.onMessage);
    this.setState({document:makeDocument(this.channel,cache,available),message:''});
   }
   onMessage(event){
    if(this.closed||event.source!==this.frame.current?.contentWindow)return;
    const data=event.data;if(!data||data.channel!==this.channel||data.kind!=='farm-save'||!allowedKey(data.key))return;
    if(data.key.indexOf('-recovery-')<0&&!validSnapshot(data.value))return;
    if(typeof data.value!=='string'||data.value.length>LIMIT)return;
    try{localStorage.setItem(data.key,data.value);}catch{event.source.postMessage({kind:'farm-save-error',channel:this.channel},'*');}
   }
   componentWillUnmount(){
    this.closed=true;window.removeEventListener('message',this.onMessage);
    // Every action was persisted immediately; the <=5s timer delta is replayed at next mount.
    if(this.release){this.release();this.release=null;}
    if(this.frame.current)this.frame.current.srcdoc='';
   }
   render(){
    if(!this.state.document)return h('section',{style:{height:'100%',minHeight:220,display:'grid',placeContent:'center',gap:16,padding:24,background:'#f7f5ed',color:'#303d31'}},h('h2',null,'大白饭庄园'),h('p',{role:'status',style:{maxWidth:460,lineHeight:1.8}},this.state.message),h('button',{onClick:()=>this.open(),style:{padding:'10px 20px',border:'1px solid #cad3bd',borderRadius:10,background:'#fffef9',cursor:'pointer'}},'重新打开'));
    return h('iframe',{ref:node=>{this.frame.current=node;},title:'大白饭庄园',srcDoc:this.state.document,sandbox:'allow-scripts allow-downloads',referrerPolicy:'no-referrer',style:{width:'100%',height:'100%',minHeight:420,border:0,display:'block',background:'#f7f5ed'}});
   }
  }
  return {inject:['slots'],apply(ctx){
   ctx.slots.inject('sidebar.panellist',()=>ctx.slots.register({name:'sidebar.panellist',id:ID,order:53,label:()=> '大白饭庄园'},Icon));
   ctx.slots.inject('main',()=>ctx.slots.register({name:'main',key:ID},Panel));
  }};
 }
});
