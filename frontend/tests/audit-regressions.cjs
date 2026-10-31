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
const tick=()=>new Promise(setImmediate)

// Execute the actual setup functions with Vue reactivity and controlled I/O.
// Browser rendering and native networking are separate acceptance checks.
function moduleUnderTest(name,overrides={},globals={}){
  const exports={}
  const context=vm.createContext({exports,console,Promise,Error,JSON,Number,Math,Date,Set,Map,setTimeout,clearTimeout,...globals,
    require:id=>Object.hasOwn(overrides,id)?overrides[id]:require(id)})
  const source=fs.readFileSync(path.join(root,name),'utf8')
  vm.runInContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,context,{filename:name})
  return exports
}
const {composeEditorRules}=moduleUnderTest('config-rules.ts')
function setup(name,props,api,bindings,extra={}){
  const events=[]
  const {descriptor}=parse(fs.readFileSync(path.join(root,name),'utf8'))
  const source=descriptor.scriptSetup.content.replace(/^import .*$/gm,'')
  const scope=Vue.effectScope()
  const context=vm.createContext({...Vue,console,JSON,Number,Math,Date,Set,Map,Promise,
    setTimeout:()=>1,clearTimeout:()=>{},setInterval:()=>1,clearInterval:()=>{},
    onMounted:()=>{},onUnmounted:()=>{},defineProps:()=>props,defineEmits:()=>((...args)=>events.push(args)),
    api,t:s=>s,message:s=>s,locale:Vue.ref('en'),isDesktop:false,confirmDialog:async()=>true,composeEditorRules,...extra})
  scope.run(()=>vm.runInContext(ts.transpileModule(source+'\nglobalThis.bindings={'+bindings+'};',{
    compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText,context,{filename:name}))
  return {...context.bindings,events,dispose:()=>scope.stop()}
}
function subscription(count=1){
  return {id:'a',title:'Original',revision:1,enabled:true,interval_minutes:60,
    source:{proxies:Array.from({length:count},(_,i)=>({name:'node-'+i,type:'ss'})),rules:[]},
    edits:{proxy_renames:{},excluded_proxies:[],group_overrides:{},deleted_groups:[],new_groups:[],removed_rules:[],added_rules:[],rule_order:[],ai_routing:null},
    preview:{errors:[],warnings:[],yaml:'',config:{}}}
}

test('publish submits one validated snapshot and retains edits entered before the response',async()=>{
  const sub=subscription();let finish,submitted,validated
  const editor=setup('ConfigEditor.vue',{subscription:sub},async(url,method,body)=>{
    if(url.endsWith('/preview')){validated=clone(body.edits);return clone(sub.preview)}
    if(url.endsWith('/edits')){submitted=clone(body.edits);return new Promise(resolve=>finish=()=>resolve({...clone(sub),revision:2,edits:submitted}))}
    throw Error(url)
  },'edits,current,dirty,busy,publish')
  try{
    editor.edits.value.proxy_renames['node-0']='First';await Vue.nextTick()
    const request=editor.publish();await tick();assert.equal(editor.busy.value,true)
    editor.edits.value.proxy_renames['node-0']='Second';await Vue.nextTick()
    finish();await request;await Vue.nextTick()
    assert.deepEqual(submitted,validated)
    assert.equal(editor.current.value.edits.proxy_renames['node-0'],'First')
    assert.equal(editor.edits.value.proxy_renames['node-0'],'Second')
    assert.equal(editor.dirty.value,true)
    assert.equal(editor.busy.value,false)
    assert.equal(editor.events.filter(e=>e[0]==='dirty').at(-1)[1],true)
  }finally{editor.dispose()}
})

test('failed publish retains the draft and releases the saving state',async()=>{
  const sub=subscription()
  const editor=setup('ConfigEditor.vue',{subscription:sub},async url=>{
    if(url.endsWith('/preview'))return clone(sub.preview)
    throw Error('save failed')
  },'edits,dirty,busy,publish,error')
  try{
    editor.edits.value.proxy_renames['node-0']='Draft';await Vue.nextTick();await editor.publish()
    assert.equal(editor.error.value,'save failed');assert.equal(editor.dirty.value,true);assert.equal(editor.busy.value,false)
    assert.equal(editor.edits.value.proxy_renames['node-0'],'Draft')
  }finally{editor.dispose()}
})

test('metadata and sharing drafts participate in navigation protection and survive other saves',async()=>{
  const sub=subscription(),network={enabled:false,port:8767,selected_host:'',addresses:[],running:false}
  const editor=setup('ConfigEditor.vue',{subscription:sub},async(url,method,body)=>{
    if(url==='/api/network')return {...network,...(body||{})}
    if(url.endsWith('/preview'))return clone(sub.preview)
    if(url.endsWith('/edits'))return {...clone(sub),revision:2,edits:clone(body.edits)}
    if(method==='PATCH')return {...clone(sub),revision:3,...clone(body)}
    throw Error(url)
  },'edits,meta,networkForm,metaDirty,networkDirty,unsaved,publish,saveMeta,loadNetwork,saveNetwork')
  try{
    await editor.loadNetwork();editor.meta.value.title='Unsaved title';assert.equal(editor.unsaved.value,true)
    editor.networkForm.value.port=9000;assert.equal(editor.networkDirty.value,true)
    await editor.loadNetwork();assert.equal(editor.networkForm.value.port,9000)
    editor.edits.value.proxy_renames['node-0']='Saved node';await Vue.nextTick();await editor.publish();await Vue.nextTick()
    assert.equal(editor.meta.value.title,'Unsaved title');assert.equal(editor.metaDirty.value,true)
    await editor.saveMeta();assert.equal(editor.metaDirty.value,false);assert.equal(editor.unsaved.value,true)
    await editor.saveNetwork();assert.equal(editor.unsaved.value,false)
  }finally{editor.dispose()}
})

function settingsBackend(){
  let state={allow_lan:false,ipv6:false,mixed_port:17890,lan_auth:false,lan_username:'',lan_password:'',dns_override:{enabled:false,mode:'fake-ip',nameserver:[],fallback:[],bootstrap:[],proxy_nameserver:[],fake_ip_filter:[]}}
  const api=async(url,method,body)=>{if(method==='PUT')state=clone(body);return {settings:clone(state),lan_addresses:[],core_version:'mock',geodata:{busy:false}}}
  return {api,get:()=>state}
}
test('saving a network draft preserves the separately saved port',async()=>{
  const backend=settingsBackend(),{saveClientSettings}=moduleUnderTest('client-settings.ts',{'./api':{api:backend.api}})
  const props=Vue.reactive({port:17890,running:false})
  const network=setup('ClientSettings.vue',props,backend.api,'load,form,dirty,save',{saveClientSettings})
  const port=setup('ProxyPortSettings.vue',props,backend.api,'port,save',{saveClientSettings})
  try{
    await network.load();network.form.value.ipv6=true;await Vue.nextTick()
    port.port.value=18900;await port.save();props.port=18900;await Vue.nextTick()
    await network.save();assert.equal(backend.get().mixed_port,18900);assert.equal(backend.get().ipv6,true)
    assert.equal(network.dirty.value,false)
  }finally{network.dispose();port.dispose()}
})

test('concurrent settings saves merge in order and a rejected save does not poison the queue',async()=>{
  const backend=settingsBackend();let fail=true
  const api=async(...args)=>{if(args[1]==='PUT'&&fail){fail=false;throw Error('failed once')}await tick();return backend.api(...args)}
  const {saveClientSettings}=moduleUnderTest('client-settings.ts',{'./api':{api}})
  await assert.rejects(saveClientSettings({mixed_port:19000}),/failed once/)
  const changes={ipv6:true};const a=saveClientSettings(changes);changes.ipv6=false
  const b=saveClientSettings({mixed_port:19001});await Promise.all([a,b])
  assert.equal(backend.get().ipv6,true);assert.equal(backend.get().mixed_port,19001)
})

test('desktop string rejection becomes a visible structured error; HTTP errors retain details',async()=>{
  const {api}=moduleUnderTest('api.ts',{'./android':{},'@tauri-apps/api/core':{invoke:()=>Promise.reject('backend unavailable')}},
    {window:{__TAURI_INTERNALS__:{}},navigator:{userAgent:'audit'}})
  await assert.rejects(api('/api/client/settings'),error=>error.message==='backend unavailable'&&error.code==='TRANSPORT_ERROR'&&error.retryable)
  const browser=moduleUnderTest('api.ts',{'./android':{}},{window:{},navigator:{userAgent:'audit'},fetch:async()=>({status:409,json:async()=>({error:{message:'conflict',code:'CONFLICT',retryable:false,operation_id:'op-1'}})})})
  await assert.rejects(browser.api('/api/test'),error=>error.status===409&&error.code==='CONFLICT'&&error.operationId==='op-1'&&!error.retryable)
})

test('refreshing a local subscription selects its editor and respects cancelled or failed selection',async()=>{
  const {descriptor}=parse(fs.readFileSync(path.join(root,'Client.vue'),'utf8'))
  const ast=ts.createSourceFile('Client.ts',descriptor.scriptSetup.content,ts.ScriptTarget.Latest,true)
  const fn=ast.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name.text==='refreshProfile').getText(ast)
  for(const outcome of ['selected','cancelled','failed']){
    const selected={value:'a'},detail={value:{id:'a'}},pages=[]
    const ctx=vm.createContext({selected,detail,isAndroid:{value:false},t:s=>s,notify:()=>{},
      choose:async id=>{if(outcome!=='cancelled'){selected.value=id;detail.value=outcome==='failed'?null:{id}}},go:async page=>pages.push(page)})
    vm.runInContext(ts.transpileModule(fn,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText,ctx)
    await ctx.refreshProfile({id:'b',source_type:'file'})
    assert.deepEqual(pages,outcome==='selected'?['studio']:[])
    if(outcome==='selected')assert.equal(selected.value,'b')
  }
})

test('linear rule composition preserves ordering, removals, deduplication and AI filtering',()=>{
  function original(source,edits,ai,managed){
    const available=[...source.filter(r=>!edits.removed_rules.includes(r)),...edits.added_rules]
    const ordered=[...new Set(edits.rule_order.filter(r=>available.includes(r)))],rest=available.filter(r=>!ordered.includes(r))
    if(!ordered.length)ordered.push(...rest);else{const final=ordered.findIndex(r=>/^(MATCH|FINAL),/i.test(r));ordered.splice(final<0?ordered.length:final,0,...rest)}
    return [...ai,...new Set(ordered.filter(r=>!managed(r)))]
  }
  for(let i=0;i<120;i++){
    const source=['DOMAIN,a,DIRECT','DOMAIN,b,REJECT','DOMAIN,c,DIRECT','MATCH,DIRECT']
    const edits=subscription().edits
    edits.removed_rules=i%2?[source[1]]:[];edits.added_rules=i%3?['DOMAIN,new,DIRECT',source[0]]:[]
    edits.rule_order=i%4?[source[i%3],source[3],source[0],'missing']:[]
    const ai=i%5?[]:['DOMAIN,ai,DIRECT'],managed=r=>!!ai.length&&r.includes(',b,')
    assert.deepEqual(Array.from(composeEditorRules(source,edits,ai,managed)),original(source,edits,ai,managed))
  }
})

test('node and rule pagination bounds rows, retains rule priority and clamps after filtering',async()=>{
  const sub=subscription(250);sub.source.rules=Array.from({length:250},(_,i)=>`DOMAIN,host-${i},DIRECT`)
  const editor=setup('ConfigEditor.vue',{subscription:sub},async()=>{},'nodePage,rulePage,pagedNodes,pagedRules,nodePages,rulePages,search,tab')
  try{
    assert.equal(editor.pagedNodes.value.length,100);editor.nodePage.value=2;assert.equal(editor.pagedNodes.value.length,50)
    editor.rulePage.value=1;assert.equal(editor.pagedRules.value[0].index,100)
    editor.search.value='node-249';await Vue.nextTick()
    assert.equal(editor.nodePage.value,0);assert.equal(editor.pagedNodes.value.length,1)
    assert.equal(editor.rulePage.value,0);assert.equal(editor.pagedRules.value.length,0)
  }finally{editor.dispose()}
})

test('large ordered rule set composes within a generous regression budget',async()=>{
  const sub=subscription(),source=Array.from({length:10000},(_,i)=>`DOMAIN,host-${i},DIRECT`)
  sub.source.rules=source;sub.edits.rule_order=[...source].reverse()
  const {descriptor}=parse(fs.readFileSync(path.join(root,'ConfigEditor.vue'),'utf8'))
  const ast=ts.createSourceFile('Editor.ts',descriptor.scriptSetup.content,ts.ScriptTarget.Latest,true)
  const declaration=ast.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(ast)==='rules')).getText(ast)
  const context=vm.createContext({computed:Vue.computed,current:Vue.ref(sub),edits:Vue.ref(sub.edits),aiRules:Vue.ref([]),aiActive:Vue.ref(false),managed:()=>false,composeEditorRules})
  vm.runInContext(ts.transpileModule(declaration+'\nglobalThis.result=rules;',{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText,context)
  const started=performance.now(),result=context.result.value,elapsed=performance.now()-started
  assert.equal(result.length,10000);assert.equal(result[0],source.at(-1));assert.ok(elapsed<500,`10k rules took ${elapsed.toFixed(2)} ms`)
  console.log(`10k ordered rules: ${elapsed.toFixed(2)} ms (actual reactive computed, no DOM)`)
})
