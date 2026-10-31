<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Activity, ArrowDownLeft, ArrowUpRight, ArrowRight, Check, ChevronDown, ChevronLeft, ChevronRight, Copy, FileCode2, FolderOpen, GitBranch, Globe2, LayoutDashboard, Layers3, Loader2, MemoryStick, Moon, Plus, Power, RefreshCw, Search, Settings2, ShieldCheck, Sun, Upload, X, Zap } from 'lucide-vue-next'
import brand from '../assets/brand.svg'

type Page = 'home'|'subscriptions'|'modules'|'proxies'|'connections'|'studio'|'settings'
type Node = {name:string;region:string;type:string;delay:number}
type Profile = {id:string;name:string;used:number;total:number;updated:string;nodes:Node[]}
type Module = {id:number;name:string;description:string;target:string;strict:boolean;enabled:boolean}
const nav = [
  {id:'home' as Page,label:'概览',icon:LayoutDashboard},{id:'subscriptions' as Page,label:'订阅',icon:FolderOpen},
  {id:'modules' as Page,label:'模块分流',icon:Layers3},{id:'proxies' as Page,label:'代理',icon:Globe2},
  {id:'connections' as Page,label:'连接',icon:Activity},{id:'studio' as Page,label:'配置工作台',icon:FileCode2},{id:'settings' as Page,label:'设置与日志',icon:Settings2},
]
const windowed=new URLSearchParams(location.search).has('windowed')
const page=ref<Page>('home'),dark=ref(false),photo=ref(true),larger=ref(false)
const title=computed(()=>nav.find(n=>n.id===page.value)!.label)
const captions:Record<Page,string>={home:'选择方案，管理接管与流量。',subscriptions:'在本机整理订阅与个人配置。',modules:'按顺序组合分流规则，为流量指定出口。',proxies:'选择节点，查看延迟与策略组。',connections:'查看当前流量的规则与出口。',studio:'编辑节点、策略组与规则。',settings:'调整外观与连接偏好。'}
const makeNodes=(offset=0):Node[]=>[
  {name:'香港 · 01',region:'香港',type:'Shadowsocks',delay:32+offset}, {name:'香港 · 02',region:'香港',type:'Trojan',delay:46+offset},
  {name:'日本 · 东京 01',region:'日本',type:'VMess',delay:68+offset},{name:'日本 · 东京 02',region:'日本',type:'Trojan',delay:75+offset},
  {name:'新加坡 · 01',region:'新加坡',type:'Shadowsocks',delay:89+offset},{name:'新加坡 · 02',region:'新加坡',type:'Trojan',delay:102+offset},
  {name:'美国 · 洛杉矶 01',region:'美国',type:'Shadowsocks',delay:168+offset},{name:'美国 · 圣何塞高速线路 02',region:'美国',type:'VMess',delay:186+offset},
]
const seedProfiles:Profile[]=[
  {id:'daily',name:'日常使用',used:32.8,total:200,updated:'今天 09:42',nodes:makeNodes()},
  {id:'work',name:'工作专线',used:18.2,total:100,updated:'今天 08:30',nodes:makeNodes(12).filter(n=>n.region!=='美国')},
  {id:'backup',name:'备用订阅',used:4.6,total:50,updated:'昨天 21:16',nodes:makeNodes(30).slice(0,4)},
]
const emptyStart=new URLSearchParams(location.search).get('empty')==='1'
const profiles=ref<Profile[]>(emptyStart?[]:seedProfiles.map(p=>({...p,nodes:[...p.nodes]})))
const hasProfiles=computed(()=>profiles.value.length>0)
function previewScenario(event:Event){const empty=(event.target as HTMLSelectElement).value==='empty';profiles.value=empty?[]:seedProfiles.map(p=>({...p,nodes:[...p.nodes]}));selected.value=empty?'':'daily';active.value=selected.value;running.value=!empty}
const selected=ref(emptyStart?'':'daily'),active=ref(emptyStart?'':'daily'),running=ref(!emptyStart),busy=ref(false),takeover=ref('system'),routing=ref('rule'),group=ref(emptyStart?'':'手动选择')
const chosen=ref<Record<string,string>>({}),current=computed<Profile>(()=>profiles.value.find(p=>p.id===selected.value)||{id:'',name:'未导入订阅',used:0,total:0,updated:'—',nodes:[]})
const activeProfile=computed(()=>profiles.value.find(p=>p.id===active.value))
const groups=['手动选择','自动选择','流媒体']
const automatic=computed(()=>group.value==='自动选择')
const availableNodes=computed(()=>group.value==='流媒体'?current.value.nodes.filter(n=>['日本','新加坡'].includes(n.region)):current.value.nodes)
const nodeKey=computed(()=>selected.value+':'+group.value)
const currentNode=computed(()=>chosen.value[nodeKey.value]||availableNodes.value[0]?.name||'暂无节点')
const pending=computed(()=>running.value&&active.value!==selected.value)
const memoryParts=computed(()=>[{name:'界面进程',value:68.4},{name:'本地服务',value:42.8},{name:'代理内核',value:running.value?36.2:0}])
const memoryTotal=computed(()=>memoryParts.value.reduce((sum,p)=>sum+p.value,0).toFixed(1))
const selectionNote=computed(()=>!hasProfiles.value?'先导入订阅':routing.value==='direct'?'直连模式不使用代理节点':pending.value?'待应用':!running.value?'下次启动使用':automatic.value?'自动选择最低延迟节点':'')
const toast=ref('');let toastTimer:ReturnType<typeof setTimeout>|undefined
const timers=new Set<ReturnType<typeof setTimeout>>()
function later(fn:()=>void,ms:number){const timer=setTimeout(()=>{timers.delete(timer);fn()},ms);timers.add(timer)}
function notify(text:string){toast.value=text;clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.value='',3200)}
function go(id:Page){page.value=id;if(windowed)document.querySelector('main')?.scrollTo({top:0,behavior:'instant'});else window.scrollTo({top:0,behavior:'instant'})}
function selectNode(name:string,whichGroup=group.value){if(whichGroup==='自动选择'||routing.value==='direct')return;chosen.value[selected.value+':'+whichGroup]=name;notify(pending.value||!running.value?'已记住选择，下次应用使用':'已切换至 '+name)}
function apply(){if(busy.value)return;const profileId=selected.value;busy.value=true;later(()=>{active.value=profileId;moduleDirty.value[profileId]=false;running.value=true;busy.value=false;notify('方案已应用 · 演示操作')},650)}
function stop(){if(busy.value)return;running.value=false;notify('已停止 · 演示操作')}
watch(selected,()=>{group.value=selected.value?'手动选择':'';modulePage.value=0})

const moduleSeeds=[
  {name:'AI 服务',description:'ChatGPT、Claude 等服务',target:'手动选择',strict:true},
  {name:'流媒体',description:'视频与音乐服务',target:'流媒体',strict:false},
  {name:'开发工具',description:'GitHub 与软件包下载',target:'自动选择',strict:false},
  {name:'即时通讯',description:'通讯与消息服务',target:'手动选择',strict:true},
  {name:'云服务',description:'云端文件与协作',target:'自动选择',strict:false},
  {name:'海外网站',description:'其余境外域名',target:'手动选择',strict:false},
  {name:'游戏服务',description:'游戏商店与更新',target:'自动选择',strict:false},
]
const moduleSets=ref<Record<string,Module[]>>(Object.fromEntries(seedProfiles.map((p,i)=>[p.id,moduleSeeds.map((m,k)=>({...m,id:k,enabled:k<(i===0?5:i===1?3:0)}))])))
const modules=computed(()=>moduleSets.value[selected.value]||[]),enabledModules=computed(()=>modules.value.filter(m=>m.enabled))
const modulePage=ref(0),modulePages=computed(()=>Math.max(1,Math.ceil(enabledModules.value.length/3)))
const visibleModules=computed(()=>enabledModules.value.slice(modulePage.value*3,modulePage.value*3+3))
watch(modulePages,n=>modulePage.value=Math.min(modulePage.value,n-1))
const moduleDirty=ref<Record<string,boolean>>({})
function toggleModule(m:Module){m.enabled=!m.enabled;moduleDirty.value[selected.value]=true;notify('模块组合已保存，应用后生效')}
const networkBusy=ref(false),networkError=ref(false)
function refreshNetwork(){if(networkBusy.value)return;networkBusy.value=true;later(()=>{networkBusy.value=false;notify(networkError.value?'检测失败示例：请重试':'示例网络信息已刷新')},600)}
const ip=computed(()=>running.value?'198.51.100.24':'192.0.2.18')
async function copyIp(){try{await navigator.clipboard.writeText(ip.value);notify('IP 已复制')}catch{notify('复制不可用，请手动选择 IP')}}
const searching=ref(''),sort=ref('original'),compact=ref(false),folded=ref<Record<string,boolean>>({}),testing=ref(false)
const proxyGroups=computed(()=>groups.map(name=>({name,nodes:current.value.nodes.filter(n=>name!=='流媒体'||['日本','新加坡'].includes(n.region))})))
function visibleNodes(nodes:Node[]){const list=nodes.filter(n=>n.name.toLowerCase().includes(searching.value.toLowerCase()));return sort.value==='delay'?[...list].sort((a,b)=>a.delay-b.delay):list}
function benchmark(){if(testing.value)return;testing.value=true;later(()=>{current.value.nodes.forEach(n=>n.delay=Math.max(12,n.delay+Math.round(Math.random()*14-7)));testing.value=false;notify('示例测速完成')},800)}
const importDialog=ref<HTMLDialogElement|null>(null),importType=ref('url'),importName=ref(''),importUrl=ref(''),importYaml=ref(''),importError=ref(''),importFileName=ref('')
function openImport(){importError.value='';importDialog.value?.showModal()}
function closeImport(){importDialog.value?.close()}
async function readFile(event:Event){const file=(event.target as HTMLInputElement).files?.[0];if(!file)return;if(file.size>1024*1024){importError.value='预览文件请小于 1 MB';return}importYaml.value=await file.text();importFileName.value=file.name;if(!importName.value)importName.value=file.name.replace(/\.ya?ml$/i,'')}
function importProfile(){
  importError.value=''
  if(!importName.value.trim()){importError.value='请填写名称';return}
  if(importType.value==='url'){try{const u=new URL(importUrl.value);if(!['https:','http:'].includes(u.protocol))throw Error()}catch{importError.value='请输入有效的 HTTP 或 HTTPS 链接';return}}
  else if(!importYaml.value.trim()){importError.value='请选择文件或粘贴 YAML';return}
  const id='demo-'+Date.now();profiles.value.push({id,name:importName.value.trim(),used:0,total:100,updated:'刚刚',nodes:makeNodes(5)})
  moduleSets.value[id]=moduleSeeds.map((m,k)=>({...m,id:k,enabled:false}));selected.value=id;closeImport();page.value='subscriptions';importName.value='';importUrl.value='';importYaml.value='';importFileName.value='';notify('已添加演示订阅，未访问链接或导入真实节点')
}
const connections=ref(Array.from({length:8},(_,i)=>({id:i,host:['api.openai.com','github.com','www.youtube.com','cdn.jsdelivr.net','music.apple.com','www.wikipedia.org','registry.npmjs.org','telegram.org'][i]!,process:i===6?'node.exe':'浏览器',rule:i===0?'AI 服务':i===2?'流媒体':'规则匹配',down:['2.4 MB','846 KB','12.6 MB','324 KB','3.1 MB','76 KB','5.2 MB','148 KB'][i]!})))
const connectionSearch=ref(''),filteredConnections=computed(()=>connections.value.filter(c=>c.host.includes(connectionSearch.value)))
const editorTab=ref('nodes'),draft=ref('# 示例配置，仅保存在本次预览中\nmode: rule\nmixed-port: 17890\nproxies: []\nrules:\n  - MATCH,手动选择\n'),editorSaved=ref(true)
const settingsPort=ref(17890),allowLan=ref(false),dnsProtected=ref(false)
function saveSettings(){notify('预览偏好已保存到本次会话')}
const flowPoints='0,60 15,58 30,64 45,40 60,46 75,34 90,44 105,22 120,35 135,30 150,38 165,12 180,24 195,18 210,38 225,34 240,48 255,26 270,31 285,14 300,27 315,19 330,35 345,29 360,39 375,21 390,34 405,18 420,26 435,12 450,24 465,18 480,30'
onUnmounted(()=>{clearTimeout(toastTimer);timers.forEach(clearTimeout)})
</script>

<template>
  <div class="proposal" :class="{dark,photo,larger,windowed}">
    <header class="topbar">
      <button class="brand" @click="go('home')" aria-label="Clash Studio 返回概览"><img :src="brand" alt=""><span>Clash <b>Studio</b></span></button>
      <div class="breadcrumb">工作空间 <ChevronRight :size="14"/><span>{{ title }}</span></div>
      <div class="top-actions"><span class="preview-label">UI 预览 <span>· 示例数据</span></span><button class="icon-button" @click="dark=!dark" :aria-label="dark?'切换浅色主题':'切换深色主题'"><Sun v-if="dark" :size="18"/><Moon v-else :size="18"/></button></div>
    </header>

    <main>
      <div class="page-heading"><div><h1>{{ title }}</h1><p>{{ captions[page] }}</p></div><div class="actions"><label v-if="page==='home'" class="scenario-select"><span>预览场景</span><select :value="hasProfiles?'ready':'empty'" aria-label="预览订阅状态" @change="previewScenario"><option value="ready">已导入订阅</option><option value="empty">未导入订阅</option></select></label><button v-if="page==='home'" class="button" @click="refreshNetwork"><RefreshCw :size="15" :class="{spin:networkBusy}"/>刷新</button><button v-if="page==='home'||page==='subscriptions'" class="button" :class="{primary:page==='subscriptions'}" @click="openImport"><Plus :size="17"/>导入订阅</button><label v-if="['modules','proxies','studio'].includes(page)" class="inline-field">方案<select v-model="selected" aria-label="当前页面方案"><option v-for="p in profiles" :value="p.id" :key="p.id">{{ p.name }}</option></select></label></div></div>

      <template v-if="page==='home'">
        <div class="overview-grid">
          <div class="overview-column overview-left">
            <section class="card control-card"><div class="card-heading"><h2>内核与接管</h2><button class="text-button" @click="go('settings')">更多设置 <ChevronRight :size="14"/></button></div>
            <div class="takeover" role="group" aria-label="接管模式"><button :aria-pressed="takeover==='system'" @click="takeover='system'"><Globe2 :size="18"/>系统代理<Check v-if="takeover==='system'" :size="15"/></button><button :aria-pressed="takeover==='tun'" @click="takeover='tun'"><ShieldCheck :size="18"/>TUN 模式<Check v-if="takeover==='tun'" :size="15"/></button></div>
            <div class="routing-row"><span>分流模式</span><div class="segments" role="group" aria-label="分流模式"><button v-for="m in [{id:'rule',name:'规则'},{id:'global',name:'全局'},{id:'direct',name:'直连'}]" :key="m.id" :aria-pressed="routing===m.id" @click="routing=m.id">{{ m.name }}</button></div></div>
            <div class="control-bottom"><div class="actions"><button class="button primary" :disabled="busy||!hasProfiles" @click="apply"><Loader2 v-if="busy" :size="16" class="spin"/><Power v-else :size="16"/>{{ busy?'正在应用…':!running?'启动':pending||moduleDirty[selected]?'应用变更':'重新应用' }}</button><button v-if="running" class="button stop" :disabled="busy" @click="stop">停止</button></div><span v-if="pending" class="muted">运行：{{ activeProfile?.name }}</span><span v-else class="muted">{{ takeover==='tun'?'TUN':'HTTP / SOCKS' }} · 17890</span></div>
          </section>
            <section class="card traffic-card"><div class="card-heading"><h2>实时速率</h2><button class="text-button" @click="go('connections')">{{ running?connections.length:0 }} 个连接 <ChevronRight :size="14"/></button></div><div class="traffic-numbers"><div><span><ArrowDownLeft :size="15"/>下载</span><strong>{{ running?'12.64':'—' }} <small v-if="running">MB/s</small></strong></div><div><span><ArrowUpRight :size="15"/>上传</span><strong>{{ running?'826':'—' }} <small v-if="running">KB/s</small></strong></div><div class="traffic-chart"><svg viewBox="0 0 480 82" preserveAspectRatio="none" aria-label="演示速率趋势" role="img"><defs><linearGradient id="flow-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--accent)" stop-opacity=".2"/><stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></linearGradient></defs><path v-if="running" :d="'M0,82 L'+flowPoints.replaceAll(' ',' L')+' L480,82 Z'" fill="url(#flow-fill)"/><polyline v-if="running" :points="flowPoints" fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke"/><path v-else d="M0 65H480" stroke="var(--border)"/></svg><span>最近 60 秒</span></div></div><div class="card-foot"><span>本次累计 <b>2.84 GB</b></span><span>↓ 2.61 GB <span class="dot-separator">·</span> ↑ 236 MB</span></div><details class="traffic-details"><summary>流量详情与趋势<ChevronDown :size="14"/></summary><div class="traffic-detail-body"><div class="trend-caption"><span>下载与上传速率</span><span>最近 60 秒 · 示例</span></div><svg viewBox="0 0 480 95" preserveAspectRatio="none" role="img" aria-label="演示流量详情趋势"><path d="M0 20H480 M0 50H480 M0 80H480" stroke="var(--border)" stroke-dasharray="3 4"/><polyline v-if="running" :points="flowPoints" fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke"/><path v-else d="M0 80H480" stroke="var(--muted)"/></svg><div class="trend-caption"><span>60 秒前</span><span>现在</span></div></div></details></section>
            <section class="card profile-summary" :class="{'profile-empty':!hasProfiles}"><div class="card-heading"><h2>当前配置</h2><button class="text-button" @click="hasProfiles?go('studio'):openImport()">{{ hasProfiles?'编辑配置':'导入订阅' }}<ArrowUpRight v-if="hasProfiles" :size="14"/><Plus v-else :size="14"/></button></div><div class="profile-title"><span class="square-icon"><FolderOpen :size="20"/></span><div><h3>{{ hasProfiles?current.name:'未导入订阅' }}</h3><span class="muted">{{ hasProfiles?'更新于'+current.updated:'添加订阅链接或 YAML 文件' }}</span></div><span class="usage-total">{{ hasProfiles?current.used:'—' }} <small>/ {{ hasProfiles?current.total:'—' }} GB</small></span></div><div class="usage-track"><span :style="{width:hasProfiles?current.used/current.total*100+'%':'0%'}"></span></div><div class="card-foot"><span>{{ hasProfiles?'已用 '+(current.used/current.total*100).toFixed(1)+'%':'等待导入' }}</span><span>{{ current.nodes.length }} 个节点 <span class="dot-sepa"></span>· {{ hasProfiles?3:0 }} 个策略组</span></div></section>
          </div>
          <div class="overview-column overview-right">
            <section class="card memory-card" aria-label="软件内存占用"><div class="memory-reading"><h2><MemoryStick :size="18"/>内存占用</h2><div><strong>{{ memoryTotal }} <small>MB</small></strong><span class="memory-demo">示例</span></div></div><details class="memory-details"><summary>RAM · 进程明细<ChevronDown :size="13"/></summary><div class="memory-processes"><div v-for="part in memoryParts" :key="part.name" class="memory-process"><span>{{ part.name }}</span><b>{{ part.value.toFixed(1) }} MB</b></div><p>软件进程合计，不是整机内存。预览示例值，尚未连接实际采样。</p></div></details></section>
            <section class="card selection-card"><div class="card-heading"><h2>方案选择</h2><span v-if="selectionNote||moduleDirty[selected]" class="tag" :class="{warning:pending||moduleDirty[selected]}">{{ moduleDirty[selected]?'模块变更待应用':selectionNote }}</span><span v-else class="muted">快捷切换</span></div>
            <label class="selection-field"><span>方案</span><select v-model="selected" :disabled="busy||!hasProfiles" aria-label="方案"><option v-if="!hasProfiles" value="">先导入订阅</option><option v-for="p in profiles" :value="p.id" :key="p.id">{{ p.name }}</option></select></label>
            <label class="selection-field"><span>策略组</span><select v-model="group" :disabled="busy||!hasProfiles||routing==='direct'" aria-label="策略组"><option v-if="!hasProfiles" value="">暂无策略组</option><option v-for="g in groups" :key="g">{{ g }}</option></select></label>
            <label class="selection-field"><span>节点</span><select :value="currentNode" :disabled="busy||!hasProfiles||automatic||routing==='direct'" aria-label="节点" @change="selectNode(($event.target as HTMLSelectElement).value)"><option v-if="!hasProfiles" value="暂无节点">暂无节点</option><option v-for="n in availableNodes" :value="n.name" :key="n.name">{{ n.name }}{{ automatic?' · 自动':'' }}</option></select></label>
          </section>
            <section class="card ip-card"><div class="card-heading"><h2>网络出口</h2><button class="text-button" :disabled="networkBusy" @click="refreshNetwork"><RefreshCw :size="14" :class="{spin:networkBusy}"/>{{ networkBusy?'检测中':'重新检测' }}</button></div><div class="network-row"><span>IP</span><div class="ip-value"><strong>{{ networkBusy?'查询中…':networkError?'未获取':ip }}</strong><button class="icon-button" :disabled="networkBusy||networkError" @click="copyIp" aria-label="复制 IP"><Copy :size="15"/></button></div></div><div class="network-row"><span>地址</span><b>{{ networkBusy?'查询中…':networkError?'未获取':running?'日本 · 东京':'中国 · 上海' }}</b></div><div class="network-row"><span>IP 属性</span><div class="ip-properties"><template v-if="!networkBusy&&!networkError"><span>{{ running?'机房 IP':'住宅 IP' }}</span><span>原生 IP</span></template><b v-else>{{ networkBusy?'查询中…':'未获取' }}</b></div></div><p v-if="networkError" class="error-message">检测未完成，请重新检测。</p></section>
            <section class="card module-summary"><div class="card-heading"><h2>已启用模块 <span class="count">{{ enabledModules.length }}</span></h2><button class="text-button" @click="go('modules')">管理 <ChevronRight :size="14"/></button></div><div v-if="!enabledModules.length" class="small-empty">当前方案未启用模块 <button class="text-button" @click="go('modules')">添加模块 <Plus :size="14"/></button></div><div v-for="m in visibleModules" :key="m.id" class="module-row"><span class="module-name"><span class="module-dot"></span>{{ m.name }}<ShieldCheck v-if="m.strict" :size="13" class="muted" aria-label="严格出口"/></span><span class="module-target">{{ m.target }}<ArrowRight :size="13"/></span></div><div v-if="modulePages>1" class="pagination"><span>每页 3 项</span><div><button class="icon-button" aria-label="上一页模块" :disabled="modulePage===0" @click="modulePage--"><ChevronLeft :size="16"/></button><span>{{ modulePage+1 }} / {{ modulePages }}</span><button class="icon-button" aria-label="下一页模块" :disabled="modulePage===modulePages-1" @click="modulePage++"><ChevronRight :size="16"/></button></div></div></section>
          </div>
        </div>
      </template>

      <template v-else-if="page==='subscriptions'">
        <div class="section-line"><span>{{ profiles.length }} 份订阅</span><span>订阅与修改记录保存在本机</span></div><div class="subscription-grid"><article v-for="p in profiles" :key="p.id" class="card subscription-card" :class="{selected:p.id===selected}"><div class="card-heading"><span class="square-icon"><FolderOpen :size="20"/></span><span v-if="p.id===selected" class="tag"><Check :size="12"/>已选择</span></div><h2>{{ p.name }}</h2><p class="muted">示例订阅 <span class="dot-separator">·</span> {{ p.nodes.length }} 个节点</p><div class="subscription-usage"><b>{{ p.used }} GB</b><span>/ {{ p.total }} GB</span></div><div class="usage-track"><span :style="{width:p.used/p.total*100+'%'}"></span></div><div class="section-line"><span>{{ p.updated }}更新</span><span>剩余 {{ (p.total-p.used).toFixed(1) }} GB</span></div><div class="subscription-actions"><button class="button" :class="{primary:p.id!==selected}" @click="selected=p.id;notify('已选择 '+p.name)">{{ p.id===selected?'当前方案':'选择方案' }}</button><button class="icon-button" aria-label="刷新订阅" @click="p.updated='刚刚';notify('示例订阅已刷新')"><RefreshCw :size="16"/></button><button class="icon-button" aria-label="编辑订阅" @click="selected=p.id;go('studio')"><FileCode2 :size="16"/></button></div></article><button class="add-subscription" @click="openImport"><Plus :size="25"/><b>导入新的订阅</b><span>订阅链接或 YAML 文件</span></button></div>
      </template>

      <template v-else-if="page==='proxies'">
        <div class="proxy-toolbar"><label class="search"><Search :size="17"/><input v-model="searching" placeholder="搜索节点名称" aria-label="搜索节点名称"></label><select v-model="sort" aria-label="节点排序"><option value="original">原始顺序</option><option value="delay">延迟优先</option></select><button class="button" @click="compact=!compact">{{ compact?'卡片视图':'紧凑视图' }}</button><button class="button" :disabled="testing" @click="benchmark"><Loader2 v-if="testing" :size="15" class="spin"/><Zap v-else :size="15"/>{{ testing?'测速中…':'全部测速' }}</button></div>
        <section v-for="g in proxyGroups" :key="g.name" class="card proxy-group"><div class="card-heading"><button class="group-heading" :aria-expanded="!folded[g.name]" @click="folded[g.name]=!folded[g.name]"><ChevronDown :size="18" :class="{folded:folded[g.name]}"/><span><h2>{{ g.name }}</h2><span class="muted">{{ g.name==='自动选择'?'自动策略':'手动选择' }} <span class="dot-separator">·</span> {{ chosen[selected+':'+g.name]||g.nodes[0]?.name }}</span></span></button><span class="muted">{{ g.nodes.length }} 个成员</span></div><div v-if="!folded[g.name]" class="node-grid" :class="{compact}"><article v-for="n in visibleNodes(g.nodes)" :key="n.name" class="node" :class="{picked:(chosen[selected+':'+g.name]||g.nodes[0]?.name)===n.name}"><button class="node-select" :disabled="g.name==='自动选择'||routing==='direct'" :aria-pressed="(chosen[selected+':'+g.name]||g.nodes[0]?.name)===n.name" :title="n.name" @click="selectNode(n.name,g.name)"><span><strong>{{ n.name }}</strong><small>{{ n.type }}</small></span><Check v-if="(chosen[selected+':'+g.name]||g.nodes[0]?.name)===n.name" :size="16"/></button><div class="node-bottom"><span>{{ g.name==='自动选择'?'自动选择':'HTTP 延迟' }}</span><button class="latency" :class="{medium:n.delay>150}" :disabled="testing" @click="benchmark">{{ testing?'检测中':n.delay+' ms' }}</button></div></article></div><p v-if="!folded[g.name]&&!visibleNodes(g.nodes).length" class="small-empty">没有匹配的节点</p></section>
      </template>

      <template v-else-if="page==='modules'">
        <div class="section-line"><span>已启用 {{ enabledModules.length }} / {{ modules.length }} 个模块</span><button class="text-button" @click="apply();moduleDirty[selected]=false">应用组合 <ArrowRight :size="14"/></button></div><div class="module-grid"><article v-for="m in modules" :key="m.id" class="card module-card"><div class="card-heading"><span class="square-icon"><GitBranch :size="19"/></span><button class="switch" role="switch" :aria-checked="m.enabled" :aria-label="m.name" @click="toggleModule(m)"><span></span></button></div><h2>{{ m.name }}</h2><p>{{ m.description }}</p><div class="module-card-foot"><span><ArrowRight :size="14"/>{{ m.target }}</span><span v-if="m.strict" class="tag"><ShieldCheck :size="12"/>严格出口</span></div></article></div><p class="page-note">模块按顺序匹配，规则优先于源订阅。变更在应用后生效。</p>
      </template>

      <template v-else-if="page==='connections'">
        <div class="proxy-toolbar"><label class="search"><Search :size="17"/><input v-model="connectionSearch" placeholder="搜索域名" aria-label="搜索连接"></label><span class="muted">{{ connections.length }} 个演示连接</span></div><div class="card table-card"><div class="table-scroll"><table><thead><tr><th>目标地址</th><th>进程</th><th>匹配规则</th><th>下载</th><th>操作</th></tr></thead><tbody><tr v-for="c in filteredConnections" :key="c.id"><td><b>{{ c.host }}</b><small>TCP · 443</small></td><td>{{ c.process }}</td><td>{{ c.rule }}</td><td>{{ c.down }}</td><td><button class="icon-button" :aria-label="'关闭 '+c.host" @click="connections=connections.filter(x=>x.id!==c.id);notify('演示连接已关闭')"><X :size="16"/></button></td></tr></tbody></table><p v-if="!filteredConnections.length" class="small-empty">没有匹配的连接</p></div></div>
      </template>

      <template v-else-if="page==='studio'">
        <section class="card"><div class="card-heading"><div class="segments editor-tabs"><button v-for="tab in [{id:'nodes',label:'节点'},{id:'groups',label:'策略组'},{id:'rules',label:'规则'},{id:'yaml',label:'YAML'}]" :key="tab.id" :aria-pressed="editorTab===tab.id" @click="editorTab=tab.id">{{ tab.label }}</button></div><button class="button primary" @click="editorSaved=true;notify('演示配置已保存，正式配置未改变')">{{ editorSaved?'保存配置':'保存修改' }}</button></div><textarea v-if="editorTab==='yaml'" v-model="draft" class="yaml-editor" spellcheck="false" aria-label="YAML 示例编辑器" @input="editorSaved=false"></textarea><div v-else-if="editorTab==='nodes'" class="editor-list"><div v-for="n in current.nodes" :key="n.name"><span>{{ n.name }}</span><span class="muted">{{ n.type }}</span><input type="checkbox" checked :aria-label="'启用 '+n.name" @change="editorSaved=false"></div></div><div v-else-if="editorTab==='groups'" class="editor-list"><div v-for="g in groups" :key="g"><b>{{ g }}</b><span class="muted">{{ g==='自动选择'?'url-test':'select' }}</span><span>{{ current.nodes.length }} 个节点</span></div></div><div v-else class="editor-list"><div v-for="rule in ['DOMAIN-SUFFIX,openai.com,手动选择','DOMAIN-SUFFIX,youtube.com,流媒体','GEOIP,CN,DIRECT','MATCH,手动选择']" :key="rule"><code>{{ rule }}</code></div></div></section>
      </template>

      <template v-else-if="page==='settings'">
        <div class="settings-grid"><section class="card"><div class="card-heading"><h2>外观</h2><Sun :size="18" class="muted"/></div><div class="setting-row"><div><b>深色主题</b><small>在浅色与深色之间切换</small></div><button class="switch" role="switch" :aria-checked="dark" aria-label="深色主题" @click="dark=!dark"><span></span></button></div><div class="setting-row"><div><b>柔和背景</b><small>查看半透明卡片的层次</small></div><button class="switch" role="switch" :aria-checked="photo" aria-label="柔和背景" @click="photo=!photo"><span></span></button></div><div class="setting-row"><div><b>增大正文</b><small>对比 15 px 与 16 px 字号</small></div><button class="switch" role="switch" :aria-checked="larger" aria-label="增大正文" @click="larger=!larger"><span></span></button></div></section><section class="card"><div class="card-heading"><h2>连接偏好</h2><Globe2 :size="18" class="muted"/></div><div class="setting-row"><label for="preview-port"><b>代理端口</b><small>本次预览中的示例参数</small></label><input id="preview-port" v-model="settingsPort" type="number" min="1024" max="65535" class="port-input"></div><div class="setting-row"><div><b>允许局域网连接</b><small>仅演示开关交互</small></div><button class="switch" role="switch" :aria-checked="allowLan" aria-label="允许局域网连接" @click="allowLan=!allowLan"><span></span></button></div><div class="setting-row"><div><b>DNS 防泄漏</b><small>仅演示 DNS 防泄漏开关</small></div><button class="switch" role="switch" :aria-checked="dnsProtected" aria-label="DNS 防泄漏" @click="dnsProtected=!dnsProtected"><span></span></button></div></section><section class="card preview-settings"><div><h2>预览场景</h2><p>交互与网络信息均为示例，不连接本地代理服务。</p></div><label class="checkbox-label"><input v-model="networkError" type="checkbox">模拟网络检测失败</label><button class="button" @click="saveSettings">保存预览偏好</button></section></div>
      </template>
      <footer class="preview-foot"><span>Clash Studio <span class="dot-separator">·</span> UI 优化方案预览</span><a href="/ui-preview.html" target="_blank" rel="noopener">查看原版布局 <ArrowUpRight :size="12"/></a></footer>
    </main>

    <nav class="dock-shell" aria-label="主导航"><div class="dock"><button v-for="n in nav" :key="n.id" :aria-current="page===n.id?'page':undefined" @click="go(n.id)"><component :is="n.icon" :size="19"/><span>{{ n.label }}</span><i></i></button></div></nav>
    <Transition name="toast"><div v-if="toast" class="toast-message" role="status"><Check :size="17"/>{{ toast }}</div></Transition>

    <dialog ref="importDialog" class="import-dialog" @click="($event.target===importDialog)&&closeImport()">
      <div class="dialog-heading"><div><h2>导入订阅</h2><p>添加订阅链接或本地 YAML 文件。</p></div><button class="icon-button" @click="closeImport" aria-label="关闭导入"><X :size="19"/></button></div>
      <form @submit.prevent="importProfile"><div class="dialog-body"><div class="import-tabs" role="group" aria-label="订阅方式"><button type="button" :aria-pressed="importType==='url'" @click="importType='url';importError=''">订阅链接</button><button type="button" :aria-pressed="importType==='file'" @click="importType='file';importError=''">YAML 文件</button></div><label class="form-field">名称<input v-model="importName" placeholder="例如：我的日常配置" maxlength="100" autofocus></label><label v-if="importType==='url'" class="form-field">订阅 URL<input v-model="importUrl" placeholder="https://example.com/subscribe" type="url"></label><template v-else><label class="file-upload"><Upload :size="21"/><b>{{ importFileName||'选择 YAML 文件' }}</b><span>也可以在下方粘贴内容</span><input type="file" accept=".yaml,.yml" @change="readFile"></label><label class="form-field">YAML 内容<textarea v-model="importYaml" rows="5" placeholder="proxies: …"></textarea></label></template><p class="preview-help">演示导入仅添加示例订阅，不访问链接或解析真实节点。</p><p v-if="importError" class="error-message" role="alert">{{ importError }}</p></div><div class="dialog-footer"><button type="button" class="button" @click="closeImport">取消</button><button type="submit" class="button primary"><Plus :size="16"/>导入订阅</button></div></form>
    </dialog>
  </div>
</template>
