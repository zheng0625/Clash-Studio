export const isDesktop = '__TAURI_INTERNALS__' in window
export async function desktopInfo():Promise<{backend_base:string;version:string;desktop:boolean}> {
  if(isDesktop){const {invoke}=await import('@tauri-apps/api/core');return invoke('desktop_info')}
  return {backend_base:location.origin,version:'0.5.1',desktop:false}
}
export async function restartElevated(){const {invoke}=await import('@tauri-apps/api/core');return invoke('restart_elevated')}
export async function quitDesktop(){const {invoke}=await import('@tauri-apps/api/core');return invoke('quit_app')}
export async function api<T>(path:string,method='GET',body?:unknown):Promise<T>{
  let status:number,data:any
  if(isDesktop){
    const {invoke}=await import('@tauri-apps/api/core')
    const result=await invoke<{status:number;data:any}>('backend_request',{path,method,body:body??null})
    status=result.status;data=result.data
  }else{
    const response=await fetch(path,{method,headers:{'Content-Type':'application/json','X-Clash-Studio':'1'},body:body===undefined?undefined:JSON.stringify(body)})
    status=response.status;data=await response.json()
  }
  if(status>=400){const detail=data.detail;throw new Error(typeof detail==='string'?detail:detail?.errors?.join('；')||detail?.message||'输入格式无效或操作未完成')}
  return data
}
