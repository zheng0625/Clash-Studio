type Reply={id:string;status:number;data:any}
type Bridge={postMessage:(message:string)=>void;onmessage:((event:{data:string})=>void)|null}
declare global {interface Window {ClashAndroid?:Bridge}}
const pending=new Map<string,{resolve:(reply:Reply)=>void;reject:(error:Error)=>void;timer:ReturnType<typeof setTimeout>}>()
let attached:Bridge|undefined
export function androidRequest(path:string,method:string,body?:unknown):Promise<Reply>{
  const bridge=window.ClashAndroid
  if(!bridge)return Promise.reject(new Error('Android 原生桥接未加载，请更新 System WebView'))
  if(attached!==bridge){
    attached=bridge
    bridge.onmessage=event=>{
      let reply:Reply
      try{reply=JSON.parse(event.data)}catch{return}
      const request=pending.get(reply.id)
      if(request){clearTimeout(request.timer);pending.delete(reply.id);request.resolve(reply)}
    }
  }
  return new Promise((resolve,reject)=>{
    const id=crypto.randomUUID(),timer=setTimeout(()=>{pending.delete(id);reject(new Error('Android 操作超时，请检查网络后刷新状态'))},path==='/api/android/qr'?600000:path==='/api/android/export'||path==='/api/client/runtime/apply'||path==='/api/client/runtime/delay'?180000:45000)
    pending.set(id,{resolve,reject,timer})
    try{bridge.postMessage(JSON.stringify({id,path,method,body:body??null}))}
    catch(error){clearTimeout(timer);pending.delete(id);reject(error as Error)}
  })
}
export async function saveTextFile(filename:string,text:string):Promise<boolean>{
  if(window.ClashAndroid){
    const result=await androidRequest('/api/android/export','POST',{filename,text})
    if(result.status>=400)throw new Error(result.data?.detail||'文件保存失败')
    return !!result.data.saved
  }
  const url=URL.createObjectURL(new Blob([text],{type:'text/yaml'})),link=document.createElement('a')
  link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),500)
  return true
}
