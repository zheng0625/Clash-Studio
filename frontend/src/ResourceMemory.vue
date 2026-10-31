<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ChevronDown, MemoryStick, RefreshCw } from 'lucide-vue-next'
import { api } from './api'
import { t } from './i18n'
import type { MemorySample as Sample } from './memory-types'
import ResourceMemoryView from './ResourceMemoryView.vue'
const sample=ref<Sample|null>(null),failed=ref(false)
const privateLabel=computed(()=>sample.value?.private_method==='private_commit_sum'?t('私有提交合计'):t('匿名驻留合计'))
const privateWorking=computed(()=>sample.value?.ram_method==='private_working_set_sum')
const ramBytes=computed(()=>privateWorking.value?sample.value?.private_working_set_total_bytes:sample.value?.total_bytes)
const ramStatus=computed(()=>privateWorking.value?sample.value?.private_working_set_status:sample.value?.status)
let disposed=false,pending=false,timer:ReturnType<typeof setTimeout>|undefined
async function read(){
  if(disposed||document.hidden||pending)return
  pending=true
  try{const value=await api<Sample>('/api/client/resources/memory');if(!disposed){sample.value=value;failed.value=(value.ram_method==='private_working_set_sum'?value.private_working_set_status:value.status)==='unavailable'}}
  catch{if(!disposed){sample.value=null;failed.value=true}}
  finally{pending=false;clearTimeout(timer);if(!disposed&&!document.hidden)timer=setTimeout(read,5000)}
}
function resume(){clearTimeout(timer);if(!document.hidden)void read()}
onMounted(()=>{void read();document.addEventListener('visibilitychange',resume)})
onUnmounted(()=>{disposed=true;clearTimeout(timer);document.removeEventListener('visibilitychange',resume)})
</script>
<template><ResourceMemoryView :sample="sample" :failed="failed" :private-label="privateLabel" :private-working="privateWorking" :ram-bytes="ramBytes" :ram-status="ramStatus" @retry="read"/></template>
