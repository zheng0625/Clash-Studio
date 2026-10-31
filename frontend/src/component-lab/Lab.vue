<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import LayoutTools from './LayoutTools.vue'
import CanvasRulers from './CanvasRulers.vue'
import type { Selection } from './layout-editor'
import CurrentConfigCard from '../CurrentConfigCard.vue'
import SubscriptionCard from '../SubscriptionCard.vue'
import KernelControl from '../KernelControl.vue'
import ResourceMemoryView from '../ResourceMemoryView.vue'
import OverviewSelection from '../OverviewSelection.vue'
import GlassSelect from '../GlassSelect.vue'
import ListPagination from '../ListPagination.vue'
import type { ComponentId } from './catalogue'
import { catalogue, standaloneIds, androidWorkshop, workshopPath } from './platform'
import { sourceBaseline } from './source-baseline'
import { lightTheme, darkTheme } from '../theme'
import type { MemorySample } from '../memory-types'
import type { Summary } from '../types'

const layoutTools=ref<InstanceType<typeof LayoutTools>>()
const initial=new URLSearchParams(location.search).get('component')
const id=ref<ComponentId>(catalogue.find(c=>c.id===initial)?.id||'kernel')
const entry=computed(()=>catalogue.find(c=>c.id===id.value)!)
const catalogueSearch=ref('')
const groupedCatalogue=computed(()=>[...new Set(catalogue.map(c=>c.group))].map(group=>({group,items:catalogue.filter(c=>c.group===group&&(!catalogueSearch.value||(c.name+' '+c.source).toLowerCase().includes(catalogueSearch.value.toLowerCase())))})).filter(group=>group.items.length))
const scene=ref<string>(entry.value.states[0]),width=ref(480),dark=ref(false)
const view=ref(['select','pagination'].includes(id.value)?'isolated':'context'),windowWidth=ref(androidWorkshop?421:1280),frame=ref<HTMLIFrameElement>(),measuredWidth=ref(0)
const canvas=ref<HTMLElement>(),canvasWidth=ref(0),fit=ref(true)
const isolatedRoot=ref<HTMLElement>(),windowHeight=ref(androidWorkshop?927:860)
const rulerSelection=ref<Selection|null>(null),showGrid=ref(false),isolatedHeight=ref(360)
const rulerMarker=computed(()=>rulerSelection.value?{x:rulerSelection.value.canvasX,y:rulerSelection.value.canvasY,width:rulerSelection.value.width,height:rulerSelection.value.height}:null)
let isolatedObserver:ResizeObserver|undefined
watch(isolatedRoot,element=>{isolatedObserver?.disconnect();if(element){isolatedObserver=new ResizeObserver(entries=>isolatedHeight.value=entries[0].target.getBoundingClientRect().height);isolatedObserver.observe(element)}})
onUnmounted(()=>isolatedObserver?.disconnect())
function presetViewport(){if(androidWorkshop)windowHeight.value=({360:780,393:873,421:927,430:932,780:412,1024:768} as Record<number,number>)[windowWidth.value]||windowHeight.value}
function inputDimension(target:'windowWidth'|'windowHeight'|'width',event:Event){const raw=(event.target as HTMLInputElement).value,value=Number(raw);if(!raw||!Number.isFinite(value)||value<1)return;if(target==='windowWidth')windowWidth.value=Math.round(value);else if(target==='windowHeight')windowHeight.value=Math.round(value);else width.value=Math.round(value)}
function resizeViewport(event:PointerEvent){
  event.preventDefault();const handle=event.currentTarget as HTMLElement;handle.setPointerCapture(event.pointerId)
  const start={x:event.clientX,y:event.clientY,width:windowWidth.value,height:windowHeight.value,scale:scale.value}
  function move(e:PointerEvent){windowWidth.value=Math.max(1,Math.round(start.width+(e.clientX-start.x)/start.scale));windowHeight.value=Math.max(1,Math.round(start.height+(e.clientY-start.y)/start.scale))}
  function end(){handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',end);handle.removeEventListener('pointercancel',end)}
  handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',end);handle.addEventListener('pointercancel',end)
}
const contextOnly=computed(()=>!standaloneIds.includes(id.value))
const scale=computed(()=>fit.value&&canvasWidth.value?Math.min(1,(canvasWidth.value-56)/windowWidth.value):1)
let resize:ResizeObserver|undefined
watch(canvas,value=>{resize?.disconnect();if(value){resize=new ResizeObserver(entries=>canvasWidth.value=entries[0].contentRect.width);resize.observe(value)}})
onUnmounted(()=>resize?.disconnect())
const frameUrl=computed(()=>'/ui-component-frame.html?'+new URLSearchParams({component:id.value,scene:scene.value,...(androidWorkshop?{platform:'android'}:{}),...(dark.value?{theme:'dark'}:{})}).toString())
const contextAvailable=computed(()=>!['select','pagination'].includes(id.value))
const availableStates=computed(()=>view.value==='context'&&id.value==='kernel'&&!androidWorkshop?['待启动','运行中','未导入','TUN 待授权']:entry.value.states)
watch(id,()=>{view.value=contextAvailable.value?'context':'isolated'})
watch(view,()=>{if(!(availableStates.value as readonly string[]).includes(scene.value))scene.value=availableStates.value[0]})
function frameMessage(event:MessageEvent){if(event.origin!==location.origin||event.source!==frame.value?.contentWindow)return;if(event.data?.type==='clash-lab-ready'){measuredWidth.value=event.data.width;layoutTools.value?.selectTarget(entry.value.selector)};if(event.data?.type==='clash-lab-event')record(event.data.label)}
onMounted(()=>window.addEventListener('message',frameMessage))
onUnmounted(()=>window.removeEventListener('message',frameMessage))
watch(frameUrl,()=>measuredWidth.value=0)
const mode=ref('system'),routing=ref('rule'),started=ref(false),profile=ref('demo'),node=ref('香港 · 01'),choice=ref('rule'),page=ref(0)
const events=ref<string[]>([]),storageError=ref('')
type Review={locked:boolean;note:string;at:string}
const storageKey=androidWorkshop?'clash-studio-android-component-reviews-v1':'clash-studio-component-reviews-v2'
function restore():Partial<Record<ComponentId,Review>>{
  try{const data=JSON.parse(localStorage.getItem(storageKey)||'{}');return Object.fromEntries(catalogue.flatMap(c=>{const r=data?.[c.id];return r&&typeof r.locked==='boolean'&&typeof r.note==='string'&&typeof r.at==='string'?[[c.id,r]]:[]}))}
  catch{return {}}
}
const reviews=ref(restore())
const review=computed(()=>reviews.value[id.value]||{locked:false,note:'',at:''})
function record(event:string){events.value=[event,...events.value].slice(0,8)}
function saveReview(patch:Partial<Review>){
  reviews.value={...reviews.value,[id.value]:{...review.value,...patch,at:new Date().toISOString()}}
  try{localStorage.setItem(storageKey,JSON.stringify(reviews.value));storageError.value=''}catch{storageError.value='浏览器无法保存验收记录，请导出备份。'}
}
function download(){const url=URL.createObjectURL(new Blob([JSON.stringify({version:1,components:reviews.value},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='clash-studio-component-reviews.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
watch(id,()=>{scene.value=entry.value.states[0];events.value=[];const url=new URL(location.href);url.searchParams.set('component',id.value);history.replaceState(null,'',url)})
watch(scene,()=>{started.value=scene.value==='运行中';mode.value=scene.value==='TUN 待授权'?'tun':'system';routing.value='rule';profile.value='demo';node.value='香港 · 01';page.value=0})
// Paint the preview without changing the application's saved appearance or language.
function paint(){const palette=dark.value?darkTheme:lightTheme;const root=document.documentElement;for(const [key,value] of Object.entries(palette))root.style.setProperty('--client-'+key,value);root.style.setProperty('--client-sidebar-text',palette.sidebarText);root.style.setProperty('--client-accent-ink',dark.value?'#101318':'#ffffff');root.dataset.clientTheme='custom';root.style.colorScheme=dark.value?'dark':'light'}
watch(dark,paint,{immediate:true})
const ramStatus=computed(()=>scene.value==='读取失败'?'unavailable':scene.value==='部分可读'?'partial':'ok')
const memory=computed<MemorySample>(()=>({status:ramStatus.value,ram_method:'private_working_set_sum',private_working_set_status:ramStatus.value,private_working_set_total_bytes:ramStatus.value==='unavailable'?null:184.6*1024**2,total_bytes:420*1024**2,sampled_at:0,processes:['desktop','webview','service','core'].map((kind,i)=>({kind,bytes:(i+1)*18.46*1024**2,private_working_set_bytes:ramStatus.value==='unavailable'?null:(i+1)*18.46*1024**2,process_count:1,unreadable_count:0}))}))
const proxies=computed(()=>({'默认策略':{name:'默认策略',type:scene.value==='自动选择'?'URLTest':'Selector',all:['香港 · 01','日本 · 02'],now:node.value}}))
const usage=computed(()=>{if(scene.value==='无数据'||scene.value==='未导入')return null;const percent=scene.value==='即将用尽'?95:scene.value==='已用尽'?100:16;return {used:percent*2*1024**3,total:scene.value==='总量未知'?null:200*1024**3,remaining:scene.value==='总量未知'?null:(200-percent*2)*1024**3,percent:scene.value==='总量未知'?null:percent}})
const sampleProfile=computed<Summary>(()=>({id:'demo',title:'Studio · 示例订阅',source_type:'url',source_host:'example.invalid',revision:1,enabled:true,interval_minutes:60,created_at:'2026-10-30T09:00:00+08:00',updated_at:'2026-10-30T09:00:00+08:00',refreshed_at:'2026-10-30T09:00:00+08:00',last_error:'',proxy_count:4,group_count:1,rule_count:3,usage:usage.value}))
function bytes(n:number){const i=n>0?Math.min(4,Math.floor(Math.log(n)/Math.log(1024))):0;return `${(n/1024**i).toFixed(i?1:0)} ${['B','KB','MB','GB','TB'][i]}`}
function date(value:string){return new Date(value).toLocaleString()}
</script>
<template>
  <div class="lab-shell">
    <aside class="lab-sidebar">
      <a class="lab-brand" :href="workshopPath">Clash <b>Studio</b><small>{{ androidWorkshop?'ANDROID COMPONENT WORKSHOP':'COMPONENT WORKSHOP' }}</small></a>
      <p class="lab-section-label">组件 · {{ catalogue.length }}</p>
      <input v-model="catalogueSearch" class="lab-catalogue-search" aria-label="搜索页面板块" placeholder="搜索板块或组件…"><nav aria-label="组件目录"><section v-for="group in groupedCatalogue" :key="group.group"><h2 class="lab-catalogue-group">{{ group.group }}</h2><button v-for="item in group.items" :key="item.id" :class="{active:id===item.id}" :aria-current="id===item.id?'page':undefined" @click="id=item.id"><span>{{ item.name }}</span><span class="lab-state-dot" :class="{locked:reviews[item.id]?.locked}" :title="reviews[item.id]?.locked?'已确认':'打磨中'"></span></button></section></nav>
      <div class="lab-sidebar-note">默认渲染客户端原页面。<br>业务数据为本地样例。</div>
      <a class="lab-link" :href="androidWorkshop?'/ui-components.html':'/ui-android-components.html'">{{ androidWorkshop?'桌面组件工坊':'安卓组件工坊' }} ↗</a><a class="lab-link" :href="androidWorkshop?'/ui-android.html':'/ui-preview.html'">{{ androidWorkshop?'安卓主题编辑器':'打开整页预览' }} ↗</a>
    </aside>
    <main class="lab-main">
      <header class="lab-header"><div><p class="lab-section-label">CLASH STUDIO / {{ androidWorkshop?'ANDROID UI LAB':'UI LAB' }}</p><h1>{{ entry.name }}<span>{{ review.locked?'已确认':'打磨中' }}</span></h1><p>{{ entry.hint }}</p><p class="lab-source-baseline">源码基线 · {{ sourceBaseline }} · {{ androidWorkshop?'含模拟状态栏与手势安全区':'桌面正式客户端布局' }}</p></div><button class="lab-button" @click="download">导出验收记录</button></header>
      <div class="lab-toolbar"><label>查看方式<select v-model="view"><option value="context" :disabled="!contextAvailable">客户端原位</option><option value="isolated" :disabled="contextOnly">组件单独预览</option></select></label><label>状态<select v-model="scene"><option v-for="state in availableStates" :key="state">{{ state }}</option></select></label><label v-if="view==='context'">窗口宽度<select v-model.number="windowWidth" @change="presetViewport"><template v-if="androidWorkshop"><option :value="360">360 px · 小屏手机</option><option :value="393">393 px · 标准手机</option><option :value="421">421 px · 当前测试机</option><option :value="430">430 px · 大屏手机</option><option :value="780">780 px · 横屏手机</option><option :value="1024">1024 px · 平板</option></template><option v-if="!androidWorkshop" :value="720">720 px · 最小窗口</option><template v-if="!androidWorkshop"><option :value="1000">1000 px</option><option :value="1280">1280 px · 默认窗口</option><option :value="1440">1440 px</option></template></select></label><label v-else>画布宽度<select v-model.number="width"><option :value="320">320 px</option><option :value="480">480 px</option><option :value="720">720 px</option><option :value="1000">1000 px</option></select></label><label v-if="view==='context'" class="lab-check"><input v-model="fit" type="checkbox">缩放适应</label><label class="lab-check"><input v-model="dark" type="checkbox">深色背景</label></div>
      <div class="lab-free-dimensions"><label v-if="view==='context'">自定义窗口宽度<input aria-label="自定义窗口宽度" type="number" min="1" :value="windowWidth" @input="inputDimension('windowWidth',$event)"></label><label v-if="view==='context'">窗口高度<input aria-label="窗口高度" type="number" min="1" :value="windowHeight" @input="inputDimension('windowHeight',$event)"></label><label v-else>自定义画布宽度<input aria-label="自定义画布宽度" type="number" min="1" :value="width" @input="inputDimension('width',$event)"></label><label><input v-model="showGrid" type="checkbox" aria-label="显示 10 px 网格">10 px 网格</label><small>布局与文字修改对当前页面的所有状态共用。刻度单位为实际 CSS 像素；粉色虚线标出元素边界。{{ rulerSelection?'画布坐标 '+Math.round(rulerSelection.canvasX)+', '+Math.round(rulerSelection.canvasY)+' · 中心 ('+rulerSelection.centerX+', '+rulerSelection.centerY+')':'' }}</small></div><LayoutTools :storage-key="androidWorkshop?'clash-android-component-layout-v1':'clash-component-layout-v1'" ref="layoutTools" @selection="rulerSelection=$event" :frame="view==='context'?frame:undefined" :root="view==='isolated'?isolatedRoot:undefined" :surface="view" :locked="review.locked" :viewport="{width:view==='context'?windowWidth:width,height:windowHeight}" @viewport="value=>{if(view==='context')windowWidth=value.width;else width=value.width;windowHeight=value.height}"/><p class="lab-context-note" v-if="view==='context'">{{ androidWorkshop?'直接加载安卓 Client.vue 及正式移动样式；手机导航、精确分流和权限页面使用本地样例，系统授权、相机与 VPN 操作不在浏览器执行。':'直接加载当前源码的 Client.vue，保留父级布局、两列比例、Dock 与正式样式；描边标出当前组件。默认沿用此浏览器保存的外观，数据为样例，不代表正在运行的桌面实例。' }}{{ measuredWidth?'组件实际宽度：'+measuredWidth+' px':'' }}</p>
      <section v-if="view==='context'" ref="canvas" class="lab-context-canvas" aria-label="客户端原位预览"><CanvasRulers :width="windowWidth" :height="windowHeight" :scale="scale" :grid="showGrid" :marker="rulerMarker"><div class="lab-artboard-wrap" :style="{width:windowWidth*scale+'px',height:windowHeight*scale+'px'}"><iframe ref="frame" title="客户端原位预览" :src="frameUrl" :style="{width:windowWidth+'px',height:windowHeight+'px',transform:`scale(${scale})`,transformOrigin:'top left'}"></iframe><button class="lab-viewport-resize" aria-label="拖动调整画布尺寸" @pointerdown="resizeViewport">◢</button></div></CanvasRulers></section>
      <section v-else class="lab-canvas" aria-label="组件预览"><CanvasRulers :width="width" :height="isolatedHeight" :grid="showGrid" :marker="rulerMarker"><div ref="isolatedRoot" class="lab-preview desk" data-ui-page="home" :style="{width:width+'px'}" :key="id+'-'+scene">
        <KernelControl v-if="id==='kernel'" :runtime="{running:started,active:{title:'Studio · 示例订阅'},proxy:{supported:true},tun:{supported:true,admin:scene!=='TUN 待授权'},routing_mode:routing}" :proxy-mode="mode" :busy="scene==='应用中'?'apply':''" :needs-apply="scene==='待应用'" :apply-failed="false" :editor-dirty="false" :selected="scene==='未导入'?'':'demo'" :native-core-unavailable="false" :runtime-ready="true" :is-android="scene==='安卓 VPN'" :native-development="true" :validation-build="false" :apply-label="started?'重新应用':'启动'" @mode="value=>{mode=value;record('接管模式 → '+value)}" @routing="value=>{routing=value;record('分流模式 → '+value)}" @apply="started=true;record('启动 / 应用（示例）')" @stop="started=false;record('停止（示例）')" @settings="record('打开更多设置')" @proxies="record('选择出口')" @elevate="record('申请权限（示例）')"/>
        <ResourceMemoryView v-else-if="id==='memory'" :sample="memory" :failed="ramStatus==='unavailable'" private-label="私有提交合计" :private-working="true" :ram-bytes="memory.private_working_set_total_bytes" :ram-status="ramStatus" @retry="record('重试内存读取（示例）')"/>
        <OverviewSelection v-else-if="id==='selection'" :profiles="scene==='未导入'?[]:[{id:'demo',title:'Studio · 示例订阅'},{id:'work',title:'工作专线'}]" :selected="scene==='未导入'?'':profile" :proxies="scene==='未导入'?{}:proxies" :busy="false" :loading="scene==='加载中'" :live="true" :running="true" :mode="scene==='直连'?'direct':'rule'" status="" :error="scene==='读取失败'?'暂时无法读取策略组':''" :has-providers="false" @choose="value=>{profile=value;record('方案 → '+value)}" @select="(_group,name)=>{node=name;record('节点 → '+name)}" @retry="record('重试策略组读取')" @proxies="record('打开代理页')"/>
        <CurrentConfigCard v-else-if="id==='config'" :current="scene==='未导入'?null:sampleProfile" :bytes="bytes" :date="date" @edit="record('编辑配置 / 导入订阅')"/>
        <div v-else-if="id==='usage'" class="profile-grid"><SubscriptionCard :p="sampleProfile" selected="demo" busy="" :date="date" @choose="record('选择配置')" @refresh="record('刷新订阅')" @delete="record('删除订阅（示例）')"/></div>
        <div v-else-if="id==='select'" class="desk-card"><GlassSelect v-model="choice" label="示例分流模式" :options="[{value:'rule',label:scene==='长文本'?'工作专线 · 面向跨区域协作的默认分流策略与备用出口':'规则模式'},{value:'global',label:'全局模式'},{value:'direct',label:'直连模式'}]" @update:model-value="record('下拉选择 → '+$event)"/></div>
        <div v-else class="desk-card"><p>分页展示 · {{ scene==='单页'?'只有一页时自动隐藏分页':'点击上一页 / 下一页查看边界状态' }}</p><ListPagination v-model="page" :pages="scene==='单页'?1:5" :page-size="100" label="示例列表分页" @update:model-value="record('页码 → '+($event+1))"/></div>
      </div></CanvasRulers></section>
      <div class="lab-bottom"><section class="lab-panel"><h2>交互记录</h2><p v-if="!events.length">操作组件后，事件会显示在这里。</p><ol v-else><li v-for="(event,index) in events" :key="index">{{ event }}</li></ol><code>src/{{ entry.source }}</code></section><section class="lab-panel"><h2>验收与锁定</h2><p>确认代表本浏览器的验收标记；源码仍需在后续修改时遵守约定。</p><label>打磨备注<textarea :value="review.note" :readonly="review.locked" placeholder="记录间距、排版、状态与下一步调整…" @input="saveReview({note:($event.target as HTMLTextAreaElement).value})"></textarea></label><button class="lab-button" @click="saveReview({locked:!review.locked})">{{ review.locked?'解锁，继续打磨':'确认满意并锁定' }}</button><small v-if="review.at">上次记录：{{ new Date(review.at).toLocaleString() }}</small><p v-if="storageError" role="alert">{{ storageError }}</p></section></div>
    </main>
  </div>
</template>
