<script setup lang="ts">
import { t } from './i18n'

import { computed, onMounted, ref, watch } from 'vue'
import { Palette, X, RotateCcw, Check } from 'lucide-vue-next'

type Theme = {accent:string;background:string;surface:string;text:string;sidebar:string;sidebarText:string}
const defaults:Theme={accent:'#202020',background:'#f6f6f6',surface:'#ffffff',text:'#242424',sidebar:'#161616',sidebarText:'#eeeeee'}
const presets=[
  {name:'极简黑白',colors:defaults},
  {name:'松林绿',colors:{accent:'#26735a',background:'#f3f6f2',surface:'#ffffff',text:'#263a30',sidebar:'#15291f',sidebarText:'#e1ede4'}},
  {name:'雾蓝',colors:{accent:'#3569ab',background:'#f2f5f9',surface:'#ffffff',text:'#243247',sidebar:'#172438',sidebarText:'#e4ecf7'}},
  {name:'暖砂',colors:{accent:'#8b6140',background:'#f6f2eb',surface:'#fffdf8',text:'#40372f',sidebar:'#302820',sidebarText:'#f2e8d9'}},
  {name:'深夜',colors:{accent:'#9abcf7',background:'#12151b',surface:'#1c222c',text:'#e3e8f0',sidebar:'#0d1016',sidebarText:'#dce4f0'}},
]
const fields:{key:keyof Theme;label:string}[]=[{key:'accent',label:'主色'},{key:'background',label:'页面背景'},{key:'surface',label:'卡片背景'},{key:'text',label:'文字颜色'},{key:'sidebar',label:'侧栏背景'},{key:'sidebarText',label:'侧栏文字'}]
const storageKey='clash-studio-theme-v1'
const valid=(v:unknown):v is string=>typeof v==='string' && /^#[0-9a-f]{6}$/i.test(v)
function readTheme():Theme{
  try{const saved=JSON.parse(localStorage.getItem(storageKey)||'null');return Object.fromEntries(fields.map(({key})=>[key,valid(saved?.[key])?saved[key]:defaults[key]])) as Theme}catch{return {...defaults}}
}
const theme=ref<Theme>(readTheme()), dialog=ref<HTMLDialogElement|null>(null), saveError=ref(false)
const activePreset=computed(()=>presets.find(p=>fields.every(f=>theme.value[f.key]===p.colors[f.key]))?.name)
function rgb(hex:string){return [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16))}
function mix(a:string,b:string,t:number){const x=rgb(a),y=rgb(b);return '#'+x.map((v,i)=>Math.round(v+(y[i]!-v)*t).toString(16).padStart(2,'0')).join('')}
function luminance(hex:string){const c=rgb(hex).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return .2126*c[0]!+.7152*c[1]!+.0722*c[2]!}
function contrast(a:string,b:string){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)}
const contrastWarning=computed(()=>contrast(theme.value.text,theme.value.surface)<4.5 || contrast(theme.value.text,theme.value.background)<4.5 || contrast(theme.value.sidebarText,theme.value.sidebar)<4.5)
function apply(){
  const t=theme.value,s=document.documentElement.style
  for(const [key,value] of Object.entries(t))s.setProperty('--theme-'+key,value)
  for(let n=0;n<256;n++){
    s.setProperty('--neutral-'+n,mix(t.text,t.surface,n/255))
    s.setProperty('--side-'+n,mix(t.sidebar,t.sidebarText,n/255))
  }
  s.setProperty('--theme-accent-ink',contrast('#ffffff',t.accent)>=contrast('#111111',t.accent)?'#ffffff':'#111111')
  s.setProperty('--theme-accent-hover',mix(t.accent,t.text,.16))
  s.colorScheme=luminance(t.surface)<.18?'dark':'light'
}
function updateHex(key:keyof Theme,event:Event){const input=event.target as HTMLInputElement;if(valid(input.value))theme.value[key]=input.value.toLowerCase();else input.value=theme.value[key]}
watch(theme,()=>{apply();try{localStorage.setItem(storageKey,JSON.stringify(theme.value));saveError.value=false}catch{saveError.value=true}},{deep:true,flush:'sync'})
onMounted(apply)
</script>

<template>
  <button class="theme-open" @click="dialog?.showModal()" :title="t('自定义界面配色')"><Palette :size="15"/><span>{{ t('配色') }}</span></button>
  <dialog ref="dialog" class="theme-dialog" aria-labelledby="theme-title" @click="($event.target===dialog)&&dialog?.close()">
    <header><div><span class="theme-eyebrow">APPEARANCE</span><h2 id="theme-title">{{ t('自定义配色') }}</h2></div><button class="icon-button" :aria-label="t('关闭配色设置')" @click="dialog?.close()"><X :size="19"/></button></header>
    <p class="theme-description">{{ t('选择一个起点，再调整成你喜欢的颜色。') }}</p>
    <div class="theme-presets"><button v-for="preset in presets" :key="preset.name" :aria-pressed="activePreset===preset.name" @click="theme={...preset.colors}"><span class="theme-swatches"><i v-for="key in ['sidebar','accent','surface'] as const" :key="key" :style="{background:preset.colors[key]}"/></span><span>{{ t(preset.name) }}</span><Check v-if="activePreset===preset.name" :size="12"/></button></div>
    <div class="theme-fields"><label v-for="field in fields" :key="field.key"><span>{{ t(field.label) }}</span><div class="theme-color-field"><input type="color" v-model="theme[field.key]" :aria-label="t(field.label)+t('颜色选择器')"/><input type="text" :value="theme[field.key]" :aria-label="t(field.label)+t('十六进制色值')" maxlength="7" spellcheck="false" @change="updateHex(field.key,$event)"/></div></label></div>
    <p v-if="contrastWarning" class="theme-warning" role="status">{{ t('部分文字与背景对比度较低，建议调整颜色以方便阅读。') }}</p>
    <p v-if="saveError" class="theme-warning" role="status">{{ t('浏览器未能保存配色，本次预览仍然有效。') }}</p>
    <footer><button class="text-button" @click="theme={...defaults}"><RotateCcw :size="13"/>{{ t('恢复默认') }}</button><span>{{ t('实时生效 · 自动保存在当前浏览器') }}</span><button class="button primary small" @click="dialog?.close()">{{ t('完成') }}</button></footer>
  </dialog>
</template>
