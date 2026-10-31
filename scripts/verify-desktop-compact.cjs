const {chromium}=require('playwright')
const assert=require('node:assert/strict')
const fs=require('node:fs')
;(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'})
 try{
  const page=await browser.newPage({viewport:{width:1280,height:860}}),errors=[]
  page.on('pageerror',e=>errors.push(e.message))
  await page.goto('http://127.0.0.1:5188/ui-component-frame.html?component=kernel&scene='+encodeURIComponent('运行中'))
  await page.waitForSelector('.lab-target')
  const dimensions=async selector=>page.locator(selector).evaluate(e=>({width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}))
  for(const [selector,width,height] of [['.kernel-launch-card',380,213],['.bandwidth-card',380,238],['.config-card',380,159],['.overview-selection',300,196],['.ip-card',300,164],['.resource-memory-card',300,84]]){
   const r=await dimensions(selector);assert.ok(Math.abs(r.width-width)<1,`${selector}: width ${r.width}`);assert.ok(r.height>=height,`${selector}: height ${r.height}`)
  }
  await page.locator('.network-expanded').evaluate(e=>e.open=true)
  assert.ok((await dimensions('.bandwidth-card')).height>238)
  await page.locator('.network-expanded').evaluate(e=>e.open=false)
  await page.locator('.resource-memory-details').evaluate(e=>e.open=true)
  assert.ok((await dimensions('.resource-memory-card')).height>84)
  await page.locator('.resource-memory-details').evaluate(e=>e.open=false)
  fs.mkdirSync('test-output/desktop-compact',{recursive:true})
  await page.screenshot({path:'test-output/desktop-compact/home-1280.png'})
  for(const [width,height] of [[720,520],[800,600],[840,760],[1000,680],[1280,860]]){
   await page.setViewportSize({width,height})
   assert.equal(await page.locator('html').getAttribute('data-mobile-tier'),null)
   assert.equal(await page.locator('.liquid-dock .dock-item:visible').count(),7)
   assert.equal(await page.locator('.window-controls button:visible').count(),3)
   for(let i=0;i<7;i++){
    await page.locator('.liquid-dock .dock-item').nth(i).click()
    await page.waitForTimeout(150)
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`page ${i} at ${width}: document overflow`)
    const stage=await page.locator('.desk-content').evaluate(e=>({width:e.clientWidth,scroll:e.scrollWidth}))
    assert.ok(stage.scroll<=stage.width+1,`page ${i} at ${width}: stage overflow ${JSON.stringify(stage)}`)
    if(i===1&&width===1280){const r=await dimensions('.profile-card');assert.ok(r.width>=380);assert.ok(r.height>=260)}
    if(i===1&&width===840){const cards=await page.locator('.profile-grid>*').evaluateAll(elements=>elements.map(e=>{const r=e.getBoundingClientRect();return {y:r.y,width:r.width}}));assert.equal(cards[0].y,cards[1].y);assert.ok(cards[0].width>=380)}
   }
   await page.locator('.liquid-dock .dock-item').nth(0).click()
   await page.getByRole('button',{name:'导入订阅',exact:true}).first().click()
   const dialog=page.locator('dialog[open]');await dialog.waitFor()
   const r=await dialog.boundingBox();assert.equal(r.width,440);assert.equal(r.height,430);assert.ok(r.y>=0&&r.y+r.height<=height)
   await page.keyboard.press('Escape')
   if(width===720)await page.screenshot({path:'test-output/desktop-compact/home-720.png'})
   if(width===840)await page.screenshot({path:'test-output/desktop-compact/home-840.png'})
  }
  assert.deepEqual(errors,[])
  console.log('PASS: exported card sizes; expanding details; seven desktop pages at 720x520/800x600/840x760/1000x680/1280x860; default subscription two-column layout; native controls, Dock, no page overflow; 440x430 import dialog; no browser errors')
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1})
