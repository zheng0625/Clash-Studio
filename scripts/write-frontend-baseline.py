from __future__ import annotations
import hashlib
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'memory' / 'baseline-source-20261029'
MANIFEST = ROOT / 'artifacts' / 'memory' / 'checkpoint-20261029' / 'SHA256SUMS.txt'
ns = runpy.run_path(str(ROOT / 'scripts' / 'reconstruct-frontend-baseline.py'))
read, sub = ns['read'], ns['sub']

def proxy_baseline():
    t = read('frontend/src/ProxyPanel.vue')
    t = sub(t, """const RENDER_BUDGET=300,PAGE_SIZE=100
const groupPages=ref<Record<string,number>>({})
const expandedGroups=computed(()=>visibleGroups.value.filter(item=>!collapsed.value[item.group.name]))
// Strict global allocation: expanded groups never render more than RENDER_BUDGET
// cards in total. Groups beyond the budget receive 0 slots until others fold.
const groupLimits=computed<Record<string,number>>(()=>{
  const names=expandedGroups.value.map(item=>item.group.name),limits:Record<string,number>={}
  if(!names.length)return limits
  const total=Math.min(RENDER_BUDGET,names.length*PAGE_SIZE),base=Math.floor(total/names.length),extra=total%names.length
  names.forEach((name,index)=>{limits[name]=Math.min(PAGE_SIZE,base+(index<extra?1:0))})
  return limits
})
function groupLimit(name:string){return groupLimits.value[name]??0}
function groupPageCount(names:string[],name:string){return Math.max(1,Math.ceil(names.length/Math.max(1,groupLimit(name))))}
function groupPageIndex(names:string[],name:string){return Math.min(groupPages.value[name]||0,groupPageCount(names,name)-1)}
function groupPage(names:string[],name:string){const limit=groupLimit(name);if(!limit)return[];const start=groupPageIndex(names,name)*limit;return names.slice(start,start+limit)}
function moveGroupPage(names:string[],name:string,offset:number){groupPages.value[name]=Math.max(0,Math.min(groupPageCount(names,name)-1,groupPageIndex(names,name)+offset))}
watch([search,availableOnly,sort],()=>{groupPages.value={}})""",
            "", 'proxy block')
    t = sub(t, """  collapsed.value[group.name]=false
  await nextTick()
  if(!groupLimit(group.name)){
    groups.value.forEach(item=>{if(item.name!==group.name)collapsed.value[item.name]=true})
    await nextTick()
  }
  const names=members(group),index=names.indexOf(group.now!),limit=Math.max(1,groupLimit(group.name))
  if(index>=0)groupPages.value[group.name]=Math.floor(index/limit)""",
            """  collapsed.value[group.name]=false""", 'proxy locate')
    t = sub(t, '<div v-if="!collapsed[group.name]" class="node-grid"><article v-for="name in groupPage(names,group.name)" :key="name"',
            '<div v-show="!collapsed[group.name]" class="node-grid"><article v-for="name in names" :key="name"', 'proxy grid')
    t = sub(t, """    <p v-if="!collapsed[group.name]&&!groupLimit(group.name)" class="page-caption">{{ t('已达到同时显示上限；折叠其他策略组后可查看此组节点。') }}</p>
    <nav v-if="!collapsed[group.name]&&groupPageCount(names,group.name)>1" class="group-pagination" :aria-label="t('策略组节点分页')"><button class="desk-btn" :disabled="groupPageIndex(names,group.name)===0" @click="moveGroupPage(names,group.name,-1)">{{ t('上一页节点') }}</button><span role="status">{{ t('第 {0} / {1} 页 · 每页最多 {2} 项',[groupPageIndex(names,group.name)+1,groupPageCount(names,group.name),groupLimit(group.name)]) }}</span><button class="desk-btn" :disabled="groupPageIndex(names,group.name)===groupPageCount(names,group.name)-1" @click="moveGroupPage(names,group.name,1)">{{ t('下一页节点') }}</button></nav>
""", "", 'proxy pagination')
    t = t.replace('\n\nfunction clearFilters', '\nfunction clearFilters', 1)
    return t

ORIGINAL_RESOURCE_MEMORY = '''<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ChevronDown, MemoryStick, RefreshCw } from 'lucide-vue-next'
import { api } from './api'
import { t } from './i18n'
type Sample={status:'ok'|'partial'|'unavailable';total_bytes:number|null;processes:{kind:'interface'|'service'|'core';bytes:number|null;process_count:number;unreadable_count:number}[];sampled_at:number}
const sample=ref<Sample|null>(null),failed=ref(false)
let disposed=false,pending=false,timer:ReturnType<typeof setTimeout>|undefined
function mb(value:number|null|undefined){return value===null||value===undefined?'—':(value/1024**2).toFixed(1)}
async function read(){
  if(disposed||document.hidden||pending)return
  pending=true
  try{const value=await api<Sample>('/api/client/resources/memory');if(!disposed){sample.value=value;failed.value=value.status==='unavailable'}}
  catch{if(!disposed){sample.value=null;failed.value=true}}
  finally{pending=false;clearTimeout(timer);if(!disposed&&!document.hidden)timer=setTimeout(read,5000)}
}
function resume(){clearTimeout(timer);if(!document.hidden)void read()}
onMounted(()=>{void read();document.addEventListener('visibilitychange',resume)})
onUnmounted(()=>{disposed=true;clearTimeout(timer);document.removeEventListener('visibilitychange',resume)})
</script>
<template>
  <section class="desk-card resource-memory-card" :aria-label="t('软件内存占用')"><div class="resource-memory-reading"><h2><MemoryStick :size="18"/>{{ t('内存占用') }}</h2><strong>{{ sample?.status==='partial'?'≈ ':'' }}{{ mb(sample?.total_bytes) }} <small v-if="sample?.total_bytes!==null&&sample?.total_bytes!==undefined">MB</small></strong></div><details class="resource-memory-details"><summary>RAM · {{ t('进程明细') }}<ChevronDown :size="13"/></summary><div class="resource-memory-processes"><div v-for="part in sample?.processes||[]" :key="part.kind"><span>{{ t({interface:'界面进程',service:'本地服务',core:'代理内核'}[part.kind]) }}</span><b>{{ mb(part.bytes) }} MB</b></div><p>{{ t('软件各进程工作集合计，包含共享内存页。') }}</p><p v-if="sample?.status==='partial'">{{ t('部分进程暂不可读取，当前显示已读取部分。') }}</p><button v-if="failed" class="desk-text-btn" @click="read"><RefreshCw :size="13"/>{{ t('重新读取内存') }}</button></div></details></section>
</template>
'''

def diagnostics_baseline():
    t = read('frontend/src/ui-diagnostics.css')
    return sub(t, '\n.desk .group-pagination{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:12px;margin:4px 0 18px;color:var(--client-secondary);font-size:13px}', '', 'diagnostics')

def benchmark_baseline():
    t = read('scripts/benchmark-backend.py')
    t = sub(t, "        runtime.process = SimpleNamespace(pid=123, poll=lambda:None, terminate=lambda:None, kill=lambda:None, wait=lambda **kwargs:0)",
            "        runtime.process = SimpleNamespace(pid=123, poll=lambda:None)", 'benchmark process')
    t = sub(t, """        # Entry+byte budget under distinct revision keys; oversized entries must not be retained.
        budget = RevisionCache(capacity=8, max_bytes=8*1024*1024)
        for index in range(16):
            budget.get(('budget', index), lambda index=index: dict(compose(yaml, 'p', Workspace()), key=index))
        stats = budget.stats()
        result['composition_budget'] = dict(keys=16, entries=stats['entries'], bytes=stats['bytes'],
                                           max_bytes=stats['max_bytes'], evictions=stats['evictions'],
                                           oversized=stats['oversized'], method=stats['method'])
        # Stopping must release cached connection objects/bytes/session while keeping totals.
        runtime._stop_locked(final_sample=False, report=False)
        result['connection_cleanup'] = dict(
            sample_released=runtime._connection_sample is None,
            wire_released=runtime._connection_wire is None,
            session_released=runtime._connection_session is None,
            final_download_retained=runtime.last_traffic['download'] == 20000,
            final_running_flag=runtime.last_traffic['running'])
""", "", 'benchmark block')
    return t

files = {
    'frontend/src/Client.vue': ns['client_baseline'](),
    'frontend/src/ConfigEditor.vue': ns['config_baseline'](),
    'frontend/src/ConnectionPanel.vue': ns['connection_baseline'](),
    'frontend/src/NetworkDashboard.vue': ns['dashboard_baseline'](),
    'frontend/src/ProxyPanel.vue': proxy_baseline(),
    'frontend/src/ResourceMemory.vue': ORIGINAL_RESOURCE_MEMORY,
    'frontend/src/ui-diagnostics.css': diagnostics_baseline(),
    'scripts/benchmark-backend.py': benchmark_baseline(),
}

manifest = {}
for line in MANIFEST.read_text(encoding='utf-8').splitlines():
    if '|' in line:
        rel, digest, size = line.split('|')
        manifest[rel.replace('\\', '/')] = (digest, int(size))

for rel, text in files.items():
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    expected = manifest.get(rel)
    matched = False
    for newline in ('\n', '\r\n'):
        with path.open('w', encoding='utf-8', newline=newline) as handle:
            handle.write(text)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest().upper()
        if expected and digest == expected[0]:
            matched = True
            break
    print(f'{"MATCH" if matched else "MISMATCH"} {rel} newline={newline!r} bytes={len(data)} sha={digest[:12]} expected={expected[0][:12] if expected else "none"} expected_bytes={expected[1] if expected else "?"}')
