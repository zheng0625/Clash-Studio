<script setup lang="ts">
import { confirmDialog } from '../confirm'
import { t, locale, message as translateMessage } from './i18n'

import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import ThemeSettings from './ThemeSettings.vue'
import LanguageSettings from './LanguageSettings.vue'
import { ArrowDown, ArrowUp, ArrowUpRight, Check, CheckCircle2, ChevronRight, CircleHelp, Clipboard, Code2, Download, ExternalLink, FileCode2, FileUp, FolderClock, Globe2, Layers3, Link2, ListFilter, Loader2, MoreHorizontal, Network, Plus, RefreshCw, RotateCcw, Save, Search, Settings2, ShieldCheck, SlidersHorizontal, Trash2, Waypoints, X, AlertTriangle, PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'
import type { AICatalogue, Edits, Group, History, NetworkStatus, Preview, Subscription, Summary } from './types'

type Tab = 'nodes'|'groups'|'rules'|'preview'|'history'|'settings'
const subs = ref<Summary[]>([]), current = ref<Subscription|null>(null), edits = ref<Edits|null>(null)
const preview = ref<Preview|null>(null), tab = ref<Tab>('groups'), busy = ref(false), checking = ref(false)
const modal = ref(false), importType = ref<'url'|'file'>('url'), importTitle = ref(''), importUrl = ref(''), importYaml = ref(''), importFile = ref(''), importError = ref('')
const toast = ref(''), toastError = ref(false), error = ref(''), nodeSearch = ref(''), memberSearch = ref(''), ruleSearch = ref('')
const groupKey = ref(''), history = ref<History[]>([]), historical = ref<{yaml:string; id:number; label:string}|null>(null)
const rawView = ref(false), sourceExpanded = ref(false), sidebarOpen = ref(false)
const settings = ref({title:'', enabled:true, interval_minutes:0})
const ruleForm = ref({kind:'DOMAIN-SUFFIX', value:'', target:'DIRECT', noResolve:false}), rulePosition = ref('top'), advancedRule = ref(''), advanced = ref(false)
const newGroupName = ref(''), addGroupOpen = ref(false), newGroupType = ref('select')
const aiCatalogue = ref<AICatalogue|null>(null), aiDialog = ref(false), aiOutlet = ref(''), aiError = ref(''), aiDetails = ref(false)
const network = ref<NetworkStatus|null>(null), networkBusy = ref(false), networkError = ref('')
const networkForm = ref({enabled:false,port:8767,selected_host:''})
const linkMode = ref<'local'|'lan'>(localStorage.getItem('clash-studio-link-mode')==='lan'?'lan':'local')
const replacement = ref<HTMLInputElement|null>(null), importNameInput = ref<HTMLInputElement|null>(null)
const aiOutletInput = ref<HTMLSelectElement|null>(null)
let previewTimer: ReturnType<typeof setTimeout>|undefined, toastTimer: ReturnType<typeof setTimeout>|undefined, requestSeq = 0
const clone = <T,>(value:T):T => JSON.parse(JSON.stringify(value))
const dirty = computed(() => !!current.value  &&  !!edits.value  &&  JSON.stringify(edits.value) !== JSON.stringify(current.value.edits))
const sourceNodes = computed(() => current.value?.source.proxies || [])
const filteredNodes = computed(() => sourceNodes.value.filter(p => `${p.name} ${p.type} ${p.server} ${edits.value?.proxy_renames[p.name]||''}`.toLowerCase().includes(nodeSearch.value.toLowerCase())))
const groupEntries = computed(() => {
  if (!current.value || !edits.value) return []
  const base = (current.value.source['proxy-groups']||[]).filter(g=>!edits.value!.deleted_groups.includes(g.name)).map(g=>({key:g.name, added:false, group:{...g,...edits.value!.group_overrides[g.name]}}))
  return [...base, ...edits.value.new_groups.map((g,i)=>({key:`new:${i}`,added:true,group:g}))]
})
const selectedGroup = computed(()=>groupEntries.value.find(g=>g.key===groupKey.value))
const memberOptions = computed(()=>{
  if (!edits.value) return []
  return [
    ...sourceNodes.value.filter(p=>!edits.value!.excluded_proxies.includes(p.name)).map(p=>({name:p.name,label:edits.value!.proxy_renames[p.name]||p.name,type:p.type})),
    ...groupEntries.value.filter(g=>g.key!==groupKey.value).map(g=>({name:g.added?g.group.name:g.key,label:g.group.name,type:t("代理组")})),
    ...['DIRECT','REJECT'].map(name=>({name,label:name,type:t("内置策略")})),
  ].filter(n=>`${n.name} ${n.label}`.toLowerCase().includes(memberSearch.value.toLowerCase()))
})
const policies = computed(()=>[
  {value:'DIRECT',label:t("DIRECT · 直连")}, {value:'REJECT',label:t("REJECT · 拒绝")},
  ...groupEntries.value.map(g=>({value:g.added?g.group.name:g.key,label:g.group.name})),
  ...sourceNodes.value.filter(p=>!edits.value?.excluded_proxies.includes(p.name)).map(p=>({value:p.name,label:edits.value?.proxy_renames[p.name]||p.name})),
])
const aiActive = computed(()=>!!edits.value?.ai_routing && edits.value.ai_routing.enabled!==false)
const aiRules = computed(()=>aiActive.value && aiCatalogue.value?aiCatalogue.value.services.flatMap(s=>s.rules.map(r=>`${r.type},${r.domain},${edits.value!.ai_routing!.group}`)):[])
const aiGroup = computed(()=>groupEntries.value.find(g=>(g.added?g.group.name:g.key)===edits.value?.ai_routing?.group))
const aiOutlets = computed(()=>policies.value.filter(p=>!['DIRECT','REJECT',edits.value?.ai_routing?.group].includes(p.value) && p.label!==aiCatalogue.value?.group_name))
function managedDomainRule(rule:string){
  const [kind,rawDomain]=rule.split(',').map(p=>p.trim())
  if(!['DOMAIN','DOMAIN-SUFFIX'].includes(kind?.toUpperCase())||!rawDomain)return false
  const domain=rawDomain.toLowerCase().replace(/\.$/,'')
  return !!aiCatalogue.value?.services.some(s=>s.rules.some(r=>r.type==='DOMAIN-SUFFIX'?(domain===r.domain||domain.endsWith('.'+r.domain)):(kind.toUpperCase()==='DOMAIN' && domain===r.domain)))
}
function isAIManaged(rule:string){return aiActive.value && managedDomainRule(rule)}
const visibleRules = computed(()=>{
  if (!current.value || !edits.value) return []
  const available = [...(current.value.source.rules||[]).filter(r=>!edits.value!.removed_rules.includes(r)), ...edits.value.added_rules]
  const ordered = [...new Set(edits.value.rule_order.filter(r=>available.includes(r)))]
  const rest = available.filter(r=>!ordered.includes(r))
  if (!ordered.length) ordered.push(...rest)
  else {
    const index = ordered.findIndex(r=>/^(MATCH|FINAL),/i.test(r))
    ordered.splice(index<0?ordered.length:index,0,...rest)
  }
  return [...aiRules.value,...new Set(ordered.filter(r=>!aiActive.value||!managedDomainRule(r)))]
})
const filteredRules = computed(()=>visibleRules.value.map((raw,index)=>({raw,index})).filter(r=>r.raw.toLowerCase().includes(ruleSearch.value.toLowerCase())))
const changes = computed(()=>edits.value?Object.keys(edits.value.proxy_renames).length+edits.value.excluded_proxies.length+Object.keys(edits.value.group_overrides).length+edits.value.deleted_groups.length+edits.value.new_groups.length+edits.value.added_rules.length+edits.value.removed_rules.length+(edits.value.rule_order.length?1:0)+(edits.value.ai_routing?1:0):0)
const localOutputUrl = computed(()=>current.value?`${window.location.origin}${current.value.subscription_path}`:'')
const lanOutputUrl = computed(()=>current.value && network.value?.running && network.value?.base_url?`${network.value.base_url}${current.value.subscription_path}`:'')
const outputUrl = computed(()=>linkMode.value==='lan'?lanOutputUrl.value:localOutputUrl.value)
const otherFields = computed(()=>current.value?Object.fromEntries(Object.entries(current.value.source).filter(([k])=>!['proxies','proxy-groups','rules'].includes(k))):{})
const missingPatches = computed(()=>Object.keys(edits.value?.group_overrides||{}).filter(n=>!(current.value?.source['proxy-groups']||[]).some(g=>g.name===n)))
const statusText = computed(()=>!current.value?.enabled?t("已停用"):current.value?.last_error?t("待处理"):dirty.value?t("尚未发布"):t("已发布"))
const tabs = computed(()=>[
  {key:'nodes' as Tab,label:t("代理节点"),icon:Globe2,count:sourceNodes.value.length},
  {key:'groups' as Tab,label:t("代理组"),icon:Layers3,count:groupEntries.value.length},
  {key:'rules' as Tab,label:t("分流规则"),icon:ListFilter,count:visibleRules.value.length},
  {key:'preview' as Tab,label:t("配置预览"),icon:Code2},
  {key:'history' as Tab,label:t("版本历史"),icon:FolderClock},
  {key:'settings' as Tab,label:t("设置"),icon:Settings2},
])

async function api<T>(path:string, method='GET', data?:unknown):Promise<T> {
  const response = await fetch(path,{method,headers:{'Content-Type':'application/json','X-Clash-Studio':'1'},body:data===undefined?undefined:JSON.stringify(data)})
  const json = await response.json()
  if(!response.ok) {
    const detail=json.detail
    const message=typeof detail==='string'?detail:detail?.errors?.join('；') || detail?.message || (Array.isArray(detail)?t("输入格式无效，请检查字段内容"):t("请求失败"))
    throw new Error(message)
  }
  return json
}
function notify(message:string,failed=false) {
  clearTimeout(toastTimer); toast.value=message; toastError.value=failed
  toastTimer=setTimeout(()=>toast.value='',5500)
}
function fmtDate(value:string) { return new Date(value).toLocaleString(locale.value,{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) }
async function reloadList() { subs.value=await api<Summary[]>('/api/subscriptions') }
function applyDetail(detail:Subscription) {
  requestSeq++; clearTimeout(previewTimer); checking.value=false
  detail.edits.ai_routing ??= null
  current.value=detail; edits.value=clone(detail.edits); preview.value=detail.preview
  settings.value={title:detail.title,enabled:!!detail.enabled,interval_minutes:detail.interval_minutes}
  error.value=''; historical.value=null
  if(!groupEntries.value.some(g=>g.key===groupKey.value)) groupKey.value=groupEntries.value[0]?.key||''
  localStorage.setItem('clash-studio-selected',detail.id)
}
async function selectSub(id:string) {
  if(busy.value || (dirty.value  &&  !await confirmDialog(t("当前修改尚未保存，切换后将丢弃。是否继续？")))) return
  busy.value=true
  try { applyDetail(await api<Subscription>(`/api/subscriptions/${id}`)); sidebarOpen.value=false; if(tab.value==='history') await loadHistory() }
  catch(e) { notify((e as Error).message,true) }
  finally { busy.value=false }
}
async function previewDraft() {
  if(!current.value || !edits.value) return
  const seq=++requestSeq, id=current.value.id
  checking.value=true
  try {
    const result=await api<Preview>(`/api/subscriptions/${id}/preview`,'POST',{revision:current.value.revision,edits:edits.value})
    if(seq===requestSeq){preview.value=result;error.value=''}
  } catch(e){if(seq===requestSeq)error.value=(e as Error).message}
  finally{if(seq===requestSeq)checking.value=false}
}
watch(edits,()=>{
  clearTimeout(previewTimer)
  if(dirty.value){requestSeq++;checking.value=true;previewTimer=setTimeout(previewDraft,350)}
  else { requestSeq++; checking.value=false; if(current.value) preview.value=current.value.preview }
},{deep:true})
watch(tab,async value=>{if(value==='history') await loadHistory()})
watch(modal,async value=>{if(value){await nextTick();importNameInput.value?.focus()}})
watch(aiDialog,async value=>{if(value){await nextTick();aiOutletInput.value?.focus()}})
watch(linkMode,value=>localStorage.setItem('clash-studio-link-mode',value))
window.addEventListener('beforeunload',beforeUnload)
function beforeUnload(e:BeforeUnloadEvent){if(dirty.value){e.preventDefault();e.returnValue=''}}
onUnmounted(()=>{window.removeEventListener('beforeunload',beforeUnload);clearTimeout(previewTimer);clearTimeout(toastTimer)})
onMounted(async()=>{
  try {await loadNetwork()}catch{}
  try {aiCatalogue.value=await api<AICatalogue>('/api/presets/ai')}catch{}
  try {await reloadList();const last=localStorage.getItem('clash-studio-selected');const first=subs.value.find(s=>s.id===last)||subs.value[0];if(first)await selectSub(first.id)}
  catch(e){error.value=t("无法连接本地服务：")+(e as Error).message}
})
async function loadNetwork(){
  const status=await api<NetworkStatus>('/api/network')
  network.value=status
  networkForm.value={enabled:status.enabled,port:status.port,selected_host:status.selected_host}
  if(!status.running)linkMode.value='local'
}
async function refreshAddresses(){
  networkBusy.value=true;networkError.value=''
  try{await loadNetwork();notify(t("局域网地址已刷新"))}catch(e){networkError.value=(e as Error).message}finally{networkBusy.value=false}
}
async function saveNetwork(){
  networkBusy.value=true;networkError.value=''
  try{
    const status=await api<NetworkStatus>('/api/network','PUT',networkForm.value)
    network.value=status;networkForm.value={enabled:status.enabled,port:status.port,selected_host:status.selected_host}
    linkMode.value=status.running && status.base_url?'lan':'local'
    notify(status.running?t("局域网订阅已开启，可复制链接到其他设备"):t("局域网订阅共享已关闭"))
  }catch(e){networkError.value=(e as Error).message;notify(networkError.value,true)}finally{networkBusy.value=false}
}
async function save(){
  if(!current.value || !edits.value)return
  busy.value=true
  try{applyDetail(await api<Subscription>(`/api/subscriptions/${current.value.id}/edits`,'PUT',{revision:current.value.revision,edits:edits.value}));await reloadList();notify(t("修改已保存，本地订阅已更新"))}
  catch(e){error.value=(e as Error).message;notify(error.value,true)}finally{busy.value=false}
}
async function refreshSource(yaml?:string){
  if(!current.value)return
  if(dirty.value){notify(t("请先保存或撤销当前修改，再刷新源订阅"),true);return}
  if(current.value.source_type==='file'  &&  yaml===undefined){replacement.value?.click();return}
  busy.value=true
  try{const detail=await api<Subscription>(`/api/subscriptions/${current.value.id}/refresh`,'POST',{revision:current.value.revision,...(yaml===undefined?{}:{yaml})});applyDetail(detail);await reloadList();notify(detail.last_error||t("源订阅已刷新，已重新应用你的修改"),!!detail.last_error)}
  catch(e){notify((e as Error).message,true);try{applyDetail(await api<Subscription>(`/api/subscriptions/${current.value.id}`));await reloadList()}catch{}}
  finally{busy.value=false}
}
async function replacementFile(event:Event){const input=event.target as HTMLInputElement;const file=input.files?.[0];if(file){if(file.size>8*1024*1024){notify(t("文件不能超过 8 MB"),true)}else await refreshSource(await file.text())}input.value=''}
function openImport(){importError.value='';modal.value=true}
async function readImport(event:Event){const file=(event.target as HTMLInputElement).files?.[0];if(file){if(file.size>8*1024*1024){importError.value=t("文件不能超过 8 MB");return}importYaml.value=await file.text();importFile.value=file.name;if(!importTitle.value)importTitle.value=file.name.replace(/\.ya?ml$/i,'')}}
async function createSubscription(demo=false){
  if(dirty.value  &&  !await confirmDialog(t("导入新订阅将离开当前编辑，是否丢弃未保存修改？")))return
  busy.value=true;importError.value=''
  try{
    const detail=await api<Subscription>('/api/subscriptions','POST',demo?{title:t("示例订阅"),source_type:'demo'}:{title:importTitle.value,source_type:importType.value,source_url:importType.value==='url'?importUrl.value:'',yaml:importType.value==='file'?importYaml.value:''})
    applyDetail(detail);await reloadList();modal.value=false;tab.value='groups';importTitle.value='';importUrl.value='';importYaml.value='';importFile.value='';notify(demo?t("演示配置已载入，示例节点无法实际连接"):t("订阅已导入"))
  }catch(e){importError.value=(e as Error).message;if(demo)notify(importError.value,true)}finally{busy.value=false}
}
function renameProxy(name:string,value:string){if(!edits.value)return;if(value===name||!value.trim())delete edits.value.proxy_renames[name];else edits.value.proxy_renames[name]=value.trim()}
function toggleProxy(name:string){if(!edits.value)return;const list=edits.value.excluded_proxies;const i=list.indexOf(name);i<0?list.push(name):list.splice(i,1)}
function patchGroup(field:string,value:unknown){
  if(!edits.value||!selectedGroup.value)return
  if(selectedGroup.value.added){
    const target=edits.value.new_groups[Number(groupKey.value.slice(4))]
    if(field==='name' && typeof value==='string' && value!==target.name){
      const old=target.name
      for(const group of [...edits.value.new_groups,...Object.values(edits.value.group_overrides)]){
        if(group.proxies)group.proxies=group.proxies.map(n=>n===old?value:n)
      }
      const renameRule=(rule:string)=>{
        const parts=rule.split(',');if(parts[0]==='SUB-RULE')return rule
        const i=parts.length-(parts.at(-1)==='no-resolve'?2:1)
        if(parts[i]===old)parts[i]=value
        return parts.join(',')
      }
      edits.value.added_rules=edits.value.added_rules.map(renameRule)
      edits.value.rule_order=edits.value.rule_order.map(renameRule)
      if(edits.value.ai_routing?.group===old)edits.value.ai_routing.group=value
    }
    ;(target as any)[field]=value
  }
  else {
    const name=groupKey.value, base=(current.value?.source['proxy-groups']||[]).find(g=>g.name===name)!
    const patch=edits.value.group_overrides[name]||{}
    if(JSON.stringify(value)===JSON.stringify(base[field]))delete patch[field];else (patch as any)[field]=value
    if(Object.keys(patch).length)edits.value.group_overrides[name]=patch;else delete edits.value.group_overrides[name]
  }
}
function toggleMember(name:string){const list=[...(selectedGroup.value?.group.proxies||[])];const index=list.indexOf(name);index<0?list.push(name):list.splice(index,1);patchGroup('proxies',list)}
function moveMember(index:number,offset:number){const list=[...(selectedGroup.value?.group.proxies||[])];const next=index+offset;if(next<0||next>=list.length)return;[list[index],list[next]]=[list[next],list[index]];patchGroup('proxies',list)}
function memberLabel(name:string){return edits.value?.proxy_renames[name] || groupEntries.value.find(g=>g.key===name)?.group.name || name}
function addGroup(){
  if(!edits.value||!newGroupName.value.trim())return
  const name=newGroupName.value.trim()
  if(policies.value.some(p=>p.value===name||p.label===name)){notify(t("名称已存在，请换一个名称"),true);return}
  const group:Group={name,type:newGroupType.value,proxies:['DIRECT']}
  if(group.type!=='select' && group.type!=='relay'){group.url='https://www.gstatic.com/generate_204';group.interval=300}
  edits.value.new_groups.push(group);groupKey.value=`new:${edits.value.new_groups.length-1}`;newGroupName.value='';addGroupOpen.value=false
}
async function deleteGroup(){
  if(aiActive.value && selectedGroup.value && (selectedGroup.value.added?selectedGroup.value.group.name:groupKey.value)===edits.value?.ai_routing?.group){notify(t("请先在分流规则页面停用 AI 预设，再删除该代理组"),true);return}
  if(!edits.value||!selectedGroup.value||!await confirmDialog(t("删除代理组「{0}」？仍引用它的规则或代理组需要你调整。",[selectedGroup.value.group.name])))return
  if(selectedGroup.value.added)edits.value.new_groups.splice(Number(groupKey.value.slice(4)),1)
  else edits.value.deleted_groups.push(groupKey.value)
  groupKey.value=groupEntries.value[0]?.key||''
}
function resetGroup(){if(edits.value && selectedGroup.value && !selectedGroup.value.added)delete edits.value.group_overrides[groupKey.value]}
function addRule(){
  if(!edits.value)return
  const f=ruleForm.value
  const rule=advanced.value?advancedRule.value.trim():`${f.kind},${f.kind==='MATCH'?'':f.value.trim()+','}${f.target}${f.noResolve && f.kind!=='MATCH'?',no-resolve':''}`
  if(!rule||(!advanced.value && f.kind!=='MATCH' && !f.value.trim())){notify(t("请填写匹配内容"),true);return}
  if(isAIManaged(rule)){notify(t("该域名已由 AI 预设统一管理，可通过“管理 AI 分流”调整出口"),true);return}
  if(visibleRules.value.includes(rule)){notify(t("这条规则已经存在"),true);return}
  const list=[...visibleRules.value]
  if(edits.value.removed_rules.includes(rule))edits.value.removed_rules=edits.value.removed_rules.filter(r=>r!==rule)
  else edits.value.added_rules.push(rule)
  if(rulePosition.value==='top')list.unshift(rule)
  else{const final=list.findIndex(r=>/^(MATCH|FINAL),/i.test(r));list.splice(final<0?list.length:final,0,rule)}
  edits.value.rule_order=list;f.value='';advancedRule.value=''
}
function removeRule(rule:string){if(!edits.value||isAIManaged(rule))return;if(edits.value.added_rules.includes(rule))edits.value.added_rules=edits.value.added_rules.filter(r=>r!==rule);else edits.value.removed_rules.push(rule);edits.value.rule_order=visibleRules.value.filter(r=>r!==rule)}
function moveRule(index:number,offset:number){if(!edits.value)return;const list=[...visibleRules.value],next=index+offset;if(index<aiRules.value.length||next<aiRules.value.length||next>=list.length)return;[list[index],list[next]]=[list[next],list[index]];edits.value.rule_order=list}
function dropRule(event:DragEvent,index:number){event.preventDefault();if(!edits.value||index<aiRules.value.length)return;const from=Number(event.dataTransfer?.getData('text/plain'));if(!Number.isInteger(from)||from<aiRules.value.length||from>=visibleRules.value.length)return;const list=[...visibleRules.value];const [rule]=list.splice(from,1);list.splice(index,0,rule);edits.value.rule_order=list}
async function openAI(){
  aiError.value='';aiDetails.value=false
  try{if(!aiCatalogue.value)aiCatalogue.value=await api<AICatalogue>('/api/presets/ai')}
  catch(e){notify(t("AI 预设加载失败：")+(e as Error).message,true);return}
  const existing=aiGroup.value||groupEntries.value.find(g=>g.group.name===aiCatalogue.value!.group_name)
  aiOutlet.value=aiOutlets.value.find(p=>p.value===existing?.group.proxies?.[0])?.value||aiOutlets.value[0]?.value||''
  aiDialog.value=true
}
async function applyAI(){
  if(!current.value||!edits.value||!aiOutlet.value)return
  busy.value=true;aiError.value=''
  try{
    const draft=await api<{edits:Edits;preview:Preview}>(`/api/subscriptions/${current.value.id}/ai-preset`,'POST',{revision:current.value.revision,edits:edits.value,outlet:aiOutlet.value})
    edits.value=draft.edits;preview.value=draft.preview;aiDialog.value=false
    notify(t("AI 分流已加入草稿，包含 {0} 条规则；保存后发布",[aiCatalogue.value!.rule_count]))
  }catch(e){aiError.value=(e as Error).message}finally{busy.value=false}
}
function disableAI(){if(edits.value?.ai_routing){edits.value.ai_routing.enabled=false;notify(t("AI 预设已在草稿中停用，原有分流规则恢复；AI 代理组保留"))}}
async function copy(value:string,label=t("已复制")){try{await navigator.clipboard.writeText(value);notify(label)}catch{notify(t("浏览器未允许剪贴板访问，请手动复制"),true)}}
function download(){if(!preview.value||checking.value||error.value||preview.value.errors.length)return;const url=URL.createObjectURL(new Blob([preview.value.yaml],{type:'text/yaml;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`${current.value?.title||'clash'}.yaml`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
async function discard(){if(current.value && (!dirty.value||await confirmDialog(t("撤销所有未保存的修改？")))){applyDetail(clone(current.value));notify(t("已恢复到上次保存状态"))}}
async function loadHistory(){if(!current.value)return;try{history.value=await api<History[]>(`/api/subscriptions/${current.value.id}/history`)}catch(e){notify((e as Error).message,true)}}
async function viewHistory(item:History){if(!current.value)return;try{historical.value=await api(`/api/subscriptions/${current.value.id}/history/${item.id}`)}catch(e){notify((e as Error).message,true)}}
async function restoreHistory(item:History){
  if(!current.value||!await confirmDialog(t("恢复到 {0} 的版本？原始配置与修改记录会一同恢复，当前版本会保留在历史中。",[fmtDate(item.created_at)])))return
  busy.value=true
  try{applyDetail(await api<Subscription>(`/api/subscriptions/${current.value.id}/history/${item.id}/restore`,'POST',{revision:current.value.revision}));await loadHistory();await reloadList();notify(t("历史版本已恢复"))}
  catch(e){notify((e as Error).message,true)}finally{busy.value=false}
}
async function saveSettings(){
  if(!current.value)return
  if(dirty.value){notify(t("请先保存或撤销配置修改"),true);return}
  busy.value=true
  try{applyDetail(await api<Subscription>(`/api/subscriptions/${current.value.id}`,'PATCH',{revision:current.value.revision,...settings.value}));await reloadList();notify(t("订阅设置已保存"))}
  catch(e){notify((e as Error).message,true)}finally{busy.value=false}
}
async function rotateToken(){
  if(!current.value||!await confirmDialog(t("重新生成订阅地址后，旧地址立即失效。是否继续？")))return
  if(dirty.value){notify(t("请先保存或撤销配置修改"),true);return}
  busy.value=true
  try{applyDetail(await api<Subscription>(`/api/subscriptions/${current.value.id}/rotate-token`,'POST',{revision:current.value.revision}));notify(t("订阅地址已更换，请更新客户端中的地址"))}
  catch(e){notify((e as Error).message,true)}finally{busy.value=false}
}
async function deleteSub(){
  if(!current.value||!await confirmDialog(t("永久删除「{0}」及其历史记录？对应本地订阅地址将立即失效。",[current.value.title])))return
  busy.value=true
  try{await api(`/api/subscriptions/${current.value.id}?revision=${current.value.revision}`,'DELETE');current.value=null;edits.value=null;preview.value=null;await reloadList();notify(t("订阅已删除"))}
  catch(e){notify((e as Error).message,true)}finally{busy.value=false}
}
</script>

<template>
  <div class="app-shell">
    <button v-if="sidebarOpen" class="sidebar-mask" :aria-label="t('关闭侧栏')" @click="sidebarOpen=false"></button>
    <aside class="sidebar" :class="{open:sidebarOpen}" :inert="modal||aiDialog">
      <a class="brand" href="/" :aria-label="t('Clash Studio 首页')"><span class="brand-mark"><Waypoints :size="23"/></span><span>Clash<span class="brand-light"> Studio</span></span></a>
      <button class="sidebar-close icon-button" :aria-label="t('收起侧栏')" @click="sidebarOpen=false"><PanelLeftClose :size="18"/></button>
      <div class="workspace-label"><span class="live-dot"></span>{{ t('本地工作空间') }}<span class="version">v0.4.1</span></div>
      <div class="sidebar-section-title"><span>{{ t('我的订阅') }}</span><span>{{ subs.length.toString().padStart(2,'0') }}</span></div>
      <nav class="subscription-nav" :aria-label="t('订阅列表')">
        <button v-for="s in subs" :key="s.id" class="subscription-item" :class="{active:current?.id===s.id}" :disabled="busy" @click="selectSub(s.id)">
          <span class="subscription-icon"><FileCode2 :size="18"/></span>
          <span class="subscription-text"><strong>{{ s.title }}</strong><small>{{ s.source_type==='demo'?t("演示配置"):s.source_host }}</small></span>
          <span class="sub-dot" :class="{warning:s.last_error,disabled:!s.enabled}"></span>
        </button>
        <p v-if="!subs.length" class="no-subscriptions">{{ t('还没有订阅，') }}<br>{{ t('从导入第一份配置开始。') }}</p>
      </nav>
      <button class="sidebar-add" :disabled="busy" @click="openImport"><Plus :size="16"/>{{ t('导入订阅') }}</button>
      <div class="sidebar-bottom">
        <div class="local-card"><ShieldCheck :size="20"/><div><strong>{{ t('配置，留在你的电脑') }}</strong><p>{{ t('本地存储 · 本地分发') }}</p></div></div>
        <div class="sidebar-foot"><span>SUBSCRIPTION WORKBENCH</span><span>01</span></div>
      </div>
    </aside>

    <div class="main-shell" :inert="modal||aiDialog">
      <header class="topbar">
        <div class="breadcrumbs"><button class="mobile-toggle icon-button" :aria-label="t('打开侧栏')" @click="sidebarOpen=true"><PanelLeftOpen :size="20"/></button><span>{{ t('工作空间') }}</span><ChevronRight :size="14"/><strong>{{ current?.title||t("开始使用") }}</strong></div>
        <div class="topbar-right"><LanguageSettings/><ThemeSettings/><span class="local-indicator"><span class="live-dot"></span>{{ t('本地服务运行中') }}</span><span class="topbar-date">CLASH / MIHOMO</span></div>
      </header>

      <main class="page" v-if="!current">
        <div class="eyebrow">YOUR SUBSCRIPTION, YOUR RULES.</div>
        <section class="welcome-heading"><h1>{{ t('让订阅，按你的方式运行。') }}</h1><p>{{ t('把节点、代理组和分流规则放在一张工作台上。') }}<br>{{ t('从导入到修改，再到发布，每一步都看得见。') }}</p></section>
        <section class="welcome-grid">
          <button class="welcome-import" :disabled="busy" @click="openImport"><span class="large-icon"><FileUp :size="30"/></span><h2>{{ t('导入你的第一份订阅') }}</h2><p>{{ t('粘贴订阅链接，或上传 Clash / Mihomo YAML 配置。') }}</p><span class="button primary">{{ t('开始导入') }}<ArrowUpRight :size="17"/></span><span class="card-index">01 / IMPORT</span></button>
          <div class="welcome-flow"><div class="eyebrow">{{ t('一次编辑，持续生效') }}</div><div class="flow-line"><span><Link2 :size="19"/></span><div><strong>{{ t('原始订阅') }}</strong><small>{{ t('保留机场下发的配置') }}</small></div></div><div class="flow-connector"></div><div class="flow-line"><span><SlidersHorizontal :size="19"/></span><div><strong>{{ t('你的修改') }}</strong><small>{{ t('改名、分组与分流规则') }}</small></div></div><div class="flow-connector"></div><div class="flow-line"><span class="green"><Check :size="19"/></span><div><strong>{{ t('专属本地订阅') }}</strong><small>{{ t('刷新源订阅时，重新应用修改') }}</small></div></div></div>
        </section>
        <div class="demo-strip"><span><CircleHelp :size="19"/>{{ t('想先看看编辑效果？示例配置包含 4 个演示节点和 3 个代理组。') }}</span><button class="text-button" :disabled="busy" @click="createSubscription(true)">{{ t('载入演示配置') }}<ArrowUpRight :size="16"/></button></div>
        <div v-if="error" class="notice error"><AlertTriangle :size="18"/>{{ translateMessage(error) }}</div>
        <div class="welcome-footer"><span>{{ t('01 导入配置') }}</span><ChevronRight :size="14"/><span>{{ t('02 可视化调整') }}</span><ChevronRight :size="14"/><span>{{ t('03 保存并订阅') }}</span></div>
      </main>

      <main class="page" v-else>
        <section class="page-heading">
          <div><div class="eyebrow">SUBSCRIPTION WORKBENCH <span>/ {{ current.source_type==='demo'?'DEMO':current.source_type.toUpperCase() }}</span></div><div class="title-row"><h1>{{ current.title }}</h1><span class="status-pill" :class="{amber:dirty||current.last_error,muted:!current.enabled}"><span></span>{{ statusText }}</span></div><p>{{ t('源配置与修改记录独立保存，订阅更新后自动重新应用。') }}</p></div>
          <div class="heading-actions"><button class="button" :disabled="busy||dirty" @click="refreshSource()"><RefreshCw :size="16" :class="{spin:busy}"/>{{ current.source_type==='file'?t("更新文件"):t("刷新源订阅") }}</button><button class="button primary" :disabled="busy||!dirty" @click="save"><Save :size="16"/>{{ t('保存并发布') }}<span v-if="dirty" class="button-dot"></span></button></div>
        </section>
        <input ref="replacement" type="file" accept=".yaml,.yml,text/yaml,text/plain" class="sr-only" :aria-label="t('更新源 YAML 文件')" @change="replacementFile"/>
        <div v-if="current.source_type==='demo'" class="demo-note"><CircleHelp :size="15"/>{{ t('这是演示配置，节点地址不可用于实际代理。你可以自由编辑并体验完整流程。') }}</div>
        <div v-if="current.last_error" class="notice error"><AlertTriangle :size="18"/><div><strong>{{ t('仍在提供上一份可用配置') }}</strong><p>{{ translateMessage(current.last_error) }}</p></div></div>
        <div v-if="error" class="notice error"><AlertTriangle :size="18"/><div>{{ translateMessage(error) }} <button class="text-button" @click="selectSub(current.id)">{{ t('重新载入') }}</button></div></div>

        <section class="stats-row">
          <div class="stat"><span class="stat-icon"><Globe2 :size="20"/></span><div><small>{{ t('代理节点') }}</small><strong>{{ (preview?.config.proxies||[]).length.toString().padStart(2,'0') }}<span> / {{ sourceNodes.length }}</span></strong></div></div>
          <div class="stat"><span class="stat-icon"><Layers3 :size="20"/></span><div><small>{{ t('代理组') }}</small><strong>{{ groupEntries.length.toString().padStart(2,'0') }}<span>{{ t('个策略组') }}</span></strong></div></div>
          <div class="stat"><span class="stat-icon"><ListFilter :size="20"/></span><div><small>{{ t('分流规则') }}</small><strong>{{ visibleRules.length.toString().padStart(2,'0') }}<span>{{ t('条规则') }}</span></strong></div></div>
          <div class="stat"><span class="stat-icon green"><SlidersHorizontal :size="20"/></span><div><small>{{ t('自定义修改') }}</small><strong>{{ changes.toString().padStart(2,'0') }}<span>{{ dirty?t(" 等待保存"):t(" 项已记录") }}</span></strong></div></div>
        </section>

        <nav class="tabs" :aria-label="t('配置编辑区域')"><button v-for="entry in tabs" :key="entry.key" :class="{active:tab===entry.key}" @click="tab=entry.key"><component :is="entry.icon" :size="16"/>{{ entry.label }}<span v-if="entry.count!==undefined" class="tab-count">{{ entry.count }}</span></button></nav>
        <div class="editor-layout" :inert="busy">
          <section class="editor-content">
            <template v-if="tab==='groups'">
              <div class="section-heading"><div><h2>{{ t('代理组编排') }}</h2><p>{{ t('选择一个代理组，调整策略与成员。') }}</p></div><button class="button small" @click="addGroupOpen=!addGroupOpen"><Plus :size="15"/>{{ t('新建代理组') }}</button></div>
              <form v-if="addGroupOpen" class="inline-form panel" @submit.prevent="addGroup"><label>{{ t('代理组名称') }}<input v-model="newGroupName" :placeholder="t('例如：AI 服务')" required maxlength="100"/></label><label>{{ t('策略') }}<select v-model="newGroupType"><option>select</option><option>url-test</option><option>fallback</option><option>load-balance</option></select></label><button class="button primary small" type="submit">{{ t('创建') }}</button><button type="button" class="icon-button" :aria-label="t('取消新建代理组')" @click="addGroupOpen=false"><X :size="17"/></button></form>
              <div class="group-cards"><button v-for="(entry,i) in groupEntries" :key="entry.key" class="group-card" :class="{selected:groupKey===entry.key}" @click="groupKey=entry.key;memberSearch=''">
                <div class="group-card-top"><span class="group-number">{{ String(i+1).padStart(2,'0') }}</span><span v-if="entry.added||edits?.group_overrides[entry.key]" class="changed-dot" :title="t('有自定义修改')"></span><CheckCircle2 v-else-if="entry.key===groupKey" :size="16"/><Layers3 v-else :size="16"/></div><strong>{{ entry.group.name }}</strong><div class="group-card-foot"><span class="type-tag">{{ entry.group.type }}</span><small>{{ entry.group.proxies?.length||0 }}{{ t('个成员') }}{{ entry.group.use?.length?' + provider':'' }}</small></div>
              </button></div>
              <div v-if="!groupEntries.length" class="empty-inline panel"><Layers3 :size="25"/><p>{{ t('还没有代理组，点击“新建代理组”开始。') }}</p></div>
              <section v-if="selectedGroup" class="panel group-editor">
                <div class="panel-heading"><div><h3>{{ selectedGroup.group.name }}</h3><span class="subtle">{{ selectedGroup.added?t("新建代理组"):t("基于原订阅的代理组") }}</span></div><div class="row-actions"><button v-if="!selectedGroup.added" class="icon-button" :title="t('恢复该组的原始设置')" :aria-label="t('恢复代理组设置')" @click="resetGroup"><RotateCcw :size="15"/></button><button class="icon-button danger" :title="t('删除代理组')" :aria-label="t('删除代理组')" @click="deleteGroup"><Trash2 :size="15"/></button></div></div>
                <div class="form-grid"><label>{{ t('名称') }}<input :aria-label="t('代理组名称')" :value="selectedGroup.group.name" @input="patchGroup('name',($event.target as HTMLInputElement).value)"/></label><label>{{ t('选择策略') }}<select :aria-label="t('代理组策略')" :value="selectedGroup.group.type" @change="patchGroup('type',($event.target as HTMLSelectElement).value)"><option value="select">{{ t('select · 手动选择') }}</option><option value="url-test">{{ t('url-test · 自动测速') }}</option><option value="fallback">{{ t('fallback · 故障转移') }}</option><option value="load-balance">{{ t('load-balance · 负载均衡') }}</option><option value="relay">{{ t('relay · 原样保留 / 兼容性取决于内核') }}</option></select></label><template v-if="['url-test','fallback','load-balance'].includes(selectedGroup.group.type)"><label>{{ t('测试 URL') }}<input :value="selectedGroup.group.url||''" placeholder="https://www.gstatic.com/generate_204" @change="patchGroup('url',($event.target as HTMLInputElement).value)"/></label><label>{{ t('检测间隔（秒）') }}<input type="number" min="1" :value="selectedGroup.group.interval||300" @change="patchGroup('interval',Number(($event.target as HTMLInputElement).value))"/></label></template></div>
                <div v-if="selectedGroup.group.use?.length" class="provider-note"><Network :size="15"/>{{ t('使用外部 provider：') }}{{ selectedGroup.group.use.join('、') }}{{ t('。这些引用会被保留。') }}</div>
                <div v-if="selectedGroup.group['include-all']||selectedGroup.group['include-all-proxies']||selectedGroup.group['include-all-providers']" class="provider-note"><CircleHelp :size="15"/>{{ t('该组启用了自动包含节点/provider；以下列表仅编辑显式成员。') }}</div>
                <div class="member-heading"><h4>{{ t('组内成员') }}<span>{{ selectedGroup.group.proxies?.length||0 }}</span></h4><small>{{ t('按列表顺序排列') }}</small></div>
                <div class="selected-members"><div v-for="(member,index) in selectedGroup.group.proxies||[]" :key="member+index" class="selected-member"><span class="member-order">{{ index+1 }}</span><span class="member-name">{{ memberLabel(member) }}</span><div class="row-actions"><button class="icon-button" :disabled="index===0" :aria-label="t('上移成员 ')+memberLabel(member)" @click="moveMember(index,-1)"><ArrowUp :size="13"/></button><button class="icon-button" :disabled="index===(selectedGroup.group.proxies?.length||0)-1" :aria-label="t('下移成员 ')+memberLabel(member)" @click="moveMember(index,1)"><ArrowDown :size="13"/></button><button class="icon-button" :aria-label="t('移除成员 ')+memberLabel(member)" @click="toggleMember(member)"><X :size="13"/></button></div></div><p v-if="!selectedGroup.group.proxies?.length" class="subtle">{{ t('从下方选择成员。') }}</p></div>
                <div class="member-heading"><h4>{{ t('添加节点与策略组') }}</h4><div class="search small-search"><Search :size="14"/><input v-model="memberSearch" :placeholder="t('搜索成员')" :aria-label="t('搜索成员')"/></div></div>
                <div class="member-options"><label v-for="item in memberOptions" :key="item.name" class="member-option" :class="{checked:selectedGroup.group.proxies?.includes(item.name)}"><input type="checkbox" :checked="selectedGroup.group.proxies?.includes(item.name)" @change="toggleMember(item.name)"/><span>{{ item.label }}</span><small>{{ item.type }}</small></label></div>
              </section>
              <div v-if="edits?.deleted_groups.length" class="panel removed-panel"><h4>{{ t('已删除的代理组') }}</h4><div v-for="name in edits.deleted_groups" :key="name" class="removed-row"><span>{{ name }}</span><button class="text-button" @click="edits!.deleted_groups=edits!.deleted_groups.filter(n=>n!==name)">{{ t('恢复代理组') }}</button></div></div>
              <div v-if="missingPatches.length" class="panel removed-panel"><h4>{{ t('源订阅中已消失的代理组') }}</h4><div v-for="name in missingPatches" :key="name" class="removed-row"><span>{{ name }}</span><button class="text-button" @click="delete edits!.group_overrides[name]">{{ t('清除失效修改') }}</button></div></div>
            </template>

            <template v-if="tab==='nodes'">
              <div class="section-heading"><div><h2>{{ t('代理节点') }}</h2><p>{{ t('修改展示名称，或从输出配置中排除节点。') }}</p></div><div class="search"><Search :size="16"/><input v-model="nodeSearch" :placeholder="t('搜索名称、类型或地址')" :aria-label="t('搜索节点')"/></div></div>
              <div class="panel node-table"><div class="node-table-head"><span>{{ t('保留') }}</span><span>{{ t('节点名称 / 自定义名称') }}</span><span>{{ t('协议与地址') }}</span><span>{{ t('状态') }}</span></div><div v-for="node in filteredNodes" :key="node.name" class="node-row" :class="{excluded:edits?.excluded_proxies.includes(node.name)}"><input type="checkbox" :checked="!edits?.excluded_proxies.includes(node.name)" :aria-label="t('保留节点 ')+node.name" @change="toggleProxy(node.name)"/><div class="node-name"><strong>{{ node.name }}</strong><input :value="edits?.proxy_renames[node.name]||node.name" :aria-label="t('重命名节点 ')+node.name" @change="renameProxy(node.name,($event.target as HTMLInputElement).value)"/></div><div class="node-server"><span class="type-tag">{{ node.type }}</span><small>{{ node.server }}:{{ node.port }}</small></div><span class="node-state" :class="{off:edits?.excluded_proxies.includes(node.name)}">{{ edits?.excluded_proxies.includes(node.name)?t("已排除"):edits?.proxy_renames[node.name]?t("已改名"):t("保留") }}</span></div><p v-if="!filteredNodes.length" class="empty-table">{{ t('没有匹配的节点。外部 provider 节点暂不展开。') }}</p></div>
              <div class="info-note"><CircleHelp :size="16"/>{{ t('排除的节点会从代理组的显式成员中移除；如果有规则直接引用它，校验会提示你调整。') }}</div>
              <div v-if="Object.keys(current.source['proxy-providers']||{}).length" class="panel read-only-panel"><h3>{{ t('外部代理提供者') }}</h3><p class="subtle">{{ t('引用原样保留。第一版只编辑 YAML 中的内联节点。') }}</p><div class="provider-tags"><span v-for="(_,name) in current.source['proxy-providers']" class="type-tag">{{ name }}</span></div></div>
            </template>

            <template v-if="tab==='rules'">
              <div class="section-heading rules-heading"><div><h2>{{ t('分流规则') }}</h2><p>{{ t('从上到下依次匹配，可拖动或用箭头调整优先级。') }}</p></div><div class="row-actions"><button class="text-button" @click="advanced=!advanced">{{ advanced?t("切换表单"):t("输入完整规则") }}<Code2 :size="15"/></button><button class="button small ai-trigger" :disabled="busy" @click="openAI"><Waypoints :size="15"/>{{ aiActive?t("管理 AI 分流"):t("一键创建 AI 分流") }}</button></div></div>
              <section v-if="aiActive" class="ai-banner panel"><div class="ai-banner-title"><span class="ai-badge"><Waypoints :size="18"/></span><div><h3>{{ t('AI 分流已启用') }}<span class="type-tag green">{{ aiCatalogue?.service_count }}{{ t('组服务') }}</span></h3><p>{{ aiRules.length }}{{ t('条域名规则 →') }}{{ aiGroup?.group.name||edits?.ai_routing?.group }} · {{ preview?.ai_routing?.overridden||0 }}{{ t('条原有域名规则已合并') }}</p></div><button class="text-button" :disabled="busy" @click="disableAI">{{ t('停用预设') }}</button></div><p class="ai-banner-note">{{ t('预设规则保持优先，刷新订阅后重新应用。停用后恢复原有规则，保留 AI 代理组。') }}{{ dirty?t("当前为未发布草稿。"):'' }}</p></section>
              <form class="panel rule-form" @submit.prevent="addRule"><div v-if="advanced" class="full-rule"><label>{{ t('完整 Clash / Mihomo 规则') }}<input v-model="advancedRule" placeholder="DOMAIN-SUFFIX,example.com,DIRECT" :aria-label="t('完整规则')" required/></label><p class="subtle">{{ t('复杂逻辑规则和 RULE-SET 可在此输入；provider 定义从原配置保留。') }}</p></div><div v-else class="rule-form-fields"><label>{{ t('匹配类型') }}<select v-model="ruleForm.kind" :aria-label="t('规则类型')"><option>DOMAIN-SUFFIX</option><option>DOMAIN</option><option>DOMAIN-KEYWORD</option><option>IP-CIDR</option><option>IP-CIDR6</option><option>GEOIP</option><option>GEOSITE</option><option>PROCESS-NAME</option><option>NETWORK</option><option>MATCH</option></select></label><label v-if="ruleForm.kind!=='MATCH'" class="rule-value">{{ t('匹配内容') }}<input v-model="ruleForm.value" :placeholder="t('例如：example.com')" :aria-label="t('规则匹配内容')" required/></label><label>{{ t('目标策略') }}<select v-model="ruleForm.target" :aria-label="t('规则目标')"><option v-for="p in policies" :value="p.value">{{ p.label }}</option></select></label></div><div class="rule-form-bottom"><label v-if="!advanced && ruleForm.kind!=='MATCH'" class="checkbox-label"><input type="checkbox" v-model="ruleForm.noResolve"/>no-resolve</label><label class="position-select">{{ t('添加位置') }}<select v-model="rulePosition" :aria-label="t('规则添加位置')"><option value="top">{{ t('置于最前') }}</option><option value="bottom">{{ t('兜底规则之前') }}</option></select></label><button class="button primary small" type="submit"><Plus :size="15"/>{{ t('添加规则') }}</button></div></form>
              <div class="rule-list-toolbar"><span>{{ filteredRules.length }}{{ t('条规则') }}<span class="subtle">{{ t('/ 顺序即优先级') }}</span></span><div class="search small-search"><Search :size="14"/><input v-model="ruleSearch" :placeholder="t('搜索规则')" :aria-label="t('搜索规则')"/></div></div>
              <div class="panel rules-list" :class="{'ai-enabled':aiActive}"><div v-for="item in filteredRules" :key="item.raw" class="rule-row" :draggable="!isAIManaged(item.raw)" @dragstart="$event.dataTransfer?.setData('text/plain',String(item.index))" @dragover.prevent @drop="dropRule($event,item.index)"><span class="rule-index">{{ String(item.index+1).padStart(2,'0') }}</span><div class="rule-body"><span class="type-tag" :class="{green:/^(MATCH|FINAL),/.test(item.raw)}">{{ item.raw.split(',')[0] }}</span><code>{{ item.raw.slice(item.raw.indexOf(',')+1) }}</code><span v-if="isAIManaged(item.raw)" class="new-rule">{{ t('AI 预设') }}</span><span v-else-if="edits?.added_rules.includes(item.raw)" class="new-rule">{{ t('新增') }}</span></div><div class="row-actions"><button class="icon-button" :disabled="isAIManaged(item.raw)||item.index<=aiRules.length" :aria-label="t('上移规则 ')+(item.index+1)" @click="moveRule(item.index,-1)"><ArrowUp :size="14"/></button><button class="icon-button" :disabled="isAIManaged(item.raw)||item.index===visibleRules.length-1" :aria-label="t('下移规则 ')+(item.index+1)" @click="moveRule(item.index,1)"><ArrowDown :size="14"/></button><button class="icon-button danger" :disabled="isAIManaged(item.raw)" :aria-label="t('删除规则 ')+(item.index+1)" @click="removeRule(item.raw)"><Trash2 :size="14"/></button></div></div><p v-if="!filteredRules.length" class="empty-table">{{ t('没有匹配的规则。') }}</p></div>
              <div v-if="edits?.removed_rules.length" class="panel removed-panel"><h4>{{ t('已移除的原始规则') }}</h4><div v-for="rule in edits.removed_rules" :key="rule" class="removed-row"><code>{{ rule }}</code><button class="text-button" @click="edits!.removed_rules=edits!.removed_rules.filter(r=>r!==rule)">{{ t('恢复') }}</button></div></div>
            </template>

            <template v-if="tab==='preview'">
              <div class="section-heading"><div><h2>{{ t('配置预览') }}</h2><p>{{ rawView?t("机场下发的原始内容。"):t("应用当前修改后生成的完整 YAML。") }}{{ dirty?t("当前包含未保存修改。"):'' }}</p></div><button class="button small" :disabled="checking||!!error||!!preview?.errors.length" @click="download"><Download :size="15"/>{{ t('下载 YAML') }}</button></div>
              <div class="code-panel"><div class="code-toolbar"><div class="segmented"><button :class="{active:!rawView}" @click="rawView=false">{{ t('生成配置') }}</button><button :class="{active:rawView}" @click="rawView=true">{{ t('原始配置') }}</button></div><button class="code-copy" @click="copy(rawView?current.source_yaml:preview?.yaml||'')"><Clipboard :size="14"/>{{ t('复制') }}</button></div><pre :class="{checking}"><code>{{ rawView?current.source_yaml:preview?.yaml }}</code></pre></div>
              <div class="info-note"><ShieldCheck :size="16"/>{{ t('配置可能包含节点凭据，仅在本机展示。这里的检查为结构与引用校验，未调用代理内核。') }}</div>
            </template>

            <template v-if="tab==='history'">
              <div class="section-heading"><div><h2>{{ t('版本历史') }}</h2><p>{{ t('保存与成功刷新时创建快照，保留最近 50 个版本。') }}</p></div><button class="icon-button" :aria-label="t('刷新历史记录')" @click="loadHistory"><RefreshCw :size="16"/></button></div>
              <div class="panel history-list"><div v-for="(item,index) in history" :key="item.id" class="history-row"><span class="history-icon"><FolderClock :size="18"/></span><div class="history-title"><strong>{{ translateMessage(item.label) }} <span v-if="index===0" class="type-tag green">{{ t('最新快照') }}</span></strong><small>{{ fmtDate(item.created_at) }} · {{ (item.size/1024).toFixed(1) }} KB · #{{ item.id }}</small></div><div class="row-actions"><button class="text-button" @click="viewHistory(item)">{{ t('查看') }}</button><button class="button small" :disabled="busy" @click="restoreHistory(item)"><RotateCcw :size="13"/>{{ t('恢复') }}</button></div></div></div>
              <div v-if="historical" class="code-panel history-preview"><div class="code-toolbar"><span>{{ translateMessage(historical.label) }} · #{{ historical.id }}</span><button class="code-copy" @click="historical=null"><X :size="15"/>{{ t('关闭') }}</button></div><pre><code>{{ historical.yaml }}</code></pre></div>
            </template>

            <template v-if="tab==='settings'">
              <div class="section-heading"><div><h2>{{ t('订阅设置') }}</h2><p>{{ t('管理刷新周期、本地订阅地址和原始配置。') }}</p></div></div>
              <form class="panel settings-panel lan-settings" @submit.prevent="saveNetwork"><div class="lan-heading"><div><h3><Network :size="17"/>{{ t('局域网订阅共享') }}</h3><p class="subtle">{{ t('所有订阅共用此设置，开启后其他设备可获取已发布配置。') }}</p></div><span class="status-pill" :class="{muted:!network?.running}"><span></span>{{ network?.running?t("运行中"):t("未开启") }}</span></div><label class="checkbox-label"><input type="checkbox" v-model="networkForm.enabled" :disabled="networkBusy"/>{{ t('启用局域网订阅共享') }}</label><div class="form-grid"><label>{{ t('共享地址') }}<select v-model="networkForm.selected_host" :aria-label="t('局域网共享地址')" :disabled="networkBusy"><option v-if="!network?.addresses.length" value="">{{ t('未检测到局域网地址') }}</option><option v-for="item in network?.addresses" :key="item.address" :value="item.address">{{ item.address }}{{ item.preferred?t(" · 推荐"):'' }}</option></select></label><label>{{ t('共享端口') }}<input type="number" min="1024" max="65535" v-model.number="networkForm.port" :aria-label="t('局域网共享端口')" :disabled="networkBusy" required/></label></div><p class="subtle lan-help">{{ t('管理页面仅限本机。共享端口只提供带令牌的订阅下载，其他设备需连接同一局域网，电脑和服务需保持运行。') }}</p><div v-if="networkError||network?.error" class="notice error"><AlertTriangle :size="17"/>{{ translateMessage(networkError||network?.error) }}</div><div v-if="network?.running && lanOutputUrl" class="lan-link-box"><label>{{ t('当前订阅的局域网地址') }}</label><div class="subscription-url"><code>{{ lanOutputUrl }}</code><button type="button" class="icon-button" :aria-label="t('复制局域网订阅地址')" @click="copy(lanOutputUrl,t('局域网订阅地址已复制'))"><Clipboard :size="16"/></button></div></div><div class="settings-footer"><button class="text-button" type="button" :disabled="networkBusy" @click="refreshAddresses"><RefreshCw :size="13"/>{{ t('刷新网卡地址') }}</button><button class="button primary small" type="submit" :disabled="networkBusy"><Loader2 v-if="networkBusy" :size="14" class="spin"/>{{ t('保存共享设置') }}</button></div><details class="lan-troubleshooting"><summary>{{ t('其他设备无法连接？') }}</summary><p>{{ t('检查是否连接同一个网络、路由器是否开启访客隔离。Windows 防火墙开启时，可双击软件目录中的“配置局域网防火墙.cmd”，只放行专用网络下本地子网的共享端口。电脑 IP 改变后需重新复制地址。') }}</p></details></form>
              <form class="panel settings-panel" @submit.prevent="saveSettings"><h3>{{ t('基本设置') }}</h3><label>{{ t('订阅名称') }}<input v-model="settings.title" maxlength="100" required/></label><label class="checkbox-label"><input type="checkbox" v-model="settings.enabled"/>{{ t('启用本地订阅地址') }}</label><label v-if="current.source_type==='url'">{{ t('自动刷新源订阅') }}<select v-model="settings.interval_minutes"><option :value="0">{{ t('关闭 · 手动刷新') }}</option><option :value="30">{{ t('每 30 分钟') }}</option><option :value="60">{{ t('每小时') }}</option><option :value="360">{{ t('每 6 小时') }}</option><option :value="720">{{ t('每 12 小时') }}</option><option :value="1440">{{ t('每天') }}</option></select></label><p v-else class="subtle">{{ t('本地 YAML 文件通过“更新文件”按钮手动替换。') }}</p><div class="settings-footer"><p class="subtle">{{ t('自动刷新仅在本地服务运行期间执行。') }}</p><button class="button primary small" type="submit" :disabled="busy">{{ t('保存设置') }}</button></div></form>
              <section class="panel settings-panel"><h3>{{ t('原始配置中的其他字段') }}<span class="type-tag">{{ t('只读') }}</span></h3><p class="subtle">{{ t('DNS、TUN、rule-providers 等字段在生成时保留其配置值。') }}</p><button class="text-button" @click="sourceExpanded=!sourceExpanded">{{ sourceExpanded?t("收起字段"):t("展开查看字段") }}<ChevronRight :size="15" :class="{rotated:sourceExpanded}"/></button><pre v-if="sourceExpanded" class="json-view">{{ JSON.stringify(otherFields,null,2) }}</pre></section>
              <section class="panel settings-panel"><h3>{{ t('本机订阅地址') }}</h3><div class="subscription-url"><code>{{ localOutputUrl }}</code><button class="icon-button" :aria-label="t('复制本机订阅地址')" @click="copy(localOutputUrl,t('本机订阅地址已复制'))"><Clipboard :size="16"/></button></div><p class="subtle">{{ t('同一台电脑使用；重新生成后需要在客户端更新地址。') }}</p><button class="button small" :disabled="busy" @click="rotateToken"><RefreshCw :size="14"/>{{ t('重新生成地址') }}</button></section>
              <section class="panel settings-panel danger-zone"><div><h3>{{ t('删除订阅') }}</h3><p class="subtle">{{ t('删除配置、修改记录和历史版本，订阅地址随之失效。') }}</p></div><button class="button danger small" :disabled="busy" @click="deleteSub"><Trash2 :size="14"/>{{ t('删除订阅') }}</button></section>
            </template>
          </section>

          <aside class="inspector">
            <section class="publish-card"><div class="eyebrow">SUBSCRIPTION LINK</div><div class="publish-symbol"><Network :size="25"/><span class="live-dot"></span></div><h3>{{ t('你的专属订阅') }}</h3><p>{{ t('在 Clash / Mihomo 客户端中导入此地址，即可获取已保存的配置。') }}</p><div class="link-mode"><button :class="{active:linkMode==='local'}" @click="linkMode='local'">{{ t('本机') }}</button><button :class="{active:linkMode==='lan'}" :disabled="!lanOutputUrl" @click="linkMode='lan'">{{ t('局域网') }}</button></div><div class="url-preview"><Link2 :size="14"/><code>{{ outputUrl }}</code></div><button class="button primary full-width" :disabled="!outputUrl" @click="copy(outputUrl,linkMode==='lan'?t('局域网订阅地址已复制'):t('本地订阅地址已复制'))"><Clipboard :size="15"/>{{ linkMode==='lan'?t("复制局域网订阅"):t("复制订阅地址") }}</button><button v-if="!network?.running" class="text-button lan-enable-link" @click="tab='settings'">{{ t('启用局域网共享') }}<ArrowUpRight :size="13"/></button><span class="publish-footnote">{{ dirty?t("未保存的修改还未发布到此地址。"):!current.enabled?t("当前订阅已停用，可在设置中启用。"):linkMode==='lan'?t("同一局域网可用 · 服务需保持运行"):t("当前电脑使用 · 服务需保持运行") }}</span></section>
            <section class="validation-card"><div class="aside-heading"><h4>{{ t('配置检查') }}</h4><Loader2 v-if="checking" :size="15" class="spin"/><span v-else class="live-dot" :class="{red:preview?.errors.length||error}"></span></div><div v-if="checking" class="validation-result"><Loader2 :size="18" class="spin"/><span>{{ t('正在检查修改…') }}</span></div><div v-else-if="!preview?.errors.length && !error" class="validation-result"><CheckCircle2 :size="18"/><span>{{ t('结构与引用检查通过') }}</span></div><div v-else class="validation-result failed"><AlertTriangle :size="18"/><span>{{ t('需要处理') }}{{ preview?.errors.length||1 }}{{ t('个问题') }}</span></div><ul v-if="preview?.errors.length" class="validation-errors"><li v-for="message in preview.errors" :key="message">{{ translateMessage(message) }}</li></ul><details v-if="preview?.warnings.length" class="validation-warnings"><summary>{{ preview.warnings.length }}{{ t('条提醒') }}</summary><ul><li v-for="message in preview.warnings" :key="message">{{ translateMessage(message) }}</li></ul></details><p class="validation-disclaimer">{{ t('基础校验通过后，仍需由客户端内核验证实际兼容性。') }}</p></section>
            <section class="source-card"><h4>{{ t('源订阅') }}</h4><dl><div><dt>{{ t('来源') }}</dt><dd>{{ current.source_type==='demo'?t("演示 YAML"):current.source_host }}</dd></div><div><dt>{{ t('最近刷新') }}</dt><dd>{{ fmtDate(current.refreshed_at) }}</dd></div><div><dt>{{ t('刷新方式') }}</dt><dd>{{ current.interval_minutes && current.source_type==='url'?t("每 {0} 分钟",[current.interval_minutes]):t("手动刷新") }}</dd></div><div><dt>{{ t('配置版本') }}</dt><dd>revision {{ current.revision }}</dd></div></dl></section>
            <div v-if="dirty" class="draft-note"><span class="changed-dot"></span><div><strong>{{ t('有未保存的修改') }}</strong><p>{{ t('保存后将更新本地订阅。') }}</p><button class="text-button" @click="discard"><RotateCcw :size="13"/>{{ t('撤销未保存修改') }}</button></div></div>
          </aside>
        </div>
        <footer class="page-footer"><span>Clash Studio <span> / </span>{{ t('本地订阅工作台') }}</span><span>{{ t('你的配置，你的规则。') }}</span></footer>
      </main>
    </div>

    <div v-if="modal" class="modal-backdrop" @click.self="!busy && (modal=false)" @keydown.esc="!busy && (modal=false)"><section class="import-modal" role="dialog" aria-modal="true" aria-labelledby="import-title"><button class="modal-close icon-button" :disabled="busy" :aria-label="t('关闭导入窗口')" @click="modal=false"><X :size="20"/></button><span class="modal-icon"><FileUp :size="25"/></span><div class="eyebrow">ADD A SUBSCRIPTION</div><h2 id="import-title">{{ t('导入订阅') }}</h2><p class="subtle">{{ t('从现有配置开始，建立自己的分流方案。') }}</p><div class="import-tabs"><button :class="{active:importType==='url'}" @click="importType='url'"><Link2 :size="16"/>{{ t('订阅链接') }}</button><button :class="{active:importType==='file'}" @click="importType='file'"><FileCode2 :size="16"/>{{ t('YAML 文件') }}</button></div><form @submit.prevent="createSubscription()"><label>{{ t('订阅名称') }}<input ref="importNameInput" v-model="importTitle" :placeholder="t('例如：我的日常订阅')" maxlength="100" required/></label><label v-if="importType==='url'">{{ t('订阅链接') }}<input v-model="importUrl" type="url" placeholder="https://example.com/subscribe?token=…" required autocomplete="off" spellcheck="false"/><span class="field-help">{{ t('需要返回 Clash / Mihomo YAML 格式。') }}</span></label><div v-else><label class="file-drop"><FileUp :size="25"/><strong>{{ importFile||t("选择 YAML 配置文件") }}</strong><span>{{ t('支持 .yaml / .yml，最大 8 MB') }}</span><input type="file" accept=".yaml,.yml,text/yaml,text/plain" :aria-label="t('选择 YAML 文件')" @change="readImport"/></label><label class="paste-label">{{ t('或粘贴 YAML 内容') }}<textarea v-model="importYaml" placeholder="proxies:&#10;  - name: ..." rows="5" :aria-label="t('粘贴 YAML 内容')" :required="importType==='file'"></textarea></label></div><div v-if="importError" class="notice error"><AlertTriangle :size="17"/>{{ translateMessage(importError) }}</div><div class="modal-footer"><span><ShieldCheck :size="14"/>{{ t('本地保存') }}</span><button type="submit" class="button primary" :disabled="busy"><Loader2 v-if="busy" :size="16" class="spin"/><Plus v-else :size="16"/>{{ busy?t("正在导入…"):t("导入并编辑") }}</button></div></form></section></div>
    <div v-if="aiDialog" class="modal-backdrop" @click.self="!busy && (aiDialog=false)" @keydown.esc="!busy && (aiDialog=false)"><section class="import-modal ai-modal" role="dialog" aria-modal="true" aria-labelledby="ai-title"><button class="modal-close icon-button" :disabled="busy" :aria-label="t('关闭 AI 分流窗口')" @click="aiDialog=false"><X :size="20"/></button><span class="modal-icon"><Waypoints :size="25"/></span><div class="eyebrow">AI ROUTING PRESET</div><h2 id="ai-title">{{ aiActive?t("管理 AI 分流"):t("一键创建 AI 分流") }}</h2><p class="subtle">{{ aiCatalogue?.service_count }}{{ t('组海外 AI 服务 ·') }}{{ aiCatalogue?.rule_count }}{{ t('条专用域名规则 · 含 Muse AI') }}</p><form @submit.prevent="applyAI" class="ai-preset-form"><label>{{ t('AI 分流出口') }}<select ref="aiOutletInput" v-model="aiOutlet" :aria-label="t('AI 分流出口')" :disabled="busy" required autofocus><option v-for="p in aiOutlets" :key="p.value" :value="p.value">{{ p.label }}</option></select><span class="field-help">{{ t('创建或复用 AI 手动选择组，以所选节点 / 代理组作为出口；实际可用性取决于节点和服务限制。') }}</span></label><div v-if="!aiOutlets.length" class="notice error">{{ t('当前没有可用出口，请先添加代理节点或代理组。') }}</div><div class="ai-plan"><div><CheckCircle2 :size="15"/><span>{{ t('AI 规则排在普通分流前，同域名规则统一指向 AI 组') }}</span></div><div><CheckCircle2 :size="15"/><span>{{ t('刷新源订阅后继续应用，重复创建不增加重复组和规则') }}</span></div><div><ShieldCheck :size="15"/><span>{{ t('国内 AI 服务沿用原分流，共享登录 / 支付 / 通用 CDN 沿用原规则') }}</span></div></div><button type="button" class="text-button ai-details-toggle" @click="aiDetails=!aiDetails">{{ aiDetails?t("收起完整规则清单"):t("查看完整规则清单") }}<ChevronRight :size="15" :class="{rotated:aiDetails}"/></button><div v-if="aiDetails" class="ai-catalogue"><div v-for="service in aiCatalogue?.services" :key="service.name" class="ai-service"><strong>{{ service.name }}</strong><div v-for="rule in service.rules" :key="rule.type+rule.domain"><span>{{ rule.type==='DOMAIN'?t("精确"):t("后缀") }}</span><code>{{ rule.domain }}</code></div></div><p class="subtle">{{ t('规则版本') }}{{ aiCatalogue?.version }}{{ t('· 内置清单，无需额外下载 GeoSite 或远程规则集。') }}</p></div><div v-if="aiError" class="notice error"><AlertTriangle :size="17"/>{{ translateMessage(aiError) }}</div><div class="modal-footer"><span><FileCode2 :size="14"/>{{ t('先生成草稿，保存后发布') }}</span><button type="submit" class="button primary" :disabled="busy||!aiOutlet"><Loader2 v-if="busy" :size="16" class="spin"/><Waypoints v-else :size="16"/>{{ busy?t("正在生成…"):t("应用到草稿") }}</button></div></form></section></div>
    <Transition name="toast"><div v-if="toast" role="status" class="toast-message" :class="{error:toastError}"><AlertTriangle v-if="toastError" :size="18"/><CheckCircle2 v-else :size="18"/><span>{{ translateMessage(toast) }}</span><button :aria-label="t('关闭提示')" @click="toast=''"><X :size="14"/></button></div></Transition>
  </div>
</template>
