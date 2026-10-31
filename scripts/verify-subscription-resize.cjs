const {chromium}=require('playwright')
const assert=require('node:assert/strict')
const fs=require('node:fs')
;(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'})
 try{
  const page=await browser.newPage(),errors=[]
  page.on('pageerror',e=>errors.push(e.message))
  await page.goto('http://127.0.0.1:5188/ui-component-frame.html?component=usage')
  await page.waitForSelector('.profile-card')
  // Keep the real component/styles; add cards to exercise wrapping into rows.
  await page.locator('.profile-grid').evaluate(grid=>{
   const card=grid.querySelector('.profile-card')
   for(let i=0;i<2;i++)grid.insertBefore(card.cloneNode(true),grid.lastElementChild)
  })
  fs.mkdirSync('test-output/subscription-resize',{recursive:true})
  for(const width of [1280,1000,900,800,720,686,640,686,800,900,1280]){
   await page.setViewportSize({width,height:800})
   const layout=await page.evaluate(()=>{
    const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,right:r.right,width:r.width,y:r.y}}
    const grid=document.querySelector('.profile-grid'),content=document.querySelector('.desk-content')
    return {grid:rect(grid),cards:[...grid.children].map(rect),heading:rect(document.querySelector('.desk-page-heading')),overflow:content.scrollWidth>content.clientWidth+1}
   })
   assert.equal(layout.overflow,false,`overflow at ${width}`)
   assert.ok(layout.heading.x>=0&&layout.heading.right<=width,`heading clipped at ${width}`)
   const rows=new Map()
   for(const card of layout.cards){
    assert.ok(card.x>=layout.grid.x-1&&card.right<=layout.grid.right+1,`card clipped at ${width}`)
    if(!rows.has(card.y))rows.set(card.y,[])
    rows.get(card.y).push(card)
   }
   const firstRow=[...rows.values()][0]
   assert.ok(Math.abs(firstRow.at(-1).right-layout.grid.right)<1,`unused row width at ${width}`)
   if(width===686)await page.screenshot({path:'test-output/subscription-resize/narrow.png'})
  }
  await page.screenshot({path:'test-output/subscription-resize/wide.png'})
  await page.locator('.profile-card').evaluateAll(cards=>cards.forEach(card=>card.remove()))
  await page.setViewportSize({width:720,height:520})
  const add=await page.locator('.add-profile').boundingBox(),grid=await page.locator('.profile-grid').boundingBox()
  assert.ok(Math.abs(add.width-grid.width)<1,'empty import card fills row')
  assert.deepEqual(errors,[])
  console.log('PASS: repeated desktop resizing 640–1280px; filled rows, unclipped headings/cards, no horizontal overflow; empty import card; no browser errors')
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1})
