// Run with Playwright available and the component workshop dev server running.
const {chromium}=require('playwright')
const assert=require('node:assert/strict')
const fs=require('node:fs')
;(async()=>{
  const browser=await chromium.launch({headless:true,channel:'msedge'})
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}})
    const errors=[],apiRequests=[]
    page.on('pageerror',error=>errors.push(error.message))
    page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/api/'))apiRequests.push(request.url())})
    await page.goto(process.env.COMPONENT_LAB_URL||'http://127.0.0.1:5181/ui-components.html')
    await page.getByRole('button',{name:'交互预览',exact:true}).click()
    const context=page.frameLocator('iframe[title="客户端原位预览"]')
    await context.locator('.kernel-launch-card.lab-target').waitFor()
    assert.equal(await context.locator('.home-masonry .home-left .kernel-launch-card').count(),1)
    const originalStorage=await page.evaluate(()=>localStorage.getItem('clash-desk-mode'))
    for(const [name,selector] of [['内存占用','.resource-memory-card'],['方案选择','.overview-selection'],['实时速率与累计流量','.bandwidth-card'],['网络出口','.ip-card'],['已启用模块','.flow-card'],['当前配置 · 概览','.config-card'],['订阅卡片 · 订阅页','.profile-card']]){
      await page.getByRole('navigation',{name:'组件目录'}).getByRole('button',{name:new RegExp('^'+name)}).click()
      await context.locator(selector+'.lab-target').waitFor()
    }
    await page.getByRole('combobox',{name:'状态',exact:true}).selectOption('已用尽')
    await context.getByText('额度已用尽',{exact:true}).waitFor()
    for(const width of ['1000','1280','1440']){
      await page.getByRole('combobox',{name:'窗口宽度'}).selectOption(width)
      assert.equal(await context.locator('body').evaluate(()=>innerWidth),Number(width))
    }
    await page.getByRole('navigation',{name:'组件目录'}).getByRole('button',{name:/内核与接管/}).click()
    await page.getByRole('combobox',{name:'查看方式'}).selectOption('isolated')
    const preview=page.getByRole('region',{name:'组件预览'})
    assert.equal(await page.locator('.lab-preview').evaluate(e=>getComputedStyle(e,'::before').content),'none')
    await preview.getByRole('button',{name:'启动',exact:true}).click()
    await preview.getByRole('button',{name:'停止',exact:true}).click()
    await page.getByRole('combobox',{name:'状态',exact:true}).selectOption('未导入')
    assert.equal(await preview.getByRole('button',{name:'启动',exact:true}).isDisabled(),true)
    let states=0
    for(const name of ['内核与接管','内存占用','方案选择','当前配置 · 概览','订阅卡片 · 订阅页','下拉选择','列表分页']){
      await page.getByRole('navigation',{name:'组件目录'}).getByRole('button',{name:new RegExp('^'+name)}).click()
      await page.getByRole('combobox',{name:'查看方式'}).selectOption('isolated')
      const values=await page.getByRole('combobox',{name:'状态',exact:true}).locator('option').allTextContents()
      for(const value of values){await page.getByRole('combobox',{name:'状态',exact:true}).selectOption(value);await page.waitForTimeout(30);assert.ok(await preview.innerText());states++}
    }
    await page.getByRole('navigation',{name:'组件目录'}).getByRole('button',{name:/内核与接管/}).click()
    await page.getByRole('textbox',{name:'打磨备注'}).fill('浏览器验收样例')
    await page.getByRole('button',{name:'确认满意并锁定'}).click()
    await page.reload()
    assert.equal(await page.getByRole('textbox',{name:'打磨备注'}).inputValue(),'浏览器验收样例')
    assert.equal(await page.getByRole('textbox',{name:'打磨备注'}).getAttribute('readonly'),'')
    await page.getByRole('button',{name:'解锁，继续打磨'}).click()
    await page.getByRole('combobox',{name:'查看方式'}).selectOption('isolated')
    await page.getByRole('checkbox',{name:'深色背景'}).check()
    await page.getByRole('checkbox',{name:'深色背景'}).uncheck()
    await page.getByRole('combobox',{name:'画布宽度'}).selectOption('320')
    const output=process.env.COMPONENT_LAB_SCREENSHOT
    if(output){fs.mkdirSync(require('node:path').dirname(output),{recursive:true});await page.screenshot({path:output,fullPage:true})}
    await page.setViewportSize({width:390,height:844})
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
    assert.deepEqual(apiRequests,[])
    assert.deepEqual(errors,[])
    assert.equal(await page.evaluate(()=>localStorage.getItem('clash-desk-mode')),originalStorage)
    console.log(JSON.stringify({states,contextTargets:8,windowWidths:[1000,1280,1440],apiRequests:apiRequests.length,errors,lockPersistence:true,mobileNoPageOverflow:true,actualClientContext:true,usageExhaustion:true,preferencesUnchanged:true}))
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1})
