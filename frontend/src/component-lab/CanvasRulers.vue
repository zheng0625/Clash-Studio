<script setup lang="ts">
import { computed } from 'vue'
const props=withDefaults(defineProps<{width:number;height:number;scale?:number;grid?:boolean;marker?:{x:number;y:number;width:number;height:number}|null}>(),{scale:1,grid:false,marker:null})
const step=computed(()=>props.scale>=.75?10:props.scale>=.35?20:50)
const major=computed(()=>step.value*5)
const ticks=(length:number)=>Array.from({length:Math.floor(length/step.value)+1},(_,i)=>i*step.value)
const horizontal=computed(()=>ticks(props.width)),vertical=computed(()=>ticks(props.height))
const size=computed(()=>({width:props.width*props.scale,height:props.height*props.scale}))
const guidesX=computed(()=>props.marker?[props.marker.x,props.marker.x+props.marker.width].filter(x=>x>=0&&x<=props.width):[])
const guidesY=computed(()=>props.marker?[props.marker.y,props.marker.y+props.marker.height].filter(y=>y>=0&&y<=props.height):[])
const center=computed(()=>props.marker?{x:props.marker.x+props.marker.width/2,y:props.marker.y+props.marker.height/2}:null)
const centerVisible=computed(()=>center.value&&center.value.x>=0&&center.value.x<=props.width&&center.value.y>=0&&center.value.y<=props.height)
</script>
<template>
  <div class="ruler-board" :style="{width:size.width+24+'px',height:size.height+24+'px'}">
    <div class="ruler-origin" title="画布原点 (0, 0)，单位为 CSS 像素">px</div>
    <svg class="ruler-horizontal" role="img" aria-label="水平像素刻度尺" :width="size.width" height="24">
      <g v-for="value in horizontal" :key="value" :data-pixel="value" :transform="`translate(${value*scale},0)`"><line x1="0" x2="0" :y1="value%major===0?14:19" y2="24"/><text v-if="value%major===0" x="3" y="10">{{ value }}</text></g>
      <rect v-if="marker" :x="Math.max(0,marker.x*scale)" y="20" :width="Math.max(0,Math.min(size.width,(marker.x+marker.width)*scale)-Math.max(0,marker.x*scale))" height="4"/>
    </svg>
    <svg class="ruler-vertical" role="img" aria-label="垂直像素刻度尺" width="24" :height="size.height">
      <g v-for="value in vertical" :key="value" :data-pixel="value" :transform="`translate(0,${value*scale})`"><line :x1="value%major===0?14:19" x2="24" y1="0" y2="0"/><text v-if="value%major===0" :transform="'translate(10,3) rotate(90)'">{{ value }}</text></g>
      <rect v-if="marker" x="20" :y="Math.max(0,marker.y*scale)" width="4" :height="Math.max(0,Math.min(size.height,(marker.y+marker.height)*scale)-Math.max(0,marker.y*scale))"/>
    </svg>
    <div class="ruler-content" :style="{width:size.width+'px',height:size.height+'px'}"><slot/>
      <div class="ruler-grid" v-if="grid" :style="{backgroundSize:`${10*scale}px ${10*scale}px`}" aria-hidden="true"></div>
      <div class="ruler-guides" aria-hidden="true"><i v-for="(x,index) in guidesX" :key="'x'+index" class="guide-x" :style="{left:x*scale+'px'}"></i><i v-for="(y,index) in guidesY" :key="'y'+index" class="guide-y" :style="{top:y*scale+'px'}"></i></div>
      <div v-if="center&&centerVisible" class="ruler-centers" aria-label="选中元素中心点" :data-center-x="center.x.toFixed(1)" :data-center-y="center.y.toFixed(1)"><i class="center-x" :style="{left:center.x*scale+'px'}"></i><i class="center-y" :style="{top:center.y*scale+'px'}"></i><span class="center-point" :style="{left:center.x*scale+'px',top:center.y*scale+'px'}"><b>{{ center.x.toFixed(1) }}, {{ center.y.toFixed(1) }}</b></span></div>
    </div>
  </div>
</template>
<style scoped>
.ruler-centers{position:absolute;inset:0;pointer-events:none;z-index:6;overflow:hidden}.ruler-centers>i{position:absolute;display:block}.center-x{top:0;bottom:0;border-left:1px dashed #0891b2}.center-y{left:0;right:0;border-top:1px dashed #0891b2}.center-point{position:absolute;width:7px;height:7px;border-radius:50%;background:#0891b2;border:1px solid white;transform:translate(-50%,-50%)}.center-point b{position:absolute;left:10px;top:9px;background:#0e7490;color:white;font:10px monospace;white-space:nowrap;padding:3px 5px;border-radius:3px}
.ruler-board{position:relative;flex:none}.ruler-origin{position:absolute;left:0;top:0;width:24px;height:24px;display:grid;place-items:center;background:var(--client-surface);border:1px solid var(--client-border);color:var(--client-secondary);font:9px monospace}.ruler-horizontal,.ruler-vertical{position:absolute;display:block;background:var(--client-surface);overflow:hidden;z-index:4}.ruler-horizontal{left:24px;top:0;border-bottom:1px solid var(--client-border)}.ruler-vertical{left:0;top:24px;border-right:1px solid var(--client-border)}line{stroke:var(--client-secondary);stroke-width:1;opacity:.65}text{fill:var(--client-secondary);font:9px monospace}rect{fill:#db2777;opacity:.7}.ruler-content{position:absolute;top:24px;left:24px}.ruler-grid,.ruler-guides{position:absolute;inset:0;pointer-events:none;z-index:5;overflow:hidden}.ruler-grid{background-image:linear-gradient(#64748b21 1px,transparent 1px),linear-gradient(90deg,#64748b21 1px,transparent 1px)}.ruler-guides i{position:absolute;display:block}.guide-x{top:0;bottom:0;border-left:1px dashed #db2777a0}.guide-y{left:0;right:0;border-top:1px dashed #db2777a0}
</style>
