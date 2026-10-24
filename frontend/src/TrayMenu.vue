<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { isDesktop } from './api'
import { t } from './i18n'
import { Power, ExternalLink, LogOut } from 'lucide-vue-next'
type State={enabled:boolean;can_start:boolean;routing_mode:string;proxy_mode:string;busy:boolean}
const state=ref<State>(),error=ref(''),pending=ref(false)
let timer:ReturnType<typeof setInterval>,reading=false
async function refresh(){if(reading||!isDesktop)return;reading=true;try{state.value=await invoke<State>('tray_menu_state');error.value=''}catch(e){error.value=String(e)}finally{reading=false}}
async function action(action:string){if(pending.value)return;pending.value=true;try{if(isDesktop)await invoke('tray_menu_action',{action});await refresh()}catch(e){error.value=String(e)}finally{pending.value=false}}
function key(event:KeyboardEvent){if(event.key==='Escape'){void action('hide');return}if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();const buttons=Array.from(document.querySelectorAll<HTMLButtonElement>('.tray-panel button:not(:disabled)'));const index=buttons.indexOf(document.activeElement as HTMLButtonElement);const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowUp'?-1:1)+buttons.length)%buttons.length;buttons[next]?.focus()}}
onMounted(()=>{void refresh();timer=setInterval(refresh,800);document.addEventListener('keydown',key)})
onUnmounted(()=>{clearInterval(timer);document.removeEventListener('keydown',key)})
</script>
<template>
 <main class="tray-panel" :aria-label="t('托盘菜单')">
  <header><img src="./assets/brand.svg" alt=""/><strong>Clash Studio</strong><span :class="['tray-status',{live:state?.enabled}]">{{ state?.enabled?t('运行中'):t('已停止') }}</span></header>
  <button class="tray-toggle" :disabled="!state||pending||state.busy||(!state.enabled&&!state.can_start)" role="switch" :aria-checked="!!state?.enabled" @click="action('toggle')"><span><Power :size="16"/>{{ t('开启代理') }}</span><i :class="{on:state?.enabled}"/></button>
  <section><h2>{{ t('代理模式') }}</h2><div class="tray-segments"><button v-for="item in [{id:'rule',name:'规则'},{id:'global',name:'全局'},{id:'direct',name:'直连'}]" :key="item.id" :disabled="!state||pending||state.busy" :aria-pressed="state?.routing_mode===item.id" @click="action(item.id)">{{ t(item.name) }}</button></div></section>
  <section><h2>{{ t('接管方式') }}</h2><div class="tray-segments"><button v-for="item in [{id:'system',name:'系统代理'},{id:'tun',name:'TUN 模式'}]" :key="item.id" :disabled="!state||pending||state.busy" :aria-pressed="state?.proxy_mode===item.id" @click="action(item.id)">{{ t(item.name) }}</button></div></section>
  <p v-if="error" class="tray-error" role="alert">{{ error }}</p>
  <footer><button @click="action('open')"><ExternalLink :size="15"/>{{ t('打开主窗口') }}</button><button class="tray-quit" @click="action('quit')"><LogOut :size="15"/>{{ t('退出') }}</button></footer>
 </main>
</template>
<style>
html.tray-surface,html.tray-surface body,html.tray-surface #app{background:transparent!important;color:#182333;color-scheme:light;margin:0;overflow:hidden}
.tray-panel{box-sizing:border-box;margin:8px;padding:16px;background:#fff;color:#182333;border:1px solid #d7dfe9;border-radius:20px;box-shadow:0 3px 8px #18233320;font:13px/1.5 'Segoe UI','Microsoft YaHei',sans-serif}
.tray-panel header{display:flex;align-items:center;gap:8px;margin-bottom:14px}.tray-panel header img{width:25px;height:25px}.tray-panel header strong{font-size:14px}.tray-status{margin-left:auto;font-size:11px;color:#dc2626}.tray-status.live{color:#15803d}
.tray-panel button{display:flex;align-items:center;justify-content:center;gap:7px;color:#182333;background:transparent;border:1px solid transparent;border-radius:10px;font:inherit;padding:8px;cursor:pointer}.tray-panel button:hover:not(:disabled){background:#e7edf5}.tray-panel button:focus-visible{outline:2px solid #2563eb;outline-offset:1px}.tray-panel button:disabled{opacity:.45;cursor:default}
.tray-panel .tray-toggle{width:100%;justify-content:space-between;border-color:#d7dfe9;padding:10px}.tray-toggle>span{display:flex;align-items:center;gap:8px}.tray-toggle i{width:30px;height:18px;background:#a2acba;border-radius:20px;padding:2px;box-sizing:border-box}.tray-toggle i:after{content:'';display:block;width:14px;height:14px;background:#fff;border-radius:50%;transition:transform .15s}.tray-toggle i.on{background:#2563eb}.tray-toggle i.on:after{transform:translateX(12px)}
.tray-panel section{margin-top:14px}.tray-panel h2{font-size:11px;font-weight:500;color:#586679;margin:0 0 6px}.tray-segments{display:flex;gap:4px;padding:3px;background:#f5f7fa;border-radius:12px}.tray-segments button{flex:1;padding:7px 3px}.tray-segments button[aria-pressed=true]{background:#e7edf5;color:#2563eb;border-color:#c4d7f5}
.tray-panel footer{display:flex;gap:6px;border-top:1px solid #d7dfe9;padding-top:10px;margin-top:16px}.tray-panel footer button{flex:1;font-size:12px}.tray-panel .tray-quit{color:#dc2626}.tray-error{color:#dc2626;font-size:11px;max-height:40px;overflow:auto;margin-top:8px}
</style>
