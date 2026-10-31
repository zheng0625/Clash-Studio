// Run against Vite's isolated preview; never calls the real backend or VPN.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'chrome'});
  try{
    const page=await browser.newPage({viewport:{width:1280,height:860}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(process.env.UI_PREVIEW_URL||'http://127.0.0.1:5189/ui-preview.html');
    await page.waitForSelector('.desk');
    await page.waitForTimeout(500);
    await page.evaluate(()=>{
      window.__auditPaths=[];
      window.__auditConnections=Array.from({length:250},(_,index)=>({id:String(index),metadata:{host:`host-${index}.example`,destinationIP:'192.0.2.1',destinationPort:'443',process:'browser.exe',network:'tcp'},rule:'Match',chains:['Test'],upload:index,download:index*2}));
      const original=window.fetch;
      window.fetch=async (input,init)=>{
        const path=new URL(String(input),location.href).pathname;
        window.__auditPaths.push(path);
        if(path==='/api/client/runtime/connections')return Response.json({connections:window.__auditConnections,sampled_at:Date.now()/1000});
        if(path.startsWith('/api/client/runtime/connections/')&&init?.method==='DELETE'){
          const id=path.split('/').at(-1);window.__auditConnections=window.__auditConnections.filter(value=>value.id!==id);
          return Response.json({closed:true});
        }
        return original(input,init);
      };
    });
    const paths=()=>page.evaluate(()=>window.__auditPaths.splice(0));
    const nav=label=>page.locator('.liquid-dock button').filter({hasText:label}).click();
    await page.waitForTimeout(3200);
    assert.ok(!(await paths()).includes('/api/client/runtime/connections'),'Home must not request full connections');
    await nav('代理');await page.waitForTimeout(800);await paths();
    await page.waitForTimeout(3200);
    const proxyPaths=await paths();
    const cycles=proxyPaths.filter(path=>path==='/api/client/runtime').length;
    assert.ok(cycles>=1);
    assert.equal(proxyPaths.filter(path=>path==='/api/client/proxy-catalog').length,cycles,'One catalog request per polling cycle');
    assert.ok(!proxyPaths.includes('/api/client/runtime/proxies'),'Catalog must replace the duplicate proxy request');
    assert.ok(!proxyPaths.includes('/api/client/runtime/connections'));
    await nav('连接');await page.waitForSelector('.connection-item');
    assert.equal(await page.locator('.connection-item').count(),100);
    assert.match(await page.locator('.connection-pagination').innerText(),/1 \/ 3/);
    await page.locator('.connection-pagination button').last().click();
    assert.match(await page.locator('.connection-item').first().innerText(),/host-100/);
    await page.locator('.connection-pagination button').last().click();
    assert.equal(await page.locator('.connection-item').count(),50);
    await page.locator('.connection-inspect').first().click();
    await page.waitForSelector('dialog[open].connection-detail');
    assert.match(await page.locator('.connection-detail').innerText(),/host-200/);
    await page.locator('.connection-detail .app-dialog-heading .desk-icon-btn').click();
    await page.getByRole('button',{name:'暂停刷新',exact:true}).click();
    await page.evaluate(()=>{window.__auditConnections=window.__auditConnections.slice(0,1)});
    await page.waitForTimeout(3200);
    assert.equal(await page.locator('.connection-item').count(),50,'Paused page must retain its snapshot');
    await page.getByRole('button',{name:'恢复刷新',exact:true}).click();
    await page.waitForTimeout(100);
    assert.equal(await page.locator('.connection-item').count(),1,'Page must clamp after the connection count shrinks');
    await page.locator('.connection-controls input').fill('no-such-host');
    assert.equal(await page.locator('.connection-item').count(),0);
    await nav('概览');await page.waitForTimeout(300);await paths();
    assert.equal(await page.locator('.connection-item').count(),0,'Hidden connection DOM must be released');
    await page.waitForTimeout(3200);
    assert.ok(!(await paths()).includes('/api/client/runtime/connections'));
    await nav('连接');await page.waitForSelector('.connection-controls input');
    assert.equal(await page.locator('.connection-controls input').inputValue(),'no-such-host','Filters must survive navigation');
    await page.locator('.connection-controls input').fill('');
    await page.waitForSelector('.connection-item');
    await page.locator('.connection-item > .desk-icon-btn').click();
    await page.waitForTimeout(500);
    assert.equal(await page.locator('.connection-item').count(),0,'Close connection must refresh the list');
    assert.deepEqual(errors,[]);
    console.log('PASS: page-scoped polling, no duplicate proxy request, bounded 250-connection rendering, pagination, detail, pause/resume, filters, hidden DOM, close');
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
