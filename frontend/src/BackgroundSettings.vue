<script setup lang="ts">
import { t, message, locale } from './i18n'

import { computed, onUnmounted, ref } from 'vue'
import { ImagePlus, Trash2, Save, RotateCcw, Crop as CropIcon } from 'lucide-vue-next'
import SettingsDialog from './SettingsDialog.vue'
import { backgroundState, readBackground, preparePhoto, photoInfo, saveBackground, clearBackground, type Wallpaper } from './background'
import { currentTheme, lightTheme, darkTheme, readableCoverage, secondaryColor } from './theme'
const emit=defineEmits<{notice:[message:string,error?:boolean]}>()
const dialog=ref<InstanceType<typeof SettingsDialog>|null>(null),stage=ref<HTMLElement|null>(null)
const source=ref<Blob|null>(null),sourceUrl=ref(''),name=ref(''),size=ref({width:1,height:1,dark:false})
const shade=ref(45),blur=ref(0),panel=ref(92),adapt=ref(false),busy=ref(false),error=ref(''),ratio=ref('window'),zoom=ref(1),cx=ref(.5),cy=ref(.5),windowRatio=ref(1.5)
let sequence=0,disposed=false,drag:{id:number;x:number;y:number}|null=null
const aspect=computed(()=>ratio.value==='source'?size.value.width/size.value.height:ratio.value==='16:9'?16/9:ratio.value==='4:3'?4/3:windowRatio.value)
const geometry=computed(()=>{const scale=Math.max(1/size.value.width,1/(aspect.value*size.value.height))*zoom.value;return {width:size.value.width*scale,height:size.value.height*scale}})
const crop=computed(()=>{const width=1/geometry.value.width,height=1/(aspect.value*geometry.value.height);const x=Math.max(width/2,Math.min(1-width/2,cx.value)),y=Math.max(height/2,Math.min(1-height/2,cy.value));return {x:Math.max(0,x-width/2),y:Math.max(0,y-height/2),width:Math.min(1,width),height:Math.min(1,height)}})
const imageStyle=computed(()=>({width:`${100/crop.value.width}%`,height:`${100/crop.value.height}%`,left:`${-crop.value.x/crop.value.width*100}%`,top:`${-crop.value.y/crop.value.height*100}%`}))
const palette=computed(()=>adapt.value?{...(size.value.dark?darkTheme:lightTheme),accent:currentTheme.value.accent}:currentTheme.value)
const previewStyle=computed(()=>({'--photo-surface':palette.value.surface,'--photo-text':palette.value.text,'--photo-side':palette.value.sidebar,'--photo-side-text':palette.value.sidebarText,'--photo-accent':palette.value.accent,'--photo-bg':palette.value.background,'--photo-panel':Math.max(readableCoverage(palette.value.surface,palette.value.text,panel.value),readableCoverage(palette.value.surface,secondaryColor(palette.value,adapt.value),panel.value))+'%','--photo-chrome':readableCoverage(palette.value.sidebar,palette.value.sidebarText,Math.max(80,panel.value-8))+'%','--photo-shade':shade.value+'%','--photo-blur':blur.value+'px',aspectRatio:String(aspect.value)}))
const savedSignature=ref('')
const photoSignature=computed(()=>JSON.stringify({source:sourceUrl.value,shade:shade.value,blur:blur.value,panel:panel.value,adapt:adapt.value,crop:crop.value,ratio:ratio.value}))
const photoDirty=computed(()=>!!source.value&&photoSignature.value!==savedSignature.value)
function reset(){zoom.value=1;cx.value=cy.value=.5}
async function install(blob:Blob,label:string,saved:Wallpaper|undefined,ticket:number){
  const info=await photoInfo(blob);if(disposed||ticket!==sequence)return
  if(sourceUrl.value)URL.revokeObjectURL(sourceUrl.value)
  source.value=blob;sourceUrl.value=URL.createObjectURL(blob);name.value=label;size.value=info;ratio.value=saved?.ratio??'window';reset()
  if(saved?.crop){cx.value=saved.crop.x+saved.crop.width/2;cy.value=saved.crop.y+saved.crop.height/2;zoom.value=Math.max(1,Math.min(4,(1/(info.width*saved.crop.width))/Math.max(1/info.width,1/(aspect.value*info.height))))}
}
async function open(){
  const ticket=++sequence;windowRatio.value=window.innerWidth/window.innerHeight;source.value=null;name.value='';if(sourceUrl.value)URL.revokeObjectURL(sourceUrl.value);sourceUrl.value='';error.value='';busy.value=true
  const current=backgroundState.value;shade.value=current.shade;blur.value=current.blur;panel.value=current.panel;adapt.value=current.adapt;dialog.value?.open()
  try{const saved=await readBackground();if(saved)await install(saved.blob,saved.name,saved,ticket)}catch(e){error.value=(e as Error).message}finally{if(ticket===sequence){savedSignature.value=photoSignature.value;busy.value=false}}
}
async function select(event:Event){
  const input=event.target as HTMLInputElement,file=input.files?.[0];input.value='';if(!file)return
  const ticket=++sequence;busy.value=true;error.value=''
  try{const blob=await preparePhoto(file);await install(blob,file.name,undefined,ticket)}catch(e){error.value=(e as Error).message}finally{if(ticket===sequence)busy.value=false}
}
function pointerDown(event:PointerEvent){if(busy.value||!source.value)return;drag={id:event.pointerId,x:event.clientX,y:event.clientY};stage.value?.setPointerCapture(event.pointerId)}
function pointerMove(event:PointerEvent){if(!drag||drag.id!==event.pointerId||!stage.value)return;const width=stage.value.clientWidth;cx.value=crop.value.x+crop.value.width/2-(event.clientX-drag.x)/(width*geometry.value.width);cy.value=crop.value.y+crop.value.height/2-(event.clientY-drag.y)/(width*geometry.value.height);drag.x=event.clientX;drag.y=event.clientY}
function keyMove(event:KeyboardEvent){if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();const step=event.shiftKey?.05:.01;cx.value=crop.value.x+crop.value.width/2+(event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0);cy.value=crop.value.y+crop.value.height/2+(event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0)}
async function save(){if(busy.value||!source.value)return;busy.value=true;error.value='';try{await saveBackground({blob:source.value,name:name.value,shade:shade.value,blur:blur.value,panel:panel.value,adapt:adapt.value,dark:size.value.dark,crop:crop.value,ratio:ratio.value});savedSignature.value=photoSignature.value;emit('notice',t("照片裁切、配色与背景效果已保存"))}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
async function clear(){if(busy.value)return;busy.value=true;try{await clearBackground();++sequence;source.value=null;if(sourceUrl.value)URL.revokeObjectURL(sourceUrl.value);sourceUrl.value='';error.value='';emit('notice',t("已清除照片，恢复原配色"))}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
onUnmounted(()=>{disposed=true;++sequence;if(sourceUrl.value)URL.revokeObjectURL(sourceUrl.value)})
</script>
<template>
  <section class="desk-card appearance-entry"><div><ImagePlus :size="22"/><div><h2>{{ t("背景图片") }}</h2><p>{{ backgroundState.hasImage?backgroundState.name:t("全窗口照片背景 · 预览与裁切") }}</p></div></div><button class="desk-btn" @click="open">{{ t("设置背景 →") }}</button></section>
  <SettingsDialog ref="dialog" :dirty="photoDirty" :busy="busy" :title="t('照片背景与裁切')" :description="t('拖动照片选择区域，支持缩放和方向键微调；保存前不会改变当前背景。')">
    <label class="desk-field photo-file">{{ t("选择本地照片") }}<input type="file" accept="image/jpeg,image/png,image/webp" :disabled="busy" @change="select"/></label>
    <p class="small-explanation">{{ name||t("支持 JPEG / PNG / WebP，最大 15 MB；仅本机保存，不修改原照片。") }}</p>
    <template v-if="sourceUrl">
      <div class="crop-toolbar"><CropIcon :size="16"/><label>{{ t("裁切比例") }}<select v-model="ratio" :disabled="busy"><option value="window">{{ t("当前窗口") }}</option><option value="16:9">16:9</option><option value="4:3">4:3</option><option value="source">{{ t("原图比例") }}</option></select></label><button class="desk-btn" :disabled="busy" @click="reset"><RotateCcw :size="14"/>{{ t("居中重置") }}</button></div>
      <div ref="stage" class="photo-crop-stage" :style="{width:`min(100%, ${Math.min(720,340*aspect)}px)`,aspectRatio:String(aspect)}" tabindex="0" role="group" :aria-label="t('照片裁切区域，可拖动或使用方向键')" @pointerdown="pointerDown" @pointermove="pointerMove" @pointerup="drag=null" @pointercancel="drag=null" @lostpointercapture="drag=null" @keydown="keyMove"><img :src="sourceUrl" :style="imageStyle" :alt="t('待裁切照片')" draggable="false"/><span class="crop-guides" aria-hidden="true"/></div>
      <label class="desk-field photo-slider">{{ t("缩放 · {0}×", [zoom.toFixed(2)]) }}<input v-model.number="zoom" type="range" min="1" max="4" step="0.01" :disabled="busy"/></label>
      <div class="photo-options"><label class="desk-field">{{ t("配色方式") }}<select v-model="adapt" :disabled="busy"><option :value="false">{{ t("保留我的配色") }}</option><option :value="true">{{ t("根据照片自动适配") }}</option></select></label><label class="desk-field photo-slider">{{ t("照片遮罩 · {0}%", [shade]) }}<input v-model.number="shade" type="range" min="0" max="90" :disabled="busy"/></label><label class="desk-field photo-slider">{{ t("面板覆盖 · {0}%", [panel]) }}<input v-model.number="panel" type="range" min="75" max="100" :disabled="busy"/></label><label class="desk-field photo-slider">{{ t("背景模糊 · {0}px", [blur]) }}<input v-model.number="blur" type="range" min="0" max="20" :disabled="busy"/></label></div>
      <h3 class="submenu-heading">{{ t("整窗效果预览") }}</h3><div class="photo-window-preview" :style="previewStyle"><img :src="sourceUrl" :style="imageStyle" alt="" draggable="false"/><div class="photo-preview-shade"/><aside><strong>Clash Studio</strong><span>{{ t("概览") }}</span><span>{{ t("订阅") }}</span><span>{{ t("代理") }}</span><span>{{ t("设置") }}</span></aside><header>{{ t("工作空间 / 概览") }}<span>— □ ×</span></header><main><strong>{{ t("你的网络工作空间") }}</strong><article><span>{{ t("实时速率") }}</span><b>128 KB/s</b><i/></article></main></div>
      <p class="small-explanation">{{ t("自动模式不覆盖已保存的配色。面板至少保留 75% 覆盖，实际应用时会按正文及辅助文字对比度提高覆盖，避免照片明暗影响阅读。") }}</p>
    </template>
    <p v-else class="page-caption">{{ t("选择照片后即可预览和裁切。") }}</p><p v-if="error" class="desk-alert error" role="status">{{ message(error) }}</p>

  <template #footer><div class="config-actions"><button class="desk-btn primary" :disabled="busy||!source" @click="save"><Save :size="15"/>{{ busy?t("处理中…"):t("保存并应用") }}</button><button class="desk-btn" :disabled="busy||!backgroundState.hasImage" @click="clear"><Trash2 :size="15"/>{{ t("清除背景") }}</button></div></template></SettingsDialog>
</template>
