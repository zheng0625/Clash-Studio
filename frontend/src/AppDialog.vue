<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, useId, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { t } from './i18n'
const props=withDefaults(defineProps<{title:string;description?:string;modelValue?:boolean;dirty?:boolean;busy?:boolean;closeLabel?:string;initialFocus?:string}>(),{dirty:false,busy:false,closeLabel:'关闭设置窗口'})
const emit=defineEmits<{'update:modelValue':[value:boolean];closed:[]}>()
const id=useId(),panel=ref<HTMLDialogElement|null>(null),discardPrompt=ref(false),opened=ref(false)
let previous:HTMLElement|null=null,mounted=false,openTicket=0
async function open(){const ticket=++openTicket;await nextTick();if(!mounted||ticket!==openTicket||!panel.value||panel.value.open)return;previous=document.activeElement instanceof HTMLElement?document.activeElement:null;discardPrompt.value=false;opened.value=true;await nextTick();if(!mounted||ticket!==openTicket)return;panel.value.showModal();await nextTick();const preferred=props.initialFocus?panel.value.querySelector<HTMLElement>(props.initialFocus):panel.value.querySelector<HTMLElement>('input:not([type=checkbox]):not(:disabled),textarea:not(:disabled),select:not(:disabled)');preferred?.focus()}
function close(){++openTicket;discardPrompt.value=false;emit('update:modelValue',false);if(panel.value?.open)panel.value.close();else opened.value=false}
async function requestClose(){if(props.busy||panel.value?.inert)return;if(discardPrompt.value){discardPrompt.value=false;return}if(props.dirty){discardPrompt.value=true;await nextTick();panel.value?.querySelector<HTMLElement>('[data-keep-editing]')?.focus();return}close()}
function closed(){if(panel.value?.open)return;opened.value=false;emit('update:modelValue',false);emit('closed');if(previous?.isConnected)previous.focus();previous=null}
function trapFocus(event:KeyboardEvent){if(event.key!=='Tab')return;const controls=Array.from(panel.value?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]')||[]).filter(element=>element.getClientRects().length&&!element.closest('[inert]'));const first=controls[0],last=controls.at(-1);if(!first||!last){event.preventDefault();return}if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}}
watch(()=>props.modelValue,value=>{if(value)void open();else if(value===false)close()})
onMounted(()=>{mounted=true;if(props.modelValue)void open()})
onUnmounted(()=>{mounted=false;++openTicket;if(panel.value?.open)panel.value.close();if(previous?.isConnected)previous.focus()})
defineExpose({open,close,requestClose})
</script>
<template>
 <dialog ref="panel" class="desk-modal settings-dialog app-dialog" aria-modal="true" :aria-busy="busy||undefined" :data-dialog-dirty="dirty" :aria-labelledby="id" :aria-describedby="description?id+'-description':undefined" :aria-label="title" @cancel.prevent="requestClose" @close="closed" @keydown="trapFocus" @click.self="requestClose">
  <header class="settings-dialog-heading app-dialog-heading"><div><h2 :id="id">{{ title }}</h2><p v-if="description" :id="id+'-description'">{{ description }}</p></div><button type="button" class="desk-icon-btn" :aria-label="t(closeLabel)" :disabled="busy" @click="requestClose"><X :size="20"/></button></header>
  <div v-if="opened" class="settings-dialog-body app-dialog-body"><slot/></div>
  <footer v-if="opened&&(discardPrompt||$slots.footer)" class="app-dialog-footer"><template v-if="discardPrompt"><p role="alert">{{ t('有未保存的输入，确定丢弃并关闭？') }}</p><button type="button" class="desk-btn primary" data-keep-editing @click="discardPrompt=false">{{ t('继续编辑') }}</button><button type="button" class="desk-btn danger" @click="close">{{ t('丢弃输入') }}</button></template><slot v-else name="footer"/></footer>
 </dialog>
</template>
