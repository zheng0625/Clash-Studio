<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, ref } from 'vue'
import { Copy, Search, Trash2 } from 'lucide-vue-next'
const props=defineProps<{events:{time:string;message:string}[]}>()
const emit=defineEmits<{notice:[message:string,error?:boolean]}>()
const query=ref(''),level=ref('all'),hidden=ref(new Set<string>())
const key=(event:{time:string;message:string})=>event.time+'\n'+event.message
function category(message:string){return /失败|异常|错误|未确认/.test(message)?'error':/冲突|缺少|警告/.test(message)?'warning':'info'}
const visible=computed(()=>[...props.events].reverse().filter(e=>!hidden.value.has(key(e))&&(level.value==='all'||category(e.message)===level.value)&&`${e.time} ${e.message} ${message(e.message)}`.toLowerCase().includes(query.value.toLowerCase())))
async function copy(){try{await navigator.clipboard.writeText(visible.value.map(e=>`${e.time} ${e.message}`).join('\n'));emit('notice',t("当前筛选结果已复制"))}catch{emit('notice',t("复制失败，请手动选择日志文字"),true)}}
</script>
<template>
  <section class="desk-card runtime-log-panel">
    <div class="section-head"><div><h2>{{ t("运行日志") }}</h2><p>{{ t("本程序记录的最近运行事件；级别按消息内容分类。") }}</p></div><span class="small-badge">{{ t("{0} 条", [visible.length]) }}</span></div>
    <div class="log-toolbar"><label class="desk-search"><Search :size="16"/><input v-model="query" :placeholder="t('搜索运行事件')" :aria-label="t('搜索运行日志')"/></label><select v-model="level" :aria-label="t('筛选日志级别')"><option value="all">{{ t("全部级别") }}</option><option value="info">{{ t("信息") }}</option><option value="warning">{{ t("提醒") }}</option><option value="error">{{ t("异常") }}</option></select><button class="desk-btn" :disabled="!visible.length" @click="copy"><Copy :size="14"/>{{ t("复制筛选结果") }}</button><button class="desk-btn" @click="hidden=new Set(props.events.map(key))"><Trash2 :size="14"/>{{ t("清空显示") }}</button><button v-if="hidden.size" class="desk-text-btn" @click="hidden=new Set()">{{ t("恢复显示") }}</button></div>
    <div class="runtime-log-rows"><article v-for="(event,index) in visible" :key="key(event)+index"><code>{{ event.time }}</code><span class="log-level" :class="category(event.message)">{{ {info:t("信息"),warning:t("提醒"),error:t("异常")}[category(event.message)] }}</span><p>{{ message(event.message) }}</p></article><p v-if="!visible.length" class="page-caption">{{ t("暂无符合条件的事件。清空显示不会删除磁盘日志。") }}</p></div>
  </section>
</template>
