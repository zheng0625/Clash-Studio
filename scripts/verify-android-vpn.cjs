// Run only on an authorized test device with app and optional :vpn-probe installed.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
const net=require('node:net');
const adb=process.env.ADB||'adb',serial=process.env.ANDROID_SERIAL;
const packageName=process.env.ANDROID_PACKAGE||'studio.clash.android.validation';
const component=packageName+'/studio.clash.android.MainActivity';
if(!serial)throw Error('Set ANDROID_SERIAL to the wireless or USB test device');
const command=(...args)=>execFileSync(adb,['-s',serial,...args],{encoding:'utf8',timeout:30000});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function listenerResponds(){return new Promise(resolve=>{const socket=net.connect(17893,'127.0.0.1');socket.setTimeout(2000);socket.on('connect',()=>socket.write('GET / HTTP/1.1\r\nHost: invalid\r\nConnection: close\r\n\r\n'));socket.on('data',data=>{socket.destroy();resolve(data.toString().startsWith('HTTP/'))});socket.on('timeout',()=>{socket.destroy();resolve(false)});socket.on('error',()=>resolve(false));socket.on('end',()=>resolve(false))})}
const output=path.resolve(process.env.ANDROID_TEST_OUTPUT||'artifacts/android-vpn');fs.mkdirSync(output,{recursive:true});
let ws,sequence=0;const calls=new Map();
async function connect(){
 command('shell','am','start','-W','-n',component);
 const pid=command('shell','pidof',packageName).trim();
 command('forward','tcp:9223',`localabstract:webview_devtools_remote_${pid}`);
 let target;for(let i=0;i<60;i++){try{target=(await(await fetch('http://127.0.0.1:9223/json/list')).json()).find(t=>t.url.includes('appassets.androidplatform.net'));if(target)break}catch{}await sleep(100)}
 assert.ok(target,'WebView debugging target');ws=new WebSocket(target.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
 ws.onmessage=e=>{const r=JSON.parse(e.data),call=calls.get(r.id);if(call){calls.delete(r.id);clearTimeout(call.timer);r.error?call.reject(Error(JSON.stringify(r.error))):call.resolve(r.result)}};
 ws.onclose=()=>{for(const call of calls.values()){clearTimeout(call.timer);call.reject(Error('WebView closed'))}calls.clear()};
 for(let i=0;i<100;i++){if(await evaluate("!!window.ClashAndroid&&!!document.querySelector('.desk')"))break;await sleep(100)}
 await evaluate(`(()=>{const b=window.ClashAndroid,original=b.onmessage,requests=new Map();b.onmessage=e=>{const r=JSON.parse(e.data),resolve=requests.get(r.id);if(resolve){requests.delete(r.id);resolve(r)}else original?.(e)};window.__vpnTest=(path,method,body)=>new Promise(resolve=>{const id='vpn-test-'+crypto.randomUUID();requests.set(id,resolve);b.postMessage(JSON.stringify({id,path,method,body}))});return true})()`);
}
async function evaluate(expression){
 const r=await new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>{calls.delete(id);reject(Error('CDP timed out'))},180000);calls.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method:'Runtime.evaluate',params:{expression,returnByValue:true,awaitPromise:true}}))});
 if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;
}
async function raw(p,m='GET',body=null){return evaluate(`window.__vpnTest(${JSON.stringify(p)},${JSON.stringify(m)},${JSON.stringify(body)})`)}
async function api(...args){const r=await raw(...args);assert.equal(r.status,200,JSON.stringify(r));return r.data}
async function probe(){
 await sleep(1000); // Android publishes the new default VPN network asynchronously.
 command('shell','am','force-stop','studio.clash.vpnprobe');
 command('shell','run-as','studio.clash.vpnprobe','rm','-f','files/result.json');
 command('shell','am','start','-W','-n','studio.clash.vpnprobe/.ProbeActivity');
 let result;for(let i=0;i<100;i++){try{result=JSON.parse(command('shell','run-as','studio.clash.vpnprobe','cat','files/result.json'));break}catch{}await sleep(500)}
 command('shell','am','start','-W','-n',component);
 assert.ok(result,'Separate UID probe completed');return result;
}
(async()=>{
 const results=[];let profile,oldSelected;
 const pass=(name,detail)=>{results.push({name,passed:true,...(detail?{detail}:{})});console.log('PASS '+name)};
 await connect();assert.equal((await api('/api/client/runtime')).running,false,'Stop existing VPN manually before this test');
 oldSelected=await evaluate("localStorage.getItem('clash-desk-profile')");
 try{
  const capabilities=(await api('/api/client/platform')).capabilities;assert.equal(capabilities.core,true);assert.equal(capabilities.vpn,true);pass('arm64-capabilities');
  profile=await api('/api/subscriptions','POST',{title:'VPN 自动验证 · 测试后清理',source_type:'file',yaml:'proxies: []\nproxy-groups:\n - {name: VPN-Test, type: select, proxies: [DIRECT, REJECT]}\nrules:\n - MATCH,VPN-Test\n'});
  const payload={profile_id:profile.id,profile_revision:profile.revision,workspace_revision:1,mixed_port:17890,proxy_mode:'vpn'};
  const pick=async(group,name)=>api('/api/client/proxy-selection','PUT',{...payload,group,name});
  assert.equal((await api('/api/client/runtime/apply','POST',payload)).vpn.enabled,true);pass('vpn-start');
  let check=await probe();console.log(JSON.stringify(check));assert.equal(check.vpn,true);assert.equal(check.udp_dns,true);assert.equal(check.https,true);assert.equal(check.http_status,200);pass('separate-uid-tcp-https-udp-dns',check);
  const counters=await api('/api/client/network/traffic');assert.ok(counters.download>0);assert.ok(counters.upload>0);pass('real-traffic-counters');
  await pick('VPN-Test','REJECT');check=await probe();assert.equal(check.vpn,true);assert.equal(check.udp_dns,true);assert.equal(check.https,false);pass('rule-selector-rejects-https');
  assert.equal((await raw(`/api/subscriptions/${profile.id}?revision=${profile.revision}`,'DELETE')).status,409);pass('active-profile-delete-protected');
  await api('/api/client/runtime/routing-mode','PUT',{mode:'direct'});check=await probe();assert.equal(check.https,true);pass('direct-mode-bypasses-selected-reject');
  await api('/api/client/runtime/routing-mode','PUT',{mode:'global'});await pick('GLOBAL','DIRECT');
  const live=await api('/api/client/proxy-catalog?profile_id='+profile.id);assert.equal(live.live,true);assert.equal(live.proxies.GLOBAL.now,'DIRECT');
  check=await probe();assert.equal(check.https,true);pass('global-mode-and-global-selection');
  await pick('VPN-Test','DIRECT');await api('/api/client/runtime/routing-mode','PUT',{mode:'rule'});
  assert.equal((await api('/api/client/runtime/apply','POST',payload)).running,true);
  check=await probe();assert.equal(check.https,true);pass('reapply-keeps-foreground-vpn');
  assert.match(command('shell','dumpsys','activity','services',packageName),/isForeground=true foregroundId=27/);pass('foreground-service');
  const connections=await api('/api/client/runtime/connections');assert.ok(Object.hasOwn(connections,'uploadTotal'));pass('native-connections-snapshot');
  await evaluate(`localStorage.setItem('clash-desk-profile',${JSON.stringify(profile.id)});location.reload();true`);ws.close();await sleep(500);await connect();
  for(let i=0;i<100;i++){if(await evaluate("document.querySelector('.kernel-summary')?.innerText.includes('Android VPN')"))break;await sleep(100)}
  assert.equal(await evaluate("document.querySelector('.kernel-summary')?.innerText.includes('Android VPN')"),true);
  assert.equal(await evaluate("document.querySelectorAll('.mobile-navigation button').length"),5);
  assert.equal(await evaluate("document.querySelector('.desk-content').scrollWidth>document.querySelector('.desk-content').clientWidth+2"),false);pass('real-vpn-ui-and-liquid-dock');
  if(!await evaluate('document.hidden'))fs.writeFileSync(path.join(output,'vpn-running.png'),execFileSync(adb,['-s',serial,'exec-out','screencap','-p']));
  await evaluate("document.querySelector('.kernel-actions .danger').click();true");
  for(let i=0;i<100;i++){if(!(await api('/api/client/runtime')).running)break;await sleep(100)}
  assert.equal((await api('/api/client/runtime')).running,false);pass('ui-stop-closes-vpn');
  command('forward','tcp:17893','tcp:17890');assert.equal(await listenerResponds(),false);pass('stop-releases-mixed-listener');
  for(let i=0;i<100;i++){if(await evaluate("document.querySelector('.kernel-actions>button:first-child')?.disabled===false"))break;await sleep(100)}
  await evaluate("document.querySelector('.kernel-actions>button:first-child').click();true");
  for(let i=0;i<100;i++){if((await api('/api/client/runtime')).running)break;await sleep(100)}
  assert.equal((await api('/api/client/runtime')).vpn.enabled,true);pass('ui-restart');
 }finally{
  await api('/api/client/runtime/stop','POST',{});
  if(profile){const current=await api('/api/subscriptions/'+profile.id);await api(`/api/subscriptions/${profile.id}?revision=${current.revision}`,'DELETE')}
  if(oldSelected)await evaluate(`localStorage.setItem('clash-desk-profile',${JSON.stringify(oldSelected)});true`);else await evaluate("localStorage.removeItem('clash-desk-profile');true");
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({at:new Date().toISOString(),results},null,2));
  ws.close();command('forward','--remove','tcp:9223');
  try{command('forward','--remove','tcp:17893')}catch{}
 }
 console.log(JSON.stringify({passed:results.length,output}));
})().catch(error=>{console.error(error);process.exit(1)});
