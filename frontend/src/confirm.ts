import { createApp } from 'vue'
import ConfirmDialog from './ConfirmDialog.vue'

type Options={title?:string;confirmText?:string;danger?:boolean}
let active=false
/** Concurrent requests are cancelled so a second action cannot share approval. */
export function confirmDialog(description:string,options:Options={}):Promise<boolean>{
  if(active)return Promise.resolve(false)
  active=true
  const previous=document.activeElement instanceof HTMLElement?document.activeElement:null
  const host=document.createElement('div')
  document.body.appendChild(host)
  return new Promise(resolve=>{
    const app=createApp(ConfirmDialog,{
      title:options.title??'确认操作',description,
      confirmText:options.confirmText??'确认继续',danger:options.danger??/删除|丢弃|撤销|恢复|失效|delete|discard|restore|regenerate/i.test(description),
      onResult:(value:boolean)=>{
        app.unmount();host.remove();active=false
        if(previous?.isConnected)previous.focus()
        resolve(value)
      },
    })
    app.mount(host)
  })
}
