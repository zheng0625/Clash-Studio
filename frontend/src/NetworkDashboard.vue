<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Activity, ArrowDownLeft, ArrowUpRight, Check, Copy, RefreshCw } from 'lucide-vue-next'
import { api } from './api'

const props=defineProps<{running:boolean;configKey:string;active?:boolean;trafficTarget?:string;egressTarget?:string}>()
const emit=defineEmits<{speed:[value:{upload:number|null;download:number|null;running:boolean}];connections:[]}>()
type Counter={sampled_at?:number|string;stale?:boolean;running:boolean;session:string;upload:number;download:number;connections:number}
type Lookup={status:'ok'|'partial'|'unavailable';ip:string;family:string;country:string;country_code?:string;region:string;city:string;is_residential?:boolean|null;is_broadcast?:boolean|null;isp:string;asn:string;provider:string;route:'system'|'proxy';route_label:string;profile:string;checked_at:string;elapsed_ms:number;cached:boolean;message:string}
type Sample={at:number;upload:number;download:number}
const route=computed<'system'|'proxy'>(()=>props.running?'proxy':'system'), checking=ref(false), lookup=ref<Lookup|null>(null), ipError=ref(''), copied=ref(false)
const counter=ref<Counter>({running:false,session:'',upload:0,download:0,connections:0})
const upload=ref<number|null>(null), download=ref<number|null>(null), samples=ref<Sample[]>([]), trafficError=ref('')
let baseline:{at:number;value:Counter}|null=null, timer:ReturnType<typeof setTimeout>|undefined, copyTimer:ReturnType<typeof setTimeout>|undefined
let disposed=false, pending=false, lookupSequence=0
const country=computed(()=>{const code=lookup.value?.country_code;if(code&&/^[A-Z]{2}$/i.test(code)){try{return new Intl.DisplayNames([locale.value],{type:'region'}).of(code.toUpperCase())||lookup.value?.country}catch{}}return lookup.value?.country})
const location=computed(()=>[...new Set([country.value,lookup.value?.region,lookup.value?.city].filter(Boolean))].join(' · '))
const ipProperties=computed(()=>{
  const value=lookup.value,tags:string[]=[]
  if(typeof value?.is_residential==='boolean')tags.push(t(value.is_residential?'住宅 IP':'机房 IP'))
  if(typeof value?.is_broadcast==='boolean')tags.push(t(value.is_broadcast?'广播 IP':'原生 IP'))
  return tags
})
const chartMax=computed(()=>Math.max(1024,...samples.value.flatMap(p=>[p.upload,p.download])))
const end=computed(()=>samples.value.at(-1)?.at??performance.now())
function format(n:number|null, rate=false){if(n===null)return '—';const units=['B','KB','MB','GB','TB'];const index=n>0?Math.max(0,Math.min(4,Math.floor(Math.log(n)/Math.log(1024)))):0;return `${(n/1024**index).toFixed(index?1:0)} ${units[index]}${rate?'/s':''}`}
function points(direction:'upload'|'download'){return samples.value.map(p=>`${(8+Math.max(0,1-(end.value-p.at)/60000)*584).toFixed(1)},${(128-p[direction]/chartMax.value*110).toFixed(1)}`).join(' ')}
function area(direction:'upload'|'download'){const line=points(direction);if(!line)return '';const first=line.split(' ')[0]?.split(',')[0];return `${first},132 ${line} 592,132`}
function publish(){emit('speed',{upload:upload.value,download:download.value,running:counter.value.running})}
async function sample(){
  if(disposed||document.hidden)return
  if(pending){
    if(baseline&&performance.now()-baseline.at>5000){trafficError.value=t("速率数据已过期，等待内核响应");baseline=null;upload.value=null;download.value=null;samples.value=[];publish()}
    return
  }
  pending=true
  try{
    const value=await api<Counter>('/api/client/network/traffic');if(disposed)return
    const stamp=typeof value.sampled_at==='number'?value.sampled_at*1000:value.sampled_at?Date.parse(value.sampled_at):Date.now()
    const age=Number.isFinite(stamp)?Math.max(0,Date.now()-stamp):0
    if(value.running&&(value.stale||age>5000))throw new Error('Stale sample')
    const at=performance.now()-age;counter.value=value;trafficError.value=''
    const previous=baseline
    if(previous&&value.running&&previous.value.session===value.session&&at<=previous.at){publish();return}
    if(!value.running){upload.value=null;download.value=null;baseline=null;samples.value=[]}
    else if(previous&&previous.value.session===value.session&&at-previous.at<6000&&value.upload>=previous.value.upload&&value.download>=previous.value.download){
      const seconds=(at-previous.at)/1000
      upload.value=(value.upload-previous.value.upload)/seconds;download.value=(value.download-previous.value.download)/seconds
      if(props.active!==false)samples.value=[...samples.value.filter(p=>at-p.at<=60000),{at,upload:upload.value,download:download.value}]
      baseline={at,value}
    }else{upload.value=null;download.value=null;samples.value=[];baseline={at,value}}
    publish()
  }catch{if(!disposed){trafficError.value=t("暂时无法读取速率");baseline=null;upload.value=null;download.value=null;samples.value=[];publish()}}
  finally{pending=false;schedule()}
}
async function detect(refresh=false){
  const sequence=++lookupSequence;checking.value=true;ipError.value='';lookup.value=null
  try{const result=await api<Lookup>(`/api/client/network/ip?route=${route.value}&refresh=${refresh}`);if(sequence===lookupSequence&&!disposed)lookup.value=result}
  catch(e){if(sequence===lookupSequence&&!disposed)ipError.value=(e as Error).message}
  finally{if(sequence===lookupSequence)checking.value=false}
}
async function copy(){if(!lookup.value?.ip)return;try{await navigator.clipboard.writeText(lookup.value.ip);copied.value=true;clearTimeout(copyTimer);copyTimer=setTimeout(()=>copied.value=false,2000)}catch{ipError.value=t("复制失败，可以选中上方 IP 地址手动复制")}}
function schedule(){clearTimeout(timer);if(disposed||document.hidden)return;const fast=props.running||counter.value.running;timer=setTimeout(sample,fast?(props.active===false?5000:1000):5000)}
function resume(){clearTimeout(timer);if(!document.hidden)sample()}
watch(route,()=>{copied.value=false;detect()})
watch(()=>props.configKey,()=>{if(route.value==='proxy'){++lookupSequence;checking.value=false;lookup.value=null;ipError.value=t("运行配置已变化，请重新检测出口")}})
watch(()=>props.running,running=>{clearTimeout(timer);if(!running){baseline=null;counter.value={...counter.value,running:false,connections:0};upload.value=null;download.value=null;samples.value=[];publish()}sample()})
watch(()=>props.active,active=>{clearTimeout(timer);if(active)sample();else{samples.value=[];schedule()}})
onMounted(()=>{sample();detect();document.addEventListener('visibilitychange',resume)})
onUnmounted(()=>{disposed=true;++lookupSequence;clearTimeout(timer);clearTimeout(copyTimer);document.removeEventListener('visibilitychange',resume)})
</script>

<template>
  <section class="network-dashboard" :aria-label="t('网络概况')">
    <Teleport :to="trafficTarget||'body'" :disabled="!trafficTarget" defer>
    <article class="desk-card bandwidth-card">
      <div class="network-card-heading"><div><span class="desk-eyebrow">LIVE TRAFFIC</span><h2>{{ t("实时速率") }}<span class="live-indicator" :class="{online:counter.running&&!trafficError}"></span></h2></div><span class="network-pill"><Activity :size="12"/>{{ trafficError?t("读取异常"):counter.running?t(props.active===false?'低频采样':'每秒采样'):t("等待内核") }}</span></div>
      <div class="bandwidth-readings"><div class="download-reading"><span><ArrowDownLeft :size="15"/>{{ t("下载速率") }}</span><strong>{{ format(download,true) }}</strong></div><div class="upload-reading"><span><ArrowUpRight :size="15"/>{{ t("上传速率") }}</span><strong>{{ format(upload,true) }}</strong></div><div class="connections-reading"><span>{{ t("活跃连接") }}</span><button type="button" class="network-count-button" :aria-label="t('连接诊断')" @click="emit('connections')"><strong>{{ counter.running&&!trafficError?counter.connections:'—' }}<small>{{ t("条") }}</small></strong></button></div></div>
      <div class="session-traffic"><div><span>{{ counter.running?t("本次连接累计"):t("上次连接累计") }}</span><strong>{{ format(counter.upload+counter.download) }}</strong></div><span>↓ {{ format(counter.download) }}<br>↑ {{ format(counter.upload) }}</span><small>{{ t("从主内核启动计数") }}<br>{{ t("含接管的直连流量") }}</small></div>
      <details class="network-expanded"><summary>{{ t('流量详情与趋势') }}</summary>
      <div v-if="counter.running" class="bandwidth-plot"><div class="chart-scale"><span>{{ format(chartMax,true) }}</span><span>0</span></div><svg viewBox="0 0 600 140" preserveAspectRatio="none" role="img" :aria-label="t('最近一分钟上传和下载速率趋势')"><defs><linearGradient id="download-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#8065eb" stop-opacity=".25"/><stop offset="100%" stop-color="#8065eb" stop-opacity="0"/></linearGradient><linearGradient id="upload-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#26a89a" stop-opacity=".13"/><stop offset="100%" stop-color="#26a89a" stop-opacity="0"/></linearGradient></defs><path d="M8 18H592 M8 55H592 M8 92H592 M8 129H592" class="plot-grid"/><polygon :points="area('download')" fill="url(#download-fill)"/><polygon :points="area('upload')" fill="url(#upload-fill)"/><polyline :points="points('download')" class="download-line"/><polyline :points="points('upload')" class="upload-line"/></svg><div v-if="!samples.length" class="plot-empty">{{ trafficError||(!counter.running?t("启动内核后，查看真实流量曲线"):t("正在采集第一个速率样本…")) }}</div></div>
      <div v-if="counter.running" class="chart-time"><span>{{ t("60 秒前") }}</span><span>{{ t("30 秒前") }}</span><span>{{ t("现在") }}</span></div>
      <div v-if="!counter.running" class="plot-idle"><Activity :size="14"/>{{ t("启动内核后，这里显示最近 60 秒的速率曲线") }}</div>
      </details>
    </article>

    </Teleport>
    <Teleport :to="egressTarget||'body'" :disabled="!egressTarget" defer>
    <article class="desk-card ip-card">
      <div class="network-card-heading"><h2>{{ t('网络出口') }}</h2><button class="desk-text-btn" :disabled="checking" @click="detect(true)"><RefreshCw :size="14" :class="{rotate:checking}"/>{{ checking?t('检测中'):t('重新检测') }}</button></div>
      <div class="egress-row"><span>IP</span><div class="egress-ip"><strong>{{ checking?t('查询中…'):lookup?.ip||t('未获取') }}</strong><button class="desk-icon-btn" :disabled="!lookup?.ip" :aria-label="t('复制公网 IP')" @click="copy"><Check v-if="copied" :size="15"/><Copy v-else :size="15"/></button></div></div>
      <div class="egress-row"><span>{{ t('地址') }}</span><strong>{{ checking?t('查询中…'):location||t('未获取') }}</strong></div>
      <div class="egress-row"><span>{{ t('IP 属性') }}</span><div class="egress-properties"><span v-for="tag in ipProperties" :key="tag" class="ip-property">{{ tag }}</span><span v-if="checking||!ipProperties.length">{{ checking?t('查询中…'):t('未获取') }}</span></div></div>
      <p v-if="ipError||lookup?.status==='unavailable'||lookup?.status==='partial'" class="ip-message" role="status">{{ message(ipError||lookup?.message) }}</p>
    </article>
    </Teleport>
  </section>
</template>
