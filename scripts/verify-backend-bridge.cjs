// Requires the local Vite preview and Playwright. No native core or VPN is started.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'chrome'});
  try{
    const page=await browser.newPage();
    await page.goto(process.env.UI_PREVIEW_URL||'http://127.0.0.1:5187/ui-preview.html');
    const result=await page.evaluate(async()=>{
      const {lifecycle,ApiError}=await import('/src/api.ts');
      const original=window.fetch;
      const paths=[];
      try{
        let poll=0;
        window.fetch=async (path, options)=>{
          if(!String(path).includes('/runtime/apply')&&!String(path).includes('/operations/'))return original(path,options);
          paths.push(String(path));
          const value=String(path).includes('/operations/')?
            (++poll===1?{operation_id:'job',phase:'running'}:{operation_id:'job',phase:'succeeded',result:{running:true}}):
            {operation_id:'job',phase:'queued'};
          return new Response(JSON.stringify(value),{status:poll?200:202});
        };
        const desktop=await lifecycle('/api/client/runtime/apply',{});
        window.fetch=async()=>new Response(JSON.stringify({operation_id:'failed',phase:'failed',error:{code:'APPLY_ROLLED_BACK',message:'rolled back',retryable:true}}),{status:202});
        let code='';
        try{await lifecycle('/api/client/runtime/apply',{})}catch(error){if(error instanceof ApiError)code=error.code}
        const nativePaths=[];
        const bridge={onmessage:null,postMessage(text){
          const request=JSON.parse(text);nativePaths.push(request.path);
          queueMicrotask(()=>bridge.onmessage({data:JSON.stringify({id:request.id,status:200,data:{running:true,operation_id:'native-ticket',phase:'running'}})}));
        }};
        window.ClashAndroid=bridge;
        const native=await lifecycle('/api/client/runtime/apply',{});
        return {desktop,paths,code,native,nativePaths};
      }finally{window.fetch=original;delete window.ClashAndroid}
    });
    assert.equal(result.desktop.running,true);
    assert.equal(result.paths[0],'/api/client/runtime/apply?background=true');
    assert.equal(result.paths.length,3);
    assert.equal(result.code,'APPLY_ROLLED_BACK');
    assert.equal(result.native.running,true);
    assert.deepEqual(result.nativePaths,['/api/client/runtime/apply']);
    console.log('PASS: desktop job polling, stable failure codes, Android direct lifecycle response');
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
