<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, ref, watch } from 'vue'
import { Save } from 'lucide-vue-next'
import { api } from './api'
const props=defineProps<{running:boolean;port:number}>()
const emit=defineEmits<{changed:[port:number];notice:[message:string,error?:boolean];dirty:[value:boolean]}>()
const port=ref(props.port),saving=ref(false),error=ref('')
const savedPort=ref(props.port)
const dirty=computed(()=>port.value!==savedPort.value)
watch(dirty,value=>emit('dirty',value),{flush:'sync'})
watch(()=>props.port,value=>{if(!dirty.value&&!saving.value){port.value=value;savedPort.value=value}})
async function save(){
  if(saving.value||props.running)return
  if(!Number.isInteger(port.value)||port.value<1024||port.value>65535){error.value=t("端口必须为 1024–65535 之间的整数");return}
  saving.value=true;error.value=''
  try{
    const current=await api<{settings:Record<string,unknown>}>('/api/client/settings')
    const result=await api<{settings:{mixed_port:number}}>('/api/client/settings','PUT',{...current.settings,mixed_port:port.value})
    port.value=result.settings.mixed_port;savedPort.value=result.settings.mixed_port;emit('changed',result.settings.mixed_port);emit('notice',t("代理端口已保存，下次启动内核时生效"))
  }catch(e){error.value=(e as Error).message}finally{saving.value=false}
}
</script>
<template>
  <form class="proxy-port-settings" @submit.prevent="save">
    <label class="desk-field">{{ t("代理端口 · HTTP / SOCKS 混合端口") }}<div class="proxy-port-controls"><input v-model.number="port" type="number" min="1024" max="65535" step="1" :disabled="props.running||saving"/><button class="desk-btn" :disabled="props.running||saving"><Save :size="14"/>{{ saving?t("保存中…"):t("保存端口") }}</button></div></label>
    <p class="small-explanation">{{ t("本机与局域网共用此端口。{0}", [props.running?t("请先停止内核，再修改端口。"):t("保存后启动内核即可生效。")]) }}</p>
    <p v-if="error" class="desk-alert error" role="status">{{ message(error) }}</p>
  </form>
</template>
