<script setup lang="ts">
import { t } from './i18n'
defineProps<{modelValue:number;pages:number;pageSize:number;label:string;disabled?:boolean}>()
const emit=defineEmits<{'update:modelValue':[page:number]}>()
</script>
<template>
  <nav v-if="pages>1" class="list-pagination" :aria-label="label">
    <button type="button" class="desk-btn" :disabled="disabled||modelValue===0" @click="emit('update:modelValue',modelValue-1)">{{ t('上一页') }}</button>
    <span role="status">{{ t('第 {0} / {1} 页 · 每页最多 {2} 条',[modelValue+1,pages,pageSize]) }}</span>
    <button type="button" class="desk-btn" :disabled="disabled||modelValue>=pages-1" @click="emit('update:modelValue',modelValue+1)">{{ t('下一页') }}</button>
  </nav>
</template>
<style scoped>
.list-pagination{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:12px;margin:16px 0}
</style>
