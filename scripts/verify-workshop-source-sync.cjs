const {chromium}=require('playwright')
const assert=require('node:assert/strict')
const fs=require('node:fs')
;(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),results=[]
 try{
  for(const android of [false,true]){
   const page=await browser.newPage({viewport:{width:1600,height:1200}})
   const key=android?'clash-android-component-layout-v1':'clash-component-layout-v1'
   const old=[{surface:'context',page:'home',selector:'main',styles:{left:'100px',position:'relative'}}]
   await page.addInitScript(({key,old})=>{if(!localStorage.getItem('seeded')){localStorage.setItem(key,JSON.stringify(old));localStorage.setItem('seeded','1')}},{key,old})
   const base='http://127.0.0.1:5181/'+(android?'ui-android-components.html':'ui-components.html')
   await page.goto(base)
   await page.waitForFunction(()=>!!document.querySelector('iframe')?.contentDocument?.querySelector('.lab-target'))
   const saved=await page.evaluate(key=>({rules:JSON.parse(localStorage.getItem(key)),backup:JSON.parse(localStorage.getItem(key+'-before-20261031-latest-test-v1')),version:localStorage.getItem(key+'-source-baseline')}),key)
   assert.deepEqual(saved.rules,[]);assert.deepEqual(saved.backup,old)
   await page.getByRole('button',{name:'导出更新前布局备份',exact:true}).waitFor()
   const frame=page.frameLocator('iframe')
   if(android){
    for(const width of [360,393,421,430]){
     await page.getByRole('spinbutton',{name:'自定义窗口宽度',exact:true}).fill(String(width))
     await page.waitForFunction(width=>document.querySelector('iframe').contentWindow.innerWidth===width,width)
     const layout=await frame.locator('.kernel-launch-card').evaluate(e=>{
      const root=document.documentElement,group=e.querySelector('.routing-segment'),buttons=[...group.children],rect=e.getBoundingClientRect()
      const sibling=e.parentElement.querySelector('.desk-card:not(.kernel-launch-card)').getBoundingClientRect()
      return {width:rect.width,siblingWidth:sibling.width,top:getComputedStyle(document.querySelector('.desk-main')).paddingTop,status:getComputedStyle(root).getPropertyValue('--android-status-inset'),buttons:buttons.map(b=>{const r=b.getBoundingClientRect(),t=document.createRange();t.selectNodeContents(b);const text=t.getBoundingClientRect();return {width:r.width,center:(text.left+text.right-r.left-r.right)/2}})}
     })
     assert.ok(Math.abs(layout.width-layout.siblingWidth)<1)
     assert.ok(parseFloat(layout.top)>40&&Math.abs(parseFloat(layout.top)-parseFloat(layout.status))<.01)
     assert.ok(layout.buttons.every(b=>Math.abs(b.width-layout.buttons[0].width)<.1&&Math.abs(b.center)<.1))
     results.push({android,width,layout})
    }
    await page.goto(base+'?component=settings-language')
    await frame.locator('.language-settings.lab-target').waitFor()
    const widths=await frame.locator('.language-settings,.appearance-entry,.soft-background-entry').evaluateAll(es=>es.map(e=>e.getBoundingClientRect().width))
    assert.ok(widths.every(w=>Math.abs(w-widths[0])<1))
    await page.goto(base+'?component=android-delay')
    await frame.locator('.delay-fab.lab-target').waitFor()
    const bottom=await frame.locator('.desk-content').evaluate(e=>({bottom:e.getBoundingClientRect().bottom,viewport:innerHeight,margin:getComputedStyle(e).marginBottom}))
    assert.ok(Math.abs(bottom.bottom-bottom.viewport)<1);assert.equal(bottom.margin,'0px')
   }
   await page.goto(base)
   await page.waitForFunction(()=>!document.querySelector('[aria-label="中心 X"]').disabled)
   await page.getByRole('spinbutton',{name:'X 位移',exact:true}).fill('3')
   await page.reload()
   assert.ok((await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key)).some(r=>r.styles.left==='3px'))
   await page.getByRole('button',{name:'恢复正式源码布局',exact:true}).click()
   assert.deepEqual(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key),[])
   await page.screenshot({path:'test-output/workshop-source-sync-'+(android?'android':'desktop')+'.png',fullPage:true})
   results.push({android,migrationBackup:true,newEditsPersist:true,restoreSource:true})
   await page.close()
  }
  fs.writeFileSync('test-output/workshop-source-sync.json',JSON.stringify({passed:true,results},null,2))
  console.log(JSON.stringify({passed:true,checks:results.length}))
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1})
