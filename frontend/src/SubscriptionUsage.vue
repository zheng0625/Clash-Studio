<script setup lang="ts">
import { t } from './i18n'
import type { Summary } from './types'
defineProps<{usage:Summary['usage'];updatedAt:string}>()
function size(n:number){if(n===0)return '0 B';const i=Math.min(4,Math.floor(Math.log(n)/Math.log(1024)));return `${(n/1024**i).toFixed(i?1:0)} ${['B','KB','MB','GB','TB'][i]}`}
</script>
<template>
  <section class="subscription-usage" :aria-label="t('订阅流量')">
    <div class="usage-heading"><strong>{{ t('订阅流量') }}</strong><span v-if="usage?.percent!==null&&usage?.percent!==undefined">{{ usage.percent.toFixed(1) }}%</span></div>
    <template v-if="usage">
      <div class="usage-numbers"><span>{{ t('已用') }} <b>{{ size(usage.used) }}</b></span><span>{{ t('总量') }} <b>{{ usage.total===null?t('未知'):size(usage.total) }}</b></span></div>
      <progress v-if="usage.percent!==null" :value="usage.percent" max="100" :aria-label="t('订阅流量使用进度')"></progress><div v-else class="usage-track"></div>
      <div class="usage-caption"><span>{{ t('剩余') }} {{ usage.remaining===null?t('未知'):size(usage.remaining) }}</span><span v-if="usage.total!==null&&usage.used>=usage.total">{{ t('额度已用尽') }}</span></div>
      <small>{{ t('服务商数据 · 随订阅刷新更新') }}</small>
    </template>
    <template v-else><div class="usage-track"></div><p>{{ t('未提供流量信息') }}</p></template>
  </section>
</template>
