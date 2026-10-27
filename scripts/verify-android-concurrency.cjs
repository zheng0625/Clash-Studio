const fs=require('node:fs'),path=require('node:path'),net=require('node:net'),assert=require('node:assert/strict');
const {DeviceSession,sleep}=require('./android-device-session.cjs');
const device=new DeviceSession(),sockets=new Set(),results=[];
const output=path.resolve('artifacts/android-device-2026-10-26/concurrency');fs.mkdirSync(output,{recursive:true});
let accepted=0;
const server=net.createServer(socket=>{accepted++;sockets.add(socket);socket.on('close',()=>sockets.delete(socket));socket.on('error',()=>{})});
(async()=>{
  let profile;
  await new Promise(resolve=>server.listen(18443,'127.0.0.1',resolve));
  await device.connect();assert.equal((await device.api('/api/client/runtime')).running,false);
  device.command('reverse','tcp:18443','tcp:18443');device.command('forward','tcp:17894','tcp:17890');
  try{
    profile=await device.api('/api/subscriptions','POST',{title:'并发验收 · 临时',source_type:'file',yaml:'proxies:\n - {name: Blackhole, type: socks5, server: 127.0.0.1, port: 18443}\nproxy-groups:\n - {name: Test, type: select, proxies: [DIRECT, REJECT]}\nrules: ["MATCH,Test"]\n'});
    const body={profile_id:profile.id,profile_revision:profile.revision,workspace_revision:1,mixed_port:17890,proxy_mode:'vpn'};
    // TLS accepts TCP but deliberately never completes the handshake.
    await device.evaluate(`window.__slowDownloads=Promise.all([0,1].map(i=>window.__deviceRequest('/api/subscriptions','POST',{title:'Slow '+i,source_type:'url',source_url:'https://127.0.0.1:18443/slow-'+i})));true`);
    await device.waitFor(()=>accepted>=2,5000);
    device.fault('before-tunnel',6500);await device.start(body);await device.entered('before-tunnel');
    const probe={...body,name:'Blackhole',endpoint:'cloudflare',timeout_ms:5000};
    await device.evaluate(`window.__probeReplies=Promise.all(Array.from({length:13},()=>window.__deviceRequest('/api/client/runtime/delay','POST',${JSON.stringify(probe)})));true`);
    await device.waitFor(async()=>(await device.api('/api/client/diagnostics')).lifecycle_queued>=4,3000);
    const times=[];
    for(let i=0;i<20;i++){const at=performance.now();assert.equal((await device.api('/api/client/runtime')).running,false);times.push(performance.now()-at)}
    const at=performance.now();
    const stopping=device.api('/api/client/runtime/stop','POST',{});
    await device.waitFor(async()=>(await device.api('/api/client/runtime')).cancel_requested,2000);
    const intentMs=performance.now()-at;
    await stopping;await device.stopped();
    const stopMs=performance.now()-at;
    const replies=await device.evaluate('window.__probeReplies');
    const downloads=await device.evaluate('window.__slowDownloads');
    times.sort((a,b)=>a-b);
    const detail={download_connections:accepted,download_statuses:downloads.map(x=>x.status),probe_statuses:replies.map(x=>x.status),status_p50_ms:+times[9].toFixed(2),status_p95_ms:+times[18].toFixed(2),stop_intent_ms:+intentMs.toFixed(2),stop_cleanup_ms:+stopMs.toFixed(2)};
    console.log(JSON.stringify(detail));results.push({name:'slow-downloads-probes-start-stop',detail});
    assert.ok(replies.some(x=>x.status===429),'queue limit must reject excess work');
    assert.ok(replies.every(x=>[409,429].includes(x.status)),'obsolete probes must not restart a core after stop');
    assert.equal(await device.listenerResponds(),false);
    results[0].passed=true;console.log('PASS slow downloads, saturated probes, responsive status and stop, obsolete queued work discarded');
  }finally{
    device.clearFault();await device.api('/api/client/runtime/stop','POST',{});
    if(profile){const row=await device.api('/api/subscriptions/'+profile.id);await device.api(`/api/subscriptions/${row.id}?revision=${row.revision}`,'DELETE')}
    for(const socket of sockets)socket.destroy();server.close();
    device.command('reverse','--remove','tcp:18443');device.close();
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({at:new Date().toISOString(),results},null,2));
  }
})().catch(error=>{console.error(error);for(const socket of sockets)socket.destroy();server.close();device.close();process.exitCode=1});
