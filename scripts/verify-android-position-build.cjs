const {chromium}=require('playwright')
const assert=require('node:assert/strict')
const fs=require('node:fs')
;(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),errors=[],requests=[],pages=[]
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100}})
  page.on('pageerror',e=>errors.push(e.message))
  page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))requests.push(r.url())})
  const saved=JSON.parse(fs.readFileSync('frontend/src/component-lab/presets/android-position-layout.json','utf8'))
  const extra={surface:'context',page:'home',selector:'div > main > div > div:nth-of-type(1) > div > h1',styles:{'font-size':'25px'}}
  await page.addInitScript(rules=>{if(!localStorage.getItem('position-test-seeded')){localStorage.setItem('clash-android-component-layout-v1',JSON.stringify(rules));localStorage.setItem('position-test-seeded','1')}},[...saved.rules,extra])
  for(const [id,section,selectors] of [
   ['kernel','home',['.desk-page-heading','.home-masonry']],
   ['usage','subscriptions',['.page-stage']],
   ['proxy-toolbar','proxies',['.page-stage']],
   ['connection-controls','connections',['.page-stage']],
   ['settings-tabs','settings',['.page-stage']],
   ['routing-list','routing',[]],
  ]){
   await page.goto('http://127.0.0.1:5181/ui-android-components.html?component='+id)
   await page.waitForFunction(()=>!document.querySelector('[aria-label="中心 X"]').disabled)
   const frame=page.frameLocator('iframe')
   for(const width of [360,393,430]){
    await page.getByRole('spinbutton',{name:'自定义窗口宽度',exact:true}).fill(String(width))
    for(const selector of selectors){
     const position=await frame.locator(selector).evaluate(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {left:parseFloat(s.left),right:r.right,viewport:innerWidth}})
     assert.ok(Math.abs(position.left-6.9)<.02,`${section}: ${JSON.stringify(position)}`)
     assert.ok(position.right<=position.viewport,`${section} overflows: ${JSON.stringify(position)}`)
    }
   }
   if(section==='routing')assert.ok(await frame.locator('.page-stage').evaluate(e=>!parseFloat(getComputedStyle(e).left)))
   if(section==='home'){
    for(const state of ['运行中','应用中','待应用','应用失败','未导入','全局模式','直连模式']){
     await page.locator('.lab-toolbar select').nth(1).selectOption(state)
     await page.waitForFunction(state=>new URLSearchParams(document.querySelector('iframe').contentWindow.location.search).get('scene')===state,state)
     await frame.locator('.lab-target').waitFor()
     const left=await frame.locator('.home-masonry').evaluate(e=>parseFloat(getComputedStyle(e).left))
     assert.ok(Math.abs(left-6.9)<.02,`${state}: ${left}`)
    }
   }
   pages.push(section)
  }
  assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('clash-android-component-layout-v1'))),[extra])
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('clash-android-component-layout-v1-before-position-v1')).length),8)
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[])
  fs.writeFileSync('test-output/android-position-verification.json',JSON.stringify({pages,widths:[360,393,430],states:true,migrationBackup:true,preservedUnrelatedRule:true,errors,requests},null,2))
  console.log(JSON.stringify({pages,widths:[360,393,430],states:true,migrationBackup:true,preservedUnrelatedRule:true,errors,requests}))
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1})
