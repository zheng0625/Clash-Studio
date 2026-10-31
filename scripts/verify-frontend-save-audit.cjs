// Requires Vite and Playwright. The isolated UI preview mocks every API request.
const {chromium}=require('playwright')
const assert=require('node:assert/strict')

;(async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'chrome'})
  try{
    const page=await browser.newPage({viewport:{width:1280,height:860}}),errors=[]
    page.on('pageerror',error=>errors.push(error.message))
    await page.goto(process.env.UI_PREVIEW_URL||'http://127.0.0.1:5196/ui-preview.html')
    await page.waitForSelector('.desk')
    await page.evaluate(async()=>{
      const original=window.fetch,copy=value=>JSON.parse(JSON.stringify(value))
      const template=await (await original('/api/subscriptions/ui-preview')).json()
      const first={...copy(template),title:'Audit A'},second={...copy(template),id:'audit-file',title:'Local B',source_type:'file'}
      second.source.proxies=Array.from({length:250},(_,i)=>({name:'node-'+i,type:'ss',server:'example.invalid',port:443}))
      second.source.rules=Array.from({length:250},(_,i)=>`DOMAIN,host-${i}.example,DIRECT`)
      const profiles=[first,second]
      const settings=await (await original('/api/client/settings')).json()
      const runtime=await (await original('/api/client/runtime')).json()
      runtime.running=false;runtime.active=null;runtime.proxy.owned=false
      let network={enabled:false,port:8767,selected_host:'',addresses:[],running:false,base_url:''}
      window.__saveAudit={settings,profiles,waiting:false,release:null}
      window.fetch=async(input,init)=>{
        const url=new URL(String(input),location.href),p=url.pathname,method=init?.method||'GET',body=init?.body?JSON.parse(init.body):null
        if(p==='/api/subscriptions')return Response.json(profiles)
        if(p==='/api/client/runtime')return Response.json(runtime)
        if(p==='/api/client/settings'){
          if(method==='PUT')settings.settings=copy(body)
          return Response.json(settings)
        }
        if(p==='/api/network'){
          if(method==='PUT')network={...network,...body,running:body.enabled}
          return Response.json(network)
        }
        const profile=profiles.find(profile=>p===`/api/subscriptions/${profile.id}`||p.startsWith(`/api/subscriptions/${profile.id}/`)||p===`/api/client/preview/${profile.id}`)
        if(profile){
          if(p.startsWith('/api/client/preview/'))return Response.json({...profile.preview,profile_revision:profile.revision,workspace_revision:1})
          if(p.endsWith('/preview'))return Response.json(profile.preview)
          if(p.endsWith('/edits')){
            window.__saveAudit.waiting=true
            await new Promise(resolve=>window.__saveAudit.release=resolve)
            profile.edits=copy(body.edits);profile.revision++
            window.__saveAudit.waiting=false
          }else if(method==='PATCH'){Object.assign(profile,body);profile.revision++}
          return Response.json(profile)
        }
        return original(input,init)
      }
    })
    const nav=label=>page.locator('.liquid-dock button').filter({hasText:label}).click()
    await nav('订阅')
    await page.locator('.profile-card').filter({hasText:'Local B'}).locator('button[title="刷新订阅"]').click()
    await page.waitForSelector('.native-editor')
    assert.match(await page.locator('.native-editor-head h2').innerText(),/Local B/)
    assert.equal(await page.locator('.editor-node-row:not(.table-head)').count(),100)
    await page.locator('.list-pagination button').filter({hasText:'下一页'}).click()
    assert.equal(await page.getByRole('textbox',{name:'节点名称 node-100',exact:true}).count(),1)
    await page.locator('.editor-tabs button').filter({hasText:'分流规则'}).click()
    assert.equal(await page.locator('.native-rule-row').count(),100)
    await page.locator('.list-pagination button').filter({hasText:'下一页'}).click()
    assert.equal(await page.locator('.native-rule-row>span').first().innerText(),'101')

    await page.locator('.editor-tabs button').filter({hasText:'订阅设置'}).click()
    await page.getByRole('textbox',{name:'名称',exact:true}).fill('Unsaved Local B')
    await nav('概览')
    await page.waitForSelector('.confirm-dialog[open]')
    await page.locator('.confirm-dialog button').filter({hasText:'取消'}).click()
    assert.equal(await page.locator('.native-editor').count(),1)
    await page.locator('.native-lan input[type=number]').fill('9000')
    await page.getByRole('button',{name:'保存订阅设置',exact:true}).click()
    await nav('概览')
    await page.waitForSelector('.confirm-dialog[open]')
    await page.locator('.confirm-dialog button').filter({hasText:'取消'}).click()
    await page.getByRole('button',{name:'保存共享设置',exact:true}).click()

    await page.locator('.editor-tabs button').filter({hasText:'代理节点'}).click()
    await page.getByRole('textbox',{name:'节点名称 node-0',exact:true}).fill('Renamed node')
    await page.getByRole('button',{name:'保存并发布',exact:true}).click()
    await page.waitForFunction(()=>window.__saveAudit.waiting)
    assert.equal(await page.locator('.native-editor').evaluate(element=>element.inert),true)
    await page.evaluate(()=>window.__saveAudit.release())
    await page.waitForFunction(()=>!document.querySelector('.native-editor').inert)
    assert.equal(await page.getByRole('textbox',{name:'节点名称 node-0',exact:true}).inputValue(),'Renamed node')

    await nav('设置与日志')
    await page.waitForSelector('.proxy-port-controls input')
    await page.getByRole('switch',{name:'IPv6 支持',exact:true}).click()
    await page.locator('.proxy-port-controls input').fill('18900')
    await page.getByRole('button',{name:'保存端口',exact:true}).click()
    await page.waitForFunction(()=>window.__saveAudit.settings.settings.mixed_port===18900)
    await page.locator('.settings-save-bar button').click()
    await page.waitForFunction(()=>!document.querySelector('.settings-save-bar'))
    const saved=await page.evaluate(()=>window.__saveAudit.settings.settings)
    assert.equal(saved.mixed_port,18900);assert.equal(saved.ipv6,false)
    assert.deepEqual(errors,[])
    console.log('PASS: local-file selection, bounded node/rule DOM, pagination priority, metadata/sharing navigation guard, inert save, saved draft, network/port merge; no page errors')
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1})
