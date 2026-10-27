<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppDialog from './AppDialog.vue'
import { t, message } from './i18n'
const props=defineProps<{title:string;description:string;confirmText:string;danger:boolean}>()
const emit=defineEmits<{result:[value:boolean]}>()
const panel=ref<InstanceType<typeof AppDialog>|null>(null)
let settled=false
function finish(value:boolean){if(settled)return;settled=true;panel.value?.close();emit('result',value)}
onMounted(()=>{void panel.value?.open()})
</script>
<template><AppDialog ref="panel" class="confirm-dialog" role="alertdialog" :title="t(props.title)" :description="message(props.description)" close-label="取消" initial-focus="[data-confirm-cancel]" @closed="finish(false)"><template #footer><div class="modal-actions"><button type="button" class="desk-btn" data-confirm-cancel @click="finish(false)">{{ t('取消') }}</button><button type="button" class="desk-btn" :class="danger?'danger':'primary'" @click="finish(true)">{{ t(confirmText) }}</button></div></template></AppDialog></template>
