// Requires Playwright and a running Vite dev server for ui-memory.html.
//   pnpm --dir frontend dev --port 5178 --strictPort
//   node scripts/verify-memory-ui.cjs
const {chromium}=require('playwright')
const assert=require('node:assert/strict')

const url=process.env.UI_MEMORY_URL||'http://127.0.0.1:5178/ui-memory.html'
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms))

;(async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'msedge'})
  const results={url,started_at:new Date().toISOString(),cases:{}}
  try{
    const page=await browser.newPage({viewport:{width:1280,height:860}}),errors=[]
    page.on('pageerror',error=>errors.push(error.message))
    await page.goto(url)
    await page.waitForSelector('.desk')
    const probe=()=>page.evaluate(()=>JSON.parse(document.getElementById('memory-probe').textContent))
    const nav=label=>page.getByRole('button',{name:label,exact:true}).click()

    await wait(2500)
    await nav('代理')
    await wait(2500)
    results.cases.proxy_budget={groups:await page.locator('.proxy-group').count(),cards:await page.locator('.proxy-node-card').count()}
    assert.equal(results.cases.proxy_budget.groups,16)
    assert.equal(results.cases.proxy_budget.cards,300)
    const pageLabel=await page.locator('.group-pagination span').first().innerText()
    results.cases.proxy_budget.pagination=pageLabel
    assert.match(pageLabel,/每页最多 (1\d|20) 项/)

    await page.getByRole('button',{name:'全部折叠',exact:true}).click()
    await wait(400)
    results.cases.folded_cards=await page.locator('.proxy-node-card').count()
    assert.equal(results.cases.folded_cards,0)
    await page.getByRole('button',{name:/策略组 0/}).first().click()
    await wait(400)
    results.cases.single_group_cards=await page.locator('.proxy-node-card').count()
    assert.equal(results.cases.single_group_cards,100)
    await page.getByRole('button',{name:'全部展开',exact:true}).click()
    await wait(400)
    results.cases.expanded_cards=await page.locator('.proxy-node-card').count()
    assert.equal(results.cases.expanded_cards,300)

    await nav('连接')
    await wait(1600)
    results.cases.connections={
      items:await page.locator('.connection-item').count(),
      status:await page.locator('.connection-sample').innerText()
    }
    assert.equal(results.cases.connections.items,100)
    assert.match(results.cases.connections.status,/5000 \/ 5000/)
    await page.getByRole('button',{name:'暂停刷新',exact:true}).click()
    await wait(200)
    results.cases.pause=await page.locator('.connection-sample').innerText()
    assert.match(results.cases.pause,/已暂停显示/)
    await page.getByRole('button',{name:'恢复刷新',exact:true}).click()
    await wait(200)
    assert.match(await page.locator('.connection-sample').innerText(),/每 3 秒刷新/)

    await nav('概览')
    await wait(1200)
    const c0=await probe()
    await wait(6200)
    const c1=await probe()
    results.cases.leave_connections={connections_delta:c1.connections-c0.connections,traffic_delta:c1.traffic-c0.traffic}
    assert.equal(results.cases.leave_connections.connections_delta,0)
    assert.ok(results.cases.leave_connections.traffic_delta>=4)

    await nav('代理')
    await wait(1000)
    const p0=await probe()
    await wait(6200)
    const p1=await probe()
    results.cases.proxy_cadence={traffic_delta:p1.traffic-p0.traffic,catalog_delta:(p1.by_path['/api/client/proxy-catalog']||0)-(p0.by_path['/api/client/proxy-catalog']||0)}
    assert.ok(results.cases.proxy_cadence.traffic_delta<=3)
    assert.ok(results.cases.proxy_cadence.catalog_delta<=3)

    await nav('概览')
    await wait(1200)
    const h0=await probe()
    await page.getByRole('button',{name:'toggle hidden',exact:true}).click()
    await wait(5200)
    const h1=await probe()
    results.cases.hidden={traffic_delta:h1.traffic-h0.traffic,resource_delta:h1.resource-h0.resource}
    assert.equal(results.cases.hidden.traffic_delta,0)
    assert.equal(results.cases.hidden.resource_delta,0)
    await page.getByRole('button',{name:'toggle hidden',exact:true}).click()
    await wait(600)
    const h2=await probe()
    results.cases.resume_traffic_delta=h2.traffic-h1.traffic
    assert.ok(results.cases.resume_traffic_delta>=1)

    await page.getByText('RAM · 进程明细').click()
    await wait(300)
    results.cases.memory_roles=await page.locator('.resource-memory-processes').innerText()
    for(const label of ['桌面宿主','WebView','本地服务','主内核','私有提交合计'])assert.ok(results.cases.memory_roles.includes(label),label)

    assert.deepEqual(errors,[])
    results.status='passed'
  }catch(error){
    results.status='failed'
    results.error=error&&error.message||String(error)
    throw error
  }finally{
    results.finished_at=new Date().toISOString()
    require('node:fs').writeFileSync(require('node:path').join(__dirname,'..','artifacts','memory','browser-validation-auto.json'),JSON.stringify(results,null,2))
    await browser.close()
    console.log(JSON.stringify(results,null,2))
  }
})().catch(error=>{console.error(error);process.exit(1)})
