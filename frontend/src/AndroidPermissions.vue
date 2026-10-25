<script setup lang="ts">
import { onMounted,onUnmounted,ref } from 'vue'
import { api } from './api'
import { t,message } from './i18n'
const state=ref<{camera:boolean;notifications:boolean;vpn:boolean}|null>(null),error=ref('')
async function refresh(){if(document.hidden)return;try{state.value=await api('/api/android/permissions');error.value=''}catch(e){error.value=(e as Error).message}}
async function settings(){try{await api('/api/android/app-settings','POST')}catch(e){error.value=(e as Error).message}}
onMounted(()=>{refresh();document.addEventListener('visibilitychange',refresh);window.addEventListener('focus',refresh)})
onUnmounted(()=>{document.removeEventListener('visibilitychange',refresh);window.removeEventListener('focus',refresh)})
</script>
<template><section class="desk-card android-permissions"><div class="section-head"><h2>{{ t('权限与访问') }}</h2><button class="desk-btn" @click="settings">{{ t('权限设置') }}</button></div><template v-if="state"><div v-for="item in [{label:t('相机'),granted:state.camera},{label:t('通知'),granted:state.notifications},{label:t('VPN 连接'),granted:state.vpn}]" :key="item.label" class="setting-row"><strong>{{ item.label }}</strong><span>{{ item.granted?t('已允许'):t('未允许') }}</span></div></template><div class="setting-row"><strong>{{ t('照片') }}</strong><span>{{ t('仅访问所选图片') }}</span></div><p class="page-caption">{{ t('相机在扫码时申请；照片通过系统选择器逐张授权；VPN 在应用配置时由系统确认。') }}</p><p v-if="error" class="desk-alert error">{{ message(error) }}</p></section></template>
<style scoped>.android-permissions{padding:20px}.android-permissions .page-caption{line-height:1.8;margin-top:14px}.android-permissions .setting-row>span{font-size:12px;color:var(--client-secondary)}</style>
