<script setup lang="ts">
import { t, message, locale } from './i18n'

import { onMounted, onUnmounted, ref } from 'vue'
import { X } from 'lucide-vue-next'

defineProps<{title:string;description:string;confirmText:string;danger:boolean}>()
const emit=defineEmits<{result:[value:boolean]}>()
const panel=ref<HTMLElement|null>(null), cancel=ref<HTMLButtonElement|null>(null)
function keyboard(event:KeyboardEvent){
  if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();emit('result',false)}
  if(event.key==='Tab'){
    const buttons=panel.value?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')
    if(!buttons?.length)return
    const first=buttons[0]!,last=buttons[buttons.length-1]!
    if(event.shiftKey&&(document.activeElement===first||!panel.value?.contains(document.activeElement))){event.preventDefault();last.focus()}
    else if(!event.shiftKey&&(document.activeElement===last||!panel.value?.contains(document.activeElement))){event.preventDefault();first.focus()}
  }
}
onMounted(()=>{cancel.value?.focus();document.addEventListener('keydown',keyboard,true)})
onUnmounted(()=>document.removeEventListener('keydown',keyboard,true))
</script>

<template>
  <div class="desk-backdrop confirm-backdrop" @click.self="emit('result',false)">
    <section ref="panel" class="desk-modal confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirmation-title" aria-describedby="confirmation-description">
      <button class="modal-x desk-icon-btn" :aria-label="t('取消')" @click="emit('result',false)"><X :size="20"/></button>
      <h2 id="confirmation-title">{{ t(title) }}</h2>
      <p id="confirmation-description">{{ message(description) }}</p>
      <div class="modal-actions">
        <button ref="cancel" class="desk-btn" @click="emit('result',false)">{{ t("取消") }}</button>
        <button class="desk-btn" :class="danger?'danger':'primary'" @click="emit('result',true)">{{ t(confirmText) }}</button>
      </div>
    </section>
  </div>
</template>
