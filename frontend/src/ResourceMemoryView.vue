<script setup lang="ts">
import { ChevronDown, MemoryStick, RefreshCw } from 'lucide-vue-next'
import { t } from './i18n'
import type { MemorySample } from './memory-types'
defineProps<{sample:MemorySample|null;failed:boolean;privateLabel:string;privateWorking:boolean;ramBytes:number|null|undefined;ramStatus:string|undefined}>()
const emit=defineEmits<{retry:[]}>()
const labels:Record<string,string>={desktop:'桌面宿主',webview:'WebView',service:'本地服务',core:'主内核',probe:'测速内核',other:'其他进程'}
function mb(value:number|null|undefined){return value==null?'—':(value/1024**2).toFixed(1)}
</script>
<template>
  <section class="desk-card resource-memory-card" :aria-label="t('软件内存占用')">
    <div class="resource-memory-reading"><h2><MemoryStick :size="18"/>{{ t('内存占用') }}</h2><strong>{{ ramStatus==='partial'?'≈ ':'' }}{{ mb(ramBytes) }} <small v-if="ramBytes!==null&&ramBytes!==undefined">MB</small></strong></div>
    <details class="resource-memory-details">
      <summary>RAM · {{ t('进程明细') }}<ChevronDown :size="13"/></summary>
      <div class="resource-memory-processes">
        <div v-for="part in (sample?.processes||[]).filter(p=>p.process_count)" :key="part.kind"><span>{{ t(labels[part.kind]||part.kind) }}</span><b>{{ (privateWorking?part.private_working_set_unreadable_count:part.unreadable_count)&&((privateWorking?part.private_working_set_bytes:part.bytes)!=null)?'≈ ':'' }}{{ mb(privateWorking?part.private_working_set_bytes:part.bytes) }} MB</b></div>
        <p v-if="privateWorking">{{ t('当前显示私有工作集：进程独占且驻留在 RAM 中的内存，便于与任务管理器对照。') }}</p>
        <p v-else>{{ t('软件各进程工作集合计，包含共享内存页。') }}</p>
        <p>{{ t('统计本应用进程树及受管理内核；进程分组和采样时间可能与任务管理器不同。') }}</p>
        <p v-if="privateWorking&&sample?.total_bytes!=null">{{ t('工作集合计（含共享页）') }} {{ sample?.status==='partial'?'≈ ':'' }}{{ mb(sample?.total_bytes) }} MB</p>
        <p v-if="sample?.private_total_bytes!=null">{{ privateLabel }} {{ mb(sample?.private_total_bytes) }} MB<span v-if="sample?.private_method==='private_commit_sum'"> · {{ t('包含未驻留的分配，不等于 RAM 占用。') }}</span></p>
        <p v-if="ramStatus==='partial'">{{ t('部分进程暂不可读取，当前显示已读取部分。') }}</p>
        <p v-if="privateWorking&&ramStatus==='unavailable'">{{ t('私有工作集暂不可读取，不使用工作集或提交量替代。') }}</p>
        <button v-if="failed" class="desk-text-btn" @click="emit('retry')"><RefreshCw :size="13"/>{{ t('重新读取内存') }}</button>
      </div>
    </details>
  </section>
</template>
