const {chromium}=require('playwright')
const assert=require('node:assert/strict')
const fs=require('node:fs')
;(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),results=[],errors=[],requests=[]
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100}})
  page.on('pageerror',error=>errors.push(error.message))
  page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/api/'))requests.push(request.url())})
  await page.goto('http://127.0.0.1:5181/ui-components.html')
  const entries=await page.evaluate(async()=>{const m=await import('/src/component-lab/catalogue.ts');return m.catalogue.filter(e=>!['select','pagination'].includes(e.id))})
  for(const entry of entries){
   try{
    await page.goto('http://127.0.0.1:5181/ui-components.html?component='+entry.id)
    const frame=page.frameLocator('iframe[title="客户端原位预览"]')
    const target=frame.locator(entry.selector).first()
    await target.locator('xpath=self::*[contains(@class,"lab-target")]').waitFor({timeout:6500})
    const dimensions=await target.evaluate(e=>[e.getBoundingClientRect().width,e.getBoundingClientRect().height])
    assert.ok(dimensions[0]>0&&dimensions[1]>0)
    await page.waitForFunction(()=>!document.querySelector('[aria-label="中心 X"]').disabled)
    const centerX=page.getByRole('spinbutton',{name:'中心 X',exact:true})
    assert.equal(await centerX.isEnabled(),true)
    const previous=Number(await centerX.inputValue())
    await centerX.fill(String(previous+2))
    assert.ok(Math.abs(Number(await centerX.inputValue())-previous-2)<.15)
    const centerY=page.getByRole('spinbutton',{name:'中心 Y',exact:true})
    const previousY=Number(await centerY.inputValue())
    await centerY.fill(String(previousY+2))
    const measured=await target.evaluate(e=>{const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})
    assert.ok(Math.abs(measured.x-previous-2)<.15)
    assert.ok(Math.abs(measured.y-previousY-2)<.15)
    await page.getByRole('button',{name:'重置当前元素',exact:true}).click()
    results.push({id:entry.id,page:entry.page,ok:true,centerEditing:true})
   }catch(error){results.push({id:entry.id,page:entry.page,ok:false,error:error.message.slice(0,180)});console.log('FAIL',entry.id)}
  }
  fs.mkdirSync('test-output',{recursive:true})
  fs.writeFileSync('test-output/component-catalogue-report.json',JSON.stringify({results,errors,apiRequests:requests},null,2))
  console.log(JSON.stringify({targets:results.length,pages:[...new Set(results.map(r=>r.page))],failures:results.filter(r=>!r.ok),errors,apiRequests:requests.length}))
  assert.deepEqual(results.filter(r=>!r.ok),[]);assert.deepEqual(errors,[]);assert.deepEqual(requests,[])
 }finally{await browser.close()}
})().catch(error=>{console.error(error.message);process.exitCode=1})
