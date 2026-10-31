const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs')
const path=require('node:path')
const vm=require('node:vm')
const ts=require('typescript')
const Vue=require('vue')
const {parse}=require('vue/compiler-sfc')
const root=path.resolve(__dirname,'../src')
const clone=value=>JSON.parse(JSON.stringify(value))
const tick=()=>new Promise(resolve=>setImmediate(resolve))

// Executes the real <script setup> block with Vue reactivity and controlled I/O.
function setup(name,props,api,bindings,extra={}){
  const events=[]
  const {descriptor}=parse(fs.readFileSync(path.join(root,name),'utf8'))
  const source=descriptor.scriptSetup.content.replace(/^import .*$/gm,'')
  const scope=Vue.effectScope()
  const context=vm.createContext({...Vue,console,JSON,Number,Math,Date,Set,Map,Promise,Intl,URL,
    setTimeout:()=>1,clearTimeout:()=>{},setInterval:()=>1,clearInterval:()=>{},
    document:{hidden:false,addEventListener(){},removeEventListener(){},querySelector(){return null}},
    performance:{now:()=>0},
    localStorage:{getItem:()=>null,setItem(){}},
    navigator:{clipboard:{writeText:async()=>{}},languages:['zh-CN'],language:'zh-CN'},
    matchMedia:()=>({matches:false}),
    onMounted:()=>{},onUnmounted:()=>{},defineProps:()=>props,defineEmits:()=>((...args)=>events.push(args)),
    api,t:s=>s,message:s=>s,locale:Vue.ref('zh-CN'),isDesktop:false,confirmDialog:async()=>true,...extra})
  scope.run(()=>vm.runInContext(ts.transpileModule(source+'\nglobalThis.bindings={'+bindings+'};',{
    compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText,context,{filename:name}))
  return {...context.bindings,events,dispose:()=>scope.stop()}
}

const connection=(id)=>({id,metadata:{host:`h-${id}.invalid`,destinationIP:'127.0.0.1',destinationPort:'443',process:'app'},rule:'MATCH',rulePayload:'',chains:['G','DIRECT'],upload:1,download:2})

test('memory card uses private resident RAM, preserves missing values and old backend semantics',async()=>{
  const panel=setup('ResourceMemory.vue',{},async()=>{},'sample,privateWorking,ramBytes,ramStatus')
  try{
    panel.sample.value={ram_method:'private_working_set_sum',private_working_set_total_bytes:175.7,
      private_working_set_status:'ok',total_bytes:459.9,private_total_bytes:415.7,status:'ok'}
    assert.equal(panel.ramBytes.value,175.7)
    assert.equal(panel.privateWorking.value,true)
    panel.sample.value={...panel.sample.value,private_working_set_total_bytes:null,private_working_set_status:'unavailable'}
    assert.equal(panel.ramBytes.value,null)
    assert.equal(panel.ramStatus.value,'unavailable')
    panel.sample.value={total_bytes:459.9,status:'partial'}
    assert.equal(panel.ramBytes.value,459.9)
    assert.equal(panel.privateWorking.value,false)
    assert.equal(panel.ramStatus.value,'partial')
  }finally{panel.dispose()}
})

test('connection panel resume releases the paused deep copy',async()=>{
  const connections=[connection('1'),connection('2'),connection('3')]
  const panel=setup('ConnectionPanel.vue',{connections,sampledAt:1,running:true,busy:false,active:true,configKey:'',appLabels:{}},async()=>{},'paused,frozen,togglePause,data')
  try{
    panel.togglePause();await Vue.nextTick()
    assert.equal(panel.paused.value,true)
    assert.equal(panel.frozen.value.length,3)
    assert.notEqual(panel.frozen.value,connections)
    panel.togglePause();await Vue.nextTick()
    assert.equal(panel.paused.value,false)
    assert.equal(panel.frozen.value.length,0)
    assert.equal(panel.data.value,connections)
  }finally{panel.dispose()}
})

test('connection panel keeps an active pause snapshot',async()=>{
  const connections=[connection('1')]
  const panel=setup('ConnectionPanel.vue',{connections,sampledAt:1,running:true,busy:false,active:true,configKey:'',appLabels:{}},async()=>{},'paused,frozen,togglePause,data')
  try{
    panel.togglePause();await Vue.nextTick()
    assert.equal(panel.data.value.length,1)
    assert.notEqual(panel.data.value,connections)
  }finally{panel.dispose()}
})

function proxyFixture(groups,members){
  const proxies={}
  for(let g=0;g<groups;g++){
    proxies[`G${g}`]={name:`G${g}`,type:'Selector',all:[],now:'node-0'}
    for(let i=0;i<members;i++){
      const name=`node-${i}`
      if(!proxies[name])proxies[name]={name,type:'ss'}
      proxies[`G${g}`].all.push(name)
    }
  }
  return proxies
}

function proxyProps(proxies){
  return {proxies,busy:false,pending:{},sessionKey:'k',profileId:'p',profileRevision:1,workspaceRevision:1,live:true,hasProviders:false,benchmarkAvailable:true}
}

test('proxy panel pages each group and applies a strict global render budget',async()=>{
  const panel=setup('ProxyPanel.vue',proxyProps(proxyFixture(2,250)),async()=>{},
    'groupLimit,groupPages,groupPage,groupPageCount,moveGroupPage,visibleGroups,members')
  try{
    const names=panel.visibleGroups.value[0].names
    assert.equal(panel.groupLimit('G0'),100)
    assert.equal(panel.groupPage(names,'G0').length,100)
    assert.equal(panel.groupPageCount(names,'G0'),3)
    panel.moveGroupPage(names,'G0',1);await Vue.nextTick()
    assert.equal(panel.groupPage(names,'G0')[0],'node-100')
  }finally{panel.dispose()}

  const budget=(groups,members)=>{
    const panel=setup('ProxyPanel.vue',proxyProps(proxyFixture(groups,members)),async()=>{},
      'groupLimit,groupPage,visibleGroups')
    try{
      const items=panel.visibleGroups.value
      const rendered=items.reduce((sum,item)=>sum+panel.groupPage(item.names,item.group.name).length,0)
      const empty=items.filter(item=>panel.groupLimit(item.group.name)===0).length
      return {rendered,empty,items:items.length}
    }finally{panel.dispose()}
  }
  assert.deepEqual(budget(16,100),{rendered:300,empty:0,items:16})
  assert.deepEqual(budget(30,100),{rendered:300,empty:0,items:30})
  assert.deepEqual(budget(400,5),{rendered:300,empty:100,items:400})
})

test('network dashboard slows sampling outside the overview page',async()=>{
  const delays=[]
  const clock={setTimeout:(fn,ms)=>{delays.push(ms);return 1}}
  const home=setup('NetworkDashboard.vue',{running:true,configKey:'',active:true},async()=>{},'schedule,counter',clock)
  try{home.counter.value.running=true;home.schedule();assert.equal(delays.at(-1),1000)}finally{home.dispose()}
  delays.length=0
  const elsewhere=setup('NetworkDashboard.vue',{running:true,configKey:'',active:false},async()=>{},'schedule,counter',clock)
  try{elsewhere.counter.value.running=true;elsewhere.schedule();assert.equal(delays.at(-1),5000)}finally{elsewhere.dispose()}
})

function subscription(count=2000){
  return {id:'a',title:'Large',revision:1,enabled:true,interval_minutes:60,
    source:{proxies:Array.from({length:count},(_,i)=>({name:`node-${i}`,type:'ss',server:'example.invalid',port:443})),rules:[]},
    source_yaml:'proxies: []\n',
    edits:{proxy_renames:{},excluded_proxies:[],group_overrides:{},deleted_groups:[],new_groups:[],removed_rules:[],added_rules:[],rule_order:[],ai_routing:null},
    preview:{errors:[],warnings:[],yaml:'x'.repeat(1000),config:{}}}
}

test('config editor reuses immutable snapshots and only copies the draft',async()=>{
  const sub=subscription()
  const editor=setup('ConfigEditor.vue',{subscription:sub,backendBase:'http://127.0.0.1'},async()=>{},'current,edits,preview,dirty',{composeEditorRules:rules=>rules})
  try{
    assert.equal(editor.current.value,sub)
    assert.equal(editor.preview.value,sub.preview)
    assert.notEqual(editor.edits.value,sub.edits)
    assert.equal(editor.dirty.value,false)
    editor.edits.value.proxy_renames['node-0']='renamed';await Vue.nextTick()
    assert.equal(editor.dirty.value,true)
    delete editor.edits.value.proxy_renames['node-0'];await Vue.nextTick()
    assert.equal(editor.dirty.value,false)
  }finally{editor.dispose()}
})

test('config editor keeps one preview request in flight and runs the latest pending check',async()=>{
  const sub=subscription(5),calls=[]
  let release
  const api=async()=>{
    calls.push(1)
    if(calls.length===1)await new Promise(resolve=>release=resolve)
    return clone(sub.preview)
  }
  const editor=setup('ConfigEditor.vue',{subscription:sub,backendBase:'http://127.0.0.1'},api,'checkDraft,checking,edits',
    {composeEditorRules:rules=>rules,setTimeout:(fn)=>{if(typeof fn==='function')queueMicrotask(fn);return 1}})
  try{
    editor.edits.value.proxy_renames['node-0']='renamed';await Vue.nextTick()
    const first=editor.checkDraft()
    await tick()
    assert.equal(calls.length,1)
    const second=editor.checkDraft()
    await tick()
    assert.equal(calls.length,1)
    release()
    await first;await second;await tick()
    assert.equal(calls.length,2)
  }finally{editor.dispose()}
})

test('config editor stops preview scheduling after unmount',async()=>{
  const sub=subscription(5),calls=[],timers=[],pending=[],unmounts=[]
  let release
  const api=async()=>{
    calls.push(1)
    if(calls.length===1)await new Promise(resolve=>release=resolve)
    return clone(sub.preview)
  }
  const runTimers=()=>{
    for(const fn of timers.splice(0)){
      const result=fn()
      if(result&&typeof result.then==='function')pending.push(result)
    }
  }
  const editor=setup('ConfigEditor.vue',{subscription:sub,backendBase:'http://127.0.0.1'},api,'edits,checkDraft',
    {composeEditorRules:rules=>rules,onUnmounted:fn=>unmounts.push(fn),
     setTimeout:(fn)=>{if(typeof fn==='function')timers.push(fn);return timers.length},clearTimeout:()=>{}})
  try{
    editor.edits.value.proxy_renames['node-0']='renamed';await Vue.nextTick()
    runTimers()
    await tick()
    assert.equal(calls.length,1)
    editor.checkDraft()
    for(const fn of unmounts)fn()
    release()
    await Promise.all(pending);await tick()
    runTimers()
    assert.equal(calls.length,1)
    assert.equal(timers.length,0)
  }finally{editor.dispose()}
})


test('network dashboard keeps chart history only on the overview page',async()=>{
  const run=async(active)=>{
    let now=0,upload=100
    const api=async()=>({running:true,session:'s',upload,download:200,sampled_at:Date.now()/1000,connections:1})
    const dash=setup('NetworkDashboard.vue',{running:true,configKey:'',active},api,'sample,samples',
      {performance:{now:()=>now}})
    try{
      await dash.sample()
      now=1000;upload=200
      await dash.sample()
      return dash.samples.value.length
    }finally{dash.dispose()}
  }
  assert.equal(await run(true),1)
  assert.equal(await run(false),0)
})
