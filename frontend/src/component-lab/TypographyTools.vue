<script setup lang="ts">
import type { Selection } from './layout-editor'
import type { TypographyKey } from './typography'
defineProps<{selection:Selection|null;disabled:boolean}>()
const emit=defineEmits<{change:[key:TypographyKey,value:string|null];reset:[]}>()
const numbers=[{key:'font-size',label:'字号',min:1,max:240},{key:'line-height',label:'行高',min:1,max:600},{key:'letter-spacing',label:'字距',min:-20,max:100},{key:'text-indent',label:'首行缩进',min:-1000,max:1000}] as const
const menus=[
 {key:'font-weight',label:'字重',options:[['100','100 · 极细'],['200','200 · 细'],['300','300 · 较细'],['400','400 · 常规'],['500','500 · 中等'],['600','600 · 半粗'],['700','700 · 粗体'],['800','800 · 加粗'],['900','900 · 极粗']]},
 {key:'text-align',label:'文字对齐',options:[['start','随语言方向'],['left','左对齐'],['center','居中'],['right','右对齐'],['end','末端对齐'],['justify','两端对齐']]},
 {key:'white-space',label:'文字换行',options:[['normal','自动换行'],['nowrap','不换行'],['pre-wrap','保留空格并换行'],['pre-line','保留换行'],['break-spaces','保留所有空白']]},
 {key:'word-break',label:'长词换行',options:[['normal','默认规则'],['break-all','任意位置断行'],['keep-all','保持词组']]},
 {key:'writing-mode',label:'文字方向',options:[['horizontal-tb','横向排版'],['vertical-rl','纵向 · 从右到左'],['vertical-lr','纵向 · 从左到右']]},
] as const
function numeric(value?:string){const number=parseFloat(value||'');return Number.isFinite(number)?number:''}
function number(key:TypographyKey,event:Event){const input=event.target as HTMLInputElement;if(input.value===''){emit('change',key,null);return}if(input.validity.valid)emit('change',key,Number(input.value)+'px')}
</script>
<template>
 <fieldset class="lab-typography" :disabled="disabled"><legend>字体与文字排版</legend>
  <div class="lab-type-fields">
   <label v-for="field in numbers" :key="field.key">{{ field.label }} · px<input :aria-label="field.label" type="number" step="0.1" :min="field.min" :max="field.max" :value="numeric(selection?.typography[field.key])" placeholder="自动" @input="number(field.key,$event)"></label>
   <label v-for="menu in menus" :key="menu.key">{{ menu.label }}<select :aria-label="menu.label" :value="selection?.typography[menu.key]" @change="emit('change',menu.key,($event.target as HTMLSelectElement).value)"><option v-for="option in menu.options" :key="option[0]" :value="option[0]">{{ option[1] }}</option></select></label>
   <label>字体<select aria-label="字体" :value="selection?.typography['font-family']" @change="emit('change','font-family',($event.target as HTMLSelectElement).value)"><option v-if="selection" :value="selection.typography['font-family']">当前字体：{{ selection.typography['font-family'] }}</option><option value="inherit">继承父级字体</option><option value="system-ui, sans-serif">系统字体</option><option value="sans-serif">无衬线</option><option value="serif">衬线</option><option value="monospace">等宽</option></select></label>
  </div><div class="lab-designer-bar"><button type="button" class="lab-button" @click="emit('reset')">重置文字样式</button><small>选择文字或容器后调整；容器设置会影响继承该样式的子元素。清空数值可恢复默认。</small></div>
 </fieldset>
</template>
