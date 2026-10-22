<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, ref } from 'vue'
import { Check, Palette, RotateCcw, Save } from 'lucide-vue-next'
import { currentTheme, defaultTheme, themeFields, themePresets, themeError, contrast, saveTheme, resetTheme, type ClientTheme } from './theme'
import SettingsDialog from './SettingsDialog.vue'
import { backgroundState } from './background'

const emit=defineEmits<{notice:[message:string,error?:boolean]}>()
const draft=ref<ClientTheme>({...currentTheme.value}), error=ref('')
const dialog=ref<InstanceType<typeof SettingsDialog>|null>(null)
function open(){draft.value={...currentTheme.value};error.value='';dialog.value?.open()}
const validation=computed(()=>themeError(draft.value))
const activePreset=computed(()=>themePresets.find(p=>themeFields.every(f=>p.colors[f.key].toLowerCase()===draft.value[f.key].toLowerCase()))?.name)
function save(){try{saveTheme(draft.value);error.value='';emit('notice',t("界面配色已保存并生效"))}catch(e){error.value=(e as Error).message}}
function reset(){try{resetTheme();draft.value={...defaultTheme};error.value='';emit('notice',t("已恢复默认配色"))}catch{error.value=t("无法清除本机配色记录，请检查本地存储是否可用。")}}
function ratio(value:number){return Number.isFinite(value)?value.toFixed(2):'—'}
</script>

<template>
  <section class="desk-card appearance-entry"><div><Palette :size="22"/><div><h2>{{ t("外观与配色") }}</h2><p>{{ t("选择配色预设，定制你喜欢的界面。") }}</p></div></div><button class="desk-btn" @click="open">{{ t("自定义配色 →") }}</button></section>
  <SettingsDialog ref="dialog" :title="t('自定义配色')" :description="t('选择预设或调整颜色，保存后全局生效并在下次启动时恢复。')">
    <p v-if="backgroundState.adapt" class="small-explanation">{{ t("当前由照片自动适配界面；颜色会保留。如需完整应用自定义配色，请在背景设置中选择“保留我的配色”。") }}</p>
    <div class="appearance-presets" role="group" :aria-label="t('配色预设')">
      <button v-for="preset in themePresets" :key="preset.name" type="button" :aria-pressed="activePreset===preset.name" @click="draft={...preset.colors};error=''">
        <span class="appearance-swatches" aria-hidden="true"><i v-for="key in ['sidebar','accent','surface'] as const" :key="key" :style="{background:preset.colors[key]}"/></span>{{ t(preset.name) }}<Check v-if="activePreset===preset.name" :size="14"/>
      </button>
    </div>
    <div class="appearance-body">
      <div class="appearance-fields"><label v-for="field in themeFields" :key="field.key" class="desk-field">{{ t(field.label) }}<span class="appearance-color"><input v-model="draft[field.key]" type="color" :aria-label="t(field.label)+t('颜色选择器')"/><input v-model="draft[field.key]" type="text" :aria-label="t(field.label)+t('十六进制色值')" pattern="#[0-9a-fA-F]{6}" maxlength="7" spellcheck="false" autocomplete="off"/></span></label></div>
      <div class="appearance-preview" :style="{'--preview-bg':draft.background,'--preview-surface':draft.surface,'--preview-text':draft.text,'--preview-accent':draft.accent,'--preview-side':draft.sidebar,'--preview-side-text':draft.sidebarText}">
        <div class="appearance-preview-side">Clash Studio<br><span>{{ t("概览") }}</span><span>{{ t("代理") }}</span><span>{{ t("设置") }}</span></div>
        <div class="appearance-preview-main"><strong>{{ t("配色预览") }}</strong><div><span>{{ t("实时速率") }}</span><strong>128 KB/s</strong><i aria-hidden="true"/></div></div>
      </div>
    </div>
    <p class="small-explanation">{{ t("正文对比度：{0}:1 · 侧栏：{1}:1。保存要求至少 4.5:1，辅助文字及按钮文字自动适配。", [ratio(Math.min(contrast(draft.text,draft.surface),contrast(draft.text,draft.background))), ratio(contrast(draft.sidebarText,draft.sidebar))]) }}</p>
    <p v-if="validation||error" class="desk-alert error" role="status">{{ message(error||validation) }}</p>
    <div class="config-actions"><button type="button" class="desk-btn primary" :disabled="!!validation" @click="save"><Save :size="15"/>{{ t("保存配色") }}</button><button type="button" class="desk-btn" @click="reset"><RotateCcw :size="15"/>{{ t("恢复默认") }}</button><span class="small-explanation">{{ t("只影响界面外观，无需重启内核。") }}</span></div>
  </SettingsDialog>
</template>
