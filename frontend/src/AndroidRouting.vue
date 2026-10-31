<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ArrowDown, ArrowRight, ArrowUp, Check, GripVertical, Loader2, Pencil, Plus, Power, Save, Search, Trash2, X } from 'lucide-vue-next'
import { api } from './api'
import { t, message } from './i18n'
import { confirmDialog } from './confirm'
import AppDialog from './AppDialog.vue'
import ListPagination from './ListPagination.vue'

type Rule={kind:string;value:string;target:string;enabled:boolean}
type Row=Rule&{key:string}
type State={revision:number;rules:Rule[];targets:string[]}
const props=defineProps<{profileId:string;needsApply?:boolean;busy?:boolean;applyLabel?:string;viewState?:{query:string;kindFilter:string;stateFilter:string;page?:number;pageSize?:number}}>()
const emit=defineEmits<{changed:[];dirty:[value:boolean];apply:[];ready:[];viewState:[value:{query:string;kindFilter:string;stateFilter:string;page:number;pageSize:number}]}>()
const rules=ref<Row[]>([]), targets=ref<string[]>([]), revision=ref(0), loading=ref(false), saving=ref(false), error=ref(''), baseline=ref('[]'), loaded=ref(false), saveFailed=ref(false)
const query=ref(props.viewState?.query||''), kindFilter=ref(props.viewState?.kindFilter||''), stateFilter=ref(props.viewState?.stateFilter||''), appQuery=ref('')
const pageSize=ref([5,10,20].includes(props.viewState?.pageSize||0)?props.viewState!.pageSize!:5),rulePage=ref(Math.max(0,Math.floor(props.viewState?.page||0)))
watch([query,kindFilter,stateFilter,pageSize],()=>{rulePage.value=0;stopDrag()},{flush:'sync'})
watch([query,kindFilter,stateFilter,pageSize,rulePage],()=>emit('viewState',{query:query.value,kindFilter:kindFilter.value,stateFilter:stateFilter.value,page:rulePage.value,pageSize:pageSize.value}),{flush:'sync'})
type App={package:string;label:string;icon?:string}
const apps=ref<App[]>([]),brokenIcons=ref(new Set<string>())
function appIcon(app:App){return app.icon&&app.icon.length<300000&&/^data:image\/(png|webp|jpeg);base64,/.test(app.icon)&&!brokenIcons.value.has(app.package)?app.icon:''}
function ruleLabel(rule:Rule){return rule.kind==='PROCESS-NAME'?apps.value.find(app=>app.package===rule.value)?.label||rule.value:rule.value}
const dialog=ref<InstanceType<typeof AppDialog>|null>(null), draft=ref<Rule|null>(null), editingKey=ref<string|null>(null), initialDraft=ref(''), draftError=ref(''), appError=ref('')
const kinds=computed(()=>[{value:'DOMAIN-SUFFIX',label:t('域名后缀')},{value:'DOMAIN',label:t('精确域名')},{value:'IP-CIDR',label:t('IPv4 网段')},{value:'IP-CIDR6',label:t('IPv6 网段')},{value:'PROCESS-NAME',label:t('应用包名')}])
const strip=(rule:Rule):Rule=>({kind:rule.kind,value:rule.value,target:rule.target,enabled:rule.enabled})
const payload=computed(()=>rules.value.map(strip))
const listDirty=computed(()=>JSON.stringify(payload.value)!==baseline.value)
const draftDirty=computed(()=>!!draft.value&&JSON.stringify(draft.value)!==initialDraft.value)
const dirty=computed(()=>listDirty.value||draftDirty.value)
watch(dirty,value=>emit('dirty',value),{flush:'sync'})
const locked=computed(()=>loading.value||saving.value||!!props.busy)
const visibleRules=computed(()=>rules.value.map((rule,index)=>({rule,index})).filter(({rule})=>(!kindFilter.value||rule.kind===kindFilter.value)&&(!stateFilter.value||(stateFilter.value==='enabled')===rule.enabled)&&`${rule.value} ${rule.target} ${kinds.value.find(k=>k.value===rule.kind)?.label} ${apps.value.find(app=>app.package===rule.value)?.label||''}`.toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase())))
const pageCount=computed(()=>Math.max(1,Math.ceil(visibleRules.value.length/pageSize.value)))
const pageRules=computed(()=>visibleRules.value.slice(rulePage.value*pageSize.value,(rulePage.value+1)*pageSize.value))
watch([pageCount,loaded],([count,ready])=>{if(ready)rulePage.value=Math.min(rulePage.value,count-1)},{flush:'sync'})
function revealRule(key:string){const index=visibleRules.value.findIndex(item=>item.rule.key===key);if(index>=0)rulePage.value=Math.floor(index/pageSize.value)}
async function changePage(value:number){if(locked.value||draft.value||draggedKey.value)return;rulePage.value=Math.max(0,Math.min(value,pageCount.value-1));await nextTick();document.querySelector('.routing-result-count')?.scrollIntoView({block:'start',behavior:'instant'})}

const draggedKey=ref(''),dropKey=ref(''),dragNotice=ref('')
const dropBefore=computed(()=>rules.value.findIndex(rule=>rule.key===dropKey.value)<rules.value.findIndex(rule=>rule.key===draggedKey.value))
let dragStart:{id:number;key:string;x:number;y:number}|null=null,dragPoint={x:0,y:0},dragFrame=0
function stopDrag(){if(dragFrame)cancelAnimationFrame(dragFrame);dragFrame=0;dragStart=null;draggedKey.value='';dropKey.value=''}
function dragTick(){if(!dragStart||!draggedKey.value)return;const container=document.querySelector<HTMLElement>('.desk-content');if(container){const rect=container.getBoundingClientRect();if(dragPoint.y<rect.top+70)container.scrollTop-=12;else if(dragPoint.y>rect.bottom-150)container.scrollTop+=12}const row=document.elementFromPoint(dragPoint.x,dragPoint.y)?.closest<HTMLElement>('.routing-summary[data-rule-key]');dropKey.value=row?.dataset.ruleKey||'';dragFrame=requestAnimationFrame(dragTick)}
function startDrag(event:PointerEvent,key:string){if(locked.value||event.button!==0)return;event.preventDefault();const button=event.currentTarget as HTMLButtonElement;button.focus();button.setPointerCapture(event.pointerId);dragStart={id:event.pointerId,key,x:event.clientX,y:event.clientY};dragPoint={x:event.clientX,y:event.clientY}}
function pointerMove(event:PointerEvent){if(!dragStart||dragStart.id!==event.pointerId)return;dragPoint={x:event.clientX,y:event.clientY};if(!draggedKey.value&&Math.hypot(event.clientX-dragStart.x,event.clientY-dragStart.y)>6){draggedKey.value=dragStart.key;dragFrame=requestAnimationFrame(dragTick)}}
function endDrag(event:PointerEvent){if(!dragStart||dragStart.id!==event.pointerId)return;const from=rules.value.findIndex(rule=>rule.key===draggedKey.value),to=rules.value.findIndex(rule=>rule.key===dropKey.value);if(from>=0&&to>=0&&from!==to){const row=rules.value.splice(from,1)[0]!;rules.value.splice(to,0,row);revealRule(row.key);dragNotice.value=t('规则已移至优先级 {0}',[to+1])}stopDrag()}
function dragKey(event:KeyboardEvent){if(event.key==='Escape'&&draggedKey.value){event.preventDefault();event.stopImmediatePropagation();stopDrag()}}
const matchingApps=computed(()=>apps.value.filter(app=>`${app.label} ${app.package}`.toLocaleLowerCase().includes(appQuery.value.trim().toLocaleLowerCase())))
let request=0,disposed=false
function adopt(state:State){dragNotice.value='';rules.value=state.rules.map(rule=>({...strip(rule),key:crypto.randomUUID()}));targets.value=state.targets;revision.value=state.revision;baseline.value=JSON.stringify(state.rules.map(strip));loaded.value=true}
async function load(){
 stopDrag();const sequence=++request;error.value='';loaded.value=false;rules.value=[];baseline.value='[]';targets.value=[];draft.value=null;dialog.value?.close();saveFailed.value=false;saving.value=false
 if(!props.profileId){loading.value=false;return}
 loading.value=true
 try{const state=await api<State>('/api/android/routing?profile_id='+encodeURIComponent(props.profileId));if(sequence===request&&!disposed)adopt(state)}catch(e){if(sequence===request)error.value=(e as Error).message}finally{if(sequence===request){loading.value=false;await nextTick();emit('ready')}}
}
async function edit(rule?:Row){
 if(locked.value||!loaded.value)return
 editingKey.value=rule?.key||null;draft.value=rule?strip(rule):{kind:'DOMAIN-SUFFIX',value:'',target:targets.value.includes('DIRECT')?'DIRECT':targets.value[0]||'',enabled:true};initialDraft.value=JSON.stringify(draft.value);draftError.value='';appQuery.value=''
 await nextTick();dialog.value?.open()
}
function closeEditor(){void dialog.value?.requestClose()}
function abandonEditor(){draft.value=null;draftError.value=''}
function commitEditor(){
 if(!draft.value)return
 const value=draft.value.value.trim()
 if(!value||/[\s,]/.test(value)){draftError.value=t('匹配值不能为空，且不能包含空格、逗号或换行');return}
 if(!targets.value.includes(draft.value.target)){draftError.value=t('请选择有效的目标出口');return}
 const next={...strip(draft.value),value}
 if(editingKey.value){const index=rules.value.findIndex(rule=>rule.key===editingKey.value);if(index<0)return;rules.value[index]={...next,key:editingKey.value}}
 else{const row={...next,key:crypto.randomUUID()};rules.value.push(row);revealRule(row.key)}
 if(editingKey.value)revealRule(editingKey.value)
 dialog.value?.close();draft.value=null;saveFailed.value=false
}
function move(index:number,offset:number){if(locked.value)return;const to=index+offset;if(to<0||to>=rules.value.length)return;[rules.value[index],rules.value[to]]=[rules.value[to]!,rules.value[index]!];revealRule(rules.value[to]!.key);dragNotice.value=t('规则已移至优先级 {0}',[to+1])}
function remove(key:string){if(!locked.value){rules.value=rules.value.filter(rule=>rule.key!==key);dragNotice.value=''}}
function clearFilters(){query.value='';kindFilter.value='';stateFilter.value=''}
async function discard(){if(!locked.value&&await confirmDialog(t('放弃尚未保存的规则修改？'))){rules.value=(JSON.parse(baseline.value) as Rule[]).map(rule=>({...rule,key:crypto.randomUUID()}));error.value='';saveFailed.value=false;dragNotice.value=''}}
async function reload(){if(!locked.value&&(!dirty.value||await confirmDialog(t('重新加载将丢弃未保存的规则修改，是否继续？'))))await load()}
defineExpose({reload})
async function save(){
 if(locked.value||!loaded.value||!listDirty.value||draft.value)return
 const sequence=request,id=props.profileId;saving.value=true;error.value='';saveFailed.value=false
 try{const state=await api<State>('/api/android/routing','PUT',{profile_id:id,revision:revision.value,rules:payload.value});if(sequence!==request||disposed)return;adopt(state);emit('changed')}
 catch(e){if(sequence===request&&!disposed){error.value=(e as Error).message;saveFailed.value=true}}
 finally{if(sequence===request)saving.value=false}
}
watch(()=>props.profileId,(_id,previous)=>{if(previous!==undefined){rulePage.value=0;clearFilters()}void load()},{immediate:true})
onMounted(()=>{window.addEventListener('blur',stopDrag);window.addEventListener('keydown',dragKey,true);api<App[]>('/api/android/apps').then(value=>{if(!disposed)apps.value=value.sort((a,b)=>a.label.localeCompare(b.label))}).catch(()=>{if(!disposed)appError.value=t('未能读取应用列表，可直接输入包名')})})
onUnmounted(()=>{disposed=true;++request;stopDrag();window.removeEventListener('blur',stopDrag);window.removeEventListener('keydown',dragKey,true)})
</script>

<template>
 <section class="desk-card android-routing">
  <div class="section-head"><h2>{{ t('规则列表') }}</h2><button class="desk-btn" :disabled="locked||!loaded||rules.length>=500" @click="edit()"><Plus :size="16"/>{{ t('添加规则') }}</button></div>
  <details class="routing-help"><summary>{{ t('规则如何生效') }}</summary><p class="page-caption">{{ t('从上到下匹配，优先于订阅规则；仅规则模式生效。') }}</p></details>
  <p v-if="!profileId" class="desk-empty">{{ t('请先选择一份订阅。') }}</p>
  <p v-if="loading" role="status"><Loader2 :size="16" class="rotate"/>{{ t('读取分流规则…') }}</p>
  <div v-if="error" class="desk-alert error" role="alert">{{ message(error) }}<button v-if="!loaded" class="desk-text-btn" :disabled="locked" @click="load">{{ t('重试') }}</button><button v-else-if="saveFailed" class="desk-text-btn" :disabled="locked" @click="reload">{{ t('重新加载规则') }}</button></div>
  <template v-if="loaded">
   <div class="routing-filters"><label class="desk-search"><Search :size="16"/><input v-model="query" type="search" :aria-label="t('搜索规则或出口')" :placeholder="t('搜索规则或出口')"/></label><select v-model="kindFilter" :aria-label="t('筛选匹配类型')"><option value="">{{ t('全部类型') }}</option><option v-for="kind in kinds" :key="kind.value" :value="kind.value">{{ kind.label }}</option></select><select v-model="stateFilter" :aria-label="t('筛选启用状态')"><option value="">{{ t('全部状态') }}</option><option value="enabled">{{ t('已启用') }}</option><option value="disabled">{{ t('已停用') }}</option></select></div>
   <p v-if="dragNotice" class="routing-drag-notice" role="status">{{ dragNotice }}</p><p class="routing-result-count" role="status">{{ t('显示 {0} / {1} 条规则，序号为实际优先级',[visibleRules.length,rules.length]) }}</p>
   <div v-if="!rules.length" class="desk-empty"><p>{{ t('尚无自定义规则，当前使用订阅原有分流。') }}</p></div>
   <div v-else-if="!visibleRules.length" class="desk-empty"><p>{{ t('没有匹配的规则') }}</p><button class="desk-btn" @click="clearFilters">{{ t('清除筛选') }}</button></div>
   <div v-if="visibleRules.length" class="routing-page-size"><label>{{ t('每页规则') }}<select v-model.number="pageSize" :aria-label="t('每页规则')" :disabled="locked||!!draft||!!draggedKey"><option v-for="size in [5,10,20]" :key="size" :value="size">{{ size }}</option></select></label><small>{{ t('当前显示第 {0}–{1} 条',[rulePage*pageSize+1,Math.min((rulePage+1)*pageSize,visibleRules.length)]) }}</small></div>
   <ol class="routing-summary-list">
    <li v-for="{rule,index} in pageRules" :key="rule.key" :data-rule-key="rule.key" :class="['routing-summary',{inactive:!rule.enabled,dragging:draggedKey===rule.key,'drop-before':dropKey===rule.key&&dropBefore,'drop-after':dropKey===rule.key&&!dropBefore}]">
     <button class="routing-summary-main" :aria-label="t('编辑规则 {0}',[index+1])" :disabled="locked" @click="edit(rule)"><span class="routing-priority">{{ index+1 }}</span><span class="routing-match"><small>{{ kinds.find(kind=>kind.value===rule.kind)?.label||rule.kind }} · {{ rule.enabled?t('已启用'):t('已停用') }}</small><strong>{{ ruleLabel(rule) }}</strong><small v-if="ruleLabel(rule)!==rule.value">{{ rule.value }}</small><span class="routing-destination"><ArrowRight :size="13"/>{{ rule.target }}</span></span><Pencil :size="16"/></button>
     <div class="routing-summary-actions"><button type="button" class="desk-icon-btn routing-drag-handle" :aria-label="t('拖动规则 {0}',[index+1])" :title="t('拖动排序，也可使用方向键或上移下移按钮')" :disabled="locked" @pointerdown="startDrag($event,rule.key)" @pointermove="pointerMove" @pointerup="endDrag" @pointercancel="stopDrag" @lostpointercapture="stopDrag" @contextmenu.prevent @keydown.up.prevent="move(index,-1)" @keydown.down.prevent="move(index,1)"><GripVertical :size="16"/></button><button type="button" class="desk-icon-btn" :aria-label="t('上移规则 {0}',[index+1])" :disabled="locked||index===0" @click="move(index,-1)"><ArrowUp :size="16"/></button><button type="button" class="desk-icon-btn" :aria-label="t('下移规则 {0}',[index+1])" :disabled="locked||index===rules.length-1" @click="move(index,1)"><ArrowDown :size="16"/></button><button type="button" class="desk-icon-btn danger" :aria-label="t('删除规则 {0}',[index+1])" :disabled="locked" @click="remove(rule.key)"><Trash2 :size="16"/></button></div>
    </li>
   </ol>
   <ListPagination class="routing-pagination" :model-value="rulePage" :pages="pageCount" :page-size="pageSize" :label="t('分流规则分页')" :disabled="locked||!!draft||!!draggedKey" @update:model-value="changePage"/>
  </template>
 </section>
 <Teleport to=".desk" defer><div v-if="loaded" class="routing-save-bar" role="status"><div><strong>{{ saving?t('正在保存…'):saveFailed?t('保存失败，修改仍保留'):dirty?t('有未保存的规则'):props.needsApply?t('已保存，待应用'):t('规则已保存') }}</strong><small>{{ dirty?t('保存后再应用到运行配置'):t('仅在规则模式下生效') }}</small></div><div class="routing-save-actions"><button v-if="listDirty" class="desk-text-btn" :disabled="locked||!!draft||!!draggedKey" @click="discard">{{ t('放弃修改') }}</button><button v-if="dirty" class="desk-btn primary" :disabled="locked||!!draft||!!draggedKey||!listDirty" @click="save"><Loader2 v-if="saving" :size="15" class="rotate"/><Save v-else :size="15"/>{{ saveFailed?t('重试保存'):t('保存规则') }}</button><button v-else class="desk-btn" :class="{primary:props.needsApply}" :disabled="locked||!!draggedKey" @click="emit('apply')"><Loader2 v-if="props.busy" :size="15" class="rotate"/><Power v-else :size="15"/>{{ props.applyLabel||t('应用变更') }}</button></div></div></Teleport>
 <AppDialog ref="dialog" class="routing-editor" :title="editingKey?t('编辑规则'):t('添加规则')" :dirty="draftDirty" close-label="取消编辑" initial-focus="input[autofocus]" @closed="abandonEditor">
  <form v-if="draft" id="routing-rule-form" @submit.prevent="commitEditor">
   <div class="routing-editor-fields">
    <label class="desk-field">{{ t('匹配类型') }}<select v-model="draft.kind" :aria-label="t('匹配类型')"><option v-for="kind in kinds" :key="kind.value" :value="kind.value">{{ kind.label }}</option></select></label>
    <label class="desk-field">{{ t('匹配值') }}<input v-model="draft.value" autofocus required maxlength="253" :placeholder="draft.kind==='PROCESS-NAME'?'com.android.chrome':draft.kind.startsWith('IP-')?'192.168.1.0/24':'example.com'" autocomplete="off"/></label>
    <template v-if="draft.kind==='PROCESS-NAME'"><label class="desk-field">{{ t('搜索已安装应用') }}<input v-model="appQuery" type="search" :placeholder="t('应用名称或包名')"/></label><p v-if="appError" class="small-explanation">{{ appError }}</p><div v-if="apps.length" class="routing-app-list"><button v-for="app in matchingApps.slice(0,100)" :key="app.package" type="button" :aria-pressed="draft.value===app.package" @click="draft.value=app.package"><img v-if="appIcon(app)" :src="appIcon(app)" alt="" class="routing-app-icon" @error="brokenIcons.add(app.package)"/><span v-else class="routing-app-badge" aria-hidden="true">{{ app.label.slice(0,1).toLocaleUpperCase() }}</span><span><strong>{{ app.label }}</strong><small>{{ app.package }}</small></span><Check v-if="draft.value===app.package" :size="16"/></button><p v-if="!matchingApps.length">{{ t('没有匹配的应用，可直接输入包名') }}</p><small v-if="matchingApps.length>100">{{ t('显示前 100 项，请搜索缩小范围') }}</small></div></template>
    <label class="desk-field">{{ t('目标出口') }}<select v-model="draft.target" :aria-label="t('目标出口')" required><option v-for="target in targets" :key="target" :value="target">{{ target }}</option></select></label>
    <label class="routing-enabled"><input v-model="draft.enabled" type="checkbox"/>{{ t('启用此规则') }}</label>
    <p v-if="draftError" class="desk-alert error" role="alert">{{ draftError }}</p>
   </div>
  </form>
  <template #footer><button type="button" class="desk-btn" @click="closeEditor">{{ t('取消') }}</button><button type="submit" form="routing-rule-form" class="desk-btn primary"><Check :size="16"/>{{ t('完成编辑') }}</button><small>{{ t('编辑后请保存并应用') }}</small></template>
 </AppDialog>
</template>
