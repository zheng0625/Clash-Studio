<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Check, Copy, Download, Globe2, HardDrive, Loader2, Network, Save, Square, Settings2 } from 'lucide-vue-next'
import { api } from './api'
import AppearanceSettings from './AppearanceSettings.vue'
import BackgroundSettings from './BackgroundSettings.vue'
import SettingsDialog from './SettingsDialog.vue'
type DNSListKey='nameserver'|'fallback'|'bootstrap'|'proxy_nameserver'|'fake_ip_filter'
type DNSOverride={enabled:boolean;mode:'fake-ip'|'redir-host'}&Record<DNSListKey,string[]>
const dnsFields=computed<{key:DNSListKey;label:string;hint:string}[]>(()=>[{key:'nameserver',label:t("主 DNS"),hint:t("IP、IP:端口，或 https:// / tls:// / tcp:// / udp:// / quic:// 地址")},{key:'bootstrap',label:t("引导 DNS"),hint:t("填写纯 IPv4 / IPv6 地址，用于解析加密 DNS 服务的域名")},{key:'fallback',label:t("备用 DNS（可选）"),hint:t("留空不启用，非空时遵循 Mihomo 的默认 fallback 规则")},{key:'proxy_nameserver',label:t("节点域名 DNS（可选）"),hint:t("留空跟随主 DNS")},{key:'fake_ip_filter',label:t("Fake-IP 排除域名"),hint:t("例如 *.lan、*.local；这些域名返回真实地址")}])
const dnsLines=ref<Record<DNSListKey,string>>({nameserver:'',fallback:'',bootstrap:'',proxy_nameserver:'',fake_ip_filter:''})
const dnsDialog=ref<InstanceType<typeof SettingsDialog>|null>(null)
type Preferences={allow_lan:boolean;ipv6:boolean;lan_auth:boolean;mixed_port:number|null;dns_override:DNSOverride;lan_username:string;lan_password:string}
type Geo={busy:boolean;phase:string;completed:number;total:number;file:string;message:string;files:{name:string;installed:boolean;bytes:number;updated_at:string}[]}
type Payload={settings:Preferences;lan_addresses:string[];core_version:string;geodata:Geo}
const lanDialog=ref<InstanceType<typeof SettingsDialog>|null>(null)
const ipv6Dialog=ref<InstanceType<typeof SettingsDialog>|null>(null)
const props=defineProps<{running:boolean;port:number}>()
const emit=defineEmits<{notice:[message:string,error?:boolean];changed:[port:number]}>()
const form=ref<Preferences|null>(null), addresses=ref<string[]>([]), version=ref(t("读取中…")), geo=ref<Geo|null>(null)
const saving=ref(false), updating=ref(false), loading=ref(true), error=ref(''), showPassword=ref(false), copied=ref('')
let timer:ReturnType<typeof setInterval>|undefined, copyTimer:ReturnType<typeof setTimeout>|undefined, disposed=false, polling=false
function adopt(value:Payload){form.value={...value.settings,mixed_port:value.settings.mixed_port??props.port};for(const field of dnsFields.value)dnsLines.value[field.key]=form.value.dns_override[field.key].join('\n');addresses.value=value.lan_addresses;version.value=value.core_version;geo.value=value.geodata}
async function load(){loading.value=true;try{const value=await api<Payload>('/api/client/settings');if(!disposed){adopt(value);error.value=''}}catch(e){error.value=(e as Error).message}finally{loading.value=false}}
async function save(){if(!form.value||saving.value)return;for(const field of dnsFields.value)form.value.dns_override[field.key]=dnsLines.value[field.key].split(/\r?\n/).map(v=>v.trim()).filter(Boolean);if(form.value.dns_override.enabled&&(!form.value.dns_override.nameserver.length||!form.value.dns_override.bootstrap.length)){emit('notice',t("开启 DNS 覆写时请填写主 DNS 和引导 DNS"),true);return}if(!Number.isInteger(form.value.mixed_port)||form.value.mixed_port!<1024||form.value.mixed_port!>65535){emit('notice',t("端口必须为 1024–65535 之间的整数"),true);return}if(form.value.lan_auth&&(!/^[A-Za-z0-9_-]{1,64}$/.test(form.value.lan_username)||form.value.lan_password.length<8)){emit('notice',t("请填写有效用户名及至少 8 位密码"),true);return}saving.value=true;try{adopt(await api<Payload>('/api/client/settings','PUT',form.value));emit('changed',form.value!.mixed_port??props.port);emit('notice',props.running?t("设置已保存并应用到运行内核"):t("设置已保存，下次启动内核时生效"))}catch(e){emit('notice',(e as Error).message,true)}finally{saving.value=false}}
async function update(){if(updating.value)return;updating.value=true;try{geo.value=await api<Geo>('/api/client/geodata/update','POST',{});emit('notice',t("GeoData 更新已开始；请保持程序运行"))}catch(e){emit('notice',(e as Error).message,true)}finally{updating.value=false}}
async function cancel(){try{geo.value=await api<Geo>('/api/client/geodata/cancel','POST',{})}catch(e){emit('notice',(e as Error).message,true)}}
async function poll(){if(polling||!geo.value?.busy||disposed)return;polling=true;try{const value=await api<Geo>('/api/client/geodata');if(!disposed){geo.value=value;if(!value.busy)emit('notice',value.message,value.phase==='error')}}catch{}finally{polling=false}}
async function copy(value:string,key:string){try{await navigator.clipboard.writeText(value);copied.value=key;clearTimeout(copyTimer);copyTimer=setTimeout(()=>copied.value='',1500)}catch{emit('notice',t("复制失败，请手动选中复制"),true)}}
function url(address:string){return `http://${address.includes(':')?'['+address+']':address}:${props.port}`}
function date(value:string){return value?new Date(value).toLocaleString(locale.value,{hour12:false}):t("尚未安装")}
watch(()=>props.port,value=>{if(form.value)form.value.mixed_port=value})
onMounted(()=>{load();timer=setInterval(poll,1000)})
onUnmounted(()=>{disposed=true;clearInterval(timer);clearTimeout(copyTimer)})
</script>

<template>

  <div v-if="loading" class="desk-card settings-loading"><Loader2 :size="18" class="rotate"/>{{ t("读取客户端设置…") }}</div>
  <div v-else-if="error" class="desk-alert error">{{ message(error) }} <button class="desk-text-btn" @click="load">{{ t("重试") }}</button></div>
  <div v-else-if="form" class="advanced-settings-grid">
    <form class="desk-card advanced-settings-card" @submit.prevent="save">
      <div class="section-head"><div><span class="desk-eyebrow">CLASH SETTINGS</span><h2>{{ t("Clash 设置") }}</h2></div><Network :size="22"/></div>
      <div class="setting-row"><div><strong>{{ t("允许局域网连接") }}</strong><small>{{ t("向同网段设备提供 HTTP / SOCKS 代理。") }}</small></div><div class="setting-row-actions"><button type="button" class="desk-icon-btn" :aria-label="t('局域网详细设置')" :title="t('局域网详细设置')" @click="lanDialog?.open()"><Settings2 :size="17"/></button><button type="button" :class="['desk-switch',{on:form.allow_lan}]" role="switch" :aria-checked="form.allow_lan" :aria-label="t('允许局域网连接')" @click="form.allow_lan=!form.allow_lan"><span></span></button></div></div>
      <div class="setting-row"><div><strong>{{ t("IPv6 支持") }}</strong></div><div class="setting-row-actions"><button type="button" class="desk-icon-btn" :aria-label="t('IPv6 详细设置')" :title="t('IPv6 详细设置')" @click="ipv6Dialog?.open()"><Settings2 :size="17"/></button><button type="button" :class="['desk-switch',{on:form.ipv6}]" role="switch" :aria-checked="form.ipv6" :aria-label="t('IPv6 支持')" @click="form.ipv6=!form.ipv6"><span></span></button></div></div>

      <div class="setting-row"><div><strong>{{ t("DNS 覆写") }}</strong><small>{{ form.dns_override.enabled?t("使用自定义 DNS 配置"):t("沿用订阅 DNS 配置") }}</small></div><div class="setting-row-actions"><button type="button" class="desk-icon-btn" :aria-label="t('DNS 覆写设置')" :title="t('DNS 覆写设置')" @click="dnsDialog?.open()"><Settings2 :size="17"/></button><button type="button" :class="['desk-switch',{on:form.dns_override.enabled}]" role="switch" :aria-checked="form.dns_override.enabled" :aria-label="t('DNS 覆写')" @click="form.dns_override.enabled=!form.dns_override.enabled"><span></span></button></div></div>

      <button class="desk-btn primary" :disabled="saving||geo?.busy"><Loader2 v-if="saving" class="rotate" :size="14"/><Save v-else :size="14"/>{{ saving?t("正在应用…"):props.running?t("保存并应用"):t("保存设置") }}</button>
    </form>
    <section class="desk-card advanced-settings-card">
      <div class="section-head"><div><span class="desk-eyebrow">CORE & GEODATA</span><h2>{{ t("内核与规则数据") }}</h2></div><HardDrive :size="22"/></div>
      <div class="core-version-block"><span><Globe2 :size="14"/>{{ t("已安装内核") }}</span><code>{{ message(version) }}</code></div>
      <div class="geo-file-list"><article v-for="file in geo?.files||[]" :key="file.name"><div><strong>{{ file.name }}</strong><small>{{ date(file.updated_at) }}</small></div><span>{{ file.installed?(file.bytes/1024/1024).toFixed(1)+' MB':t("缺失") }}</span></article></div>
      <p class="small-explanation">{{ t("四项基础数据库已随软件内置，无需下载即可使用。此按钮仅用于主动更新；停止主内核后从上游 CDN 下载并检查 SHA-256，失败保留原文件。") }}</p>
      <div v-if="geo?.busy" class="geo-progress"><Loader2 :size="13" class="rotate"/><span>{{ geo.phase==='installing'?t("正在安装"):geo.file||t("准备下载") }} · {{ geo.completed }}/{{ geo.total }}</span></div>
      <p v-if="geo?.message" :class="['geo-message',{failed:geo.phase==='error'}]" role="status">{{ message(geo.message) }}</p>
      <div class="config-actions"><button class="desk-btn primary" :disabled="updating||geo?.busy||props.running||saving" @click="update"><Download :size="14"/>{{ props.running?t("请先停止主内核"):t("更新 GeoData") }}</button><button v-if="geo?.busy" class="desk-btn" :disabled="geo.phase==='installing'" @click="cancel"><Square :size="12"/>{{ t("取消更新") }}</button></div>
    </section>
  </div>
  <div class="appearance-entries">
  <AppearanceSettings @notice="(message,error)=>emit('notice',message,error)"/>
  <BackgroundSettings @notice="(message,error)=>emit('notice',message,error)"/>
  </div>
  <SettingsDialog ref="lanDialog" :title="t('局域网连接设置')" :description="t('默认无需认证；开启认证后，同网段设备需提供用户名和密码。')">
    <template v-if="form">
      <div class="setting-row"><div><strong>{{ t("启用代理认证") }}</strong><small>{{ form.lan_auth?t("局域网连接需要用户名与密码"):t("同网段设备可直接连接，无需用户名和密码") }}</small></div><button type="button" :class="['desk-switch',{on:form.lan_auth}]" role="switch" :aria-checked="form.lan_auth" :aria-label="t('启用代理认证')" @click="form.lan_auth=!form.lan_auth"><span></span></button></div>
<template v-if="form.lan_auth"><div class="lan-auth-fields"><label class="desk-field">{{ t("代理用户名") }}<input v-model="form.lan_username" required pattern="[A-Za-z0-9_-]+" maxlength="64" autocomplete="off"/></label><label class="desk-field">{{ t("代理密码") }}<input v-model="form.lan_password" :type="showPassword?'text':'password'" required minlength="8" maxlength="128" autocomplete="new-password"/></label></div><div class="lan-password-actions"><label><input v-model="showPassword" type="checkbox"/>{{ t("显示密码") }}</label><button type="button" class="desk-text-btn" @click="copy(form.lan_password,'password')"><Check v-if="copied==='password'" :size="12"/><Copy v-else :size="12"/>{{ t("复制密码") }}</button></div><p class="small-explanation">{{ t("局域网设备需填写上述用户名、密码。本机回环连接免认证；控制接口仍只在本机开放。") }}</p></template>

      <p class="small-explanation">{{ t("代理端口请在“本地运行”板块中修改，本机与局域网共用。") }}</p>
      <div class="lan-addresses"><strong>{{ t("本机局域网地址 · 当前端口 {0}", [props.port]) }}</strong><div v-for="address in addresses" :key="address"><code>{{ url(address) }}</code><button type="button" class="desk-icon-btn" :aria-label="t('复制 ')+address" @click="copy(url(address),address)"><Check v-if="copied===address" :size="13"/><Copy v-else :size="13"/></button></div><p v-if="!addresses.length">{{ t("未取得局域网地址，请检查网卡连接。") }}</p><small>{{ t("保存并启用后可连接；设备需位于允许的局域网范围，且 Windows 防火墙允许该代理端口。") }}</small></div>
      <div class="config-actions"><button type="button" class="desk-btn primary" :disabled="saving||geo?.busy" @click="save"><Save :size="15"/>{{ saving?t("正在保存…"):props.running?t("保存并应用"):t("保存设置") }}</button></div>
    </template>
  </SettingsDialog>
  <SettingsDialog ref="dnsDialog" :title="t('DNS 覆写设置')" :description="t('每行填写一个地址。保存并启用后替换订阅的 DNS 块，不修改源订阅或 Windows DNS。')">
    <template v-if="form">
      <div class="setting-row"><div><strong>{{ t("启用 DNS 覆写") }}</strong><small>{{ t("关闭时恢复订阅 DNS；TUN 仍按需补充必要配置。") }}</small></div><button type="button" :class="['desk-switch',{on:form.dns_override.enabled}]" role="switch" :aria-checked="form.dns_override.enabled" :aria-label="t('启用 DNS 覆写')" @click="form.dns_override.enabled=!form.dns_override.enabled"><span></span></button></div>
      <label class="desk-field">{{ t("解析模式") }}<select v-model="form.dns_override.mode"><option value="fake-ip">{{ t("Fake-IP · 虚拟地址") }}</option><option value="redir-host">{{ t("Redir-Host · 真实地址") }}</option></select></label>
      <div class="dns-fields"><label v-for="field in dnsFields.filter(f=>f.key!=='fake_ip_filter'||form!.dns_override.mode==='fake-ip')" :key="field.key" class="desk-field">{{ field.label }}<textarea v-model="dnsLines[field.key]" rows="3" spellcheck="false" :aria-label="field.label"/><small class="small-explanation">{{ field.hint }}</small></label></div>
      <p class="small-explanation">{{ t("DNS IPv6 解析跟随 IPv6 开关。这里只控制内核解析，不开放额外 DNS 监听端口。") }}</p>
      <div class="config-actions"><button type="button" class="desk-btn primary" :disabled="saving||geo?.busy" @click="save"><Save :size="15"/>{{ saving?t("正在保存…"):props.running?t("保存并应用"):t("保存设置") }}</button></div>
    </template>
  </SettingsDialog>
  <SettingsDialog ref="ipv6Dialog" :title="t('IPv6 详细设置')" :description="t('仅控制本程序的 Mihomo 行为，不修改 Windows 网卡设置。')">
    <template v-if="form">
      <div class="setting-row"><div><strong>{{ t("IPv6 出站与 DNS AAAA") }}</strong><small>{{ t("沿用当前联动开关，保存后应用到主内核。") }}</small></div><button type="button" :class="['desk-switch',{on:form.ipv6}]" role="switch" :aria-checked="form.ipv6" :aria-label="t('IPv6 出站与 DNS AAAA')" @click="form.ipv6=!form.ipv6"><span></span></button></div>
      <dl class="ipv6-detail-list"><div><dt>{{ t("出站连接") }}</dt><dd>{{ form.ipv6?t("允许内核使用 IPv6"):t("禁止内核使用 IPv6") }}</dd></div><div><dt>{{ t("DNS AAAA 解析") }}</dt><dd>{{ form.ipv6?t("允许返回 IPv6 地址"):t("关闭 IPv6 地址解析") }}</dd></div><div><dt>{{ t("系统网卡") }}</dt><dd>{{ t("不变更 Windows IPv6 属性") }}</dd></div></dl>
      <h3 class="submenu-heading">{{ t("本机 IPv6 地址") }}</h3><div class="ipv6-address-list"><code v-for="address in addresses.filter(a=>a.includes(':'))" :key="address">{{ address }}</code><p v-if="!addresses.some(a=>a.includes(':'))" class="small-explanation">{{ t("未发现可用 IPv6 地址；请检查当前网络是否提供 IPv6。") }}</p></div>
      <p class="small-explanation">{{ t("开启后能否联网仍取决于网络、节点及 TUN 的 IPv6 支持；这里显示的是本机网卡地址，不代表公网出口。") }}</p>
      <div class="config-actions"><button type="button" class="desk-btn primary" :disabled="saving||geo?.busy" @click="save"><Save :size="15"/>{{ saving?t("正在保存…"):props.running?t("保存并应用"):t("保存设置") }}</button></div>
    </template>
  </SettingsDialog>
</template>
