import { androidRequest } from './android'
export const isDesktop = '__TAURI_INTERNALS__' in window && !/Android/i.test(navigator.userAgent)
export async function desktopInfo():Promise<{backend_base:string;version:string;desktop:boolean}> {
  if(isDesktop){const {invoke}=await import('@tauri-apps/api/core');return invoke('desktop_info')}
  return {backend_base:location.origin,version:'1.1.0',desktop:false}
}
export async function restartElevated(){const {invoke}=await import('@tauri-apps/api/core');return invoke('restart_elevated')}
export async function quitDesktop(){const {invoke}=await import('@tauri-apps/api/core');return invoke('quit_app')}
export async function closeDesktop(){const {invoke}=await import('@tauri-apps/api/core');return invoke<boolean>('close_desktop')}
export class ApiError extends Error {
  constructor(message:string,public status:number,public code:string,public retryable:boolean,public operationId?:string){super(message)}
}
export async function lifecycle<T>(path:string,body:unknown):Promise<T>{
  type Job={operation_id:string;phase:string;result?:T;error?:{message:string;code:string;retryable:boolean}}
  let value=await api<T|Job>(path+(window.ClashAndroid?'':'?background=true'),'POST',body)
  if(window.ClashAndroid)return value as T
  if(!('operation_id' in (value as object))||!('phase' in (value as object)))return value as T
  let job=value as Job
  while(job.phase==='queued'||job.phase==='running'){
    await new Promise(resolve=>setTimeout(resolve,250))
    job=await api<Job>(`/api/client/operations/${job.operation_id}`)
  }
  if(job.phase==='succeeded')return job.result as T
  throw new ApiError(job.error?.message||'操作已取消',409,job.error?.code||'OPERATION_CANCELLED',job.error?.retryable??true,job.operation_id)
}
export async function api<T>(path:string,method='GET',body?:unknown):Promise<T>{
  let status:number,data:any
  if(window.ClashAndroid){
    const result=await androidRequest(path,method,body)
    status=result.status;data=result.data
  }else if(isDesktop){
    const {invoke}=await import('@tauri-apps/api/core')
    const result=await invoke<{status:number;data:any}>('backend_request',{path,method,body:body??null})
    status=result.status;data=result.data
  }else{
    const response=await fetch(path,{method,headers:{'Content-Type':'application/json','X-Clash-Studio':'1'},body:body===undefined?undefined:JSON.stringify(body)})
    status=response.status;data=await response.json()
  }
  if(status>=400){const detail=data.detail;throw new ApiError(data.error?.message||(typeof detail==='string'?detail:detail?.errors?.join('；')||detail?.message||'输入格式无效或操作未完成'),status,data.error?.code||'LEGACY_ERROR',data.error?.retryable??false,data.error?.operation_id)}
  return data
}
