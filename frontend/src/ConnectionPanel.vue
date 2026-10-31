<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { Activity, Copy, Pause, Play, Search, X } from 'lucide-vue-next'
import AppDialog from './AppDialog.vue'
import { t, locale } from './i18n'
type Connection={id:string;metadata:{host?:string;destinationIP?:string;destinationPort?:string;process?:string;processPath?:string;network?:string};rule:string;rulePayload?:string;chains:string[];upload:number;download:number}
const props=defineProps<{connections:Connection[];sampledAt:number;running:boolean;busy:boolean;active:boolean;configKey:string;error?:string;appLabels:Record<string,string>}>()
const emit=defineEmits<{close:[id:string];notice:[message:string,error?:boolean];ready:[]}>()
const query=ref(''),process=ref(''),outbound=ref(''),sort=ref('original'),paused=ref(false),frozen=ref<Connection[]>([]),frozenAt=ref(0)
const copied=ref(false),detailSampleAt=ref(0)
const listPage=ref(0),pageSize=100
let copyTimer:ReturnType<typeof setTimeout>|undefined
onUnmounted(()=>clearTimeout(copyTimer))
const selectedId=ref(''),snapshot=ref<Connection|null>(null),dialog=ref<InstanceType<typeof AppDialog>|null>(null)
const data=computed(()=>paused.value?frozen.value:props.connections)
const sampledAt=computed(()=>paused.value?frozenAt.value:props.sampledAt)
const processKey=(connection:Connection)=>connection.metadata.process||connection.metadata.processPath||''
function appName(value:string){return props.appLabels[value]?props.appLabels[value]+' · '+value:value||t('未知应用')}
const processes=computed(()=>[...new Set(data.value.map(processKey))].filter(Boolean).sort((a,b)=>appName(a).localeCompare(appName(b))))
const outbounds=computed(()=>[...new Set(data.value.flatMap(connection=>connection.chains||[]))].sort((a,b)=>a.localeCompare(b)))
const visible=computed(()=>{
 const filtered=data.value.filter(connection=>(!process.value||processKey(connection)===process.value)&&(!outbound.value||connection.chains?.includes(outbound.value))&&`${connection.metadata.host||''} ${connection.metadata.destinationIP||''} ${appName(processKey(connection))} ${connection.metadata.processPath||''} ${connection.rule} ${connection.rulePayload||''} ${(connection.chains||[]).join(' ')}`.toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase()))
 if(sort.value!=='original'){const amount=(connection:Connection)=>sort.value==='upload'?connection.upload:sort.value==='download'?connection.download:connection.upload+connection.download;return [...filtered].sort((a,b)=>amount(b)-amount(a)||a.id.localeCompare(b.id))}
 return filtered
})
const detail=computed(()=>data.value.find(connection=>connection.id===selectedId.value)||snapshot.value)
const pageCount=computed(()=>Math.max(1,Math.ceil(visible.value.length/pageSize)))
const pageConnections=computed(()=>visible.value.slice(listPage.value*pageSize,(listPage.value+1)*pageSize))
watch([query,process,outbound,sort],()=>{listPage.value=0})
watch(pageCount,count=>{listPage.value=Math.min(listPage.value,count-1)},{flush:'sync'})
function movePage(offset:number){listPage.value=Math.max(0,Math.min(pageCount.value-1,listPage.value+offset));document.querySelector('.connection-sample')?.scrollIntoView({block:'start'})}
const detailStatus=computed(()=>props.error?t('连接状态待确认'):paused.value?t('暂停快照，实时状态未确认'):props.connections.some(connection=>connection.id===selectedId.value)?t('最近采样时活跃'):t('连接已结束，保留最后详情'))
function bytes(value:number){if(!Number.isFinite(value)||value<=0)return '0 B';const i=Math.min(3,Math.floor(Math.log(value)/Math.log(1024)));return `${(value/1024**i).toFixed(i?1:0)} ${['B','KB','MB','GB'][i]}`}
function time(value:number){return value?new Date(value).toLocaleTimeString(locale.value,{hour12:false}):t('尚无成功采样')}
function clear(){query.value='';process.value='';outbound.value='';sort.value='original';listPage.value=0}
function togglePause(){if(!paused.value){frozen.value=JSON.parse(JSON.stringify(props.connections));frozenAt.value=props.sampledAt}else{frozen.value=[];frozenAt.value=0}paused.value=!paused.value}
async function inspect(connection:Connection){selectedId.value=connection.id;detailSampleAt.value=sampledAt.value;copied.value=false;snapshot.value=JSON.parse(JSON.stringify(connection));await nextTick();void dialog.value?.open()}
async function copy(value:string){try{await navigator.clipboard.writeText(value);copied.value=true;clearTimeout(copyTimer);copyTimer=setTimeout(()=>copied.value=false,1800);emit('notice',t('已复制'))}catch{emit('notice',t('复制失败，请手动选中复制'),true)}}
function target(connection:Connection){return `${connection.metadata.host||connection.metadata.destinationIP||t('未知目标')}${connection.metadata.destinationPort?':'+connection.metadata.destinationPort:''}`}
function allDetails(connection:Connection){return [target(connection),connection.metadata.destinationIP||'',appName(processKey(connection)),connection.metadata.processPath||'',`${connection.rule}${connection.rulePayload?': '+connection.rulePayload:''}`,(connection.chains||[]).join(' → '),`↓ ${bytes(connection.download)} / ↑ ${bytes(connection.upload)}`].filter(Boolean).join('\n')}
watch(data,connections=>{const current=connections.find(connection=>connection.id===selectedId.value);if(current){snapshot.value=JSON.parse(JSON.stringify(current));detailSampleAt.value=sampledAt.value}})
watch(()=>props.configKey,()=>{clear();paused.value=false;frozen.value=[];snapshot.value=null;selectedId.value='';dialog.value?.close()})
watch(()=>props.active,async active=>{if(active){await nextTick();emit('ready')}},{immediate:true})
</script>
<template>
 <section class="connections-panel">
  <template v-if="active">
  <div class="connection-controls desk-card"><label class="desk-search"><Search :size="16"/><input v-model="query" type="search" :placeholder="t('搜索域名、进程或策略')" :aria-label="t('搜索连接')"/></label><select v-model="process" :aria-label="t('筛选应用')"><option value="">{{ t('全部应用') }}</option><option v-for="value in processes" :key="value" :value="value">{{ appName(value) }}</option></select><select v-model="outbound" :aria-label="t('筛选出口或策略')"><option value="">{{ t('全部出口 / 策略') }}</option><option v-for="value in outbounds" :key="value" :value="value">{{ value }}</option></select><select v-model="sort" :aria-label="t('连接排序')"><option value="original">{{ t('原始顺序') }}</option><option value="total">{{ t('总流量优先') }}</option><option value="download">{{ t('下载流量优先') }}</option><option value="upload">{{ t('上传流量优先') }}</option></select><button class="desk-btn" :aria-pressed="paused" @click="togglePause"><Play v-if="paused" :size="15"/><Pause v-else :size="15"/>{{ paused?t('恢复刷新'):t('暂停刷新') }}</button></div>
  <p class="connection-sample" role="status">{{ paused?t('已暂停显示 · 采样于 {0}',[time(sampledAt)]):t('每 3 秒刷新 · 最近采样 {0}',[time(sampledAt)]) }} · {{ t('匹配 {0} / {1} 个连接',[visible.length,data.length]) }}</p>
  <p v-if="props.error" class="desk-alert error" role="alert">{{ t('连接数据可能已过期，请等待刷新成功') }}</p>
  <div class="desk-card connection-list"><div class="connection-list-heading"><span>{{ t('目标 / 应用') }}</span><span>{{ t('命中规则') }}</span><span>{{ t('策略链') }}</span><span>{{ t('传输量') }}</span></div><article v-for="connection in pageConnections" :key="connection.id" class="connection-item"><button class="connection-inspect" :aria-label="t('查看连接 {0}',[target(connection)])" @click="inspect(connection)"><span><strong>{{ target(connection) }}</strong><small>{{ appName(processKey(connection)) }} · {{ connection.metadata.network||'—' }}</small></span><span>{{ connection.rule }}<small>{{ connection.rulePayload }}</small></span><span>{{ connection.chains?.join(' → ')||t('未知') }}</span><span><small>↓ {{ bytes(connection.download) }}</small><small>↑ {{ bytes(connection.upload) }}</small></span></button><button class="desk-icon-btn danger" :aria-label="t('关闭连接 {0}',[target(connection)])" :disabled="busy||paused||!!props.error" @click="emit('close',connection.id)"><X :size="16"/></button></article><div v-if="!visible.length" class="desk-empty"><Activity :size="28"/><p>{{ data.length?t('没有匹配的连接'):props.error?t('等待连接数据恢复'):running?t('暂无连接，等待应用发起请求'):t('内核尚未运行。') }}</p><button v-if="query||process||outbound" class="desk-btn" @click="clear">{{ t('清除筛选') }}</button></div></div>
  <nav v-if="pageCount>1" class="connection-pagination" :aria-label="t('连接分页')"><button class="desk-btn" :disabled="listPage===0" @click="movePage(-1)">{{ t('上一页') }}</button><span role="status">{{ t('第 {0} / {1} 页 · 每页最多 {2} 条',[listPage+1,pageCount,pageSize]) }}</span><button class="desk-btn" :disabled="listPage===pageCount-1" @click="movePage(1)">{{ t('下一页') }}</button></nav>
  <p class="page-caption">{{ t('这里展示内核已接管的连接；绕过本机代理的流量不会出现在列表中。') }}</p>
  <AppDialog ref="dialog" class="connection-detail" :title="t('连接详情')" close-label="关闭连接详情"><template v-if="detail"><p class="connection-detail-status" role="status">{{ detailStatus }} · {{ t('详情采样于 {0}',[time(detailSampleAt)]) }}</p><dl class="connection-detail-fields"><div><dt>{{ t('完整目标') }}</dt><dd>{{ target(detail) }}<button class="desk-icon-btn" :aria-label="t('复制完整目标')" @click="copy(target(detail))"><Copy :size="16"/></button></dd></div><div><dt>IP</dt><dd>{{ detail.metadata.destinationIP||'—' }}</dd></div><div><dt>{{ t('应用 / 进程') }}</dt><dd>{{ appName(processKey(detail)) }}</dd></div><div><dt>{{ t('进程路径') }}</dt><dd>{{ detail.metadata.processPath||'—' }}</dd></div><div><dt>{{ t('命中规则') }}</dt><dd>{{ detail.rule }}<template v-if="detail.rulePayload">: {{ detail.rulePayload }}</template><button class="desk-icon-btn" :aria-label="t('复制命中规则')" @click="copy(detail.rule+(detail.rulePayload?': '+detail.rulePayload:''))"><Copy :size="16"/></button></dd></div><div><dt>{{ t('完整策略链') }}</dt><dd>{{ detail.chains?.join(' → ')||'—' }}<button class="desk-icon-btn" :aria-label="t('复制完整策略链')" @click="copy((detail.chains||[]).join(' → '))"><Copy :size="16"/></button></dd></div><div><dt>{{ t('传输量') }}</dt><dd>↓ {{ bytes(detail.download) }} / ↑ {{ bytes(detail.upload) }}</dd></div></dl></template><template #footer><small v-if="copied" role="status">{{ t('已复制') }}</small><button class="desk-btn" :disabled="!detail" @click="detail && copy(allDetails(detail))"><Copy :size="16"/>{{ t('复制详情') }}</button><button class="desk-btn danger" :disabled="busy||paused||!!props.error||!connections.some(connection=>connection.id===selectedId)" @click="emit('close',selectedId)">{{ t('关闭此连接') }}</button></template></AppDialog>
  </template>
 </section>
</template>

