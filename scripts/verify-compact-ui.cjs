// Production Client.vue on the isolated preview with controlled backend responses.
const {chromium}=require('playwright')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path')
;(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'})
 try{
  const page=await browser.newPage({viewport:{width:1280,height:860}}),errors=[]
  page.on('pageerror',e=>errors.push(e.message))
  await page.addInitScript(()=>localStorage.setItem('clash-studio-language-v1','zh-CN'))
  await page.goto(process.env.UI_PREVIEW_URL||'http://127.0.0.1:5188/ui-preview.html')
  await page.waitForSelector('.overview-selection')
  await page.waitForSelector('.ip-card .ip-property')
  const initialEgressHeight=(await page.locator('.ip-card').boundingBox()).height
  const initialTrafficHeight=(await page.locator('.bandwidth-card').boundingBox()).height
  await page.locator('.network-expanded').evaluate(e=>e.open=true)
  assert.ok((await page.locator('.bandwidth-card').boundingBox()).height>initialTrafficHeight)
  assert.ok(Math.abs((await page.locator('.ip-card').boundingBox()).height-initialEgressHeight)<1,'Egress must keep its own height when traffic expands')
  assert.equal(await page.locator('.ip-card .egress-row').count(),3)
  assert.equal(await page.locator('.ip-card').getByText('DNS 配置',{exact:true}).count(),0)
  assert.equal(await page.locator('.ip-property').count(),2)
  await page.locator('.network-expanded').evaluate(e=>e.open=false)
  await page.evaluate(async()=>{
   const original=window.fetch,copy=v=>JSON.parse(JSON.stringify(v))
   const a=await(await original('/api/subscriptions/ui-preview')).json(),b={...copy(a),id:'compact-b',title:'Second plan'}
   const runtime=await(await original('/api/client/runtime')).json();runtime.running=false;runtime.active=null
   const profiles=[a,b],choices={},calls=[],modules=Array.from({length:7},(_,i)=>({id:'m'+i,name:'Module '+i,target:'Manual',strict:i%2===0,matches:[]}))
   window.__compact={profiles,runtime,choices,calls,modules,failSelection:false,slow:false}
   window.fetch=async(input,init)=>{
    const u=new URL(String(input),location.href),p=u.pathname,method=init?.method||'GET',body=init?.body?JSON.parse(init.body):null
    calls.push({p,method,body})
    if(p==='/api/subscriptions')return Response.json(profiles)
    const profile=profiles.find(x=>p===`/api/subscriptions/${x.id}`||p===`/api/client/preview/${x.id}`)
    if(profile)return Response.json(p.includes('/preview/')?profile.preview:profile)
    if(p==='/api/client/workspace')return Response.json({revision:1,modules,plans:{[a.id]:{module_ids:modules.map(m=>m.id),default_target:''},[b.id]:{module_ids:[],default_target:''}}})
    if(p==='/api/client/runtime')return Response.json(runtime)
    if(p==='/api/client/proxy-catalog'){
     const id=u.searchParams.get('profile_id'),suffix=id===a.id?'A':'B'
     if(window.__compact.slow&&id===b.id)await new Promise(r=>setTimeout(r,450))
     const first='Node '+suffix+'1',second='Node '+suffix+'2'
     return Response.json({proxies:{Manual:{name:'Manual',type:'Selector',all:[first,second],now:choices[id]||first},Auto:{name:'Auto',type:'URLTest',all:[first,second],now:first},[first]:{name:first,type:'Shadowsocks'},[second]:{name:second,type:'Shadowsocks'}},live:runtime.running&&runtime.active?.profile_id===id,key:id,has_providers:false,profile_revision:1,workspace_revision:1})
    }
    if(p==='/api/client/proxy-selection'){
     if(window.__compact.failSelection)return Response.json({detail:'selection failure'},{status:409})
     choices[body.profile_id]=body.name
     return Response.json({live:runtime.running&&runtime.active?.profile_id===body.profile_id})
    }
    if(p==='/api/client/network/dns-summary')return Response.json({status:'ok',nameservers:['https://dns.example.invalid'],source:runtime.running?'runtime':'selected',profile_id:runtime.active?.profile_id||u.searchParams.get('profile_id'),config_hash:'test'})
    return original(input,init)
   }
  })
  const nav=label=>page.locator('.liquid-dock button').filter({hasText:label}).click()
  const selection=page.locator('.overview-selection'),scheme=selection.getByRole('combobox',{name:'方案',exact:true}),node=selection.getByRole('combobox',{name:'节点',exact:true})
  await page.getByRole('button',{name:'刷新',exact:true}).click()
  await page.waitForFunction(()=>document.querySelector('.overview-selection select[aria-label="节点"]')?.textContent.includes('Node A1'))
  assert.equal(await page.locator('.configuration-status').count(),0)
  assert.equal(await page.locator('.compact-module-row').count(),3)
  await page.getByRole('button',{name:'下一页模块'}).click();await page.getByRole('button',{name:'下一页模块'}).click();assert.equal(await page.locator('.compact-module-row').count(),1)
  await scheme.selectOption('compact-b');await page.waitForFunction(()=>document.querySelector('.overview-selection select[aria-label="节点"]')?.textContent.includes('Node B1'))
  assert.equal(await page.locator('.compact-module-row').count(),0)
  await node.selectOption('Node B2');await page.waitForFunction(()=>window.__compact.choices['compact-b']==='Node B2')
  assert.equal(await page.evaluate(()=>window.__compact.runtime.running),false)
  await selection.getByRole('combobox',{name:'策略组',exact:true}).selectOption('Auto');assert.equal(await node.isDisabled(),true)
  await selection.getByRole('combobox',{name:'策略组',exact:true}).selectOption('Manual')
  await page.evaluate(()=>window.__compact.failSelection=true)
  await node.selectOption('Node B1');await page.waitForFunction(()=>document.querySelector('.overview-selection select[aria-label="节点"]')?.value==='Node B2')
  await page.evaluate(()=>{window.__compact.failSelection=false;window.__compact.slow=true})
  // A late catalog from B must never replace A after a rapid switch.
  await scheme.selectOption('ui-preview');await scheme.selectOption('compact-b');await scheme.selectOption('ui-preview')
  await page.waitForFunction(()=>document.querySelector('.overview-selection select[aria-label="节点"]')?.textContent.includes('Node A1'))
  await page.waitForTimeout(500);assert.match(await node.innerText(),/Node A1/);assert.doesNotMatch(await node.innerText(),/Node B1/)
  await page.evaluate(()=>{window.__compact.runtime.running=true;window.__compact.runtime.active={profile_id:'ui-preview',title:'First running',revision:1,workspace_revision:1,mixed_port:17890,hash:'active'}})
  await page.getByRole('button',{name:'刷新',exact:true}).click()
  await scheme.selectOption('compact-b');await page.waitForFunction(()=>document.querySelector('.overview-selection select[aria-label="节点"]')?.textContent.includes('Node B1'))
  await node.selectOption('Node B1');await page.waitForFunction(()=>window.__compact.choices['compact-b']==='Node B1')
  assert.equal(await page.evaluate(()=>window.__compact.runtime.active.profile_id),'ui-preview')
  assert.ok(!await page.evaluate(()=>window.__compact.calls.some(c=>c.p==='/api/client/runtime/apply')))
  await scheme.selectOption('ui-preview')
  const folder=process.env.COMPACT_SCREENSHOTS
  if(folder){fs.mkdirSync(folder,{recursive:true});await page.screenshot({path:path.join(folder,'connected-home.png')})}
  await page.getByRole('button',{name:'导入订阅',exact:true}).click();await page.waitForSelector('dialog[open]')
  await page.getByRole('button',{name:'YAML 文件',exact:true}).click()
  const tab=page.locator('.import-method-tabs button.active');assert.equal(await tab.getAttribute('aria-pressed'),'true')
  assert.equal(await tab.evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)')
  if(folder)await page.screenshot({path:path.join(folder,'connected-import.png')})
  await page.keyboard.press('Escape')
  await nav('代理');await page.waitForSelector('.proxy-group')
  if(folder)await page.screenshot({path:path.join(folder,'connected-proxies.png')})
  await nav('设置与日志');const soft=page.getByRole('switch',{name:'柔和背景',exact:true});await soft.waitFor()
  assert.equal(await soft.getAttribute('aria-checked'),'true');await soft.click()
  assert.equal(await page.locator('html').getAttribute('data-soft-background'),'off')
  await page.reload();await page.waitForSelector('.overview-selection');assert.equal(await page.locator('html').getAttribute('data-soft-background'),'off')
  await nav('设置与日志');await page.getByRole('switch',{name:'柔和背景',exact:true}).click()
  assert.equal(await page.locator('html').getAttribute('data-soft-background'),'on')
  await nav('概览')
  for(const width of [1024,1280]){await page.setViewportSize({width,height:860});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));const rect=await page.locator('.home-masonry').boundingBox();assert.ok(rect.width<=width)}
  assert.deepEqual(errors,[])
  assert.ok(!await page.evaluate(()=>window.__compact?.calls.some(c=>c.p==='/api/client/network/dns-summary')),'The overview no longer reads DNS configuration')
  console.log('PASS: production UI, module pages, offline choices, automatic groups, selection rollback, late response isolation, selected vs running plan, no unintended apply, rounded import, persistent soft background, 1024/1280 layout; no page errors')
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1})
