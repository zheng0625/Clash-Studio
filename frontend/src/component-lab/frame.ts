// Use the actual Client tree and stylesheet entry, with local fixture transport.
import { catalogue as desktopCatalogue } from './catalogue'
import { androidCatalogue } from './android-catalogue'
import { mockIPC, mockWindows } from '@tauri-apps/api/mocks'
// Copy saved appearance for this document; keep preview writes in memory.
const saved=window.localStorage
const values=new Map(Array.from({length:saved.length},(_,i)=>{const key=saved.key(i)!;return [key,saved.getItem(key)!]}))
const storage={get length(){return values.size},key:(i:number)=>Array.from(values.keys())[i]??null,getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,String(value))},removeItem:(key:string)=>{values.delete(key)},clear:()=>values.clear()}
Object.defineProperty(window,'localStorage',{value:storage})
const params=new URLSearchParams(location.search)
if(params.get('scene')==='英文')storage.setItem('clash-studio-language-v1','en')
if(params.get('theme')==='dark')storage.setItem('clash-studio-theme-mode-v1','dark')
if(params.get('scene')==='TUN 待授权')storage.setItem('clash-desk-mode','tun')
const android=params.get('platform')==='android'
if(android){
  // Same CSS inset contract as MainActivity; values mirror the connected test phone.
  const updateInsets=()=>{
    const landscape=innerWidth>innerHeight
    document.documentElement.style.setProperty('--android-status-inset',landscape?'0px':'43.333333px')
    document.documentElement.style.setProperty('--android-nav-inset','24px')
  }
  updateInsets();window.addEventListener('resize',updateInsets)
  const chrome=document.createElement('div')
  chrome.setAttribute('aria-hidden','true')
  chrome.className='lab-android-system-bars'
  chrome.innerHTML='<div class="lab-system-status"><span>9:41</span><span>▰ ◔ 100%</span></div><div class="lab-system-gesture"><i></i></div>'
  document.body.append(chrome)
  const chromeStyle=document.createElement('style')
  chromeStyle.textContent='.lab-android-system-bars{pointer-events:none;color:var(--client-text);font:600 13px/1 system-ui}.lab-system-status{position:fixed;inset:0 0 auto;height:var(--android-status-inset);display:flex;align-items:center;justify-content:space-between;padding:0 24px;z-index:1000;box-sizing:border-box}.lab-system-gesture{position:fixed;inset:auto 0 0;height:var(--android-nav-inset);display:grid;place-items:center;z-index:1000}.lab-system-gesture i{width:108px;height:4px;border-radius:4px;background:currentColor;opacity:.65}@media(orientation:landscape){.lab-system-status{display:none}}'
  document.head.append(chromeStyle)
}
const catalogue=android?androidCatalogue:desktopCatalogue
const component=params.get('component')||'kernel'
const target=catalogue.find(entry=>entry.id===component)||catalogue[0]
if(android&&component==='kernel'&&['应用中','应用失败'].includes(params.get('scene')||''))target.steps=[{selector:'.kernel-actions button'}]
// Official Tauri mocks render desktop-only panels without invoking native commands.
if(!android){
mockWindows('main')
let preferences={resident:true,autostart:false}
mockIPC(async(command,args)=>{
  const payload=(args||{}) as Record<string,any>
  if(command==='backend_request'){const response=await window.fetch(String(payload.path),{method:payload.method,body:payload.body==null?undefined:JSON.stringify(payload.body)});return {status:response.status,data:await response.json()}}
  if(command==='startup_status')return {phase:'ready'}
  if(command==='desktop_info')return {backend_base:location.origin,version:'1.3.0',desktop:true}
  if(command==='system_locale')return 'zh-CN'
  if(command==='desktop_preferences')return preferences
  if(command==='set_desktop_preferences'){preferences=payload.preferences;return preferences}
  if(command==='background_load')return {has_image:false}
  return null
},{shouldMockEvents:true})
}
const style=document.createElement('style')
style.textContent='.lab-target{outline:2px solid var(--client-accent)!important;outline-offset:4px}'
document.head.append(style)
let announced=false,step=0
const observer=new MutationObserver(()=>{
  const desk=document.querySelector<HTMLElement>('.desk[data-ui-page]')
  if(!desk)return
  if(!announced&&desk.dataset.uiPage!==target.page){
    const order=android?['home','subscriptions','routing','proxies','connections','settings']:['home','subscriptions','modules','proxies','connections','studio','settings']
    const buttons=document.querySelectorAll<HTMLButtonElement>('.liquid-dock .dock-item')
    buttons[order.indexOf(target.page)]?.click()
    return
  }
  if(step<(target.steps?.length||0)){
    const action=target.steps![step]
    const buttons=Array.from(document.querySelectorAll<HTMLElement>(action.selector)).filter(el=>el.getClientRects().length&&(!action.text||el.textContent?.includes(action.text)))
    const button=buttons[action.index||0]
    if(!button||(button as HTMLButtonElement).disabled)return
    step++;button.click();return
  }
  const element=document.querySelector<HTMLElement>(target.selector)
  if(!element||!element.getClientRects().length||element.classList.contains('lab-target'))return
  element.classList.add('lab-target')
  element.scrollIntoView({block:'center',behavior:'instant'})
  if(!announced){announced=true;requestAnimationFrame(()=>{const animations=document.getAnimations().filter(animation=>animation.effect?.getComputedTiming().iterations!==Infinity);void Promise.allSettled(animations.map(animation=>animation.finished)).then(()=>{if(element.isConnected)parent.postMessage({type:'clash-lab-ready',component,width:Math.round(element.getBoundingClientRect().width)},location.origin)})})}
})
observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['data-ui-page']})
document.addEventListener('click',event=>{const button=(event.target as Element)?.closest('button');if(button)parent.postMessage({type:'clash-lab-event',label:button.getAttribute('aria-label')||button.textContent?.trim()||'点击'},location.origin)},true)
await import('../ui-editor/preview')
