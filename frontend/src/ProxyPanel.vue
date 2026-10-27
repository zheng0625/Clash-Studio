<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Activity, Check, ChevronDown, Gauge, Loader2, Play, Search, Square, Zap } from 'lucide-vue-next'
import { api, ApiError } from './api'

type Proxy={name:string;type:string;all?:string[];now?:string;history?:{delay:number}[]}
type Result={name:string;endpoint:string;status:'ok'|'unreachable';delay_ms:number|null;checked_at:string}
type Entry={status:'queued'|'testing'|'ok'|'unreachable'|'failed'|'cancelled';delay_ms:number|null;checked_at?:string}
const props=defineProps<{proxies:Record<string,Proxy>;busy:boolean;pending:Record<string,string>;sessionKey:string;profileId:string;profileRevision:number;workspaceRevision:number;live:boolean;hasProviders:boolean;benchmarkAvailable?:boolean;viewState?:{search:string;availableOnly:boolean;sort:string;view:string;benchmarkOpen:boolean;endpoint:string}}>()
const emit=defineEmits<{select:[group:Proxy,name:string];notice:[message:string,error?:boolean];refresh:[];ready:[];viewState:[value:{search:string;availableOnly:boolean;sort:string;view:string;benchmarkOpen:boolean;endpoint:string}]}>()
const collapsed=ref<Record<string,boolean>>({})
try{collapsed.value=JSON.parse(localStorage.getItem('clash-group-folds')||'{}')}catch{}
function fold(name:string){collapsed.value[name]=!collapsed.value[name];localStorage.setItem('clash-group-folds',JSON.stringify(collapsed.value))}
function foldAll(value:boolean){groups.value.forEach(group=>collapsed.value[group.name]=value);localStorage.setItem('clash-group-folds',JSON.stringify(collapsed.value))}
const endpoint=ref(props.viewState?.endpoint||'cloudflare'), results=ref<Record<string,Entry>>({}), testing=ref(false), completed=ref(0), total=ref(0), inFlight=ref(0)
let sequence=0
const groups=computed(()=>Object.values(props.proxies).filter(p=>p.all&&(props.live||p.name!=='GLOBAL')))
const search=ref(props.viewState?.search||''), availableOnly=ref(props.viewState?.availableOnly||false), sort=ref(props.viewState?.sort||'original'), view=ref(props.viewState?.view||'cards'), benchmarkOpen=ref(props.viewState?.benchmarkOpen||false)
watch([search,availableOnly,sort,view,benchmarkOpen,endpoint],()=>emit('viewState',{search:search.value,availableOnly:availableOnly.value,sort:sort.value,view:view.value,benchmarkOpen:benchmarkOpen.value,endpoint:endpoint.value}),{flush:'sync'})
onMounted(async()=>{await nextTick();emit('ready')})
function members(group:Proxy){
  const names=(group.all||[]).filter(name=>name.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase())&&(!availableOnly.value||results.value[name]?.status==='ok'))
  if(sort.value==='delay')return names.map((name,index)=>({name,index,delay:results.value[name]?.status==='ok'?results.value[name]!.delay_ms??Infinity:Infinity})).sort((a,b)=>a.delay-b.delay||a.index-b.index).map(item=>item.name)
  return names
}
const visibleGroups=computed(()=>groups.value.map(group=>({group,names:members(group)})).filter(item=>item.names.length))
function clearFilters(){search.value='';availableOnly.value=false}
async function locateCurrent(){
  clearFilters()
  const group=groups.value.find(group=>group.now&&group.all?.includes(group.now))
  if(!group){emit('notice',t('暂无当前节点'));return}
  collapsed.value[group.name]=false
  await nextTick()
  document.querySelector<HTMLElement>('.proxy-node-card.picked')?.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'})
}
async function toggleBenchmark(){
  if(testing.value){cancel();return}
  benchmarkOpen.value=!benchmarkOpen.value
  await nextTick()
  if(benchmarkOpen.value)document.querySelector('.delay-toolbar')?.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'})
}
watch(()=>props.profileId,()=>{const state=props.viewState;search.value=state?.search||'';availableOnly.value=state?.availableOnly||false;sort.value=state?.sort||'original';view.value=state?.view||'cards';benchmarkOpen.value=false;endpoint.value=state?.endpoint||'cloudflare'})
const isNode=(p:Proxy|undefined)=>!!p&&!p.all&&!['direct','reject','rejectdrop','pass','dns'].includes(p.type.toLowerCase())
function leaves(names:string[],seen=new Set<string>()):string[]{
  const found:string[]=[]
  for(const name of names){if(seen.has(name))continue;seen.add(name);const proxy=props.proxies[name];if(proxy?.all)found.push(...leaves(proxy.all,seen));else if(isNode(proxy))found.push(name)}
  return found
}
const allNodes=computed(()=>Object.values(props.proxies).filter(isNode).map(p=>p.name))
function cancel(){++sequence;testing.value=false;for(const entry of Object.values(results.value)){if(entry.status==='queued'||entry.status==='testing')entry.status='cancelled'}}
let resultScope={profile:props.profileId,endpoint:endpoint.value},scopeReady=false
let saveTimer:ReturnType<typeof setTimeout>|undefined
function cacheKey(scope:{profile:string;endpoint:string}){return 'clash-node-delay-v2:'+scope.profile+':'+scope.endpoint}
function persistResults(){if(!scopeReady)return;try{localStorage.setItem(cacheKey(resultScope),JSON.stringify(Object.fromEntries(Object.entries(results.value).filter(([,entry])=>['ok','unreachable','failed'].includes(entry.status)))))}catch{}}
function restoreResults(){
 persistResults();clearTimeout(saveTimer);cancel();resultScope={profile:props.profileId,endpoint:endpoint.value};scopeReady=true;results.value={}
 try{const saved=JSON.parse(localStorage.getItem(cacheKey(resultScope))||'{}');for(const [name,value] of Object.entries(saved)){const entry=value as Entry;if(entry&&['ok','unreachable','failed'].includes(entry.status)&&(entry.delay_ms===null||Number.isFinite(entry.delay_ms)))results.value[name]=entry}}catch{}
}
watch(()=>props.profileId,restoreResults,{immediate:true})
watch(results,()=>{clearTimeout(saveTimer);saveTimer=setTimeout(persistResults,250)},{deep:true})
async function measure(names:string[]){
  if(props.benchmarkAvailable===false||testing.value||inFlight.value||props.busy)return
  const unique=[...new Set(names)].filter(n=>isNode(props.proxies[n]))
  if(!unique.length){emit('notice',t("该范围内没有可测速的实际代理节点"),true);return}
  const run=++sequence;testing.value=true;completed.value=0;total.value=unique.length
  unique.forEach(name=>results.value[name]={status:'queued',delay_ms:null})
  if(!props.live){
    inFlight.value++
    try{await api('/api/client/probe/prepare','POST',{profile_id:props.profileId})}catch(error){if(run===sequence){cancel();emit('notice',(error as Error).message,true)}return}finally{inFlight.value--}
    if(run!==sequence)return
  }
  let cursor=0
  async function worker(){
    while(run===sequence&&cursor<unique.length){
      const name=unique[cursor++]!;results.value[name]={status:'testing',delay_ms:null}
      inFlight.value++
      try{
        const value=await api<Result>('/api/client/runtime/delay','POST',{name,endpoint:endpoint.value,timeout_ms:5000,profile_id:props.profileId,profile_revision:props.profileRevision,workspace_revision:props.workspaceRevision})
        if(run!==sequence)return
        results.value[name]={status:value.status,delay_ms:value.delay_ms,checked_at:value.checked_at}
      }catch(error){
        if(run!==sequence)return
        results.value[name]={status:'failed',delay_ms:null}
        if(error instanceof ApiError&&['CONFLICT','OPERATION_CANCELLED','APPLY_CANCELLED','UNAVAILABLE'].includes(error.code)){results.value[name]={status:'cancelled',delay_ms:null};cancel();emit('notice',(error as Error).message,true);return}
      }finally{inFlight.value--}
      completed.value++
    }
  }
  await Promise.all(Array.from({length:Math.min(4,unique.length)},worker))
  if(run===sequence){testing.value=false;const passed=unique.filter(name=>results.value[name]?.status==='ok').length;emit('notice',t("测速完成：{0} 个可达，{1} 个未成功", [passed, unique.length-passed]))}
}
async function loadProviders(){if(testing.value||inFlight.value)return;inFlight.value++;try{await api('/api/client/probe/prepare','POST',{profile_id:props.profileId});emit('refresh')}catch(error){emit('notice',(error as Error).message,true)}finally{inFlight.value--}}
function label(name:string){const value=results.value[name];if(!value)return t("未测速");return value.status==='queued'?t("等待"):value.status==='testing'?t("测速中"):value.status==='ok'?`${value.delay_ms} ms`:value.status==='cancelled'?t("已取消"):value.status==='failed'?t('请求失败'):t("超时 / 不可达")}
function color(name:string){const value=results.value[name];if(value?.status==='unreachable'||value?.status==='failed')return 'unreachable';if(value?.status!=='ok')return '';return (value.delay_ms||0)<200?'fast':(value.delay_ms||0)<600?'medium':'slow'}
watch(()=>props.sessionKey,()=>{cancel();completed.value=0;total.value=0})
watch(endpoint,()=>{restoreResults();completed.value=0;total.value=0})
onUnmounted(()=>{persistResults();clearTimeout(saveTimer);cancel()})
</script>

<template>
  <div class="proxy-tools">
    <label class="desk-search node-search"><Search :size="16"/><input v-model="search" type="search" :placeholder="t('搜索节点名称')" :aria-label="t('搜索节点名称')"/></label>
    <select v-model="sort" :aria-label="t('节点排序')"><option value="original">{{ t('原始顺序') }}</option><option value="delay">{{ t('延迟优先') }}</option></select>
    <label class="available-filter"><input v-model="availableOnly" type="checkbox"/>{{ t('仅看已测可用') }}</label>
    <button class="desk-btn" @click="locateCurrent">{{ t('定位当前') }}</button>
    <button class="desk-btn node-view-toggle" :aria-pressed="view==='compact'" @click="view=view==='compact'?'cards':'compact'">{{ view==='compact'?t('卡片视图'):t('紧凑视图') }}</button>
  </div>
  <section v-if="props.benchmarkAvailable!==false" :class="['desk-card delay-toolbar',{'benchmark-open':benchmarkOpen}]">
    <div><span class="desk-eyebrow">PROXY BENCHMARK</span><h2><Gauge :size="18"/>{{ t("节点延迟测速") }}</h2><p>{{ t("HTTP 延迟 · 单节点超时 5 秒 · 最多 4 个并发") }}</p></div>
    <div class="delay-controls"><label>{{ t("检测地址") }}<select v-model="endpoint" :aria-label="t('检测地址')" :disabled="testing||inFlight>0"><option value="cloudflare">Cloudflare · HTTPS 204</option><option value="gstatic">Google · HTTPS 204</option></select></label><button v-if="!testing" class="desk-btn primary" :disabled="props.busy||inFlight>0||!allNodes.length" @click="measure(allNodes)"><Play :size="13"/>{{ inFlight>0?t("等待请求结束"):t("全部测速") }}</button><button v-else class="desk-btn" @click="cancel"><Square :size="12"/>{{ t("取消 {0}/{1}", [completed, total]) }}</button></div>
    <div v-if="total" class="delay-progress"><span :style="{width:`${completed/total*100}%`}"></span></div>
  </section>
  <p v-if="props.benchmarkAvailable===false" class="page-caption">{{ t("节点选择会保存在手机中；代理内核接入后生效，测速暂未开放。") }}</p>
  <div class="group-fold-toolbar"><span>{{ t("{0} 个策略组", [groups.length]) }}</span><button class="desk-text-btn" @click="foldAll(false)">{{ t("全部展开") }}</button><button class="desk-text-btn" @click="foldAll(true)">{{ t("全部折叠") }}</button><button v-if="props.hasProviders&&!props.live" class="desk-btn" :disabled="props.benchmarkAvailable===false||testing||inFlight>0||props.busy" @click="loadProviders">{{ t("加载 / 刷新 Provider 节点") }}</button></div>
  <section v-for="{group,names} in visibleGroups" :key="group.name" :class="['desk-card proxy-group',{'compact-nodes':view==='compact'}]">
    <div class="section-head"><button class="group-fold-toggle" :aria-expanded="!collapsed[group.name]" @click="fold(group.name)"><ChevronDown :size="17" :class="{folded:collapsed[group.name]}"/><span><strong>{{ group.name }}</strong><small>{{ group.type }} · {{ props.live?t("当前 ")+(group.now||t("自动策略")):t("下次启动使用 ")+(group.now||t("自动策略")) }}</small></span></button><div class="group-actions"><span class="small-badge">{{ t("{0} 个成员", [group.all?.length]) }}</span><button class="desk-btn" :disabled="props.benchmarkAvailable===false||testing||inFlight>0||props.busy||!leaves(group.all||[]).length" @click="measure(leaves(group.all||[]))"><Activity :size="13"/>{{ t("整组测速") }}</button></div></div>
    <div v-show="!collapsed[group.name]" class="node-grid"><article v-for="name in names" :key="name" v-memo="[group.now===name,props.pending[group.name]===name,group.type,props.proxies[name]?.type,!!props.proxies[name]?.all,results[name]?.status,results[name]?.delay_ms,results[name]?.checked_at,testing,inFlight>0,props.busy,locale]" :class="['proxy-node-card',{picked:group.now===name}]">
      <button class="node-choice" :title="name" :aria-pressed="group.now===name" :disabled="props.busy||group.type!=='Selector'" @click="emit('select',props.proxies[group.name]!,name)"><span class="node-dot"></span><span><strong>{{ name }}</strong><small>{{ props.proxies[name]?.type||t("未知类型") }}</small></span><Loader2 v-if="props.pending[group.name]===name" class="rotate" :size="15"/><Check v-else-if="group.now===name" :size="15"/></button>
      <div class="node-measure-row"><template v-if="isNode(props.proxies[name])"><span v-if="results[name]?.checked_at" class="delay-time">{{ new Date(results[name]!.checked_at!).toLocaleTimeString('zh-CN',{hour12:false}) }}</span><span v-else class="delay-time">{{ t("HTTP 延迟") }}</span><button :class="['node-delay',color(name)]" :disabled="props.benchmarkAvailable===false||testing||inFlight>0||props.busy" :aria-label="t('测速 {0}', [name])" @click="measure([name])"><Loader2 v-if="results[name]?.status==='testing'" class="rotate" :size="11"/><Gauge v-else :size="11"/>{{ label(name) }}</button></template><button v-else-if="props.proxies[name]?.all" class="desk-text-btn" :disabled="props.benchmarkAvailable===false||testing||inFlight>0||props.busy" @click="measure(leaves([name]))"><Gauge :size="11"/>{{ t("测速组内节点") }}</button><span v-else class="delay-time">{{ t("内置出口") }}</span></div>
    </article></div>
  </section>
  <div v-if="groups.length&&!visibleGroups.length" class="desk-card desk-empty"><Search :size="24"/><p>{{ t('没有匹配的节点；仅看可用只包含已测速成功的节点。') }}</p><button class="desk-btn" @click="clearFilters">{{ t('清除筛选') }}</button></div>
  <div v-if="!groups.length" class="desk-card desk-empty"><Gauge :size="32"/><p>{{ t("当前运行配置没有代理组。") }}</p></div>
  <details v-if="props.benchmarkAvailable!==false" class="benchmark-help"><summary>{{ props.live?t('正在查看运行配置'):t('正在查看所选订阅 · 下次启动生效') }} · {{ t('测速说明') }}</summary><p class="page-caption delay-caption">{{ t("{0}测速为 HTTP 延迟，受当前网络路径影响。独立测速内核空闲两分钟自动关闭。", [props.live?t("当前节点来自运行配置。"):t("当前节点来自所选订阅的已发布配置；测速按需使用独立内核，不开启系统代理或 TUN。")]) }}</p></details>
  <!-- Keep fixed controls outside the transformed page stage during transitions. -->
  <Teleport to=".desk" defer><button v-if="props.benchmarkAvailable!==false" type="button" class="delay-fab" :aria-expanded="benchmarkOpen" :aria-label="testing?t('取消测速'):t('测速选项')" @click="toggleBenchmark"><Loader2 v-if="testing" class="rotate" :size="20"/><Zap v-else :size="20"/><span>{{ testing?t('取消测速'):t('测速') }}</span><span v-if="testing" class="delay-fab-count">{{ completed }}/{{ total }}</span></button></Teleport>
</template>
