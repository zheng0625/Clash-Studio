<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, isDesktop } from './api'
import { t } from './i18n'
type Preferences={resident:boolean;autostart:boolean}
const preferences=ref<Preferences>({resident:true,autostart:false}),busy=ref(false),loaded=ref(false),autostartSupported=ref(false)
const emit=defineEmits<{notice:[message:string,error?:boolean]}>()
onMounted(async()=>{if(!isDesktop)return;try{const {invoke}=await import('@tauri-apps/api/core');preferences.value=await invoke<Preferences>('desktop_preferences');const platform=await api<{capabilities:{autostart:boolean}}>('/api/client/platform');autostartSupported.value=platform.capabilities.autostart;loaded.value=true}catch(e){emit('notice',String(e),true)}})
async function toggle(key:keyof Preferences){if(busy.value||!loaded.value)return;busy.value=true;try{const {invoke}=await import('@tauri-apps/api/core');preferences.value=await invoke<Preferences>('set_desktop_preferences',{preferences:{...preferences.value,[key]:!preferences.value[key]}})}catch(e){emit('notice',String(e),true)}finally{busy.value=false}}
</script>
<template>
  <div v-if="isDesktop" class="desktop-settings embedded-desktop-settings">
    <div class="setting-row"><div><strong>{{ t('后台驻留') }}</strong><small>{{ t('关闭窗口后在托盘继续运行；从托盘退出可完全关闭软件。') }}</small></div><button type="button" :class="['desk-switch',{on:preferences.resident}]" role="switch" :aria-label="t('后台驻留')" :aria-checked="preferences.resident" :disabled="busy||!loaded" @click="toggle('resident')"><span></span></button></div>
    <div class="setting-row"><div><strong>{{ t('开机自启') }}</strong><small>{{ t('登录系统时启动；开启驻留时自动隐藏至托盘。') }}</small></div><button type="button" :class="['desk-switch',{on:preferences.autostart}]" role="switch" :aria-label="t('开机自启')" :aria-checked="preferences.autostart" :disabled="busy||!loaded||!autostartSupported" @click="toggle('autostart')"><span></span></button></div>
  </div>
</template>
