<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Check, Copy, Download, Globe2, HardDrive, Loader2, Network, Save, Search, Square, Settings2 } from 'lucide-vue-next'
import { api, isDesktop } from './api'
import { saveClientSettings } from './client-settings'
import AppearanceSettings from './AppearanceSettings.vue'
import BackgroundSettings from './BackgroundSettings.vue'
import SettingsDialog from './SettingsDialog.vue'
import DesktopSettings from './DesktopSettings.vue'
type DNSListKey='nameserver'|'fallback'|'bootstrap'|'proxy_nameserver'|'fake_ip_filter'
type DNSOverride={enabled:boolean;mode:'fake-ip'|'redir-host'}&Record<DNSListKey,string[]>
const dnsFields=computed<{key:DNSListKey;label:string;hint:string}[]>(()=>[{key:'nameserver',label:t("主 DNS"),hint:t("IP、IP:端口，或 https:// / tls:// / tcp:// / udp:// / quic:// 地址")},{key:'bootstrap',label:t("引导 DNS"),hint:t("填写纯 IPv4 / IPv6 地址，用于解析加密 DNS 服务的域名")},{key:'fallback',label:t("备用 DNS（可选）"),hint:t("留空不启用，非空时遵循 Mihomo 的默认 fallback 规则")},{key:'proxy_nameserver',label:t("节点域名 DNS（可选）"),hint:t("留空跟随主 DNS")},{key:'fake_ip_filter',label:t("Fake-IP 排除域名"),hint:t("例如 *.lan、*.local；这些域名返回真实地址")}])
const dnsLines=ref<Record<DNSListKey,string>>({nameserver:'',fallback:'',bootstrap:'',proxy_nameserver:'',fake_ip_filter:''})
const dnsDialog=ref<InstanceType<typeof SettingsDialog>|null>(null)
type Preferences={allow_lan:boolean;ipv6:boolean;tun_strict_route:boolean;dns_leak_prevention:boolean;lan_auth:boolean;mixed_port:number|null;dns_override:DNSOverride;lan_username:string;lan_password:string}
type Geo={busy:boolean;phase:string;completed:number;total:number;file:string;message:string;files:{name:string;installed:boolean;bytes:number;updated_at:string}[]}
type Payload={settings:Preferences;lan_addresses:string[];core_version:string;geodata:Geo}
const lanDialog=ref<InstanceType<typeof SettingsDialog>|null>(null)
const ipv6Dialog=ref<InstanceType<typeof SettingsDialog>|null>(null)
const props=defineProps<{running:boolean;port:number;android?:boolean;validation?:boolean;coreAvailable?:boolean;viewQuery?:string}>()
const emit=defineEmits<{notice:[message:string,error?:boolean];changed:[port:number];dirty:[value:boolean];diagnostics:[];connections:[];ready:[];viewQuery:[value:string]}>()
const settingsQuery=ref(props.viewQuery||'')
watch(settingsQuery,value=>emit('viewQuery',value),{flush:'sync'})
const settingGroups=computed(()=>[
 {id:'connection',label:t('连接与代理'),keywords:[t('代理端口'),t('接管方式'),'HTTP SOCKS TUN VPN proxy port']},
 {id:'network',label:t('DNS 与局域网'),keywords:[t('允许局域网连接'),t('代理认证'),t('IPv6 支持'),t('TUN 严格模式'),t('DNS 防泄漏'),'DNS LAN nameserver fallback strict route leak prevention']},
 {id:'appearance',label:t('外观与语言'),keywords:[t('主题'),t('照片背景'),t('界面语言'),'theme background language']},
 ...(props.android||isDesktop?[{id:'behavior',label:t('应用行为'),keywords:[t('后台驻留'),t('开机自启'),t('权限'),'autostart resident permissions']}]:[]),
 {id:'core',label:t('内核与诊断'),keywords:[t('运行日志'),t('规则数据'),t('连接诊断'),'Mihomo GeoData logs diagnostics']},
])
const matchingGroups=computed(()=>settingGroups.value.filter(group=>settingsQuery.value.trim().toLocaleLowerCase().split(/\s+/).every(word=>`${group.label} ${group.keywords.join(' ')}`.toLocaleLowerCase().includes(word))))
const matches=(id:string)=>matchingGroups.value.some(group=>group.id===id)
function locate(id:string){document.getElementById('settings-'+id)?.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'})}
const form=ref<Preferences|null>(null), addresses=ref<string[]>([]), version=ref(t("读取中…")), geo=ref<Geo|null>(null)
const saving=ref(false), updating=ref(false), loading=ref(true), error=ref(''), showPassword=ref(false), copied=ref('')
const savedForm=ref('')
const signature=computed(()=>JSON.stringify({form:form.value,dns:dnsLines.value}))
const dirty=computed(()=>!!form.value&&!!savedForm.value&&signature.value!==savedForm.value)
watch(dirty,value=>emit('dirty',value))
let timer:ReturnType<typeof setInterval>|undefined, copyTimer:ReturnType<typeof setTimeout>|undefined, disposed=false, polling=false
function adopt(value:Payload){form.value={...value.settings,mixed_port:value.settings.mixed_port??props.port};for(const field of dnsFields.value)dnsLines.value[field.key]=form.value.dns_override[field.key].join('\n');addresses.value=value.lan_addresses;version.value=value.core_version;geo.value=value.geodata;savedForm.value=signature.value}
async function load(){loading.value=true;try{const value=await api<Payload>('/api/client/settings');if(!disposed){adopt(value);error.value=''}}catch(e){error.value=(e as Error).message}finally{loading.value=false}}
async function save(){if(!form.value||saving.value)return;for(const field of dnsFields.value)form.value.dns_override[field.key]=dnsLines.value[field.key].split(/\r?\n/).map(v=>v.trim()).filter(Boolean);if(form.value.dns_override.enabled&&(!form.value.dns_override.nameserver.length||!form.value.dns_override.bootstrap.length)){emit('notice',t("开启 DNS 覆写时请填写主 DNS 和引导 DNS"),true);return}if(form.value.lan_auth&&(!/^[A-Za-z0-9_-]{1,64}$/.test(form.value.lan_username)||form.value.lan_password.length<8)){emit('notice',t("请填写有效用户名及至少 8 位密码"),true);return}saving.value=true;try{const {mixed_port,...changes}=form.value;adopt(await saveClientSettings<Payload>(changes));emit('changed',form.value!.mixed_port??props.port);emit('notice',props.running&&!props.android?t("设置已保存并应用到运行内核"):t("设置已保存，下次启动内核时生效"))}catch(e){emit('notice',(e as Error).message,true)}finally{saving.value=false}}
async function update(){if(updating.value)return;updating.value=true;try{geo.value=await api<Geo>('/api/client/geodata/update','POST',{});emit('notice',t("GeoData 更新已开始；请保持程序运行"))}catch(e){emit('notice',(e as Error).message,true)}finally{updating.value=false}}
async function cancel(){try{geo.value=await api<Geo>('/api/client/geodata/cancel','POST',{})}catch(e){emit('notice',(e as Error).message,true)}}
async function poll(){if(polling||!geo.value?.busy||disposed)return;polling=true;try{const value=await api<Geo>('/api/client/geodata');if(!disposed){geo.value=value;if(!value.busy)emit('notice',value.message,value.phase==='error')}}catch{}finally{polling=false}}
async function copy(value:string,key:string){try{await navigator.clipboard.writeText(value);copied.value=key;clearTimeout(copyTimer);copyTimer=setTimeout(()=>copied.value='',1500)}catch{emit('notice',t("复制失败，请手动选中复制"),true)}}
function url(address:string){return `http://${address.includes(':')?'['+address+']':address}:${props.port}`}
function date(value:string){return value?new Date(value).toLocaleString(locale.value,{hour12:false}):t("尚未安装")}
watch(()=>props.port,value=>{if(form.value&&!dirty.value){form.value.mixed_port=value;savedForm.value=signature.value}})
onMounted(()=>{void load().then(async()=>{await nextTick();emit('ready')});timer=setInterval(poll,1000)})
onUnmounted(()=>{disposed=true;clearInterval(timer);clearTimeout(copyTimer)})
</script>

<template>
  <section class="settings-finder" :aria-label="t('查找设置')"><label class="desk-search"><Search :size="16"/><input v-model="settingsQuery" type="search" :aria-label="t('搜索设置')" :placeholder="t('搜索 DNS、端口、局域网…')"/></label><nav :aria-label="t('设置快速定位')"><button v-for="group in matchingGroups" :key="group.id" class="desk-btn" @click="locate(group.id)">{{ group.label }}</button><button v-if="settingsQuery" class="desk-text-btn" @click="settingsQuery=''">{{ t('清除搜索') }}</button></nav><div v-if="settingsQuery&&matches('network')" class="settings-search-shortcuts"><button class="desk-text-btn" :disabled="!form" @click="dnsDialog?.open()">{{ t('DNS 覆写设置') }}</button><button class="desk-text-btn" :disabled="!form" @click="lanDialog?.open()">{{ t('局域网详细设置') }}</button></div><p v-if="!matchingGroups.length" role="status">{{ t('没有匹配的设置，请尝试 DNS、端口或主题') }}</p></section>
  <div :class="['settings-layout-grid',{'single-settings-column':!(matches('connection')||matches('appearance'))||!(matches('network')||matches('behavior')||matches('core'))}]"><div v-show="matches('connection')||matches('appearance')" class="settings-left-column"><div id="settings-connection" v-show="matches('connection')" class="proxy-settings-slot"><slot name="proxy"/></div>
  <div id="settings-appearance" v-show="matches('appearance')" class="appearance-entries"><h2 class="settings-group-title">{{ t('外观与语言') }}</h2><slot name="language"/>
  <AppearanceSettings @notice="(message,error)=>emit('notice',message,error)"/>
  <BackgroundSettings @notice="(message,error)=>emit('notice',message,error)"/>
  </div>
</div><div v-show="matches('network')||matches('behavior')||matches('core')" class="settings-right-column"><div class="clash-settings-slot">
  <div v-if="loading" class="desk-card settings-loading"><Loader2 :size="18" class="rotate"/>{{ t("读取客户端设置…") }}</div>
  <div v-else-if="error" class="desk-alert error">{{ message(error) }} <button class="desk-text-btn" @click="load">{{ t("重试") }}</button></div>
    <template v-else-if="form">
    <form id="settings-network" v-show="matches('network')" class="desk-card advanced-settings-card clash-settings-card" :inert="saving" @submit.prevent="save">
      <div class="section-head"><div><h2>{{ t("DNS 与局域网") }}</h2><p class="small-explanation">{{ t('修改后需保存；运行中将保存并应用网络设置。') }}</p></div><Network :size="22"/></div>
      <div class="setting-row"><div><strong>{{ t("允许局域网连接") }}</strong><small>{{ t("向同网段设备提供 HTTP / SOCKS 代理。") }}</small></div><div class="setting-row-actions"><button type="button" class="desk-icon-btn" :aria-label="t('局域网详细设置')" :title="t('局域网详细设置')" @click="lanDialog?.open()"><Settings2 :size="17"/></button><button type="button" :class="['desk-switch',{on:form.allow_lan}]" role="switch" :aria-checked="form.allow_lan" :aria-label="t('允许局域网连接')" @click="form.allow_lan=!form.allow_lan"><span></span></button></div></div>
      <div class="setting-row"><div><strong>{{ t("IPv6 支持") }}</strong></div><div class="setting-row-actions"><button type="button" class="desk-icon-btn" :aria-label="t('IPv6 详细设置')" :title="t('IPv6 详细设置')" @click="ipv6Dialog?.open()"><Settings2 :size="17"/></button><button type="button" :class="['desk-switch',{on:form.ipv6}]" role="switch" :aria-checked="form.ipv6" :aria-label="t('IPv6 支持')" @click="form.ipv6=!form.ipv6"><span></span></button></div></div>
      <div v-if="!props.android" class="setting-row"><div><strong>{{ t("TUN 严格模式") }}</strong><small>{{ t("强制全部 DNS 与连接经 TUN，防止绕过隧道泄漏；虚拟机或企业 VPN 异常时可尝试关闭。") }}</small></div><div class="setting-row-actions"><button type="button" :class="['desk-switch',{on:form.tun_strict_route}]" role="switch" :aria-checked="form.tun_strict_route" :aria-label="t('TUN 严格模式')" @click="form.tun_strict_route=!form.tun_strict_route"><span></span></button></div></div>

      <div class="setting-row"><div><strong>{{ t("DNS 覆写") }}</strong><small>{{ form.dns_override.enabled?t("使用自定义 DNS 配置"):t("沿用订阅 DNS 配置") }}</small></div><div class="setting-row-actions"><button type="button" class="desk-icon-btn" :aria-label="t('DNS 覆写设置')" :title="t('DNS 覆写设置')" @click="dnsDialog?.open()"><Settings2 :size="17"/></button><button type="button" :class="['desk-switch',{on:form.dns_override.enabled}]" role="switch" :aria-checked="form.dns_override.enabled" :aria-label="t('DNS 覆写')" @click="form.dns_override.enabled=!form.dns_override.enabled"><span></span></button></div></div>
      <div class="setting-row"><div><strong>{{ t("DNS 防泄漏") }}</strong><small>{{ t("接管订阅和覆写 DNS：主解析经专用代理组使用境外加密 DNS，节点不可用时解析失败；节点域名和直连出口仍使用国内 DNS。仅保护内核处理的 DNS。") }}</small></div><div class="setting-row-actions"><button type="button" :class="['desk-switch',{on:form.dns_leak_prevention}]" role="switch" :aria-checked="form.dns_leak_prevention" :aria-label="t('DNS 防泄漏')" @click="form.dns_leak_prevention=!form.dns_leak_prevention"><span></span></button></div></div>

      <Teleport to=".desk" defer><div v-if="dirty" class="settings-save-bar" role="status"><span>{{ t('有未保存的网络设置') }}</span><button type="button" class="desk-btn primary" :disabled="props.validation||saving||geo?.busy" @click="save"><Loader2 v-if="saving" class="rotate" :size="14"/><Save v-else :size="14"/>{{ saving?t("正在保存…"):props.running&&!props.android?t("保存并应用"):t("保存设置") }}</button></div></Teleport>
    </form>
    <section v-if="!props.android&&isDesktop" id="settings-behavior" v-show="matches('behavior')" class="desk-card advanced-settings-card"><h2>{{ t('应用行为') }}</h2><p class="small-explanation">{{ t('此处修改立即保存') }}</p><DesktopSettings @notice="(text,error)=>emit('notice',text,error)"/></section><div v-if="props.android" id="settings-behavior" v-show="matches('behavior')"><slot name="permissions"/></div>
    </template>
  </div>

    <section v-if="form" id="settings-core" v-show="matches('core')" class="desk-card advanced-settings-card core-settings-card">
      <div class="section-head"><div><h2>{{ t("内核与诊断") }}</h2></div><HardDrive :size="22"/></div><template v-if="props.coreAvailable!==false">
      <div class="core-version-block"><span><Globe2 :size="14"/>{{ t("已安装内核") }}</span><code>{{ message(version) }}</code></div>
      <div class="geo-summary-row"><div class="geo-summary-copy"><strong>GeoData</strong><small>{{ t('数据库就绪：{0}/4', [geo?.files.filter(file=>file.installed).length||0]) }} · {{ ((geo?.files||[]).reduce((sum,file)=>sum+(file.installed?file.bytes:0),0)/1024/1024).toFixed(1) }} MB</small><small>GeoIP · GeoSite · Country · ASN</small></div><button type="button" class="desk-btn" :disabled="props.validation||updating||geo?.busy||props.running||saving" :title="props.running?t('请先停止主内核'):t('更新 GeoData')" @click="update"><Loader2 v-if="geo?.busy" class="rotate" :size="14"/><Download v-else :size="14"/>{{ t("更新") }}</button></div>
      <div v-if="geo?.busy" class="geo-progress" role="status"><span>{{ geo.phase==='installing'?t("正在安装"):geo.file||t("准备下载") }} · {{ geo.completed }}/{{ geo.total }}</span><button class="desk-text-btn" :disabled="geo.phase==='installing'" @click="cancel">{{ t("取消更新") }}</button></div>
      <p v-if="geo?.message" :class="['geo-message',{failed:geo.phase==='error'}]" role="status">{{ message(geo.message) }}</p></template><button type="button" class="desk-btn" @click="emit('connections')">{{ t('连接诊断') }}</button><button type="button" class="desk-btn" @click="emit('diagnostics')">{{ t('查看运行日志') }}</button>
    </section>
  </div></div>

  <SettingsDialog :inert="saving" :busy="saving" ref="lanDialog" :title="t('局域网连接设置')" :description="t('默认无需认证；开启认证后，同网段设备需提供用户名和密码。')">
    <template v-if="form">
      <div class="setting-row"><div><strong>{{ t("启用代理认证") }}</strong><small>{{ form.lan_auth?t("局域网连接需要用户名与密码"):t("同网段设备可直接连接，无需用户名和密码") }}</small></div><button type="button" :class="['desk-switch',{on:form.lan_auth}]" role="switch" :aria-checked="form.lan_auth" :aria-label="t('启用代理认证')" @click="form.lan_auth=!form.lan_auth"><span></span></button></div>
<template v-if="form.lan_auth"><div class="lan-auth-fields"><label class="desk-field">{{ t("代理用户名") }}<input v-model="form.lan_username" required pattern="[A-Za-z0-9_-]+" maxlength="64" autocomplete="off"/></label><label class="desk-field">{{ t("代理密码") }}<input v-model="form.lan_password" :type="showPassword?'text':'password'" required minlength="8" maxlength="128" autocomplete="new-password"/></label></div><div class="lan-password-actions"><label><input v-model="showPassword" type="checkbox"/>{{ t("显示密码") }}</label><button type="button" class="desk-text-btn" @click="copy(form.lan_password,'password')"><Check v-if="copied==='password'" :size="12"/><Copy v-else :size="12"/>{{ t("复制密码") }}</button></div><p class="small-explanation">{{ t("局域网设备需填写上述用户名、密码。本机回环连接免认证；控制接口仍只在本机开放。") }}</p></template>

      <p class="small-explanation">{{ t("代理端口请在“连接与代理”中修改，本机与局域网共用。") }}</p>
      <div class="lan-addresses"><strong>{{ t("本机局域网地址 · 当前端口 {0}", [props.port]) }}</strong><div v-for="address in addresses" :key="address"><code>{{ url(address) }}</code><button type="button" class="desk-icon-btn" :aria-label="t('复制 ')+address" @click="copy(url(address),address)"><Check v-if="copied===address" :size="13"/><Copy v-else :size="13"/></button></div><p v-if="!addresses.length">{{ t("未取得局域网地址，请检查网卡连接。") }}</p><small>{{ t("保存并启用后可连接；设备需位于允许的局域网范围，且系统防火墙允许该代理端口。") }}</small></div>

    </template>
  <template #footer><div class="config-actions"><button type="button" class="desk-btn primary" :disabled="props.validation||saving||geo?.busy" @click="save"><Save :size="15"/>{{ saving?t("正在保存…"):props.running&&!props.android?t("保存并应用"):t("保存设置") }}</button></div></template></SettingsDialog>
  <SettingsDialog class="dns-settings-dialog" :inert="saving" :busy="saving" ref="dnsDialog" :title="t('DNS 覆写设置')" :description="t(props.android?'每行一个地址，保存后启用；不修改系统 DNS。':'每行填写一个地址。保存并启用后替换订阅的 DNS 块，不修改源订阅或系统 DNS。')">
    <template v-if="form">
      <div class="setting-row"><div><strong>{{ t("启用 DNS 覆写") }}</strong><small>{{ t("关闭时恢复订阅 DNS；TUN 仍按需补充必要配置。") }}</small></div><button type="button" :class="['desk-switch',{on:form.dns_override.enabled}]" role="switch" :aria-checked="form.dns_override.enabled" :aria-label="t('启用 DNS 覆写')" @click="form.dns_override.enabled=!form.dns_override.enabled"><span></span></button></div>
      <label class="desk-field">{{ t("解析模式") }}<select v-model="form.dns_override.mode"><option value="fake-ip">{{ t("Fake-IP · 虚拟地址") }}</option><option value="redir-host">{{ t("Redir-Host · 真实地址") }}</option></select></label>
      <div class="dns-fields"><label v-for="field in dnsFields.filter(f=>f.key!=='fake_ip_filter'||form!.dns_override.mode==='fake-ip')" :key="field.key" class="desk-field">{{ field.label }}<textarea v-model="dnsLines[field.key]" rows="3" spellcheck="false" :aria-label="field.label"/><small class="small-explanation">{{ field.hint }}</small></label></div>
      <p class="small-explanation">{{ t("DNS IPv6 解析跟随 IPv6 开关。这里只控制内核解析，不开放额外 DNS 监听端口。") }}</p>

    </template>
  <template #footer><div class="config-actions"><button type="button" class="desk-btn primary" :disabled="props.validation||saving||geo?.busy" @click="save"><Save :size="15"/>{{ saving?t("正在保存…"):props.running&&!props.android?t("保存并应用"):t("保存设置") }}</button></div></template></SettingsDialog>
  <SettingsDialog class="ipv6-settings-dialog" :inert="saving" :busy="saving" ref="ipv6Dialog" :title="t('IPv6 详细设置')" :description="t(props.android?'仅影响本程序，不修改系统网络设置。':'仅控制本程序的 Mihomo 行为，不修改系统网卡设置。')">
    <template v-if="form">
      <div class="setting-row"><div><strong>{{ t("IPv6 出站与 DNS AAAA") }}</strong><small>{{ t("沿用当前联动开关，保存后应用到主内核。") }}</small></div><button type="button" :class="['desk-switch',{on:form.ipv6}]" role="switch" :aria-checked="form.ipv6" :aria-label="t('IPv6 出站与 DNS AAAA')" @click="form.ipv6=!form.ipv6"><span></span></button></div>
      <dl class="ipv6-detail-list"><div><dt>{{ t("出站连接") }}</dt><dd>{{ form.ipv6?t("允许内核使用 IPv6"):t("禁止内核使用 IPv6") }}</dd></div><div><dt>{{ t("DNS AAAA 解析") }}</dt><dd>{{ form.ipv6?t("允许返回 IPv6 地址"):t("关闭 IPv6 地址解析") }}</dd></div><div><dt>{{ t("系统网卡") }}</dt><dd>{{ t("不变更系统 IPv6 属性") }}</dd></div></dl>
      <h3 class="submenu-heading">{{ t("本机 IPv6 地址") }}</h3><div class="ipv6-address-list"><code v-for="address in addresses.filter(a=>a.includes(':'))" :key="address">{{ address }}</code><p v-if="!addresses.some(a=>a.includes(':'))" class="small-explanation">{{ t("未发现可用 IPv6 地址；请检查当前网络是否提供 IPv6。") }}</p></div>
      <p class="small-explanation">{{ t("开启后能否联网仍取决于网络、节点及 TUN 的 IPv6 支持；这里显示的是本机网卡地址，不代表公网出口。") }}</p>

    </template>
  <template #footer><div class="config-actions"><button type="button" class="desk-btn primary" :disabled="props.validation||saving||geo?.busy" @click="save"><Save :size="15"/>{{ saving?t("正在保存…"):props.running&&!props.android?t("保存并应用"):t("保存设置") }}</button></div></template></SettingsDialog>
</template>
