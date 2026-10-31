<script setup lang="ts">
import {ArrowRight,ChevronDown,ChevronRight,ShieldCheck} from 'lucide-vue-next'
import {t} from './i18n'
type Module={id:string;name:string;strict:boolean;target:string}
defineProps<{activeModules:Module[];visibleModules:Module[];selected:string;modulePage:number;modulePageCount:number}>()
const emit=defineEmits<{manage:[];page:[value:number]}>()
</script>
<template><section class="desk-card flow-card"><div class="section-head"><h2>{{ t('已启用模块') }} <span class="small-badge">{{ activeModules.length }}</span></h2><button class="desk-text-btn" @click="emit('manage')">{{ t('管理') }}<ChevronRight :size="14"/></button></div><div class="compact-module-list"><div v-for="m in visibleModules" :key="m.id" class="compact-module-row"><strong>{{ m.name }} <ShieldCheck v-if="m.strict" :size="13" :aria-label="t('限定出口')"/></strong><span :title="m.target">{{ m.target }}<ArrowRight :size="13"/></span></div><p v-if="!activeModules.length" class="compact-module-empty">{{ selected?t('当前方案未启用模块。'):t('先导入订阅') }}</p></div><div v-if="modulePageCount>1" class="module-pagination"><span>{{ t('每页 3 项') }}</span><div><button class="desk-icon-btn" :disabled="modulePage===0" :aria-label="t('上一页模块')" @click="emit('page',modulePage-1)"><ChevronDown :size="14" class="module-prev"/></button><span>{{ modulePage+1 }} / {{ modulePageCount }}</span><button class="desk-icon-btn" :disabled="modulePage===modulePageCount-1" :aria-label="t('下一页模块')" @click="emit('page',modulePage+1)"><ChevronRight :size="14"/></button></div></div></section></template>
