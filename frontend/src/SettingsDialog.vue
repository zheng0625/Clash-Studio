<script setup lang="ts">
import { ref } from 'vue'
import AppDialog from './AppDialog.vue'
const props=defineProps<{title:string;description?:string;dirty?:boolean;busy?:boolean}>()
const dialog=ref<InstanceType<typeof AppDialog>|null>(null)
defineExpose({open:()=>dialog.value?.open(),close:()=>dialog.value?.close(),requestClose:()=>dialog.value?.requestClose()})
</script>
<template><AppDialog ref="dialog" v-bind="props"><slot/><template v-if="$slots.footer" #footer><slot name="footer"/></template></AppDialog></template>
