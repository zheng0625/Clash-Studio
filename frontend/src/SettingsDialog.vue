<script setup lang="ts">
import { t, message, locale } from './i18n'

import { ref } from 'vue'
import { X } from 'lucide-vue-next'
defineProps<{title:string;description?:string}>()
const dialog=ref<HTMLDialogElement|null>(null)
defineExpose({open:()=>dialog.value?.showModal(),close:()=>dialog.value?.close()})
</script>
<template>
  <dialog ref="dialog" class="desk-modal settings-dialog" :aria-label="title" @click="($event.target===dialog)&&dialog?.close()">
    <header class="settings-dialog-heading"><div><h2>{{ t(title) }}</h2><p v-if="description">{{ t(description||'') }}</p></div><button type="button" class="desk-icon-btn" :aria-label="t('关闭设置窗口')" @click="dialog?.close()"><X :size="20"/></button></header>
    <div class="settings-dialog-body"><slot/></div>
  </dialog>
</template>
