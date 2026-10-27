const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {DeviceSession,sleep}=require('./android-device-session.cjs');
const device=new DeviceSession(),results=[];
const output=path.resolve(process.env.ANDROID_LIFECYCLE_OUTPUT||'artifacts/android-device-2026-10-26/lifecycle');
fs.mkdirSync(output,{recursive:true});
function pass(name,detail){results.push({name,passed:true,detail});console.log('PASS '+name+(detail?' '+JSON.stringify(detail):''))}
(async()=>{
  let profile;
  await device.connect();
  assert.equal((await device.api('/api/client/runtime')).running,false);
  device.command('forward','tcp:17894','tcp:17890');
  try{
    profile=await device.api('/api/subscriptions','POST',{title:'生命周期故障验收 · 临时',source_type:'file',yaml:'proxies: []\nproxy-groups:\n - {name: Test, type: select, proxies: [DIRECT, REJECT]}\nrules: ["MATCH,Test"]\n'});
    const body={profile_id:profile.id,profile_revision:profile.revision,workspace_revision:1,mixed_port:17890,proxy_mode:'vpn'};
    await device.api('/api/client/proxy-selection','PUT',{...body,group:'Test',name:'DIRECT'});
    if(process.env.ANDROID_ACTIVITY_ONLY!=='1'){
    for(const stage of ['before-tunnel','after-selector-restore']){
      device.fault(stage,5000);await device.start(body);await device.entered(stage);
      if(stage==='before-tunnel')await device.evaluate(`window.__queuedStart=window.__deviceRequest('/api/client/runtime/apply','POST',${JSON.stringify(body)});true`);
      const latencies=[];
      for(let i=0;i<12;i++){const start=performance.now();const state=await device.api('/api/client/runtime');latencies.push(performance.now()-start);assert.equal(state.running,false)}
      const started=performance.now();
      const stopping=device.api('/api/client/runtime/stop','POST',{});
      await sleep(50);
      const intent=await device.api('/api/client/runtime');
      assert.equal(intent.cancel_requested,true);
      const obsolete=await device.evaluate('window.__pendingStart');
      assert.equal(obsolete.status,409);
      if(stage==='before-tunnel')assert.equal((await device.evaluate('window.__queuedStart')).status,409);
      await stopping;await device.stopped();
      assert.equal(await device.listenerResponds(),false);
      device.clearFault();
      latencies.sort((a,b)=>a-b);
      pass('cancel-'+stage,{samples:latencies.length,status_p50_ms:+latencies[5].toFixed(2),status_p95_ms:+latencies[11].toFixed(2),cleanup_ms:+(performance.now()-started).toFixed(2)});
      assert.equal((await device.api('/api/client/runtime/apply','POST',body)).running,true);
      await device.api('/api/client/runtime/stop','POST',{});await device.stopped();
    }
    device.fault('native:getProxies',40000);await device.start(body);await device.entered('native:getProxies');
    console.log('WAIT delayed native callback: 30 s callback timeout, then late delivery');
    let started=performance.now();
    const late=await device.evaluate('window.__pendingStart');
    assert.equal(late.status,504);assert.equal(late.data.error.code,'TIMEOUT');
    await device.stopped();await sleep(11500);
    assert.equal((await device.api('/api/client/runtime')).running,false);
    assert.equal(await device.listenerResponds(),false);
    pass('late-native-callback-discarded',{observed_ms:+(performance.now()-started).toFixed(2)});
    device.clearFault();
    device.fault('after-quick-setup',96000);await device.start(body);await device.entered('after-quick-setup');
    console.log('WAIT real 90 s startup deadline; lifecycle stays occupied until 96 s fault returns');
    started=performance.now();
    const deadline=await device.evaluate('window.__pendingStart');
    const elapsed=performance.now()-started;
    assert.equal(deadline.status,504);assert.equal(deadline.data.error.code,'TIMEOUT');
    assert.ok(elapsed>85000&&elapsed<95000);
    const pending=await device.api('/api/client/runtime');assert.equal(pending.running,false);assert.equal(pending.cancel_requested,true);assert.ok(pending.operation_id);
    const retry=await device.raw('/api/client/runtime/apply','POST',body);assert.equal(retry.status,409);
    await device.stopped(20000);assert.equal(await device.listenerResponds(),false);
    device.clearFault();pass('startup-90s-timeout-never-establishes-vpn',{response_ms:+elapsed.toFixed(2)});
    for(let i=0;i<3;i++){
      const state=await device.api('/api/client/runtime/apply','POST',body);assert.equal(state.vpn.enabled,true);
      await device.api('/api/client/runtime/stop','POST',{});await device.stopped();assert.equal(await device.listenerResponds(),false);
    }
    pass('three-restarts-after-timeout');
    }
    const running=await device.api('/api/client/runtime/apply','POST',body);
    device.command('shell','input','keyevent','KEYCODE_HOME');await sleep(1000);
    assert.equal((await device.api('/api/client/runtime')).session,running.session);
    device.command('shell','am','start','-W','-n',device.component);
    assert.equal((await device.api('/api/client/runtime')).running,true);
    pass('background-foreground-keeps-vpn');
    device.command('shell','am','start','-W','-f','0x10008000','-n',device.component);
    await sleep(500);device.ws.close();await device.connect();
    const rebuilt=await device.api('/api/client/runtime');
    assert.equal(rebuilt.running,true);assert.equal(rebuilt.session,running.session);
    pass('activity-destroy-recreate-keeps-running-vpn');
    // Changing AppOps alone does not revoke an already established VPN on this
    // device. Use Settings' actual per-app Forget action to invoke onRevoke.
    device.command('shell','am','start','-W','-a','android.settings.VPN_SETTINGS');
    device.openIsolatedVpnSettings();
    device.assertIsolatedVpnUi();
    device.clickUi('text','取消保存 VPN');
    device.assertIsolatedVpnUi();
    device.clickUi('text','取消保存');
    await device.stopped(15000);
    assert.equal((await device.api('/api/android/permissions')).vpn,false);
    assert.equal(await device.listenerResponds(),false);
    pass('system-vpn-authorization-revocation-cleans-resources');
    device.command('shell','am','start','-W','-n',device.component);
    await device.start(body);await sleep(600);
    await device.api('/api/client/runtime/stop','POST',{});
    assert.equal((await device.evaluate('window.__pendingStart')).status,409);
    device.command('shell','input','keyevent','KEYCODE_BACK');await sleep(500);
    assert.equal((await device.api('/api/client/runtime')).running,false);
    pass('stop-cancels-pending-system-consent');
    await device.start(body);await sleep(500);
    device.clickUi('text','确定');
    const approved=await device.evaluate('window.__pendingStart');
    assert.equal(approved.status,200);assert.equal(approved.data.running,true);
    await device.api('/api/client/runtime/stop','POST',{});await device.stopped();
    pass('system-consent-approval-starts-through-lifecycle-queue');
    device.command('shell','cmd','appops','set',device.pkg,'ACTIVATE_VPN','allow');
    device.fault('before-tunnel',5000);await device.start(body);await device.entered('before-tunnel');
    device.command('shell','am','start','-W','-f','0x10008000','-n',device.component);
    await sleep(500);device.ws.close();await device.connect();
    assert.equal((await device.api('/api/client/runtime')).running,false);
    await device.stopped(10000);device.clearFault();
    assert.equal(await device.listenerResponds(),false);
    assert.equal((await device.api('/api/client/runtime/apply','POST',body)).running,true);
    pass('activity-destroy-during-start-cancels-and-can-restart');
  }finally{
    device.command('shell','cmd','appops','set',device.pkg,'ACTIVATE_VPN','allow');
    device.clearFault();
    await device.api('/api/client/runtime/stop','POST',{});await device.stopped(20000);
    if(profile){const row=await device.api('/api/subscriptions/'+profile.id);await device.api(`/api/subscriptions/${row.id}?revision=${row.revision}`,'DELETE')}
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({at:new Date().toISOString(),results},null,2));
    device.close();
  }
})().catch(error=>{console.error(error);device.close();process.exitCode=1});
