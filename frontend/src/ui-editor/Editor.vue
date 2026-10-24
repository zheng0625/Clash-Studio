<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { MousePointer2, Hand, Download, Upload, Undo2, Redo2, ChevronUp, ChevronDown, Crosshair, Layers, Code2, Move, RotateCcw, Check, PanelLeftClose } from 'lucide-vue-next'

type Rule = { selector: string; label: string; page: string; styles: Record<string, string> }
type Project = { version: 1; rules: Rule[]; custom: string; width: number; height: number }
const storageKey = 'clash-studio-ui-workshop-v1'
const initial = (): Project => ({ version: 1, rules: [], custom: '', width: 1280, height: 900 })
function valid(value: any): value is Project { return value?.version === 1 && Array.isArray(value.rules) && value.rules.length < 5000 && value.rules.every((r: any) => typeof r.selector === 'string' && typeof r.label === 'string' && typeof r.page === 'string' && r.styles && Object.entries(r.styles).every(([k, v]) => /^[a-z-]+$/.test(k) && typeof v === 'string' && !/[{}]/.test(v))) && typeof value.custom === 'string' && Number.isFinite(value.width) && value.width >= 360 && value.width <= 2560 && Number.isFinite(value.height) && value.height >= 480 && value.height <= 1800 }
function restore() { try { const p = JSON.parse(localStorage.getItem(storageKey) || 'null'); return valid(p) ? p : initial() } catch { return initial() } }
const project = ref<Project>(restore()), frame = ref<HTMLIFrameElement>(), selected = ref(''), mode = ref('select'), page = ref('概览'), zoom = ref(.75), tab = ref('design'), ready = ref(false), status = ref('本地自动保存'), layers = ref<{selector: string; label: string; depth: number}[]>([]), values = ref<Record<string, string>>({}), box = ref({ x: 0, y: 0, w: 0, h: 0, visible: false }), search = ref(''), showLeft = ref(true)
const pages = ['概览', '订阅', '模块分流', '代理', '连接', '配置工作台', '设置与日志']
const properties = [
  { title: '位置与尺寸', fields: [['left','左偏移'],['top','上偏移'],['width','宽度'],['height','高度'],['min-height','最小高度'],['max-width','最大宽度']] },
  { title: '布局', fields: [['display','显示方式'],['grid-template-columns','网格列'],['flex-direction','排列方向'],['justify-content','主轴对齐'],['align-items','交叉对齐'],['gap','间距'],['order','排列序号']] },
  { title: '留白', fields: [['padding','内边距'],['margin','外边距']] },
  { title: '外观', fields: [['background','背景'],['color','文字颜色'],['border-radius','圆角'],['border','边框'],['box-shadow','阴影'],['font-size','字号'],['opacity','不透明度']] }
]
const history = ref<string[]>([JSON.stringify(project.value)]), cursor = ref(0)
const changed = computed(() => project.value.rules.length)
const visibleLayers = computed(() => layers.value.filter(x => !search.value || x.label.toLowerCase().includes(search.value.toLowerCase())))
const current = computed(() => project.value.rules.find(r => r.selector === selected.value && r.page === page.value))
const doc = () => frame.value?.contentDocument
const element = () => { try { return doc()?.querySelector<HTMLElement>(selected.value) } catch { return null } }
function selector(el: Element): string {
  const parts: string[] = []
  while (el && el.id !== 'app') {
    const tag = el.tagName.toLowerCase(), parent = el.parentElement
    if (!parent) break
    const cls = Array.from(el.classList).filter(c => !['chosen','selected','on','is-live','running'].includes(c)).slice(0, 2).map(c => '.' + CSS.escape(c)).join('')
    const peers = Array.from(parent.children).filter(e => e.tagName === el.tagName)
    parts.unshift(tag + cls + (peers.length > 1 ? `:nth-of-type(${peers.indexOf(el) + 1})` : ''))
    el = parent
  }
  return '#app > ' + parts.join(' > ')
}
function cssText() { return '/* Clash Studio UI 工坊 · 在现有样式之后加载 */\n' + project.value.rules.map(r => `/* ${r.page} · ${r.label.replace(/\*\//g, '')} */\nbody:has(.desk[data-ui-page="${['home','subscriptions','modules','proxies','connections','studio','settings'][pages.indexOf(r.page)] || 'home'}"]) ${r.selector} {\n${Object.entries(r.styles).map(([k,v]) => `  ${k}: ${v} !important;`).join('\n')}\n}`).join('\n\n') + '\n\n' + project.value.custom }
function apply() {
  const d = doc(); if (!d) return
  let style = d.getElementById('ui-workshop-styles') as HTMLStyleElement | null
  if (!style) { style = d.createElement('style'); style.id = 'ui-workshop-styles'; d.head.append(style) }
  style.textContent = cssText(); outline()
}
function persist() { try { localStorage.setItem(storageKey, JSON.stringify(project.value)); status.value = '已自动保存到本机' } catch { status.value = '浏览器存储已满，请导出工程' } }
function commit() { const s = JSON.stringify(project.value); if (history.value[cursor.value] === s) return; history.value = history.value.slice(0, cursor.value + 1); history.value.push(s); if (history.value.length > 100) history.value.shift(); cursor.value = history.value.length - 1; persist(); apply() }
function undo(delta: number) { const next = cursor.value + delta; if (next < 0 || next >= history.value.length) return; cursor.value = next; project.value = JSON.parse(history.value[next]!); persist(); apply(); readValues() }
function label(el: Element) { return el.getAttribute('aria-label') || (el.classList.length ? '.' + Array.from(el.classList).slice(0,2).join('.') : el.tagName.toLowerCase()) }
function outline() { const el = element(); if (!el || !el.getClientRects().length || mode.value !== 'select') { box.value.visible = false; return }; const r = el.getBoundingClientRect(); box.value = { x: r.x, y: r.y, w: r.width, h: r.height, visible: true } }
function readValues() { const el = element(); if (!el) return; const computed = el.ownerDocument.defaultView!.getComputedStyle(el); values.value = Object.fromEntries(properties.flatMap(g => g.fields.map(([key]) => [key!, current.value?.styles[key!] ?? computed.getPropertyValue(key!)]))); outline() }
function select(el: HTMLElement) { selected.value = selector(el); readValues() }
function selectPath(path: string) { const el = doc()?.querySelector<HTMLElement>(path); if (el) { select(el); el.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) } }
function setStyle(key: string, value: string, save = true) { const el = element(); if (!el) return; if (/[{}]/.test(value)) { status.value = '属性值不能包含大括号'; return }
  let rule = current.value
  if (!rule) { rule = { selector: selected.value, label: label(el), page: page.value, styles: {} }; project.value.rules.push(rule) }
  if (value.trim()) rule.styles[key] = value.trim(); else delete rule.styles[key]
  if (key === 'left' || key === 'top') rule.styles.position = 'relative'
  apply(); if (save) commit()
}
function change(key: string, event: Event) { setStyle(key, (event.target as HTMLInputElement).value) }
function resetElement() { project.value.rules = project.value.rules.filter(r => r !== current.value); commit(); readValues() }
function parentElement() { const p = element()?.parentElement; if (p && p.id !== 'app') select(p) }
function reorder(delta: number) {
  const el = element(); if (!el?.parentElement) return
  const parent = el.parentElement, display = el.ownerDocument.defaultView!.getComputedStyle(parent).display
  if (!['grid','flex','inline-flex','inline-grid'].includes(display)) { status.value = '请先选中父级，将显示方式设为 flex 或 grid'; return }
  const peers = Array.from(parent.children).filter((x): x is HTMLElement => x instanceof (frame.value!.contentWindow as any).HTMLElement)
  const sorted = peers.sort((a,b) => parseInt(a.ownerDocument.defaultView!.getComputedStyle(a).order) - parseInt(b.ownerDocument.defaultView!.getComputedStyle(b).order))
  const at = sorted.indexOf(el), to = at + delta; if (to < 0 || to >= sorted.length) return
  sorted.splice(at, 1); sorted.splice(to, 0, el)
  const original = selected.value; for (const [i, node] of sorted.entries()) { selected.value = selector(node); setStyle('order', String(i), false) }; selected.value = original; commit(); readValues()
}
function refreshLayers() { const d = doc(); if (!d) return; const id = d.querySelector('.desk')?.getAttribute('data-ui-page'); const name = pages[['home','subscriptions','modules','proxies','connections','studio','settings'].indexOf(id || '')]; if (name && name !== page.value) { page.value = name; selected.value = '' }; layers.value = Array.from(d.querySelectorAll<HTMLElement>('#app .desk, #app .desk *')).filter(el => !['svg','path','span','small','option','i','br','img','strong','p'].includes(el.tagName.toLowerCase()) && !el.closest('svg') && el.getClientRects().length).map(el => ({ selector: selector(el), label: label(el), depth: Math.min(7, selector(el).split(' > ').length - 2) })); outline() }
let observer: MutationObserver | undefined, cleanup: (() => void) | undefined, dragging: {x: number; y: number; left: number; top: number; moved: boolean} | undefined
function start(event: PointerEvent) {
  if (mode.value !== 'select' || event.button !== 0) return
  const target = event.target as HTMLElement
  if (target.closest('svg')) { const host = target.closest('svg')?.parentElement; if (host) select(host) } else if (target.closest('#app') && target.id !== 'app') select(target)
  event.preventDefault(); event.stopImmediatePropagation()
  const el = element(); if (!el) return
  const cs = el.ownerDocument.defaultView!.getComputedStyle(el)
  dragging = { x: event.clientX, y: event.clientY, left: parseFloat(cs.left) || 0, top: parseFloat(cs.top) || 0, moved: false }
}
function move(event: PointerEvent) { if (!dragging) return; const dx = event.clientX - dragging.x, dy = event.clientY - dragging.y; if (Math.abs(dx) + Math.abs(dy) < 4 && !dragging.moved) return; dragging.moved = true; setStyle('left', Math.round((dragging.left + dx) / 4) * 4 + 'px', false); setStyle('top', Math.round((dragging.top + dy) / 4) * 4 + 'px', false); readValues() }
function end() { if (dragging?.moved) commit(); dragging = undefined }
function block(event: Event) { if (mode.value === 'select') { event.preventDefault(); event.stopImmediatePropagation() } }
function loaded() {
  observer?.disconnect(); cleanup?.(); ready.value = true
  const d = doc(); if (!d) return
  d.addEventListener('keydown', keydown); d.addEventListener('pointerdown', start, true); d.addEventListener('pointermove', move, true); d.addEventListener('pointerup', end, true); d.addEventListener('click', block, true); d.addEventListener('scroll', outline, true)
  cleanup = () => { d.removeEventListener('keydown', keydown); d.removeEventListener('pointerdown', start, true); d.removeEventListener('pointermove', move, true); d.removeEventListener('pointerup', end, true); d.removeEventListener('click', block, true); d.removeEventListener('scroll', outline, true) }
  observer = new MutationObserver(refreshLayers); observer.observe(d.getElementById('app')!, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-ui-page'] }); apply(); refreshLayers()
}
function go(name: string) { const previous = mode.value; mode.value = 'interact'; page.value = name; selected.value = ''; doc()?.querySelector<HTMLButtonElement>(`.liquid-dock button[aria-label="${name}"]`)?.click(); mode.value = previous; refreshLayers() }
function saveFile(name: string, content: string, type: string) { const url = URL.createObjectURL(new Blob([content], { type })); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); status.value = '已导出 ' + name }
function exportProject() { saveFile('clash-studio-ui.layout.json', JSON.stringify(project.value, null, 2), 'application/json') }
function exportCss() { saveFile('clash-studio-ui.css', cssText(), 'text/css') }
async function exportHtml() {
  const d = doc(); if (!d) return
  const clone = d.documentElement.cloneNode(true) as HTMLElement
  clone.querySelectorAll('script').forEach(el => el.remove())
  const styles = await Promise.all(Array.from(d.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')).map(async link => { try { return await (await fetch(link.href)).text() } catch { return '' } }))
  clone.querySelectorAll('link[rel="stylesheet"]').forEach(el => el.remove())
  const style = d.createElement('style'); style.textContent = styles.join('\n'); clone.querySelector('head')?.prepend(style)
  const originals = Array.from(d.querySelectorAll<HTMLImageElement>('img'))
  await Promise.all(Array.from(clone.querySelectorAll<HTMLImageElement>('img')).map(async (img, index) => {
    const source = originals[index]; if (!source) return
    try { const blob = await (await fetch(source.src)).blob(); img.src = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsDataURL(blob) }) } catch { img.src = source.src }
  }))
  saveFile('clash-studio-ui-preview.html', '<!doctype html>\n' + clone.outerHTML, 'text/html')
}
async function importProject(event: Event) { const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return; try { if (file.size > 2e6) throw new Error('工程文件超过 2 MB'); const p = JSON.parse(await file.text()); if (!valid(p)) throw new Error('不是有效的布局工程'); project.value = p; commit(); readValues(); status.value = '工程已导入' } catch (e) { status.value = (e as Error).message }; (event.target as HTMLInputElement).value = '' }
function keydown(e: KeyboardEvent) { if ((e.target as HTMLElement)?.closest('input,textarea,select')) return; if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); undo(e.shiftKey ? 1 : -1) }; if (e.key === 'Escape') { selected.value = ''; box.value.visible = false } }
window.addEventListener('keydown', keydown); window.addEventListener('pointerup', end)
watch(mode, outline)
onBeforeUnmount(() => { observer?.disconnect(); cleanup?.(); window.removeEventListener('keydown', keydown); window.removeEventListener('pointerup', end) })
</script>

<template>
  <div class="workshop">
    <header class="toolbar"><div class="identity"><span class="logo">C<span>✦</span></span><div><strong>Clash Studio <em>布局工坊</em></strong><small>你的界面，你来定义。</small></div></div><div class="tool-group"><button :class="{active:mode==='select'}" @click="mode='select'"><MousePointer2 :size="15"/>选择 / 拖动</button><button :class="{active:mode==='interact'}" @click="mode='interact'"><Hand :size="15"/>交互预览</button><i></i><button title="撤销 Ctrl+Z" :disabled="cursor===0" @click="undo(-1)"><Undo2 :size="16"/></button><button title="重做 Ctrl+Shift+Z" :disabled="cursor===history.length-1" @click="undo(1)"><Redo2 :size="16"/></button></div><div class="exports"><label class="button"><Upload :size="14"/>导入<input type="file" accept=".json" hidden @change="importProject"></label><button @click="exportCss"><Code2 :size="14"/>导出 CSS</button><button class="primary" @click="exportProject"><Download :size="15"/>导出布局工程</button></div></header>
    <div class="workspace" :class="{collapsed:!showLeft}">
      <aside class="left-panel" v-if="showLeft"><div class="panel-title">工作空间 <span>01</span></div><div class="page-list"><button v-for="(name,i) in pages" :class="{selected:page===name}" @click="go(name)"><span>0{{i+1}}</span>{{name}}<b v-if="page===name">●</b></button></div><div class="panel-title divider"><span><Layers :size="14"/>元素图层</span><small>{{ layers.length }}</small></div><input v-model="search" class="layer-search" placeholder="搜索元素或类名…"><div class="layers"><button v-for="layer in visibleLayers" :key="layer.selector" :class="{selected:selected===layer.selector}" :style="{paddingLeft:(12+layer.depth*9)+'px'}" :title="layer.selector" @click="selectPath(layer.selector)"><span>◇</span>{{layer.label}}</button></div><div class="left-foot"><span class="green-dot"></span>复用项目真实 Vue 组件</div></aside>
      <main class="canvas-area"><div class="canvas-toolbar"><div><button title="切换图层面板" @click="showLeft=!showLeft"><PanelLeftClose :size="16"/></button><span>{{page}} <small>/ 设计画布</small></span></div><div class="viewport-controls"><select v-model.number="project.width" @change="commit"><option :value="1440">1440 · 桌面</option><option :value="1280">1280 · 标准</option><option :value="1024">1024 · 紧凑</option><option :value="768">768 · 平板</option><option :value="390">390 · 手机</option></select><span>×</span><input aria-label="画布高度" type="number" min="480" max="1800" v-model.number="project.height" @change="commit"><select aria-label="画布缩放" v-model.number="zoom"><option :value=".4">40%</option><option :value=".5">50%</option><option :value=".6">60%</option><option :value=".75">75%</option><option :value="1">100%</option></select></div></div><div class="canvas-scroll"><div class="artboard-caption"><span>CLASH STUDIO <b>{{project.width}} × {{project.height}}</b></span><span>{{ mode==='select'?'点击选择 · 拖动移动 · 4px 吸附':'操作页面控件，查看真实界面状态' }}</span></div><div class="artboard-wrap" :style="{width:project.width*zoom+'px',height:project.height*zoom+'px'}"><div class="artboard" :style="{width:project.width+'px',height:project.height+'px',transform:`scale(${zoom})`}"><iframe ref="frame" src="/ui-preview.html" title="Clash Studio 真实组件画布" @load="loaded"/><div v-if="box.visible" class="selection-box" :style="{left:box.x+'px',top:box.y+'px',width:box.w+'px',height:box.h+'px'}"><span class="selection-label">{{current?.label || selected.split(' > ').at(-1)}} · {{Math.round(box.w)}} × {{Math.round(box.h)}}</span><i v-for="n in 4" :class="'handle h'+n"></i></div></div></div><div class="canvas-note"><Move :size="13"/>拖动改变视觉偏移；调整网格、间距或排列序号，可改变实际布局。</div></div><footer class="statusbar"><span><Check :size="13"/>{{status}}</span><span>{{changed}} 个元素已修改 <i>·</i> 本地预览 / 示例数据</span></footer></main>
      <aside class="right-panel"><div class="inspector-tabs"><button :class="{selected:tab==='design'}" @click="tab='design'">属性</button><button :class="{selected:tab==='code'}" @click="tab='code'">自定义 CSS</button></div><template v-if="tab==='design'"><div v-if="!selected" class="empty-inspector"><Crosshair :size="32"/><h3>从选择一个元素开始</h3><p>点击画布中的卡片、文字或导航，右侧即可调整样式。</p><div>① 选择元素<br>② 调整布局和外观<br>③ 导出工程交给我实现</div></div><template v-else><div class="selected-info"><small>当前元素</small><code>{{selected.split(' > ').at(-1)}}</code><div><button @click="parentElement"><ChevronUp :size="14"/>父级</button><button title="在 flex/grid 父容器中前移" @click="reorder(-1)"><ChevronUp :size="14"/>前移</button><button title="在 flex/grid 父容器中后移" @click="reorder(1)"><ChevronDown :size="14"/>后移</button></div></div><section v-for="group in properties" class="property-group"><h3>{{group.title}}</h3><label v-for="[key,title] in group.fields"><span>{{title}}</span><input :value="values[key!]" :aria-label="title" spellcheck="false" @change="change(key!,$event)"></label></section><button class="reset-element" @click="resetElement"><RotateCcw :size="14"/>清除此元素的修改</button></template></template><div v-else class="code-panel"><p>支持 CSS 变量和媒体查询。样式在项目原有样式之后加载。</p><textarea v-model="project.custom" spellcheck="false" placeholder=".desk-card {&#10;  border-radius: 24px;&#10;}" @input="apply" @change="commit"></textarea><button @click="exportCss"><Download :size="14"/>导出完整 CSS</button></div><div class="delivery"><strong>完成后，返回你的设计</strong><p>导出布局工程（JSON）发给我，即可继续落实到 Clash Studio。</p><button @click="exportHtml">导出当前页 HTML 快照 ↗</button></div></aside>
    </div>
  </div>
</template>
