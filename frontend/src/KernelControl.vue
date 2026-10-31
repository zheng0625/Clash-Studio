<script setup lang="ts">
import { ArrowUpRight, Check, ChevronRight, Globe2, Loader2, Power, ShieldCheck } from 'lucide-vue-next'
import { t } from './i18n'
type RoutingMode='rule'|'global'|'direct'
defineProps<{
 runtime:{running:boolean;active?:{title?:string}|null;proxy:{supported:boolean};tun?:{supported:boolean;admin:boolean};routing_mode?:string|null}
 proxyMode:string;busy:string;needsApply:boolean;applyFailed:boolean;editorDirty:boolean;selected:string
 nativeCoreUnavailable:boolean;runtimeReady:boolean;isAndroid:boolean;nativeDevelopment:boolean;validationBuild:boolean;applyLabel:string
}>()
const emit=defineEmits<{settings:[];proxies:[];mode:[mode:'system'|'tun'];routing:[mode:RoutingMode];elevate:[];apply:[];stop:[]}>()
const routingChoices:{id:RoutingMode;label:string}[]=[{id:'rule',label:'规则'},{id:'global',label:'全局'},{id:'direct',label:'直连'}]
</script>
<template>
            <article class="desk-card kernel-launch-card">
              <div class="section-head"><h2>{{ t('内核与接管') }}</h2><button class="desk-text-btn" @click="emit('settings')">{{ t('更多设置') }}<ChevronRight :size="13"/></button></div>
              <p v-if="runtime.running&&needsApply" class="overview-running-context">{{ t('正在运行：{0}',[runtime.active?.title||'—']) }}</p>
              <div v-if="!isAndroid" class="mode-options" role="group" :aria-label="t('接管模式')"><button :class="{selected:proxyMode==='system'}" :disabled="!!busy" @click="emit('mode','system')"><Globe2 :size="18"/><span>{{ t(runtime.proxy.supported?'系统代理':'仅代理端口') }}</span><Check v-if="proxyMode==='system'" :size="15"/></button><button :class="{selected:proxyMode==='tun'}" :disabled="!!busy||!runtime.tun?.supported" @click="emit('mode','tun')"><ShieldCheck :size="18"/><span>{{ t('TUN 模式') }}</span><Check v-if="proxyMode==='tun'" :size="15"/></button></div>
              <p v-if="!isAndroid&&proxyMode==='tun'&&!runtime.tun?.admin" class="mode-warning">{{ t("TUN 需要管理员权限。") }}<button class="desk-text-btn" :disabled="!!busy" @click="emit('elevate')">{{ t("申请权限") }}<ArrowUpRight :size="12"/></button></p>
              <section class="routing-mode-card"><div><h2>{{ t("分流模式") }}</h2></div><div class="routing-segment" role="group" :aria-label="t('分流模式')"><button v-for="choice in routingChoices" :key="choice.id" :aria-pressed="runtime.routing_mode===choice.id" :disabled="!!busy||validationBuild||nativeCoreUnavailable||(isAndroid&&!runtime.running)" @click="emit('routing',choice.id)">{{ t(choice.label) }}</button></div><p v-if="runtime.routing_mode==='global'">{{ t("全局模式使用 GLOBAL 出口，可在代理页选择") }} <button class="desk-text-btn" @click="emit('proxies')">{{ t("选择出口") }}</button></p><p v-else-if="runtime.routing_mode==='direct'">{{ t("直连模式下不使用代理节点") }}</p></section>
              <details v-if="isAndroid" class="android-network-help"><summary>{{ t('VPN 接管说明') }}</summary><p class="android-network-note">{{ nativeDevelopment?t("通过 Android VPN 接管流量；首次启动需要系统授权，局域网保持直连。"):validationBuild?t("代理内核与 VPN 尚不可用。"):t("安卓 VPN 服务尚未接入，当前仅提供本地代理端口。") }}</p></details><div class="kernel-actions"><button class="desk-btn" :class="{primary:!runtime.running||needsApply||applyFailed}" :disabled="!!busy||editorDirty||!selected||nativeCoreUnavailable||!runtimeReady" @click="emit('apply')"><Loader2 v-if="busy==='apply'" class="rotate" :size="15"/><Power v-else :size="15"/>{{ applyLabel }}</button><button v-if="runtime.running||busy==='apply'||busy==='stop'" class="desk-btn danger" :disabled="!!busy&&busy!=='apply'" @click="emit('stop')"><Power :size="14"/>{{ isAndroid?t('断开'):t('停止') }}</button><button class="desk-text-btn" @click="emit('settings')">{{ t("更多设置") }}<ChevronRight :size="13"/></button></div>
            </article>
</template>
