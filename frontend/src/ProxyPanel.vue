<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, onUnmounted, ref, watch } from 'vue'
import { Activity, Check, ChevronDown, Gauge, Loader2, Play, Square } from 'lucide-vue-next'
import { api } from './api'

type Proxy={name:string;type:string;all?:string[];now?:string;history?:{delay:number}[]}
type Result={name:string;endpoint:string;status:'ok'|'unreachable';delay_ms:number|null;checked_at:string}
type Entry={status:'queued'|'testing'|'ok'|'unreachable'|'cancelled';delay_ms:number|null;checked_at?:string}
const props=defineProps<{proxies:Record<string,Proxy>;busy:boolean;sessionKey:string;profileId:string;profileRevision:number;workspaceRevision:number;live:boolean;hasProviders:boolean}>()
const emit=defineEmits<{select:[group:Proxy,name:string];notice:[message:string,error?:boolean];refresh:[]}>()
const collapsed=ref<Record<string,boolean>>({})
try{collapsed.value=JSON.parse(localStorage.getItem('clash-group-folds')||'{}')}catch{}
function fold(name:string){collapsed.value[name]=!collapsed.value[name];localStorage.setItem('clash-group-folds',JSON.stringify(collapsed.value))}
function foldAll(value:boolean){groups.value.forEach(group=>collapsed.value[group.name]=value);localStorage.setItem('clash-group-folds',JSON.stringify(collapsed.value))}
const endpoint=ref('cloudflare'), results=ref<Record<string,Entry>>({}), testing=ref(false), completed=ref(0), total=ref(0), inFlight=ref(0)
let sequence=0
const groups=computed(()=>Object.values(props.proxies).filter(p=>p.all&&p.name!=='GLOBAL'))
const isNode=(p:Proxy|undefined)=>!!p&&!p.all&&!['direct','reject','rejectdrop','pass','dns'].includes(p.type.toLowerCase())
function leaves(names:string[],seen=new Set<string>()):string[]{
  const found:string[]=[]
  for(const name of names){if(seen.has(name))continue;seen.add(name);const proxy=props.proxies[name];if(proxy?.all)found.push(...leaves(proxy.all,seen));else if(isNode(proxy))found.push(name)}
  return found
}
const allNodes=computed(()=>Object.values(props.proxies).filter(isNode).map(p=>p.name))
function cancel(){++sequence;testing.value=false;for(const entry of Object.values(results.value)){if(entry.status==='queued'||entry.status==='testing')entry.status='cancelled'}}
async function measure(names:string[]){
  if(testing.value||inFlight.value||props.busy)return
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
        results.value[name]={status:'unreachable',delay_ms:null}
        if((error as Error).message.includes('内核')||(error as Error).message.includes('配置')){results.value[name]={status:'cancelled',delay_ms:null};cancel();emit('notice',(error as Error).message,true);return}
      }finally{inFlight.value--}
      completed.value++
    }
  }
  await Promise.all(Array.from({length:Math.min(4,unique.length)},worker))
  if(run===sequence){testing.value=false;const passed=unique.filter(name=>results.value[name]?.status==='ok').length;emit('notice',t("测速完成：{0} 个可达，{1} 个超时或不可达", [passed, unique.length-passed]))}
}
async function loadProviders(){if(testing.value||inFlight.value)return;inFlight.value++;try{await api('/api/client/probe/prepare','POST',{profile_id:props.profileId});emit('refresh')}catch(error){emit('notice',(error as Error).message,true)}finally{inFlight.value--}}
function label(name:string){const value=results.value[name];if(!value)return t("测速");return value.status==='queued'?t("等待"):value.status==='testing'?t("测速中"):value.status==='ok'?`${value.delay_ms} ms`:value.status==='cancelled'?t("已取消"):t("超时 / 不可达")}
function color(name:string){const value=results.value[name];if(value?.status==='unreachable')return 'unreachable';if(value?.status!=='ok')return '';return (value.delay_ms||0)<200?'fast':(value.delay_ms||0)<600?'medium':'slow'}
watch(()=>props.sessionKey,()=>{cancel();results.value={};completed.value=0;total.value=0})
watch(endpoint,()=>{results.value={};completed.value=0;total.value=0})
onUnmounted(cancel)
</script>

<template>
  <section class="desk-card delay-toolbar">
    <div><span class="desk-eyebrow">PROXY BENCHMARK</span><h2><Gauge :size="18"/>{{ t("节点延迟测速") }}</h2><p>{{ t("HTTP 延迟 · 单节点超时 5 秒 · 最多 4 个并发") }}</p></div>
    <div class="delay-controls"><label>{{ t("检测地址") }}<select v-model="endpoint" :disabled="testing||inFlight>0"><option value="cloudflare">Cloudflare · HTTPS 204</option><option value="gstatic">Google · HTTPS 204</option></select></label><button v-if="!testing" class="desk-btn primary" :disabled="props.busy||inFlight>0||!allNodes.length" @click="measure(allNodes)"><Play :size="13"/>{{ inFlight>0?t("等待请求结束"):t("全部测速") }}</button><button v-else class="desk-btn" @click="cancel"><Square :size="12"/>{{ t("取消 {0}/{1}", [completed, total]) }}</button></div>
    <div v-if="total" class="delay-progress"><span :style="{width:`${completed/total*100}%`}"></span></div>
  </section>
  <p class="page-caption delay-caption">{{ t("{0}测速为 HTTP 延迟，受当前网络路径影响。独立测速内核空闲两分钟自动关闭。", [props.live?t("当前节点来自运行配置。"):t("当前节点来自所选订阅的已发布配置；测速按需使用独立内核，不开启系统代理或 TUN。")]) }}</p>
  <div class="group-fold-toolbar"><span>{{ t("{0} 个策略组", [groups.length]) }}</span><button class="desk-text-btn" @click="foldAll(false)">{{ t("全部展开") }}</button><button class="desk-text-btn" @click="foldAll(true)">{{ t("全部折叠") }}</button><button v-if="props.hasProviders&&!props.live" class="desk-btn" :disabled="testing||inFlight>0||props.busy" @click="loadProviders">{{ t("加载 / 刷新 Provider 节点") }}</button></div>
  <section v-for="group in groups" :key="group.name" class="desk-card proxy-group">
    <div class="section-head"><button class="group-fold-toggle" :aria-expanded="!collapsed[group.name]" @click="fold(group.name)"><ChevronDown :size="17" :class="{folded:collapsed[group.name]}"/><span><strong>{{ group.name }}</strong><small>{{ group.type }} · {{ props.live?t("当前 ")+(group.now||t("自动策略")):t("未应用到主内核") }}</small></span></button><div class="group-actions"><span class="small-badge">{{ t("{0} 个成员", [group.all?.length]) }}</span><button class="desk-btn" :disabled="testing||inFlight>0||props.busy||!leaves(group.all||[]).length" @click="measure(leaves(group.all||[]))"><Activity :size="13"/>{{ t("整组测速") }}</button></div></div>
    <div v-show="!collapsed[group.name]" class="node-grid"><article v-for="name in group.all" :key="name" :class="['proxy-node-card',{picked:group.now===name}]">
      <button class="node-choice" :disabled="!props.live||props.busy||group.type!=='Selector'" @click="emit('select',group,name)"><span class="node-dot"></span><span><strong>{{ name }}</strong><small>{{ props.proxies[name]?.type||t("未知类型") }}</small></span><Check v-if="group.now===name" :size="15"/></button>
      <div class="node-measure-row"><template v-if="isNode(props.proxies[name])"><span v-if="results[name]?.checked_at" class="delay-time">{{ new Date(results[name]!.checked_at!).toLocaleTimeString('zh-CN',{hour12:false}) }}</span><span v-else class="delay-time">{{ t("HTTP 延迟") }}</span><button :class="['node-delay',color(name)]" :disabled="testing||inFlight>0||props.busy" :aria-label="t('测速 {0}', [name])" @click="measure([name])"><Loader2 v-if="results[name]?.status==='testing'" class="rotate" :size="11"/><Gauge v-else :size="11"/>{{ label(name) }}</button></template><button v-else-if="props.proxies[name]?.all" class="desk-text-btn" :disabled="testing||inFlight>0||props.busy" @click="measure(leaves([name]))"><Gauge :size="11"/>{{ t("测速组内节点") }}</button><span v-else class="delay-time">{{ t("内置出口") }}</span></div>
    </article></div>
  </section>
  <div v-if="!groups.length" class="desk-card desk-empty"><Gauge :size="32"/><p>{{ t("当前运行配置没有代理组。") }}</p></div>
</template>
