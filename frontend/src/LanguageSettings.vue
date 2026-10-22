<script setup lang="ts">
import { Languages } from 'lucide-vue-next'
import { language, locale, systemLanguage, t } from './i18n'
</script>
<template>
  <section class="desk-card language-settings">
    <div><Languages :size="22"/><div><h2>{{ t('界面语言') }}</h2><p>{{ t('默认跟随系统语言，切换后立即生效，无需重启。') }}</p></div></div>
    <label class="desk-field">{{ t('语言') }}<select v-model="language" :aria-label="t('界面语言')"><option value="auto">{{ t('跟随系统') }}</option><option value="zh-CN">简体中文</option><option value="en">English</option></select><small>{{ t('系统：{0} · 当前：{1}', [systemLanguage, locale==='en'?'English':'简体中文']) }}</small></label>
  </section>
</template>
