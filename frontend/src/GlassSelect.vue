<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, useId } from 'vue'
import { Check, ChevronDown } from 'lucide-vue-next'
const props=defineProps<{modelValue:string;options:{value:string;label:string}[];label:string}>()
const emit=defineEmits<{ 'update:modelValue':[value:string] }>()
const id=useId(),open=ref(false),active=ref(0),trigger=ref<HTMLButtonElement>(),menu=ref<HTMLDivElement>(),position=ref<Record<string,string>>({})
const selected=computed(()=>props.options.find(o=>o.value===props.modelValue)?.label||props.modelValue)
function place(){const r=trigger.value!.getBoundingClientRect();const height=Math.min(260,innerHeight-24);const below=innerHeight-r.bottom-12;position.value={left:Math.max(12,Math.min(r.left,innerWidth-r.width-12))+'px',width:r.width+'px',maxHeight:Math.max(96,Math.min(height,below>=140?below:r.top-12))+'px',...(below>=140?{top:r.bottom+6+'px'}:{bottom:innerHeight-r.top+6+'px'})}}
async function show(){open.value=!open.value;if(open.value){active.value=Math.max(0,props.options.findIndex(o=>o.value===props.modelValue));place();await nextTick();reveal()}}
function reveal(){menu.value?.querySelectorAll('[role=option]')[active.value]?.scrollIntoView({block:'nearest'})}
function choose(i:number){const item=props.options[i];if(item)emit('update:modelValue',item.value);open.value=false;trigger.value?.focus()}
function key(event:KeyboardEvent){if(['ArrowDown','ArrowUp','Home','End','Enter',' ','Escape'].includes(event.key)){event.preventDefault();if(event.key==='Escape'){open.value=false;return}if(!open.value){void show();return}if(event.key==='Enter'||event.key===' '){choose(active.value);return}active.value=event.key==='Home'?0:event.key==='End'?props.options.length-1:(active.value+(event.key==='ArrowDown'?1:-1)+props.options.length)%props.options.length;void nextTick(reveal)}else if(event.key==='Tab')open.value=false}
function outside(event:Event){if(!trigger.value?.contains(event.target as Node)&&!menu.value?.contains(event.target as Node))open.value=false}
onMounted(()=>{document.addEventListener('pointerdown',outside);window.addEventListener('scroll',outside,true);window.addEventListener('resize',outside)})
onUnmounted(()=>{document.removeEventListener('pointerdown',outside);window.removeEventListener('scroll',outside,true);window.removeEventListener('resize',outside)})
</script>
<template>
  <div class="glass-select"><button ref="trigger" type="button" class="glass-select-trigger" role="combobox" aria-haspopup="listbox" :aria-label="label" :aria-expanded="open" :aria-controls="id" :aria-activedescendant="open?id+'-'+active:undefined" @click="show" @keydown="key"><span>{{ selected }}</span><ChevronDown :size="14"/></button>
    <Teleport to="body"><div v-if="open" :id="id" ref="menu" class="glass-select-menu" role="listbox" :aria-label="label" :style="position" @pointerdown.prevent><button v-for="(item,i) in options" :id="id+'-'+i" :key="item.value" type="button" role="option" :aria-selected="modelValue===item.value" :class="{highlight:active===i}" @pointermove="active=i" @click="choose(i)"><span>{{ item.label }}</span><Check v-if="modelValue===item.value" :size="14"/></button></div></Teleport>
  </div>
</template>
