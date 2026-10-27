<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, defineAsyncComponent, h, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Activity, ArrowDownLeft, ArrowRight, ArrowUpRight, Box, Check, ChevronDown, ChevronRight, CircleHelp, Code2, Download, ExternalLink, FileCode2, FolderOpen, GitBranch, Globe2, LayoutDashboard, Layers3, Loader2, Network, Plus, Power, RefreshCw, Search, Settings2, ShieldCheck, SlidersHorizontal, Trash2, Minus, Square, X } from 'lucide-vue-next'
import type { Summary, Subscription } from './types'
import NetworkDashboard from './NetworkDashboard.vue'
import SubscriptionUsage from './SubscriptionUsage.vue'
import GlassSelect from './GlassSelect.vue'
import AppDialog from './AppDialog.vue'
import LanguageSettings from './LanguageSettings.vue'
import { confirmDialog } from './confirm'
import { api, lifecycle, desktopInfo, isDesktop, quitDesktop, closeDesktop } from './api'
import { saveTextFile } from './android'
import { setMobilePlatformAndroid } from './mobile-tier'

const loadingComponent={setup:()=>()=>h('div',{class:'desk-card settings-loading',role:'status'},t('正在加载界面…'))}
const errorComponent={setup:()=>()=>h('div',{class:'desk-alert error',role:'alert'},t('页面加载失败，请重新打开软件。'))}
const deferred={loadingComponent,errorComponent,delay:120,timeout:15_000}
const AndroidRouting=defineAsyncComponent({...deferred,loader:()=>import('./AndroidRouting.vue')})
const AndroidPermissions=defineAsyncComponent({...deferred,loader:()=>import('./AndroidPermissions.vue')})
const ConfigEditor=defineAsyncComponent({...deferred,loader:()=>import('./ConfigEditor.vue')})
const ProxyPanel=defineAsyncComponent({...deferred,loader:()=>import('./ProxyPanel.vue')})
const ClientSettings=defineAsyncComponent({...deferred,loader:()=>import('./ClientSettings.vue')})
const ProxyPortSettings=defineAsyncComponent({...deferred,loader:()=>import('./ProxyPortSettings.vue')})
const ConnectionPanel=defineAsyncComponent({...deferred,loader:()=>import('./ConnectionPanel.vue')})
const RuntimeLogPanel=defineAsyncComponent({...deferred,loader:()=>import('./RuntimeLogPanel.vue')})

type Page = 'home'|'subscriptions'|'modules'|'proxies'|'connections'|'studio'|'routing'|'settings'
type RoutingMode = 'rule'|'global'|'direct'
const routingChoices: {id:RoutingMode;label:string}[]=[{id:'rule',label:'规则'},{id:'global',label:'全局'},{id:'direct',label:'直连'}]
type Match = {kind:string;value:string}
type Module = {id:string;name:string;target:string;strict:boolean;matches:Match[]}
type Plan = {module_ids:string[];default_target:string}
type Workspace = {revision:number;modules:Module[];plans:Record<string,Plan>}
type Preview = {yaml:string;config:Record<string,any>;errors:string[];warnings:string[];module_rules:{module:string;rule:string;strict:boolean}[];workspace_revision:number;profile_revision:number;published_conflict:boolean}
type Runtime = {egress_version?:number;vpn?:{supported:boolean;enabled:boolean};routing_mode?:RoutingMode|null;running:boolean;installed:boolean;active:null|{profile_id:string;title:string;revision:number;workspace_revision:number;mixed_port:number;hash:string;tun?:boolean};proxy:{supported:boolean;owned:boolean;enabled?:boolean;server?:string};events:{time:string;message:string}[];tun?:{supported:boolean;admin:boolean;helper?:boolean;enabled:boolean;stack:string;device:string;driver_installed:boolean;conflicts:string[]}}
type LiveProxy = {name:string;type:string;all?:string[];now?:string;history?:{delay:number}[]}
type Connection = {id:string;metadata:{host?:string;destinationIP?:string;destinationPort?:string;process?:string;processPath?:string;network?:string};rule:string;rulePayload?:string;chains:string[];upload:number;download:number}
const platform=ref<{os:string;arch:string;capabilities?:{validation?:boolean;native_insets?:boolean;development?:boolean;core?:boolean;modules?:boolean}}>({os:'',arch:''})
const validationBuild=computed(()=>platform.value.capabilities?.validation===true)
const nativeInsets=computed(()=>validationBuild.value||platform.value.capabilities?.native_insets===true)
const nativeCoreUnavailable=computed(()=>platform.value.capabilities?.core===false)
const nativeDevelopment=computed(()=>platform.value.capabilities?.development===true)
const hasModules=computed(()=>platform.value.capabilities?.modules!==false)
const isAndroid=computed(()=>platform.value.os==='android'||/Android/i.test(navigator.userAgent))
// The backend platform identity (or the UI workshop mock) completes the tier
// decision that mobile-tier.ts started from the user agent alone.
watch(isAndroid,value=>setMobilePlatformAndroid(value),{immediate:true})
const supportsTun=computed(()=>!isAndroid.value&&!!runtime.value.tun?.supported)
const supportsSystemProxy=computed(()=>!isAndroid.value&&runtime.value.proxy.supported)
const effectiveProxyMode=computed(()=>isAndroid.value&&!nativeCoreUnavailable.value?'vpn':supportsTun.value&&proxyMode.value==='tun'?'tun':supportsSystemProxy.value?'system':'manual')
const appLabels=ref<Record<string,string>>({})
function processLabel(value:string|undefined){return value&&appLabels.value[value]?appLabels.value[value]+' ('+value+')':value||''}
const platformLabel=computed(()=>({windows:'Windows',linux:'Linux',macos:'macOS',android:'Android'}[platform.value.os]||'')+' '+platform.value.arch)
const brandIcon=new URL('./assets/brand.svg',import.meta.url).href
const nav = computed(() => [
  {id:'home' as Page,label:t("概览"),icon:LayoutDashboard}, {id:'subscriptions' as Page,label:t("订阅"),icon:FolderOpen},
  {id:'routing' as Page,label:t('精确分流'),icon:GitBranch}, {id:'modules' as Page,label:t("模块分流"),icon:Layers3}, {id:'proxies' as Page,label:t("代理"),icon:Globe2},
  {id:'connections' as Page,label:t("连接"),icon:Activity}, {id:'studio' as Page,label:t("配置工作台"),icon:Code2},
  {id:'settings' as Page,label:t("设置与日志"),icon:Settings2},
].filter(item=>(item.id!=='modules'||hasModules.value)&&(item.id!=='studio'||!isAndroid.value)&&(item.id!=='routing'||isAndroid.value)))
// The WebView renderer or the whole process can be reclaimed while backgrounded; the native
// host reloads with ?resume=1 only when the task is being recollected (saved instance state),
// so a deliberate close (task swiped away, reboot) still starts on the overview page.
function restorePage():Page{try{
  if(new URLSearchParams(location.search).get('resume')!=='1')return 'home'
  const saved=localStorage.getItem('clash-page') as Page|null
  if(saved==='studio'&&isAndroid.value)return 'home'
  return saved&&['home','subscriptions','modules','proxies','connections','studio','routing','settings'].includes(saved)?saved:'home'
}catch{return 'home'}}
const page=ref<Page>(restorePage()), profiles=ref<Summary[]>([]), selected=ref(localStorage.getItem('clash-desk-profile')||'')
const diagnosticOrigin=ref<Page>('home')
watch(page,value=>{try{localStorage.setItem('clash-page',value)}catch{}},{immediate:true})
const mobileNav = computed(() => (isAndroid.value?['home','proxies','subscriptions','routing','settings']:['home','proxies','subscriptions','connections','settings']).map(id => {const item=nav.value.find(item => item.id === id)!;return id==='routing'?{...item,label:t('分流')}:item}))
const mobileTools = computed(() => nav.value.filter(item => ['modules','studio'].includes(item.id)))
const mobileSection = computed(() => (['modules','studio'].includes(page.value)||(isAndroid.value&&page.value==='connections')) ? 'settings' : page.value)
const mobileNavIndex = computed(() => Math.max(0, mobileNav.value.findIndex(item => item.id === mobileSection.value)))
// Page transitions: the stage is one stable wrapper, so v-if pages keep their
// exact mount/unmount behaviour and only real navigation restarts the class;
// rapid taps retrigger the same animation instead of stacking layers.
const pageStage=ref<HTMLElement|null>(null)
const pageOrder=(value:Page)=>{const mapped=['modules','studio'].includes(value)||(isAndroid.value&&value==='connections')?'settings':value;const ids= isAndroid.value?mobileNav.value.map(item=>item.id):nav.value.map(item=>item.id);const index=ids.indexOf(mapped);return index<0?ids.length:index}
watch(page,(next,previous)=>{
  if(!previous||previous===next)return
  const stage=pageStage.value
  if(!stage)return
  stage.classList.remove('page-enter-forward','page-enter-backward')
  void stage.offsetWidth
  stage.classList.add(pageOrder(next)>=pageOrder(previous)?'page-enter-forward':'page-enter-backward')
})
const editorDirty=ref(false), backendBase=ref(location.origin), tunDesired=ref(false), tunStack=ref('mixed')
const proxyView=ref({search:'',availableOnly:false,sort:'original',view:'cards',benchmarkOpen:false,endpoint:'cloudflare'})
const routingView=ref({query:'',kindFilter:'',stateFilter:''})
const settingsSearch=ref('')
const editorView=ref({tab:'nodes',search:'',groupKey:'',memberSearch:'',raw:false,searches:{} as Record<string,string>})
const logView=ref({query:'',level:'all',hidden:[] as string[]})
const scrollPositions=new Map<string,number>()
let pendingScroll:{key:string;top:number}|null=null
const scrollKey=(value:Page)=>value==='settings'?'settings:'+settingsTab.value:['proxies','routing','studio','modules'].includes(value)?value+':'+selected.value:value
function cancelScrollRestore(){pendingScroll=null}
async function restoreScroll(){await nextTick();if(!pendingScroll||pendingScroll.key!==scrollKey(page.value))return;const container=document.querySelector<HTMLElement>('.desk-content');if(!container)return;container.scrollTop=pendingScroll.top;if(Math.abs(container.scrollTop-pendingScroll.top)<2)pendingScroll=null}
watch(selected,()=>{proxyView.value={search:'',availableOnly:false,sort:'original',view:'cards',benchmarkOpen:false,endpoint:'cloudflare'};routingView.value={query:'',kindFilter:'',stateFilter:''};editorView.value={tab:'nodes',search:'',groupKey:'',memberSearch:'',raw:false,searches:{}};scrollPositions.delete(scrollKey('proxies'));scrollPositions.delete(scrollKey('routing'));if(['proxies','routing','studio','modules'].includes(page.value)){pendingScroll={key:scrollKey(page.value),top:0};void restoreScroll()}})
const routingPanel=ref<InstanceType<typeof AndroidRouting>|null>(null)
const proxyMode=ref<'system'|'tun'>(localStorage.getItem('clash-desk-mode')==='tun'?'tun':'system')
const networkSettingsDirty=ref(false),portSettingsDirty=ref(false)
watch([networkSettingsDirty,portSettingsDirty],()=>{if(page.value==='settings')editorDirty.value=networkSettingsDirty.value||portSettingsDirty.value},{flush:'sync'})
watch(page,()=>{networkSettingsDirty.value=false;portSettingsDirty.value=false},{flush:'sync'})
const closing=ref(false),settingsTab=ref<'general'|'logs'>('general')
async function selectSettingsTab(next:'general'|'logs'){if(settingsTab.value===next)return;const container=document.querySelector<HTMLElement>('.desk-content');if(container)scrollPositions.set(scrollKey('settings'),container.scrollTop);settingsTab.value=next;pendingScroll={key:scrollKey('settings'),top:scrollPositions.get(scrollKey('settings'))||0};await restoreScroll()}
const liveSpeed=ref<{upload:number|null;download:number|null;running:boolean}>({upload:null,download:null,running:false})
const detail=ref<Subscription|null>(null), workspace=ref<Workspace>({revision:1,modules:[],plans:{}}), preview=ref<Preview|null>(null)
const runtimeReady=ref(false)
const runtime=ref<Runtime>({running:false,installed:false,active:null,proxy:{supported:true,owned:false},events:[]})
const liveProxies=ref<Record<string,LiveProxy>>({}), connections=ref<Connection[]>([]), totals=ref({upload:0,download:0}), connectionSampledAt=ref(0)
type ProxyCatalog={proxies:Record<string,LiveProxy>;key:string;live:boolean;has_providers:boolean;profile_revision:number;workspace_revision:number}
const proxyCatalog=ref<ProxyCatalog>({proxies:{},key:'',live:false,has_providers:false,profile_revision:0,workspace_revision:0})
let selectionEpoch=0
const pendingSelections=ref<Record<string,string>>({})
const selectionQueues=new Map<string,{desired:string;confirmed:string|undefined}>()
watch(selected,id=>{pendingSelections.value=Object.fromEntries([...selectionQueues].filter(([key])=>key.startsWith(id+'\n')).map(([key,value])=>[key.slice(id.length+1),value.desired]))})
async function loadCatalog(){const id=selected.value,epoch=selectionEpoch;if(!id)return;const value=await api<ProxyCatalog>(`/api/client/proxy-catalog?profile_id=${encodeURIComponent(id)}`);if(id===selected.value&&epoch===selectionEpoch){for(const [group,name] of Object.entries(pendingSelections.value)){if(value.proxies[group])value.proxies[group]!.now=name}proxyCatalog.value=value;void restoreScroll()}}
const busy=ref(''), notice=ref(''), noticeError=ref(false), loadError=ref(''), runtimeError=ref(''), mixedPort=ref(Number(localStorage.getItem('clash-desk-port'))||17890)
const importOpen=ref(false), importType=ref<'url'|'file'|'qr'>('url'), qrBusy=ref(false), importName=ref(''), importUrl=ref(''), importYaml=ref(''), importError=ref('')
const moduleOpen=ref(false), moduleError=ref(''), moduleDraft=ref<Module>({id:'',name:'',target:'',strict:true,matches:[{kind:'DOMAIN-SUFFIX',value:''}]})
const moduleBaseline=ref('')
const moduleDirty=computed(()=>JSON.stringify(moduleDraft.value)!==moduleBaseline.value)
const importDirty=computed(()=>!!(importName.value.trim()||importUrl.value.trim()||importYaml.value.trim()))
function resetImport(){importName.value='';importUrl.value='';importYaml.value='';importError.value='';importType.value='url'}
let timer:ReturnType<typeof setInterval>|undefined, toastTimer:ReturnType<typeof setTimeout>|undefined, pollBusy=false, profileSeq=0
let unlistenClose:(()=>void)|undefined
let unlistenTray:(()=>void)|undefined
let unlistenTrayUpdated:(()=>void)|undefined, unlistenTrayError:(()=>void)|undefined
let trayContextReady=false
let dockObserver:ResizeObserver|undefined
function positionNotices(){
 const mobile=document.querySelector<HTMLElement>('.mobile-navigation')
 if(mobile&&getComputedStyle(mobile).display!=='none'){
  const rect=mobile.getBoundingClientRect(),desk=mobile.closest<HTMLElement>('.desk')
  const vertical=rect.height>rect.width*1.5
  // Native bottom insets are added by mobile.css, so reserve only the dock and its gaps here.
  desk?.style.setProperty('--mobile-nav-height',vertical?'0px':`${Math.ceil(rect.height+26)}px`)
  desk?.style.setProperty('--notice-dock-offset',vertical?'24px':`${Math.ceil(window.innerHeight-rect.top+12)}px`)
  return
 }
 const dock=document.querySelector<HTMLElement>('.liquid-dock-shell')
 if(dock)dock.closest<HTMLElement>('.desk')?.style.setProperty('--notice-dock-offset',`${Math.ceil(window.innerHeight-dock.getBoundingClientRect().top+12)}px`)
}

function androidBack(event:Event){
  if(event.defaultPrevented)return
  const cancel=document.querySelector<HTMLButtonElement>('.confirm-dialog .modal-actions button')
  if(cancel){event.preventDefault();cancel.click();return}
  const dialog=document.querySelector<HTMLDialogElement>('dialog[open]')
  if(dialog){event.preventDefault();if(dialog.dispatchEvent(new Event('cancel',{cancelable:true})))dialog.close();return}
  if(isAndroid.value&&page.value==='connections'){event.preventDefault();void go(diagnosticOrigin.value);return}
  if(page.value!=='home'){event.preventDefault();void go('home')}
}
onMounted(()=>{
  if(window.ClashAndroid)api<{package:string;label:string}[]>('/api/android/apps').then(apps=>{appLabels.value=Object.fromEntries(apps.map(app=>[app.package,app.label]))}).catch(()=>{})
  window.addEventListener('clash-android-back',androidBack)
  const dock=document.querySelector<HTMLElement>('.liquid-dock-shell')
  dockObserver=new ResizeObserver(positionNotices);if(dock)dockObserver.observe(dock);const mobile=document.querySelector<HTMLElement>('.mobile-navigation');if(mobile)dockObserver.observe(mobile)
  window.addEventListener('resize',positionNotices);positionNotices()
})
onUnmounted(()=>{dockObserver?.disconnect();window.removeEventListener('resize',positionNotices);window.removeEventListener('clash-android-back',androidBack)})
async function syncTrayContext(){if(!trayContextReady)return;await api('/api/client/tray/context','PUT',{profile_id:selected.value,proxy_mode:proxyMode.value,tun_stack:tunStack.value,mixed_port:mixedPort.value})}
const clone=<T,>(value:T):T=>JSON.parse(JSON.stringify(value))
const current=computed(()=>profiles.value.find(p=>p.id===selected.value))
const plan=computed<Plan>(()=>workspace.value.plans[selected.value]||{module_ids:[],default_target:''})
const activeModules=computed(()=>plan.value.module_ids.map(id=>workspace.value.modules.find(m=>m.id===id)).filter((m):m is Module=>!!m))
const targets=computed(()=>['DIRECT','REJECT',...(detail.value?.preview.config['proxy-groups']||[]).map(g=>g.name),...(detail.value?.preview.config.proxies||[]).map(p=>p.name)])
const liveGroups=computed(()=>Object.values(liveProxies.value).filter(p=>p.all&&p.name!=='GLOBAL'))

const primaryStrategy=computed(()=>{
 const live=runtime.value.running&&runtime.value.active?.profile_id===selected.value
 if(live){const groups=Object.values(liveProxies.value).filter(proxy=>proxy.all&&proxy.name!=='GLOBAL');const group=runtime.value.routing_mode==='global'?liveProxies.value.GLOBAL:groups.find(group=>group.type==='Selector')||groups[0];return group?{name:group.name,now:group.now||'',live:true}:null}
 const groups=detail.value?.preview.config['proxy-groups']||[];const group=groups.find(group=>group.type==='select')||groups[0];return group?{name:group.name,now:'',live:false}:null
})
const needsApply=computed(()=>!!runtime.value.running&&!!runtime.value.active&&(runtime.value.active.profile_id!==selected.value||runtime.value.active.revision!==current.value?.revision||runtime.value.active.workspace_revision!==workspace.value.revision))
const applyFailed=ref(false)
watch(selected,()=>applyFailed.value=false)
const configStatus=computed(()=>runtimeError.value?t('运行状态待确认'):!runtimeReady.value?t('正在读取运行状态…'):busy.value==='apply'?t('正在应用…'):applyFailed.value?t('应用失败，可重试'):editorDirty.value?(page.value==='settings'?t('有未保存的网络设置'):t('有未保存的修改')):!runtime.value.running?t('尚未启动'):!runtime.value.active?t('运行配置待确认'):needsApply.value?t('有变更待应用'):t('当前方案已应用'))
const applyLabel=computed(()=>!runtimeReady.value?t('读取中…'):busy.value==='apply'?t('正在应用…'):applyFailed.value?t('重试应用'):!runtime.value.running?(isAndroid.value?t('连接 VPN'):t('启动')):needsApply.value?t('应用变更'):t('重新应用'))
const title=computed(()=>nav.value.find(n=>n.id===page.value)?.label||t("工作台"))
const actualMode=computed(()=>!runtime.value.running?t("未接管"):runtime.value.vpn?.enabled?'Android VPN':supportsTun.value&&runtime.value.tun?.enabled?'TUN':supportsSystemProxy.value&&runtime.value.proxy.owned?t("系统代理"):t("仅代理端口"))
function rememberMode(mode:'system'|'tun',sync=true){proxyMode.value=mode;tunDesired.value=mode==='tun';localStorage.setItem('clash-desk-mode',mode);if(sync)void syncTrayContext().catch(e=>notify(e.message,true))}
async function selectMode(mode:'system'|'tun'){
  if(busy.value)return
  if(mode==='tun'&&!supportsTun.value)return
  if(!runtime.value.running){rememberMode(mode);return}
  await perform('mode',async()=>{runtime.value=await api<Runtime>('/api/client/runtime/mode','PUT',{mode:mode==='system'&&!supportsSystemProxy.value?'manual':mode,stack:tunStack.value});rememberMode(mode);await poll();notify(t("已切换为")+(mode==='tun'?t("TUN 接管"):t("系统代理")))})
}
async function selectRoutingMode(mode:RoutingMode){await perform('routing-mode',async()=>{runtime.value=await api<Runtime>('/api/client/runtime/routing-mode','PUT',{mode})})}
function bytes(n:number){if(!n)return '0 B';const i=Math.max(0,Math.min(Math.floor(Math.log(n)/Math.log(1024)),3));return `${(n/1024**i).toFixed(i?1:0)} ${['B','KB','MB','GB'][i]}`}
function date(s:string){return new Date(s).toLocaleString(locale.value,{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})}
function notify(message:string,error=false){notice.value=message;noticeError.value=error;clearTimeout(toastTimer);toastTimer=setTimeout(()=>notice.value='',6500)}
async function perform(name:string,fn:()=>Promise<void>){if(busy.value&&!(name==='stop'&&busy.value==='apply'))return;busy.value=name;try{await fn()}catch(e){notify((e as Error).message,true)}finally{if(busy.value===name)busy.value=''}}
async function refreshPreview(){if(selected.value)preview.value=await api<Preview>(`/api/client/preview/${selected.value}`)}
async function choose(id:string){
  if(id===selected.value&&editorDirty.value&&['settings','routing'].includes(page.value))return
  if(editorDirty.value&&!await confirmDialog(t("修改尚未保存，是否丢弃并离开？")))return
  editorDirty.value=false
  if(selected.value!==id)proxyCatalog.value={proxies:{},key:'',live:false,has_providers:false,profile_revision:0,workspace_revision:0}
  const seq=++profileSeq;selected.value=id;detail.value=null;preview.value=null;localStorage.setItem('clash-desk-profile',id);localStorage.setItem('clash-studio-selected',id)
  if(!id){await syncTrayContext();return}
  try{const [d,p]=await Promise.all([api<Subscription>(`/api/subscriptions/${id}`),api<Preview>(`/api/client/preview/${id}`)]);if(seq===profileSeq){detail.value=d;preview.value=p;loadError.value='';if(page.value==='proxies')await loadCatalog();await syncTrayContext()}}catch(e){if(seq===profileSeq)loadError.value=(e as Error).message}
}
async function load(){
  const [subs,state]=await Promise.all([api<Summary[]>('/api/subscriptions'),api<Workspace>('/api/client/workspace')]);profiles.value=subs;workspace.value=state
  const id=subs.find(p=>p.id===selected.value)?.id||subs[0]?.id||'';await choose(id);void restoreScroll()
}
async function poll(){
  if(pollBusy)return;pollBusy=true
  try{runtime.value=await api<Runtime>('/api/client/runtime');runtimeReady.value=true;if(runtime.value.running){if(runtime.value.tun?.enabled||runtime.value.proxy.owned)rememberMode(runtime.value.tun?.enabled?'tun':'system',false);tunStack.value=runtime.value.tun?.stack||tunStack.value;const [p,c]=await Promise.all([api<{proxies:Record<string,LiveProxy>}>('/api/client/runtime/proxies'),api<{connections:Connection[];uploadTotal:number;downloadTotal:number;sampled_at?:number|string}>('/api/client/runtime/connections')]);liveProxies.value=p.proxies;connections.value=c.connections||[];connectionSampledAt.value=typeof c.sampled_at==='number'?c.sampled_at*1000:c.sampled_at?Date.parse(c.sampled_at):Date.now();totals.value={upload:c.uploadTotal||0,download:c.downloadTotal||0}}else{liveProxies.value={};connections.value=[];connectionSampledAt.value=Date.now();totals.value={upload:0,download:0};const tray=await api<{proxy_mode:'system'|'tun';tun_stack:string}>('/api/client/tray');rememberMode(tray.proxy_mode,false);tunStack.value=tray.tun_stack}if(page.value==='proxies'&&selected.value)await loadCatalog();runtimeError.value=''}catch(e){runtimeError.value=(e as Error).message}finally{pollBusy=false}
}
async function saveState(next:Workspace){workspace.value=await api<Workspace>('/api/client/workspace','PUT',next);await refreshPreview()}
function openModule(module?:Module){moduleError.value='';moduleDraft.value=module?clone(module):{id:crypto.randomUUID().replaceAll('-',''),name:'',target:targets.value.find(t=>!['DIRECT','REJECT'].includes(t))||'REJECT',strict:true,matches:[{kind:'DOMAIN-SUFFIX',value:''}]};moduleBaseline.value=JSON.stringify(moduleDraft.value);moduleOpen.value=true}
async function saveModule(){
  moduleError.value='';if(!moduleDraft.value.name.trim()||moduleDraft.value.matches.some(m=>!m.value.trim())){moduleError.value=t("请填写模块名称和全部匹配条件");return}
  await perform('save-module',async()=>{const next=clone(workspace.value),index=next.modules.findIndex(m=>m.id===moduleDraft.value.id);if(index<0)next.modules.push(clone(moduleDraft.value));else next.modules[index]=clone(moduleDraft.value);await saveState(next);moduleOpen.value=false;notify(t("模块已保存；请绑定到方案，预览后应用"))})
}
async function toggleModule(id:string){await perform('module',async()=>{const next=clone(workspace.value),p=next.plans[selected.value]||{module_ids:[],default_target:''};p.module_ids=p.module_ids.includes(id)?p.module_ids.filter(n=>n!==id):[...p.module_ids,id];next.plans[selected.value]=p;await saveState(next);notify(t("方案已保存，运行配置尚未改变"))})}
async function moveModule(id:string,offset:number){await perform('order',async()=>{const next=clone(workspace.value),ids=next.plans[selected.value]?.module_ids;if(!ids)return;const i=ids.indexOf(id),j=i+offset;if(j<0||j>=ids.length)return;[ids[i],ids[j]]=[ids[j],ids[i]];await saveState(next)})}
async function deleteModule(id:string){if(!await confirmDialog(t("删除此模块，并从所有方案中移除引用？")))return;await perform('delete-module',async()=>{const next=clone(workspace.value);next.modules=next.modules.filter(m=>m.id!==id);Object.values(next.plans).forEach(p=>p.module_ids=p.module_ids.filter(n=>n!==id));await saveState(next);notify(t("模块已删除，运行配置需重新应用"))})}
async function setDefault(event:Event){const value=(event.target as HTMLSelectElement).value;await perform('default',async()=>{const next=clone(workspace.value);next.plans[selected.value]={...clone(plan.value),default_target:value};await saveState(next)})}
async function importProfile(demo=false){
  importError.value='';await perform('import',async()=>{try{const d=await api<Subscription>('/api/subscriptions','POST',demo?{title:'示例订阅 · 不提供实际代理',source_type:'demo'}:{title:importName.value.trim(),source_type:importType.value==='qr'?'url':importType.value,source_url:importType.value!=='file'?importUrl.value.trim():'',yaml:importType.value==='file'?importYaml.value:''});selected.value=d.id;await load();importOpen.value=false;importName.value='';importUrl.value='';importYaml.value='';notify(demo?t("示例已载入；示例节点无法实际代理联网"):t("订阅已导入")) }catch(e){importError.value=(e as Error).message;throw e}})
}
async function readQr(source:'camera'|'photo'){qrBusy.value=true;importError.value='';try{const result=await api<{url?:string;cancelled:boolean}>('/api/android/qr','POST',{source});if(!result.cancelled&&result.url){importUrl.value=result.url;if(!importName.value)importName.value=t('扫码订阅')}}catch(e){importError.value=(e as Error).message}finally{qrBusy.value=false}}
async function openAppPermissions(){try{await api('/api/android/app-settings','POST')}catch(e){importError.value=(e as Error).message}}
async function readFile(event:Event){const f=(event.target as HTMLInputElement).files?.[0];if(!f)return;if(f.size>8*1024*1024){importError.value=t("文件不能超过 8 MB");return}importYaml.value=await f.text();if(!importName.value)importName.value=f.name.replace(/\.ya?ml$/i,'')}
async function refreshProfile(profile:Summary){if(profile.source_type==='file'){if(isAndroid.value){notify(t('本地文件请重新导入更新。'));return}page.value='studio';notify(t("本地文件请在配置编辑器中重新上传"));return}await perform('refresh',async()=>{await api(`/api/subscriptions/${profile.id}/refresh`,'POST',{revision:profile.revision});await load();notify(t("源订阅已刷新；请检查冲突及预览，再应用到内核"))})}
async function deleteProfile(profile:Summary){if(runtime.value.active?.profile_id===profile.id){notify(t("请先停止正在使用此订阅的内核"),true);return}if(!await confirmDialog(t("删除「{0}」及其历史？", [profile.title])))return;await perform('delete-profile',async()=>{await api(`/api/subscriptions/${profile.id}?revision=${profile.revision}`,'DELETE');await load();notify(t("订阅已删除"))})}
async function apply(){if(!runtimeReady.value){notify(t('请等待运行状态读取完成'),true);return}await perform('apply',async()=>{
  applyFailed.value=false
  try{
  if(editorDirty.value)throw new Error(t("请先保存并发布订阅草稿"))
  await refreshPreview();if(!preview.value||preview.value.errors.length)throw new Error(preview.value?.errors.join('；')||t("请先选择订阅"))
  runtime.value=await lifecycle<Runtime>('/api/client/runtime/apply',{profile_id:selected.value,profile_revision:preview.value.profile_revision,workspace_revision:preview.value.workspace_revision,mixed_port:mixedPort.value,tun:effectiveProxyMode.value==='tun',tun_stack:tunStack.value,proxy_mode:effectiveProxyMode.value})
  if(!runtime.value.running||runtime.value.active?.profile_id!==selected.value||runtime.value.active.revision!==preview.value.profile_revision||runtime.value.active.workspace_revision!==preview.value.workspace_revision)throw new Error(t('后端尚未确认配置生效，请刷新状态后重试'))
  localStorage.setItem('clash-desk-port',String(mixedPort.value));rememberMode(proxyMode.value);await poll();if(runtimeError.value)throw new Error(runtimeError.value);if(!runtime.value.running||!runtime.value.active||needsApply.value)throw new Error(t('后端尚未确认配置生效，请刷新状态后重试'));notify(t("配置已应用，当前使用")+actualMode.value)
  }catch(error){applyFailed.value=true;throw error}
})}
async function stop(){await perform('stop',async()=>{runtime.value=await lifecycle<Runtime>('/api/client/runtime/stop',{});await poll();notify(isAndroid.value?t("内核已停止"):t("内核已停止，已尝试恢复系统代理"))})}
async function toggleProxy(){await perform('proxy',async()=>{runtime.value=await api<Runtime>('/api/client/runtime/system-proxy','PUT',{enabled:!runtime.value.proxy.owned});notify(runtime.value.proxy.owned?t("已开启系统代理"):t("已恢复原系统代理"))})}
async function selectProxy(group:LiveProxy,name:string){
  if(busy.value||group.type!=='Selector'||group.now===name)return
  const profileId=selected.value,key=profileId+'\n'+group.name
  const existing=selectionQueues.get(key)
  const queue=existing||{desired:name,confirmed:group.now}
  queue.desired=name
  ++selectionEpoch;group.now=name;pendingSelections.value[group.name]=name
  if(existing)return
  selectionQueues.set(key,queue)
  const revisions={profile_revision:proxyCatalog.value.profile_revision,workspace_revision:proxyCatalog.value.workspace_revision}
  try{
    while(true){
      const desired=queue.desired
      try{
        await api('/api/client/proxy-selection','PUT',{profile_id:profileId,...revisions,group:group.name,name:desired})
        queue.confirmed=desired
      }catch(error){
        if(queue.desired!==desired)continue
        if(selected.value===profileId&&proxyCatalog.value.proxies[group.name])proxyCatalog.value.proxies[group.name]!.now=queue.confirmed
        notify((error as Error).message,true)
        break
      }
      if(queue.desired===desired)break
    }
  }finally{
    selectionQueues.delete(key);++selectionEpoch
    if(selected.value===profileId)delete pendingSelections.value[group.name]
  }
}
async function closeConnection(id:string){await perform('close',async()=>{await api(`/api/client/runtime/connections/${id}`,'DELETE');await poll()})}
async function download(){if(!preview.value)return;try{await saveTextFile('clash-studio-composed.yaml',preview.value.yaml)}catch(error){notify((error as Error).message,true)}}
async function copyProxy(){try{await navigator.clipboard.writeText(`http://127.0.0.1:${runtime.value.active?.mixed_port||mixedPort.value}`);notify(t("本机 HTTP 代理地址已复制"))}catch{notify(t("复制失败，请从设置页复制地址"),true)}}
async function refreshPage(){if(page.value==='routing'){await routingPanel.value?.reload();return}await perform('reload',async()=>{await Promise.all([load(),poll()])})}
async function go(next:Page){
 if(next==='studio'&&isAndroid.value)return
 const container=document.querySelector<HTMLElement>('.desk-content')
 if(next===page.value){pendingScroll=null;scrollPositions.set(scrollKey(next),0);container?.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});return}
 if(['studio','routing','settings'].includes(page.value)&&editorDirty.value&&!await confirmDialog(t('修改尚未保存，是否丢弃并离开？')))return
 if(container)scrollPositions.set(scrollKey(page.value),container.scrollTop)
 if(next==='connections')diagnosticOrigin.value=page.value==='settings'?'settings':'home'
 editorDirty.value=false;page.value=next;pendingScroll={key:scrollKey(next),top:scrollPositions.get(scrollKey(next))||0}
 await restoreScroll()
 if(next!=='studio')try{await load();await restoreScroll()}catch(e){loadError.value=(e as Error).message}
}

async function clientSettingsChanged(port:number){mixedPort.value=port;localStorage.setItem('clash-desk-port',String(port));await poll()}
async function editorSaved(value:Subscription){detail.value=value;editorDirty.value=false;profiles.value=await api<Summary[]>('/api/subscriptions');await refreshPreview()}
async function toggleTun(){await selectMode(proxyMode.value==='tun'?'system':'tun')}
async function requestAdmin(){if(!supportsTun.value)return;runtime.value=await api<Runtime>('/api/client/runtime/elevate','POST',{})}
async function elevate(){await perform('elevate',async()=>{await requestAdmin();notify(platform.value.os==='linux'?t("Linux 内核网络权限已就绪，无需重启窗口"):t("管理员助手已连接，可直接开启 TUN，无需重启窗口"))})}
async function windowAction(action:'minimize'|'toggleMaximize'|'close'){
  if(!isDesktop)return
  try{const {getCurrentWindow}=await import('@tauri-apps/api/window');await getCurrentWindow()[action]()}catch{notify(t("窗口操作未完成，请重试"),true)}
}
function hasUnsavedInputs(){return editorDirty.value||!!document.querySelector('.app-dialog[open][data-dialog-dirty=true]')}
function beforeUnload(event:BeforeUnloadEvent){if(!isDesktop&&hasUnsavedInputs()){event.preventDefault();event.returnValue=''}}
onMounted(async()=>{
  window.addEventListener('beforeunload',beforeUnload)
  if(isDesktop){
    try{
      const {getCurrentWindow}=await import('@tauri-apps/api/window')
      unlistenClose=await getCurrentWindow().onCloseRequested(async event=>{
        event.preventDefault()
        if(closing.value)return
        const {invoke}=await import('@tauri-apps/api/core')
        const preferences=await invoke<{resident:boolean}>('desktop_preferences')
        if(preferences.resident){closing.value=true;try{await closeDesktop()}finally{closing.value=false}return}
        if(hasUnsavedInputs()&&!await confirmDialog(t("修改尚未保存，是否丢弃并退出？")))return
        closing.value=true;editorDirty.value=false
        try{if(await closeDesktop())closing.value=false}catch{closing.value=false;notify(t("退出请求未完成，请重试关闭窗口"),true)}
      })
      const {listen}=await import('@tauri-apps/api/event')
      unlistenTray=await listen('desktop-quit-request',async()=>{
        if(closing.value)return
        if(hasUnsavedInputs()&&!await confirmDialog(t("修改尚未保存，是否丢弃并退出？")))return
        closing.value=true;editorDirty.value=false
        try{await quitDesktop()}catch{closing.value=false;notify(t("退出请求未完成，请重试关闭窗口"),true)}
      })
      unlistenTrayUpdated=await listen('desktop-tray-updated',()=>{void poll()})
      unlistenTrayError=await listen<string>('desktop-tray-error',event=>{notify(message(event.payload),true);void poll()})
      const {invoke}=await import('@tauri-apps/api/core');await invoke('desktop_ready')
    }catch{notify(t("窗口关闭监听未加载，将使用原生关闭方式"),true)}
  }
  try{
    const tray=await api<{context_configured:boolean;proxy_mode:'system'|'tun';tun_stack:string;profile_id:string}>('/api/client/tray')
    if(tray.context_configured){rememberMode(tray.proxy_mode,false);tunStack.value=tray.tun_stack;if(!selected.value)selected.value=tray.profile_id}
    trayContextReady=true
    const [info,prefs]=await Promise.all([desktopInfo(),api<{settings:{mixed_port:number|null}}>('/api/client/settings'),load(),poll()])
    platform.value=await api('/api/client/platform')
    backendBase.value=info.backend_base
    if(prefs.settings.mixed_port){mixedPort.value=prefs.settings.mixed_port;localStorage.setItem('clash-desk-port',String(mixedPort.value))}
    if(runtime.value.running){rememberMode(runtime.value.tun?.enabled?'tun':'system');tunStack.value=runtime.value.tun?.stack||'mixed'}
  }catch(e){loadError.value=(e as Error).message}
  timer=setInterval(poll,3000)
})
onUnmounted(()=>{unlistenClose?.();unlistenTray?.();unlistenTrayUpdated?.();unlistenTrayError?.();window.removeEventListener('beforeunload',beforeUnload);clearInterval(timer);clearTimeout(toastTimer)})
</script>

<template>
  <div class="desk" :class="{'android-inset-host':nativeInsets}" :data-ui-page="page">
    <aside class="liquid-dock-shell">
      <nav class="liquid-dock" :aria-label="t('主导航')"><button v-for="item in nav" :key="item.id" :class="['dock-item',{chosen:page===item.id}]" :aria-label="item.label" :aria-current="page===item.id?'page':undefined" @click="go(item.id)"><span class="dock-label">{{ item.label }}</span><span class="dock-indicator" aria-hidden="true"></span></button></nav>
    </aside>
    <div class="desk-main">
      <button type="button" class="desk-brand shell-brand" :aria-label="t('Clash Studio · 返回概览')" @click="go('home')"><span class="desk-mark"><img :src="brandIcon" alt=""/></span><span class="brand-copy"><span class="brand-name">Clash <strong>Studio</strong></span><small>{{ t("配置自由 · 流量有序") }}</small></span></button>
      <header class="desk-topbar" data-tauri-drag-region><div class="desk-crumb">{{ t("工作空间") }}<ChevronRight :size="13"/><strong>{{ title }}</strong></div><div class="desk-top-right"><div v-if="liveSpeed.running" class="topbar-speed" :title="t('本程序 Mihomo 接管流量的实时速率')"><span><ArrowDownLeft :size="13"/>{{ liveSpeed.download===null?'—':bytes(liveSpeed.download)+'/s' }}</span><span><ArrowUpRight :size="13"/>{{ liveSpeed.upload===null?'—':bytes(liveSpeed.upload)+'/s' }}</span></div><span class="local-tag"><span></span>{{ t("仅本机运行") }}</span><span class="version-tag">1.2</span><div v-if="isDesktop" class="window-controls"><button :aria-label="t('最小化')" @click="windowAction('minimize')"><Minus :size="16"/></button><button :aria-label="t('最大化或还原')" @click="windowAction('toggleMaximize')"><Square :size="14"/></button><button class="window-close" :aria-label="t('关闭窗口')" :disabled="closing" @click="windowAction('close')"><X :size="18"/></button></div></div></header>
      <main :class="['desk-content',{'editor-content':page==='studio'}]" @wheel.passive="cancelScrollRestore" @touchstart.passive="cancelScrollRestore">
        <div class="page-stage" ref="pageStage">
        <div v-if="mobileTools.length&&['settings','modules','studio'].includes(page)" class="mobile-tools" :aria-label="t('配置工具')">
          <button v-for="item in mobileTools" :key="item.id" :aria-pressed="page===item.id" @click="go(item.id)"><component :is="item.icon" :size="20"/><span>{{ item.label }}</span><ChevronRight :size="16"/></button>
          <button v-if="page!=='settings'" @click="go('settings')"><Settings2 :size="20"/><span>{{ t('设置与日志') }}</span><ChevronRight :size="16"/></button>
        </div>
        <div class="desk-page-heading"><div><div class="desk-eyebrow">{{ page==='home'?'CLASH STUDIO':'CLASH STUDIO / '+page.toUpperCase() }}</div><h1>{{ page==='home'?t("概览"):title }}<span v-if="page==='home'" class="heading-dot">.</span></h1><p>{{ page==='home'?t("管理订阅配置、分流模块与本机代理。"):page==='modules'?t("管理可复用分流逻辑，按顺序组合到当前方案。"):page==='studio'?t("编辑订阅的节点、策略组与规则；保存发布后再应用。"):page==='connections'?t("读取内核真实连接，检查流量命中了什么规则。"):t("管理本机配置，查看当前运行状态。") }}</p></div><div class="heading-buttons"><button class="desk-btn" :disabled="!!busy" @click="refreshPage()"><RefreshCw :size="15"/>{{ t("刷新") }}</button><button v-if="page!=='home'" class="desk-btn" :disabled="!!busy||editorDirty||!selected||nativeCoreUnavailable||!runtimeReady" @click="apply"><Power :size="15"/>{{ applyLabel }}</button><button v-if="page==='home'||page==='subscriptions'" class="desk-btn" :class="{primary:!profiles.length}" @click="importOpen=true"><Plus :size="16"/>{{ t("导入订阅") }}</button></div></div>

        <div v-if="loadError" class="desk-alert error">{{ message(loadError) }} <button @click="perform('retry',load)">{{ t("重试") }}</button></div>
        <div v-if="runtimeError" class="desk-alert error">{{ t("运行状态读取失败：{0}", [runtimeError]) }}</div>
        <div v-if="selected" class="configuration-status" role="status"><span>{{ runtime.running?t('正在运行：{0}',[runtime.active?.title||'—']):t('内核已停止') }}</span><span>{{ editorDirty&&page!=='settings'?t('正在编辑：{0}',[current?.title||'—']):t('当前所选：{0}',[current?.title||'—']) }}</span><strong :class="{pending:needsApply||editorDirty||applyFailed}">{{ configStatus }}</strong></div>


        <div v-show="page==='home'" class="home-primary">
          <section class="overview-grid launch-overview">
            <article class="desk-card kernel-launch-card">
              <div class="section-head"><div><h2>{{ t("内核与接管") }}</h2></div><span :class="['status-chip',{'is-live':runtime.running}]"><i></i>{{ runtimeError?t('状态待确认'):!runtimeReady?t('读取中…'):busy==='apply'?t('正在应用…'):busy==='stop'?t('正在停止…'):runtime.running?t("运行中"):t("已停止") }}</span></div>
              <div class="kernel-summary"><span :class="['power-mark',{running:runtime.running}]"><Power :size="22"/></span><div><strong>{{ runtime.running?runtime.active?.title:t("启动你的网络方案") }}</strong><small>{{ runtime.running?t("当前接管：{0} · 端口 {1}", [actualMode, runtime.active?.mixed_port]):(validationBuild||nativeCoreUnavailable)?t("代理内核尚未接入，暂不支持启动代理。"):isAndroid?t("选择订阅，启动 VPN 连接。"):t("选择模式，再启动内核。") }}</small></div></div>
              <div :class="['home-plan-selection',{'has-strategy':primaryStrategy}]"><label class="desk-field launch-profile">{{ t('当前方案') }}<select :value="selected" :disabled="!!busy" @change="choose(($event.target as HTMLSelectElement).value)"><option v-if="!profiles.length" value="">{{ t('先导入订阅') }}</option><option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.title }}</option></select></label><button v-if="primaryStrategy" class="primary-strategy" :title="primaryStrategy.name+' · '+primaryStrategy.now" :aria-label="t('查看主要策略组')" @click="go('proxies')"><small>{{ primaryStrategy.live?t('当前主要策略组'):t('所选方案策略组') }}</small><strong>{{ primaryStrategy.name }}</strong><span>{{ primaryStrategy.now||t('前往代理页选择节点') }}</span></button></div>
              <p v-if="!isAndroid" class="mode-label">{{ t('接管方式') }}</p><div v-if="!isAndroid" class="mode-options" role="group" :aria-label="t('接管模式')"><button :class="{selected:proxyMode==='system'}" :disabled="!!busy" @click="selectMode('system')"><Globe2 :size="16"/><span>{{ t(runtime.proxy.supported?"系统代理":"仅代理端口") }}<small>{{ t("遵循代理设置的应用") }}</small></span><Check v-if="proxyMode==='system'" :size="14"/></button><button :class="{selected:proxyMode==='tun'}" :disabled="!!busy||!runtime.tun?.supported" @click="selectMode('tun')"><ShieldCheck :size="16"/><span>{{ t("TUN 模式") }}<small>{{ t("虚拟网卡与系统路由") }}</small></span><Check v-if="proxyMode==='tun'" :size="14"/></button></div>
              <p v-if="!isAndroid&&proxyMode==='tun'&&!runtime.tun?.admin" class="mode-warning">{{ t("TUN 需要管理员权限。") }}<button class="desk-text-btn" :disabled="!!busy" @click="elevate">{{ t("申请权限") }}<ArrowUpRight :size="12"/></button></p>
              <section class="routing-mode-card"><div><h2>{{ t("分流模式") }}</h2></div><div class="routing-segment" role="group" :aria-label="t('分流模式')"><button v-for="choice in routingChoices" :key="choice.id" :aria-pressed="runtime.routing_mode===choice.id" :disabled="!!busy||validationBuild||nativeCoreUnavailable||(isAndroid&&!runtime.running)" @click="selectRoutingMode(choice.id)">{{ t(choice.label) }}</button></div><p v-if="runtime.routing_mode==='global'">{{ t("全局模式使用 GLOBAL 出口，可在代理页选择") }} <button class="desk-text-btn" @click="go('proxies')">{{ t("选择出口") }}</button></p><p v-else-if="runtime.routing_mode==='direct'">{{ t("直连模式下不使用代理节点") }}</p></section>
              <details v-if="isAndroid" class="android-network-help"><summary>{{ t('VPN 接管说明') }}</summary><p class="android-network-note">{{ nativeDevelopment?t("通过 Android VPN 接管流量；首次启动需要系统授权，局域网保持直连。"):validationBuild?t("代理内核与 VPN 尚不可用。"):t("安卓 VPN 服务尚未接入，当前仅提供本地代理端口。") }}</p></details><div class="kernel-actions"><button class="desk-btn" :class="{primary:!runtime.running||needsApply||applyFailed}" :disabled="!!busy||editorDirty||!selected||nativeCoreUnavailable||!runtimeReady" @click="apply"><Loader2 v-if="busy==='apply'" class="rotate" :size="15"/><Power v-else :size="15"/>{{ applyLabel }}</button><button v-if="runtime.running||busy==='apply'||busy==='stop'" class="desk-btn danger" :disabled="!!busy&&busy!=='apply'" @click="stop"><Power :size="14"/>{{ isAndroid?t('断开'):t('停止') }}</button><button class="desk-text-btn" @click="go('settings')">{{ t("更多设置") }}<ChevronRight :size="13"/></button></div>
            </article>
          </section>
        <NetworkDashboard v-show="page==='home'" :running="runtime.running" :config-key="`${runtime.active?.hash||''}:${runtime.egress_version??0}`" @speed="liveSpeed=$event" @connections="go('connections')"/>
        </div>
        <template v-if="page==='home'">
          <div class="home-shortcuts"><button class="desk-btn" @click="go('subscriptions')"><FolderOpen :size="16"/>{{ t('{0} 份订阅',[profiles.length]) }}</button><button v-if="hasModules" class="desk-btn" @click="go('modules')"><Layers3 :size="16"/>{{ t('{0} 个模块 · 启用 {1} 个',[workspace.modules.length,activeModules.length]) }}</button><button class="desk-btn" @click="go('connections')"><Activity :size="16"/>{{ t('{0} 个连接',[connections.length]) }}</button></div>
          <div class="home-grid"><section class="desk-card config-card"><div class="section-head"><div><span class="desk-eyebrow">ACTIVE WORKSPACE</span><h2>{{ t("当前配置方案") }}</h2></div><FileCode2 :size="21"/></div><template v-if="current"><label class="desk-field">{{ t("选择源订阅") }}<select :value="selected" @change="choose(($event.target as HTMLSelectElement).value)"><option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.title }}</option></select></label><SubscriptionUsage :usage="current.usage" :updated-at="current.refreshed_at"/><div class="config-meta"><span><Globe2 :size="15"/>{{ t("{0} 个节点", [current.proxy_count]) }}</span><span><GitBranch :size="15"/>{{ t("{0} 个策略组", [current.group_count]) }}</span><span><SlidersHorizontal :size="15"/>{{ t("{0} 条源规则", [current.rule_count]) }}</span></div><div class="source-note"><span>{{ t("最近更新 {0}", [date(current.refreshed_at)]) }}</span><span class="small-badge">v{{ current.revision }}</span></div><div v-if="current.source_type==='demo'" class="inline-note">{{ t("这是示例配置，节点不能提供实际代理服务。") }}</div><div v-if="current.last_error" class="inline-note error">{{ current.last_error }}</div><div class="config-actions"><button v-if="isAndroid" class="desk-btn" @click="go('routing')"><GitBranch :size="16"/>{{ t("精确分流") }}</button><button v-else class="desk-btn" @click="go('studio')"><Code2 :size="16"/>{{ t("可视化编辑") }}</button></div></template><div v-else class="desk-empty"><FolderOpen :size="36"/><h3>{{ t("从一份订阅开始") }}</h3><p>{{ t("导入服务商链接或本地 YAML 文件，所有修改在本机完成。") }}</p><button class="desk-btn primary" @click="importOpen=true">{{ t("导入第一份订阅") }}</button><button class="desk-text-btn" :disabled="!!busy" @click="importProfile(true)">{{ t("先载入示例配置 →") }}</button></div></section>
          <section v-if="hasModules" class="desk-card flow-card"><div class="section-head"><div><span class="desk-eyebrow">YOUR ROUTING LOGIC</span><h2>{{ t("分流，按你的意图") }}</h2></div><button class="desk-icon-btn" :aria-label="t('管理模块')" @click="go('modules')"><ArrowUpRight :size="20"/></button></div><div v-if="activeModules.length" class="flow-list"><div v-for="(m,i) in activeModules.slice(0,4)" :key="m.id" class="flow-item"><span class="flow-order">{{ String(i+1).padStart(2,'0') }}</span><div><strong>{{ m.name }}</strong><small>{{ t("{0} 个条件 · {1}", [m.matches.length, m.strict?t("限定出口"):t("普通分流")]) }}</small></div><ArrowRight :size="15"/><span class="route-target">{{ m.target }}</span></div></div><div v-else class="route-placeholder"><span class="route-node"><Box :size="21"/>{{ t("匹配条件") }}</span><span class="route-dash"></span><span class="route-node green"><GitBranch :size="21"/>{{ t("指定策略组") }}</span><p>{{ t("将域名、进程或网段绑定到指定出口。") }}<br>{{ t("模块按顺序匹配，变更先预览、后应用。") }}</p></div><button class="wide-link" @click="go('modules')">{{ activeModules.length?t("管理当前方案的模块"):t("创建你的第一个分流模块") }} <ArrowRight :size="15"/></button></section></div>
          <section class="traffic-strip"><div><Activity :size="18"/><strong>{{ t("实时连接") }}</strong><span>{{ runtime.running?t("每 3 秒更新内核数据"):t("启动内核后显示真实数据") }}</span></div><div><button @click="go('connections')">{{ t("{0} 个连接", [connections.length]) }}<ChevronRight :size="14"/></button></div></section>
          <div v-if="!isAndroid" class="desk-footnote"><ShieldCheck :size="14"/>{{ t("TUN 需要管理员权限；系统级断网保护仍需单独实现。") }}<span>LOCAL FIRST. CONFIGURATION FIRST.</span></div>
        </template>

        <template v-if="page==='subscriptions'">
          <div class="section-toolbar"><span>{{ t("{0} 份订阅 · 数据与原项目隔离", [profiles.length]) }}</span><button class="desk-text-btn" :disabled="!!busy" @click="importProfile(true)">{{ t("载入示例配置") }}</button></div>
          <div v-if="profiles.length" class="profile-grid"><article v-for="p in profiles" :key="p.id" :class="['desk-card profile-card',{selected:p.id===selected}]"><div class="profile-top"><span class="profile-symbol"><FileCode2 :size="23"/></span><span class="small-badge">{{ p.source_type==='url'?t("远程订阅"):p.source_type==='demo'?t("演示"):t("本地文件") }}</span></div><h2>{{ p.title }}</h2><p>{{ p.source_host }}</p><div class="profile-numbers"><span><b>{{ p.proxy_count }}</b>{{ t("节点") }}</span><span><b>{{ p.group_count }}</b>{{ t("策略组") }}</span><span><b>{{ p.rule_count }}</b>{{ t("规则") }}</span></div><SubscriptionUsage :usage="p.usage" :updated-at="p.refreshed_at"/><small>{{ t("更新于 {0}", [date(p.refreshed_at)]) }}</small><div v-if="p.last_error" class="inline-note error">{{ message(p.last_error) }}</div><div class="profile-actions"><button class="desk-btn" :disabled="!!busy" @click="choose(p.id)"><Check v-if="p.id===selected" :size="14"/>{{ p.id===selected?t("当前方案"):t("选择配置") }}</button><button class="desk-icon-btn" :title="t('刷新订阅')" :disabled="!!busy" @click="refreshProfile(p)"><RefreshCw :size="16"/></button><button class="desk-icon-btn danger" :title="t('删除订阅')" :disabled="!!busy" @click="deleteProfile(p)"><Trash2 :size="16"/></button></div></article><button class="add-profile" @click="importOpen=true"><Plus :size="26"/><strong>{{ t("导入新的订阅") }}</strong><span>{{ t("URL 或 YAML 文件") }}</span></button></div><div v-else class="desk-card desk-empty"><FolderOpen :size="38"/><h3>{{ t("还没有订阅") }}</h3><button class="desk-btn primary" @click="importOpen=true">{{ t("导入订阅") }}</button></div>
        </template>

        <template v-if="page==='modules'">
          <div class="section-toolbar"><label class="inline-select">{{ t("当前方案") }}<select :value="selected" @change="choose(($event.target as HTMLSelectElement).value)"><option v-if="!profiles.length" value="">{{ t("先导入订阅") }}</option><option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.title }}</option></select></label><button class="desk-btn primary" :disabled="!selected" @click="openModule()"><Plus :size="15"/>{{ t("新建模块") }}</button></div>
          <div class="modules-layout"><section><div v-if="!workspace.modules.length" class="desk-card desk-empty"><Layers3 :size="38"/><h3>{{ t("把常用分流保存下来") }}</h3><p>{{ t("一个模块包含一组匹配条件和一个目标出口。可在不同订阅方案中复用。") }}</p><button class="desk-btn" :disabled="!selected" @click="openModule()">{{ t("创建模块") }}</button></div><article v-for="m in workspace.modules" :key="m.id" class="desk-card module-card"><div class="module-top"><span class="module-symbol"><Layers3 :size="18"/></span><div><h3>{{ m.name }}</h3><small>{{ t("{0} · {1} 个匹配条件", [m.strict?t("严格出口审查"):t("普通分流"), m.matches.length]) }}</small></div><button :class="['desk-switch',{on:plan.module_ids.includes(m.id)}]" role="switch" :aria-checked="plan.module_ids.includes(m.id)" :aria-label="t('启用{0}', [m.name])" :disabled="!!busy||!selected" @click="toggleModule(m.id)"><span></span></button></div><div class="match-tags"><code v-for="(match,i) in m.matches.slice(0,3)" :key="i">{{ match.kind }} · {{ match.value }}</code><small v-if="m.matches.length>3">+{{ m.matches.length-3 }}</small></div><div class="module-bottom"><span>{{ t("流量出口") }}<b>{{ m.target }}</b></span><div><button class="desk-text-btn" @click="openModule(m)">{{ t("编辑") }}</button><button class="desk-icon-btn danger" :aria-label="t('删除模块')" :disabled="!!busy" @click="deleteModule(m.id)"><Trash2 :size="15"/></button></div></div></article></section>
          <aside class="desk-card plan-panel"><span class="desk-eyebrow">COMPOSITION</span><h2>{{ t("方案合成") }}</h2><p>{{ t("模块规则位于源规则之前。上方模块优先匹配。") }}</p><div v-if="!activeModules.length" class="inline-note">{{ t("当前方案未启用模块。") }}</div><div v-for="(m,i) in activeModules" :key="m.id" class="plan-order"><span>{{ i+1 }}</span><strong>{{ m.name }}</strong><button :disabled="!!busy||i===0" :aria-label="t('上移模块')" @click="moveModule(m.id,-1)">↑</button><button :disabled="!!busy||i===activeModules.length-1" :aria-label="t('下移模块')" @click="moveModule(m.id,1)">↓</button></div><label class="desk-field">{{ t("未匹配流量") }}<select :value="plan.default_target" :disabled="!!busy||!selected" @change="setDefault"><option value="">{{ t("保留源订阅默认规则") }}</option><option v-for="target in targets" :key="target" :value="target">{{ target }}</option></select></label><div v-if="preview?.errors.length" class="validation-box error"><strong>{{ t("需要处理 {0} 项", [preview.errors.length]) }}</strong><p v-for="e in preview.errors" :key="e">{{ message(e) }}</p></div><div v-else-if="selected" class="validation-box"><ShieldCheck :size="17"/><span>{{ t("模块静态校验通过") }}<br><small>{{ t("应用时仍需内核校验") }}</small></span></div><div v-for="w in preview?.warnings||[]" :key="w" class="inline-note">{{ message(w) }}</div><button class="desk-btn primary full" :disabled="!!busy||!selected||!!preview?.errors.length" @click="apply"><Loader2 v-if="busy==='apply'" class="rotate" :size="15"/><Power v-else :size="15"/>{{ t("应用到本机") }}</button><button class="desk-text-btn full" :disabled="!preview" @click="download"><Download :size="14"/>{{ t("导出合成 YAML") }}</button><p class="small-explanation">{{ t("严格审查会拒绝含 DIRECT、动态 provider 或不明出口的策略链。固定策略组仍可能包含多个代理出口；本版不提供内核退出后的联网阻断。") }}</p></aside></div>
          <details v-if="preview" class="desk-card yaml-preview"><summary>{{ t("查看合成后的 {0} 条规则与 YAML", [preview.config.rules?.length||0]) }}</summary><pre>{{ preview.yaml }}</pre></details>
        </template>

        <template v-if="page==='proxies'">
          <div class="section-toolbar"><label class="inline-select">{{ t("查看订阅") }}<select :aria-label="t('查看订阅')" :value="selected" @change="choose(($event.target as HTMLSelectElement).value)"><option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.title }}</option></select></label><button class="desk-text-btn" :aria-label="t('刷新节点列表')" :title="t('刷新节点列表')" :disabled="!!busy" @click="perform('catalog',loadCatalog)"><RefreshCw :size="13"/>{{ t("刷新节点列表") }}</button></div>
          <div v-if="!selected" class="desk-card desk-empty"><Globe2 :size="38"/><h3>{{ t("导入订阅后即可查看节点和测速") }}</h3><button class="desk-btn primary" @click="go('subscriptions')">{{ t("前往订阅页") }}</button></div>
          <ProxyPanel :benchmark-available="!nativeCoreUnavailable" v-else :view-state="proxyView" @view-state="proxyView=$event" @ready="restoreScroll" :proxies="proxyCatalog.proxies" :busy="!!busy" :pending="pendingSelections" :session-key="proxyCatalog.key" :profile-id="selected" :profile-revision="proxyCatalog.profile_revision" :workspace-revision="proxyCatalog.workspace_revision" :live="proxyCatalog.live" :has-providers="proxyCatalog.has_providers" @select="selectProxy" @notice="notify" @refresh="loadCatalog"/>
        </template>

        <div v-if="isAndroid&&page==='connections'" class="diagnostic-back"><button class="desk-text-btn" @click="go('settings')">{{ t('返回设置与诊断') }}</button></div>
        <ConnectionPanel v-show="page==='connections'" :active="page==='connections'" :connections="connections" :sampled-at="connectionSampledAt" :running="runtime.running" :busy="!!busy" :error="runtimeError" :config-key="`${runtime.active?.hash||''}:${runtime.egress_version??0}`" :app-labels="appLabels" @close="closeConnection" @notice="notify" @ready="restoreScroll"/>


        <AndroidRouting ref="routingPanel" v-if="isAndroid&&page==='routing'" :view-state="routingView" @view-state="routingView=$event" @ready="restoreScroll" :profile-id="selected" :needs-apply="needsApply" :busy="!!busy" :apply-label="applyLabel" @dirty="editorDirty=$event" @changed="load().catch(e=>notify(e.message,true))" @apply="apply"/>
        <template v-if="page==='studio'&&!isAndroid">
          <div class="section-toolbar"><label class="inline-select">{{ t("当前订阅") }}<select :value="selected" @change="choose(($event.target as HTMLSelectElement).value)"><option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.title }}</option></select></label><span>{{ t("编辑草稿 → 保存发布 → 应用配置") }}</span></div>
          <ConfigEditor :desktop-features="!isAndroid" v-if="detail" :key="detail.id" :view-state="editorView" @view-state="editorView=$event" @ready="restoreScroll" :subscription="detail" :backend-base="backendBase" @saved="editorSaved" @dirty="editorDirty=$event" @notice="notify"/>
          <div v-else class="desk-card desk-empty"><FileCode2 :size="36"/><h3>{{ t("选择或导入一份订阅开始编辑") }}</h3><button class="desk-btn primary" @click="importOpen=true">{{ t("导入订阅") }}</button></div>
        </template>

        <template v-if="page==='settings'">
          <div class="settings-tabs" role="tablist" :aria-label="t('设置与日志')"><button role="tab" :aria-selected="settingsTab==='general'" @click="selectSettingsTab('general')">{{ t("设置") }}</button><button role="tab" :aria-selected="settingsTab==='logs'" @click="selectSettingsTab('logs')">{{ t("运行日志") }}</button></div>
          <div v-show="settingsTab==='general'" class="settings-stack">

          <ClientSettings :view-query="settingsSearch" @view-query="settingsSearch=$event" @ready="restoreScroll" @connections="go('connections')" :core-available="!isAndroid&&!nativeCoreUnavailable" :android="isAndroid" :validation="validationBuild" :running="runtime.running" :port="runtime.active?.mixed_port||mixedPort" @notice="notify" @changed="clientSettingsChanged" @dirty="networkSettingsDirty=$event" @diagnostics="selectSettingsTab('logs')"><template #language><LanguageSettings/></template><template #permissions><AndroidPermissions v-if="isAndroid"/></template><template #proxy><section class="desk-card settings-card local-runtime-card proxy-settings-card"><div class="section-head"><div><h2>{{ t("连接与代理") }}</h2><p>Mihomo<span v-if="platform.os"> · {{ platformLabel }}</span></p></div><Power :size="21"/></div><div class="proxy-settings-columns"><div class="proxy-mode-settings"><div class="setting-row"><div><strong>{{ t("接管模式") }}</strong><small>{{ t("当前实际状态：{0}。停止内核时尝试恢复代理与路由。", [actualMode]) }}</small></div></div><label class="desk-field launch-profile">{{ t('当前方案') }}<select :value="selected" :disabled="!!busy" @change="choose(($event.target as HTMLSelectElement).value)"><option v-if="!profiles.length" value="">{{ t('先导入订阅') }}</option><option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.title }}</option></select></label>
              <p v-if="!isAndroid" class="mode-label">{{ t('接管方式') }}</p><div v-if="!isAndroid" class="mode-options" role="group" :aria-label="t('设置接管模式')"><button :class="{selected:proxyMode==='system'}" :disabled="!!busy" @click="selectMode('system')"><Globe2 :size="16"/><span>{{ t(runtime.proxy.supported?"系统代理":"仅代理端口") }}</span><Check v-if="proxyMode==='system'" :size="14"/></button><button :class="{selected:proxyMode==='tun'}" :disabled="!!busy||!runtime.tun?.supported" @click="selectMode('tun')"><ShieldCheck :size="16"/><span>{{ t("TUN 模式") }}</span><Check v-if="proxyMode==='tun'" :size="14"/></button></div><div v-if="!isAndroid" class="tun-settings"><label class="desk-field">{{ t("TUN 协议栈") }}<select v-model="tunStack" :disabled="!runtime.tun?.supported"><option value="mixed">{{ t("Mixed · 混合协议栈") }}</option><option value="system">{{ t("System · 系统协议栈") }}</option><option value="gvisor">{{ t("gVisor · 用户空间协议栈") }}</option></select></label><p v-if="runtime.tun?.conflicts.length" class="inline-note">{{ t("其他内核运行中：{0}。启用 TUN 前请先关闭，以避免路由冲突。", [runtime.tun.conflicts.join('、')]) }}</p><button v-if="runtime.tun?.supported&&!runtime.tun?.admin" class="desk-btn" :disabled="!!busy" @click="elevate"><ShieldCheck :size="15"/>{{ t("请求管理员权限") }}</button><p v-if="runtime.tun?.supported&&platform.os==='windows'" class="small-explanation">{{ t("驱动：{0} · 网卡名称 ClashStudio", [runtime.tun?.driver_installed?t("Wintun 已就绪"):t("Wintun 缺失")]) }}</p><p v-if="runtime.tun?.supported&&platform.os==='linux'" class="small-explanation">{{ t("Linux TUN 使用系统网络权限；授权保留在内核文件上，替换内核后需重新申请。") }}</p></div></div><div class="proxy-connection-settings"><ProxyPortSettings :running="runtime.running" :port="mixedPort" @changed="clientSettingsChanged" @dirty="portSettingsDirty=$event" @notice="notify"/><div v-if="!nativeCoreUnavailable" class="proxy-address"><code>http://127.0.0.1:{{ runtime.active?.mixed_port||mixedPort }}</code><button class="desk-text-btn" @click="copyProxy">{{ t("复制") }}</button></div><p v-if="nativeCoreUnavailable" class="small-explanation">{{ t("端口仅作为配置保存，当前不会启动代理监听。") }}</p><p v-else-if="isAndroid" class="small-explanation">{{ t("可在支持 HTTP / SOCKS 代理的应用中填写上方本地地址。") }}</p><p v-else class="small-explanation">{{ t("系统代理仅覆盖遵守系统代理设置的应用；也可在单个应用中填写上方地址。当前系统代理：{0}", [runtime.proxy.enabled?runtime.proxy.server:t("未启用")]) }}</p></div></div><p v-if="isAndroid" class="android-network-note">{{ nativeDevelopment?t("通过 Android VPN 接管流量；首次启动需要系统授权，局域网保持直连。"):validationBuild?t("代理内核与 VPN 尚不可用。"):t("安卓 VPN 服务尚未接入，当前仅提供本地代理端口。") }}</p><p v-else class="helper-status">{{ !runtime.tun?.supported?(runtime.proxy.supported?t("已支持系统代理自动接管；当前平台暂未开放 TUN。"):t("当前平台暂仅支持手动代理端口。")):runtime.tun?.helper?t("管理员助手已连接"):runtime.tun?.admin?t("当前已具备 TUN 权限"):t("TUN 权限按需申请，主窗口无需重启") }}</p><div class="config-actions"><button class="desk-btn primary" :disabled="!!busy||editorDirty||!selected||nativeCoreUnavailable||!runtimeReady" @click="apply">{{ applyLabel }}</button><button class="desk-btn danger" :disabled="(!!busy&&busy!=='apply')||(!runtime.running&&busy!=='apply')" @click="stop"><Power :size="15"/>{{ t("停止内核") }}</button></div></section></template></ClientSettings>
          </div>
          <RuntimeLogPanel v-if="settingsTab==='logs'" :view-state="logView" @view-state="logView=$event" @ready="restoreScroll" :events="runtime.events" @notice="notify"/>
        </template>
        </div>
      </main>
    </div>

    <nav class="mobile-navigation" :aria-label="t('主导航')" :style="{'--nav-index':mobileNavIndex,'--nav-count':mobileNav.length}">
      <span class="mobile-nav-thumb" aria-hidden="true"></span>
      <button v-for="item in mobileNav" :key="item.id" type="button" :class="{active:mobileSection===item.id}" :aria-current="mobileSection===item.id?'page':undefined" @click="go(item.id)"><span class="mobile-nav-icon"><component :is="item.icon" :size="22" :stroke-width="mobileSection===item.id?2.3:1.8"/></span><span>{{ item.id==='settings'?t('设置'):item.label }}</span></button>
    </nav>

    <AppDialog v-model="importOpen" :title="t('导入订阅')" :description="t('订阅与修改记录保存在本机独立数据目录。')" :dirty="importDirty" :busy="!!busy||qrBusy" close-label="关闭导入" initial-focus="#import-profile-name" @closed="resetImport"><form id="import-profile-form" @submit.prevent="importProfile()"><div class="modal-tabs"><button type="button" :class="{active:importType==='url'}" @click="importType='url'">{{ t("订阅链接") }}</button><button type="button" :class="{active:importType==='file'}" @click="importType='file'">{{ t("YAML 文件") }}</button><button v-if="isAndroid" type="button" :class="{active:importType==='qr'}" @click="importType='qr'">{{ t("二维码订阅") }}</button></div><div v-if="importType==='qr'" class="qr-import-options"><p class="page-caption">{{ t("相机扫码需授权相机；从照片识别只读取你在系统选择器中授权的图片。识别后请确认链接再导入。") }}</p><div class="heading-buttons"><button type="button" class="desk-btn" :disabled="qrBusy" @click="readQr('camera')">{{ t("相机扫码") }}</button><button type="button" class="desk-btn" :disabled="qrBusy" @click="readQr('photo')">{{ t("从照片识别") }}</button><button type="button" class="desk-text-btn" :disabled="qrBusy" @click="openAppPermissions">{{ t("权限设置") }}</button></div><p v-if="qrBusy" role="status">{{ t("请在系统界面完成识别，或返回取消。") }}</p></div><label class="desk-field">{{ t("名称") }}<input id="import-profile-name" v-model="importName" required maxlength="100" :placeholder="t('例如：我的日常配置')"/></label><label v-if="importType!=='file'" class="desk-field">{{ t("订阅 URL") }}<input v-model="importUrl" type="url" required placeholder="https://…" autocomplete="off"/></label><template v-else><label class="file-import"><FileCode2 :size="22"/><span>{{ t("选择 YAML 文件") }}</span><input type="file" accept=".yaml,.yml,text/yaml" @change="readFile"/></label><label class="desk-field">{{ t("或粘贴 YAML") }}<textarea v-model="importYaml" required rows="6" placeholder="proxies: …"></textarea></label></template><div v-if="importError" class="desk-alert error">{{ message(importError) }}</div></form><template #footer><div class="modal-actions"><button type="button" class="desk-text-btn" :disabled="!!busy" @click="importProfile(true)">{{ t("载入示例") }}</button><button type="submit" form="import-profile-form" class="desk-btn primary" :disabled="!!busy||qrBusy"><Loader2 v-if="busy" class="rotate" :size="15"/>{{ t("导入配置") }}</button></div></template></AppDialog>

    <AppDialog v-model="moduleOpen" class="wide" :title="t('编辑分流模块')" :description="t('多个条件按“任一匹配”生效；模块优先级由方案排序决定。')" :dirty="moduleDirty" :busy="!!busy" close-label="关闭模块编辑" initial-focus="#module-name"><form id="module-edit-form" @submit.prevent="saveModule"><div class="form-columns"><label class="desk-field">{{ t("模块名称") }}<input id="module-name" v-model="moduleDraft.name" required maxlength="100" :placeholder="t('例如：工作应用专线')"/></label><label class="desk-field">{{ t("目标出口") }}<select v-model="moduleDraft.target" :aria-label="t('目标出口')"><option v-for="target in targets" :key="target" :value="target">{{ target }}</option></select></label></div><div class="setting-row"><div><strong>{{ t("严格出口审查") }}</strong><small>{{ t("拒绝直连、动态成员及无法完整审查的出口链。") }}</small></div><button type="button" :class="['desk-switch',{on:moduleDraft.strict}]" role="switch" :aria-checked="moduleDraft.strict" @click="moduleDraft.strict=!moduleDraft.strict"><span></span></button></div><div class="match-heading"><strong>{{ t("匹配条件") }}</strong><button type="button" class="desk-text-btn" @click="moduleDraft.matches.push({kind:'DOMAIN-SUFFIX',value:''})"><Plus :size="14"/>{{ t("添加条件") }}</button></div><div class="match-editor"><div v-for="(match,i) in moduleDraft.matches" :key="i" class="match-row"><select v-model="match.kind" :aria-label="t('匹配类型')"><option v-for="kind in ['DOMAIN-SUFFIX','DOMAIN','PROCESS-NAME','PROCESS-PATH','IP-CIDR','IP-CIDR6']" :key="kind" :value="kind">{{ kind }}</option></select><input v-model="match.value" required :aria-label="t('匹配值')" :placeholder="match.kind==='PROCESS-NAME'?'example.exe':match.kind==='DOMAIN-SUFFIX'?'example.com':t('填写完整匹配值')"/><button type="button" class="desk-icon-btn danger" :aria-label="t('移除条件')" :disabled="moduleDraft.matches.length===1" @click="moduleDraft.matches.splice(i,1)"><X :size="16"/></button></div></div><div v-if="moduleError" class="desk-alert error">{{ message(moduleError) }}</div></form><template #footer><div class="modal-actions"><span class="small-explanation">{{ t("保存模块后，在方案中启用，再应用到内核。") }}</span><button type="submit" form="module-edit-form" class="desk-btn primary" :disabled="!!busy">{{ t("保存模块") }}</button></div></template></AppDialog>
    <Transition name="toast"><div v-if="notice" :class="['desk-toast',{failed:noticeError}]" role="status"><CircleHelp v-if="noticeError" :size="18"/><Check v-else :size="18"/><span>{{ message(notice) }}</span><button :aria-label="t('关闭提示')" @click="notice=''"><X :size="14"/></button></div></Transition>
  </div>
</template>
