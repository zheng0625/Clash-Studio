<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Activity, ArrowDownLeft, ArrowUpRight, Check, Copy, Globe2, Loader2, MapPin, Radio, RefreshCw, WifiOff } from 'lucide-vue-next'
import { api } from './api'

const props=defineProps<{running:boolean;configKey:string}>()
const emit=defineEmits<{speed:[value:{upload:number|null;download:number|null;running:boolean}]}>()
type Counter={running:boolean;session:string;upload:number;download:number;connections:number}
type Lookup={status:'ok'|'partial'|'unavailable';ip:string;family:string;country:string;region:string;city:string;isp:string;asn:string;provider:string;route:'system'|'proxy';route_label:string;profile:string;checked_at:string;elapsed_ms:number;cached:boolean;message:string}
type Sample={at:number;upload:number;download:number}
const route=computed<'system'|'proxy'>(()=>props.running?'proxy':'system'), checking=ref(false), lookup=ref<Lookup|null>(null), ipError=ref(''), copied=ref(false)
const counter=ref<Counter>({running:false,session:'',upload:0,download:0,connections:0})
const upload=ref<number|null>(null), download=ref<number|null>(null), samples=ref<Sample[]>([]), trafficError=ref('')
let baseline:{at:number;value:Counter}|null=null, timer:ReturnType<typeof setTimeout>|undefined, copyTimer:ReturnType<typeof setTimeout>|undefined
let disposed=false, pending=false, lookupSequence=0
const location=computed(()=>[...new Set([lookup.value?.country,lookup.value?.region,lookup.value?.city].filter(Boolean))].join(' · '))
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
    const at=performance.now();counter.value=value;trafficError.value=''
    const previous=baseline
    if(!value.running){upload.value=null;download.value=null;baseline=null;samples.value=[]}
    else if(previous&&previous.value.session===value.session&&at-previous.at<6000&&value.upload>=previous.value.upload&&value.download>=previous.value.download){
      const seconds=(at-previous.at)/1000
      upload.value=(value.upload-previous.value.upload)/seconds;download.value=(value.download-previous.value.download)/seconds
      samples.value=[...samples.value.filter(p=>at-p.at<=60000),{at,upload:upload.value,download:download.value}]
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
function schedule(){clearTimeout(timer);if(!disposed&&!document.hidden)timer=setTimeout(sample,props.running||counter.value.running?1000:5000)}
function resume(){clearTimeout(timer);if(!document.hidden)sample()}
watch(route,()=>{copied.value=false;detect()})
watch(()=>props.configKey,()=>{if(route.value==='proxy'){++lookupSequence;checking.value=false;lookup.value=null;ipError.value=t("运行配置已变化，请重新检测出口")}})
watch(()=>props.running,running=>{clearTimeout(timer);if(!running){baseline=null;counter.value={...counter.value,running:false,connections:0};upload.value=null;download.value=null;samples.value=[];publish()}sample()})
onMounted(()=>{sample();detect();document.addEventListener('visibilitychange',resume)})
onUnmounted(()=>{disposed=true;++lookupSequence;clearTimeout(timer);clearTimeout(copyTimer);document.removeEventListener('visibilitychange',resume)})
</script>

<template>
  <section class="network-dashboard" :aria-label="t('网络概况')">
    <article class="desk-card bandwidth-card">
      <div class="network-card-heading"><div><span class="desk-eyebrow">LIVE TRAFFIC</span><h2>{{ t("实时速率") }}<span class="live-indicator" :class="{online:counter.running&&!trafficError}"></span></h2></div><span class="network-pill"><Activity :size="12"/>{{ trafficError?t("读取异常"):counter.running?t("每秒采样"):t("等待内核") }}</span></div>
      <div class="bandwidth-readings"><div class="download-reading"><span><ArrowDownLeft :size="15"/>{{ t("下载速率") }}</span><strong>{{ format(download,true) }}</strong></div><div class="upload-reading"><span><ArrowUpRight :size="15"/>{{ t("上传速率") }}</span><strong>{{ format(upload,true) }}</strong></div><div class="connections-reading"><span>{{ t("活跃连接") }}</span><strong>{{ counter.running&&!trafficError?counter.connections:'—' }}<small>{{ t("条") }}</small></strong></div></div>
      <div class="session-traffic"><div><span>{{ counter.running?t("本次连接累计"):t("上次连接累计") }}</span><strong>{{ format(counter.upload+counter.download) }}</strong></div><span>↓ {{ format(counter.download) }}<br>↑ {{ format(counter.upload) }}</span><small>{{ t("从主内核启动计数") }}<br>{{ t("含接管的直连流量") }}</small></div>
      <div v-if="counter.running" class="bandwidth-plot"><div class="chart-scale"><span>{{ format(chartMax,true) }}</span><span>0</span></div><svg viewBox="0 0 600 140" preserveAspectRatio="none" role="img" :aria-label="t('最近一分钟上传和下载速率趋势')"><defs><linearGradient id="download-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#8065eb" stop-opacity=".25"/><stop offset="100%" stop-color="#8065eb" stop-opacity="0"/></linearGradient><linearGradient id="upload-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#26a89a" stop-opacity=".13"/><stop offset="100%" stop-color="#26a89a" stop-opacity="0"/></linearGradient></defs><path d="M8 18H592 M8 55H592 M8 92H592 M8 129H592" class="plot-grid"/><polygon :points="area('download')" fill="url(#download-fill)"/><polygon :points="area('upload')" fill="url(#upload-fill)"/><polyline :points="points('download')" class="download-line"/><polyline :points="points('upload')" class="upload-line"/></svg><div v-if="!samples.length" class="plot-empty">{{ trafficError||(!counter.running?t("启动内核后，查看真实流量曲线"):t("正在采集第一个速率样本…")) }}</div></div>
      <div v-if="counter.running" class="chart-time"><span>{{ t("60 秒前") }}</span><span>{{ t("30 秒前") }}</span><span>{{ t("现在") }}</span></div>
      <div v-if="!counter.running" class="plot-idle"><Activity :size="14"/>{{ t("启动内核后，这里显示最近 60 秒的速率曲线") }}</div>
    </article>

    <article class="desk-card ip-card">
      <div class="network-card-heading"><div><span class="desk-eyebrow">NETWORK IDENTITY</span><h2>{{ t("你的网络出口") }}</h2></div><button class="desk-btn" :disabled="checking" @click="detect(true)"><RefreshCw :size="14" :class="{rotate:checking}"/>{{ checking?t("检测中"):t("重新检测") }}</button></div>
      <div class="ip-route-tabs" role="group" :aria-label="t('检测路径')"><span class="ip-route-now">{{ route==='proxy'?t("当前出口 · 本程序代理，按分流规则"):t("当前出口 · 系统路由，VPN 未开启") }}</span></div>
      <div class="ip-status" :class="{success:lookup?.status==='ok'||lookup?.status==='partial',failure:ipError||lookup?.status==='unavailable'}"><Loader2 v-if="checking" :size="13" class="rotate"/><WifiOff v-else-if="ipError||lookup?.status==='unavailable'" :size="13"/><Radio v-else :size="13"/><span>{{ checking?t("正在查询出口…"):ipError||lookup?.status==='unavailable'?t("检测未完成"):lookup?.status==='partial'?t("已联网 · 归属地暂缺"):lookup?t("检测服务可达"):t("等待检测") }}</span><span v-if="lookup?.family" class="ip-family">{{ lookup.family }}</span></div>
      <div class="ip-address"><strong>{{ lookup?.ip||'— —' }}</strong><button class="desk-icon-btn" :aria-label="t('复制公网 IP')" :title="t('复制 IP')" :disabled="!lookup?.ip" @click="copy"><Check v-if="copied" :size="15"/><Copy v-else :size="15"/></button></div>
      <div class="ip-location"><MapPin :size="14"/><span>{{ checking?t("正在查找 IP 归属地"):location||t("暂无归属地信息") }}</span></div>
      <dl class="ip-details"><div><dt>{{ t("网络服务商") }}</dt><dd :title="lookup?.isp">{{ lookup?.isp||'—' }}</dd></div><div><dt>{{ t("自治系统") }}</dt><dd>{{ lookup?.asn?'AS'+lookup.asn:'—' }}</dd></div><div><dt>{{ t("检测时间") }}</dt><dd>{{ lookup?.checked_at?new Date(lookup.checked_at).toLocaleTimeString(locale,{hour12:false}):'—' }}<small v-if="lookup?.cached">{{ t("缓存") }}</small></dd></div></dl>
      <div v-if="ipError||lookup?.status==='unavailable'||lookup?.status==='partial'" class="ip-message" role="status">{{ message(ipError||lookup?.message) }}</div>
      <div class="ip-card-bottom"><p>{{ route==='system'?t("遵循系统路由，TUN 可能影响出口。"):t("通过本程序混合端口，遵循当前分流规则。") }}<br>{{ t("服务：{0} · 归属地仅供参考", [lookup?.provider||'ipwho.is / ipify']) }}</p></div>
    </article>
  </section>
</template>
