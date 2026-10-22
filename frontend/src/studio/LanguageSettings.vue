<script setup lang="ts">
import { language, locale } from './i18n'
</script>
<template>
  <label class="language-control"><span class="sr-only">{{ locale==='en'?'Interface language':'界面语言' }}</span><select v-model="language" :aria-label="locale==='en'?'Interface language':'界面语言'"><option value="auto">{{ locale==='en'?'Auto language':'自动语言' }}</option><option value="zh-CN">简体中文</option><option value="en">English</option></select></label>
</template>
<style>
.language-control{display:inline-flex;flex-direction:row;flex-shrink:0}.language-control select{width:auto;max-width:140px;font-size:11px;padding:7px 22px 7px 8px;color:var(--ink);background:var(--paper);border-color:var(--line)}
html[lang=en] .topbar-right{gap:14px}html[lang=en] .heading-actions{flex-wrap:wrap}html[lang=en] .page-heading{flex-wrap:wrap}html[lang=en] .group-card-foot{flex-wrap:wrap}html[lang=en] .sidebar-foot{letter-spacing:.3px}html[lang=en] .welcome-heading h1{font-family:Inter,"Segoe UI",sans-serif}html[lang=en] .ai-banner-title{flex-wrap:wrap}html[lang=en] .link-mode>button{white-space:normal}
@media(max-width:760px){.language-control select{font-size:10px;max-width:105px;padding:6px 18px 6px 7px}.topbar-right{gap:7px!important}.topbar-right .local-indicator{display:none}html[lang=en] .tabs{gap:16px}html[lang=en] .member-options{grid-template-columns:1fr}html[lang=en] .theme-dialog footer{flex-wrap:wrap}html[lang=en] .modal-footer{flex-wrap:wrap}}
@media(max-width:480px){.topbar{padding-left:12px;padding-right:12px}.breadcrumbs{flex:1;overflow:hidden}.breadcrumbs>span,.breadcrumbs>svg{display:none}.breadcrumbs strong{max-width:78px}.theme-open>span{display:none}.theme-open{padding:6px 8px}}
</style>
