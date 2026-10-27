const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
class DeviceSession {
  constructor(){
    this.adb=process.env.ADB||'adb';this.serial=process.env.ANDROID_SERIAL;
    this.pkg=process.env.ANDROID_PACKAGE||'studio.clash.android.validation.acceptance';
    assert(this.serial,'ANDROID_SERIAL required');assert(this.pkg.endsWith('.acceptance'),'isolated acceptance package required');
    this.component=this.pkg+'/studio.clash.android.MainActivity';this.calls=new Map();this.sequence=0;
  }
  command(...args){return execFileSync(this.adb,['-s',this.serial,...args],{encoding:'utf8',timeout:30000,stdio:['pipe','pipe','pipe']})}
  privateFile(name){return this.command('shell','run-as',this.pkg,'cat','no_backup/'+name)}
  fault(stage,delay_ms){
    this.clearFault();
    execFileSync(this.adb,['-s',this.serial,'shell','run-as',this.pkg,'tee','no_backup/lifecycle-fault.json'],{input:JSON.stringify({stage,delay_ms}),timeout:10000,stdio:['pipe','pipe','pipe']});
  }
  clearFault(){this.command('shell','run-as',this.pkg,'rm','-f','no_backup/lifecycle-fault.json','no_backup/lifecycle-fault-entered.json')}
  async connect(){
    this.command('shell','am','start','-W','-n',this.component);
    const pid=this.command('shell','pidof',this.pkg).trim();
    this.command('forward','tcp:9224','localabstract:webview_devtools_remote_'+pid);
    let target;
    for(let i=0;i<100;i++){
      try{target=(await(await fetch('http://127.0.0.1:9224/json/list')).json()).find(t=>t.url.includes('appassets.androidplatform.net'));if(target)break}catch{}
      await sleep(100);
    }
    assert(target,'WebView debugging target');
    this.ws=new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve,reject)=>{this.ws.onopen=resolve;this.ws.onerror=reject});
    this.ws.onmessage=event=>{const value=JSON.parse(event.data),call=this.calls.get(value.id);if(call){this.calls.delete(value.id);clearTimeout(call.timer);value.error?call.reject(Error(JSON.stringify(value.error))):call.resolve(value.result)}};
    this.ws.onclose=()=>{for(const call of this.calls.values()){clearTimeout(call.timer);call.reject(Error('WebView closed'))}this.calls.clear()};
    for(let i=0;i<100;i++){if(await this.evaluate("!!window.ClashAndroid&&!!document.querySelector('.desk')"))break;await sleep(100)}
    await this.evaluate(`(()=>{const bridge=window.ClashAndroid,original=bridge.onmessage,pending=new Map();bridge.onmessage=event=>{const value=JSON.parse(event.data),resolve=pending.get(value.id);if(resolve){pending.delete(value.id);resolve(value)}else original?.(event)};window.__deviceRequest=(path,method='GET',body=null)=>new Promise(resolve=>{const id='acceptance-'+crypto.randomUUID();pending.set(id,resolve);bridge.postMessage(JSON.stringify({id,path,method,body}))});return true})()`);
  }
  async evaluate(expression){
    const result=await new Promise((resolve,reject)=>{const id=++this.sequence,timer=setTimeout(()=>{this.calls.delete(id);reject(Error('CDP timeout'))},180000);this.calls.set(id,{resolve,reject,timer});this.ws.send(JSON.stringify({id,method:'Runtime.evaluate',params:{expression,returnByValue:true,awaitPromise:true}}))});
    if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;
  }
  raw(path,method='GET',body=null){return this.evaluate(`window.__deviceRequest(${JSON.stringify(path)},${JSON.stringify(method)},${JSON.stringify(body)})`)}
  async api(...args){const value=await this.raw(...args);assert.equal(value.status,200,JSON.stringify(value));return value.data}
  async start(body){return this.evaluate(`window.__pendingStart=window.__deviceRequest('/api/client/runtime/apply','POST',${JSON.stringify(body)});true`)}
  async waitFor(check,timeout=15000){const deadline=Date.now()+timeout;while(Date.now()<deadline){const value=await check();if(value)return value;await sleep(200)}throw Error('Condition timeout '+timeout+' ms')}
  async entered(stage){return this.waitFor(()=>{try{return JSON.parse(this.privateFile('lifecycle-fault-entered.json')).stage===stage}catch{return false}},15000)}
  uiNodes(){
    this.command('shell','uiautomator','dump','/data/local/tmp/clash-acceptance-ui.xml');
    const xml=this.command('shell','cat','/data/local/tmp/clash-acceptance-ui.xml');
    return xml.match(/<node\b[^>]*>/g)||[];
  }
  openIsolatedVpnSettings(){
    const nodes=this.uiNodes(),label='Clash Studio · 验收';
    const own=nodes.find(node=>node.includes('text="'+label+'"')||node.includes('content-desc="'+label+'"'));
    assert.ok(own,'Only the isolated acceptance VPN may be changed');
    const icons=nodes.filter(node=>node.includes('content-desc="设置"'));
    if(!icons.length){assert.ok(nodes.some(node=>node.includes('text="取消保存 VPN"')),'Expected acceptance VPN details');return}
    const bounds=node=>{const value=node.match(/bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/);assert(value);return value.slice(1).map(Number)};
    const [,top,,bottom]=bounds(own);
    const matches=icons.filter(node=>{const [,y1,,y2]=bounds(node);return (y1+y2)/2>=top&&(y1+y2)/2<=bottom});
    assert.equal(matches.length,1,'A settings icon must align with the acceptance VPN row');
    const [x1,y1,x2,y2]=bounds(matches[0]);
    this.command('shell','input','tap',String(Math.round((x1+x2)/2)),String(Math.round((y1+y2)/2)));
  }
  assertIsolatedVpnUi(){
    assert.ok(this.uiNodes().some(node=>node.includes('text="Clash Studio · 验收"')||node.includes('content-desc="Clash Studio · 验收"')),'Refusing to forget another VPN');
  }
  clickUi(attribute,value,optional=false){
    assert.ok(['text','content-desc'].includes(attribute));
    const node=this.uiNodes().find(node=>node.includes(attribute+'="'+value+'"'));
    if(!node&&optional)return false;
    assert.ok(node,'Expected Android control: '+value);
    const bounds=node.match(/bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/);
    assert.ok(bounds,'Control bounds');
    this.command('shell','input','tap',String(Math.round((+bounds[1]+ +bounds[3])/2)),String(Math.round((+bounds[2]+ +bounds[4])/2)));
  }
  async stopped(timeout=15000){return this.waitFor(async()=>{const state=await this.api('/api/client/runtime');return !state.running&&state.phase==='stopped'&&!state.operation_id?state:null},timeout)}
  async listenerResponds(){
    const net=require('node:net');
    return new Promise(resolve=>{const socket=net.connect(17894,'127.0.0.1');socket.setTimeout(1000);socket.on('connect',()=>socket.write('GET / HTTP/1.1\r\nHost: invalid\r\nConnection: close\r\n\r\n'));socket.on('data',data=>{socket.destroy();resolve(data.toString().startsWith('HTTP/'))});socket.on('error',()=>resolve(false));socket.on('end',()=>resolve(false));socket.on('timeout',()=>{socket.destroy();resolve(false)})});
  }
  close(){this.ws?.close();try{this.command('forward','--remove','tcp:9224')}catch{}try{this.command('forward','--remove','tcp:17894')}catch{}}
}
module.exports={DeviceSession,sleep};
