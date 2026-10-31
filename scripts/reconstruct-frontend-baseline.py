from __future__ import annotations
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'memory' / 'baseline-source-20261029'
MANIFEST = ROOT / 'artifacts' / 'memory' / 'checkpoint-20261029' / 'SHA256SUMS.txt'

def read(rel): return (ROOT / rel).read_text(encoding='utf-8')
def sub(text, new, old, label):
    if text.count(new) != 1:
        raise SystemExit(f'{label}: expected one match, got {text.count(new)} for {new[:80]!r}')
    return text.replace(new, old, 1)

def client_baseline():
    t = read('frontend/src/Client.vue')
    t = sub(t, "import { computed, defineAsyncComponent, h, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'",
            "import { computed, defineAsyncComponent, h, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'", 'client import')
    t = sub(t, """// Wholesale-replaced, read-only list: shallow reactivity avoids proxying every
// connection object when filters scan thousands of rows.
const connections=shallowRef<Connection[]>([]), connectionSampledAt=ref(0)""",
            "const connections=ref<Connection[]>([]), connectionSampledAt=ref(0)", 'client connections')
    t = sub(t, 'let pollView:Page=page.value,pollEpoch=0,pageEpoch=0', 'let pollView:Page=page.value,pollEpoch=0', 'client epoch')
    t = sub(t, '  const epoch=runtimeEpoch,view=page.value,visit=pageEpoch', '  const epoch=runtimeEpoch,view=page.value', 'client poll once')
    t = sub(t, "        if(current()&&page.value===view&&visit===pageEpoch){connections.value=value.connections||[];connectionSampledAt.value=typeof value.sampled_at==='number'?value.sampled_at*1000:value.sampled_at?Date.parse(value.sampled_at):Date.now()}",
            "        if(current()&&page.value===view){connections.value=value.connections||[];connectionSampledAt.value=typeof value.sampled_at==='number'?value.sampled_at*1000:value.sampled_at?Date.parse(value.sampled_at):Date.now()}", 'client connection check')
    t = sub(t, "watch(page,(next,previous)=>{++pageEpoch;if(previous==='connections'&&next!=='connections'){connections.value=[];connectionSampledAt.value=0}void poll()})",
            "watch(page,()=>{void poll()})", 'client page watch')
    t = sub(t, """const catalogLoads=new Map<string,Promise<void>>()
const catalogError=ref(''),catalogLoading=ref(false)
const CATALOG_TTL_MS=5000
let catalogAt=0,catalogEgress=-1
async function loadCatalog(force=false){
  const id=selected.value,epoch=selectionEpoch,generation=runtimeEpoch,profileGeneration=profileSeq;if(!id)return
  if(!force&&proxyCatalog.value.key&&Date.now()-catalogAt<CATALOG_TTL_MS&&catalogEgress===runtime.egress_version)return
  const key=id+'\\n'+epoch+'\\n'+generation+'\\n'+profileGeneration,existing=catalogLoads.get(key);if(existing)return existing
  catalogLoading.value=true;catalogError.value=''
  const task=(async()=>{
    const value=await api<ProxyCatalog>(`/api/client/proxy-catalog?profile_id=${encodeURIComponent(id)}`)
    if(id===selected.value&&profileGeneration===profileSeq&&epoch===selectionEpoch&&generation===runtimeEpoch){
      for(const [group,name] of Object.entries(pendingSelections.value)){if(value.proxies[group])value.proxies[group]!.now=name}
      proxyCatalog.value=value;catalogAt=Date.now();catalogEgress=runtime.egress_version;void restoreScroll()
    }
  })()""",
            """const catalogLoads=new Map<string,Promise<void>>()
const catalogError=ref(''),catalogLoading=ref(false)
async function loadCatalog(){
  const id=selected.value,epoch=selectionEpoch,generation=runtimeEpoch,profileGeneration=profileSeq;if(!id)return
  const key=id+'\\n'+epoch+'\\n'+generation+'\\n'+profileGeneration,existing=catalogLoads.get(key);if(existing)return existing
  catalogLoading.value=true;catalogError.value=''
  const task=(async()=>{
    const value=await api<ProxyCatalog>(`/api/client/proxy-catalog?profile_id=${encodeURIComponent(id)}`)
    if(id===selected.value&&profileGeneration===profileSeq&&epoch===selectionEpoch&&generation===runtimeEpoch){
      for(const [group,name] of Object.entries(pendingSelections.value)){if(value.proxies[group])value.proxies[group]!.now=name}
      proxyCatalog.value=value;void restoreScroll()
    }
  })()""", 'client catalog')
    t = t.replace('@retry="loadCatalog(true)"', '@retry="loadCatalog"')
    t = t.replace('@refresh="loadCatalog(true)"', '@refresh="loadCatalog"')
    t = t.replace("@click=\"perform('catalog',()=>loadCatalog(true))\"", "@click=\"perform('catalog',loadCatalog)\"")
    t = t.replace(':active="page===\'home\'" ', '')
    return t

def config_baseline():
    t = read('frontend/src/ConfigEditor.vue')
    t = sub(t, "import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'",
            "import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'", 'editor import')
    t = sub(t, """// The subscription and its preview are immutable snapshots owned by the parent;
// only the editable draft needs a deep copy and deep reactivity.
const current=shallowRef(props.subscription), edits=ref<Edits>(clone(props.subscription.edits)), preview=shallowRef(props.subscription.preview)""",
            "const current=ref(clone(props.subscription)), edits=ref<Edits>(clone(props.subscription.edits)), preview=ref<Preview>(clone(props.subscription.preview))", 'editor refs')
    t = sub(t, 'let timer:ReturnType<typeof setTimeout>|undefined, sequence=0, disposed=false',
            'let timer:ReturnType<typeof setTimeout>|undefined, sequence=0', 'editor timer')
    t = sub(t, "function adopt(value:Subscription,resetMeta=false){const preserveMeta=metaDirty.value&&!resetMeta;current.value=value;edits.value=clone(value.edits);preview.value=value.preview;",
            "function adopt(value:Subscription,resetMeta=false){const preserveMeta=metaDirty.value&&!resetMeta;current.value=clone(value);edits.value=clone(value.edits);preview.value=clone(value.preview);", 'editor adopt')
    t = sub(t, "watch(()=>props.subscription,(value)=>{if(!unsaved.value&&!busy.value&&(value.id!==current.value.id||value.revision!==current.value.revision)){current.value=value;edits.value=clone(value.edits);preview.value=value.preview;",
            "watch(()=>props.subscription,(value)=>{if(!unsaved.value&&!busy.value&&(value.id!==current.value.id||value.revision!==current.value.revision)){current.value=clone(value);edits.value=clone(value.edits);preview.value=clone(value.preview);", 'editor watch')
    t = sub(t, "else{checking.value=false;preview.value=current.value.preview}}", "else{checking.value=false;preview.value=clone(current.value.preview)}}", 'editor edit watch')
    t = sub(t, """let previewInFlight=false, previewPending=false
async function checkDraft(){
  if(disposed)return
  if(!dirty.value){checking.value=false;preview.value=current.value.preview;return}
  if(previewInFlight){previewPending=true;return}
  previewInFlight=true
  const seq=++sequence;checking.value=true
  try{const result=await api<Preview>(`/api/subscriptions/${current.value.id}/preview`,'POST',{revision:current.value.revision,edits:edits.value});if(!disposed&&seq===sequence){preview.value=result;error.value=''}}
  catch(e){if(!disposed&&seq===sequence)error.value=(e as Error).message}
  finally{previewInFlight=false;if(!disposed&&seq===sequence)checking.value=false;if(!disposed&&previewPending){previewPending=false;clearTimeout(timer);timer=setTimeout(()=>checkDraft(),0)}}}""",
            "async function checkDraft(){const seq=++sequence;checking.value=true;try{const result=await api<Preview>(`/api/subscriptions/${current.value.id}/preview`,'POST',{revision:current.value.revision,edits:edits.value});if(seq===sequence){preview.value=result;error.value=''}}catch(e){if(seq===sequence)error.value=(e as Error).message}finally{if(seq===sequence)checking.value=false}}", 'editor check')
    t = sub(t, "preview.value=current.value.preview;error.value=''}", "preview.value=clone(current.value.preview);error.value=''}", 'editor discard')
    t = t.replace('checking.value=false}}\n\nasync function publish', 'checking.value=false}}\nasync function publish', 1)
    t = sub(t, "onUnmounted(()=>{disposed=true;clearTimeout(timer);++sequence;previewPending=false;emit('dirty',false)})",
            "onUnmounted(()=>{clearTimeout(timer);emit('dirty',false)})", 'editor unmount')
    return t

def connection_baseline():
    t = read('frontend/src/ConnectionPanel.vue')
    return sub(t, "function togglePause(){if(!paused.value){frozen.value=JSON.parse(JSON.stringify(props.connections));frozenAt.value=props.sampledAt}else{frozen.value=[];frozenAt.value=0}paused.value=!paused.value}",
               "function togglePause(){if(!paused.value){frozen.value=JSON.parse(JSON.stringify(props.connections));frozenAt.value=props.sampledAt}paused.value=!paused.value}", 'connection pause')

def dashboard_baseline():
    t = read('frontend/src/NetworkDashboard.vue')
    t = sub(t, "const props=defineProps<{running:boolean;configKey:string;active?:boolean;trafficTarget?:string;egressTarget?:string}>()",
            "const props=defineProps<{running:boolean;configKey:string;trafficTarget?:string;egressTarget?:string}>()", 'dashboard props')
    t = sub(t, "function schedule(){clearTimeout(timer);if(disposed||document.hidden)return;const fast=props.running||counter.value.running;timer=setTimeout(sample,fast?(props.active===false?5000:1000):5000)}",
            "function schedule(){clearTimeout(timer);if(!disposed&&!document.hidden)timer=setTimeout(sample,props.running||counter.value.running?1000:5000)}", 'dashboard schedule')
    t = sub(t, "      if(props.active!==false)samples.value=[...samples.value.filter(p=>at-p.at<=60000),{at,upload:upload.value,download:download.value}]",
            "      samples.value=[...samples.value.filter(p=>at-p.at<=60000),{at,upload:upload.value,download:download.value}]", 'dashboard history')
    t = sub(t, "watch(()=>props.active,active=>{clearTimeout(timer);if(active)sample();else{samples.value=[];schedule()}})\n", "", 'dashboard active watch')
    t = sub(t, '{{ trafficError?t("读取异常"):counter.running?t(props.active===false?\'低频采样\':\'每秒采样\'):t("等待内核") }}',
            '{{ trafficError?t("读取异常"):counter.running?t("每秒采样"):t("等待内核") }}', 'dashboard pill')
    return t
