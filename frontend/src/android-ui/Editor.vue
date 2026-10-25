<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { Palette, Droplets, Smartphone, Type, Download, Upload, Copy, RotateCcw, Image as ImageIcon, TriangleAlert, Check, MousePointer2, Hand, ChevronUp, Crosshair, Monitor } from 'lucide-vue-next'
import { contrast, readableCoverage, themeError, themeFields, lightTheme, darkTheme, validHex, type ClientTheme } from '../theme'

/* Token-level UI editor with a live preview of the real app. Two preview modes
   (Android phone / desktop window) share one token model; the free-form layer
   adds per-element position/size rules exactly like the layout workshop, and
   everything the preview shows is regenerated verbatim into the exported CSS. */
type ElementRule = { selector:string; label:string; page:string; styles:Record<string,string> }
type Glass = { dockBlur:number; dockTint:number; panelOpacity:number; wallpaperShade:number; wallpaperImage:string }
type Dock = { height:number; radius:number; pad:number; gap:number; slideMs:number; press:number; pop:number }
type Shape = { cardRadius:number; cardPadding:number; h1Size:number; labelSize:number }
type Tokens = { version:3; theme:ClientTheme; glass:Glass; dock:Dock; shape:Shape; sim:{safeBottom:number}; elements:ElementRule[] }
const storageKey = 'clash-studio-android-ui-v3'
const pageIds = ['home','subscriptions','modules','proxies','connections','studio','settings'] as const
const pageNames = ['概览','订阅','模块分流','代理','连接','配置工作台','设置与日志'] as const
const defaults = (): Tokens => ({ version: 3, theme: { ...lightTheme }, glass: { dockBlur: 18, dockTint: 35, panelOpacity: 85, wallpaperShade: 45, wallpaperImage: '' },
  dock: { height: 68, radius: 26, pad: 5, gap: 3, slideMs: 420, press: .94, pop: 1.08 }, shape: { cardRadius: 20, cardPadding: 20, h1Size: 28, labelSize: 11 }, sim: { safeBottom: 0 }, elements: [] })
const numberIn = (value:unknown, min:number, max:number) => typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max
function validElements(value:any): value is ElementRule[] {
  return Array.isArray(value) && value.length < 5000 && value.every((rule:any) => typeof rule.selector === 'string' && rule.selector.startsWith('#app') && rule.selector.length < 400
    && typeof rule.label === 'string' && rule.label.length < 120 && typeof rule.page === 'string' && (pageNames as readonly string[]).includes(rule.page)
    && rule.styles && Object.entries(rule.styles).every(([key, v]) => /^[a-z-]+$/.test(key) && typeof v === 'string' && v.length < 200 && !/[{}]/.test(v)))
}
function validProject(value:any): value is Tokens {
  if (value?.version !== 3) return false
  const theme:ClientTheme = value.theme
  if (!theme || !themeFields.every(field => validHex(theme[field.key]))) return false
  const g = value.glass
  if (!g || !numberIn(g.dockBlur, 0, 60) || !numberIn(g.dockTint, 0, 100) || !numberIn(g.panelOpacity, 0, 100) || !numberIn(g.wallpaperShade, 0, 90)
    || !(typeof g.wallpaperImage === 'string' && (g.wallpaperImage === '' || (g.wallpaperImage.startsWith('data:image/') && g.wallpaperImage.length < 4_000_000)))) return false
  const d = value.dock
  if (!d || !numberIn(d.height, 52, 104) || !numberIn(d.radius, 0, 40) || !numberIn(d.pad, 0, 14) || !numberIn(d.gap, 0, 12) || !numberIn(d.slideMs, 80, 900) || !numberIn(d.press, .7, 1) || !numberIn(d.pop, 1, 1.5)) return false
  const s = value.shape
  if (!s || !numberIn(s.cardRadius, 0, 36) || !numberIn(s.cardPadding, 8, 36) || !numberIn(s.h1Size, 18, 44) || !numberIn(s.labelSize, 8, 16)) return false
  return numberIn(value.sim?.safeBottom, 0, 60) && validElements(value.elements)
}
function restore(): Tokens {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey) || 'null')
    if (validProject(parsed)) return parsed
    if (parsed?.version === 2) { const upgraded = { ...defaults(), ...parsed, version: 3 as const, elements: [] as ElementRule[] }; if (validProject(upgraded)) return upgraded }
  } catch { /* fall through */ }
  return defaults()
}
const tokens = reactive<Tokens>(restore())
const frame = ref<HTMLIFrameElement>(), ready = ref(false), status = ref('本地自动保存'), tab = ref('color')
const mode = ref<'mobile' | 'desktop'>('mobile'), device = ref(1), zoom = ref(.8), stage = ref('dots'), pick = ref(false)
const width = ref(393), height = ref(873)
const devices = computed(() => mode.value === 'mobile'
  ? [ { name:'小屏 · 360 × 780', w:360, h:780 }, { name:'主流 · 393 × 873', w:393, h:873 }, { name:'大屏 · 412 × 915', w:412, h:915 }, { name:'超大屏 · 430 × 932', w:430, h:932 }, { name:'高清 · 480 × 1040', w:480, h:1040 }, { name:'横屏 · 780 × 412', w:780, h:412 } ]
  : [ { name:'紧凑 · 1280 × 800', w:1280, h:800 }, { name:'标准 · 1440 × 900', w:1440, h:900 }, { name:'宽裕 · 1660 × 1000', w:1660, h:1000 }, { name:'全高清 · 1920 × 1080', w:1920, h:1080 } ])
const frameSrc = computed(() => '/ui-preview.html?platform=' + (mode.value === 'mobile' ? 'android' : 'windows'))
watch(mode, () => { device.value = 0; const next = devices.value[0]!; width.value = next.w; height.value = next.h; clearSelection(); if (mode.value === 'desktop') pick.value = false })
watch(device, () => { const next = devices.value[device.value]; if (next) { width.value = next.w; height.value = next.h } })
const themeWarning = computed(() => themeError(tokens.theme))
const accentInk = computed(() => contrast('#F0F3F8', tokens.theme.accent) >= contrast('#101318', tokens.theme.accent) ? '#F0F3F8' : '#101318')
const darkSurface = computed(() => contrast(tokens.theme.surface, '#FFFFFF') > contrast(tokens.theme.surface, '#000000'))
const sliders = [
  { group: 'glass' as const, fields: [
    ['dockBlur', 'Dock 背景模糊', 0, 40, 1, 'px'], ['dockTint', 'Dock 选中底浓度', 0, 100, 1, '%'], ['panelOpacity', '卡片面板浓度', 0, 100, 1, '%'], ['wallpaperShade', '壁纸压暗程度', 0, 90, 1, '%'] ] },
  { group: 'dock' as const, fields: [
    ['height', 'Dock 高度', 56, 96, 1, 'px'], ['radius', 'Dock 圆角', 12, 34, 1, 'px'], ['pad', '内边距', 0, 12, 1, 'px'], ['gap', '列间距', 0, 10, 1, 'px'],
    ['slideMs', '滑块时长', 120, 800, 10, 'ms'], ['press', '按压缩放', .82, 1, .02, ''], ['pop', '选中图标放大', 1, 1.4, .02, ''] ] },
  { group: 'shape' as const, fields: [
    ['cardRadius', '卡片圆角', 0, 32, 1, 'px'], ['cardPadding', '卡片内边距', 8, 32, 1, 'px'], ['h1Size', '页面标题字号', 20, 40, 1, 'px'], ['labelSize', 'Dock 文字字号', 9, 14, 1, 'px'] ] },
]
const elementFields = [ ['left','左偏移'], ['top','上偏移'], ['width','宽度'], ['height','高度'], ['font-size','字号'], ['border-radius','圆角'], ['padding','内边距'], ['gap','间距'] ]
const selected = ref(''), values = ref<Record<string,string>>({}), box = ref({ x: 0, y: 0, w: 0, h: 0, visible: false })
const currentPage = () => {
  const id = frame.value?.contentDocument?.querySelector('.desk')?.getAttribute('data-ui-page') || 'home'
  return pageNames[pageIds.indexOf(id as typeof pageIds[number])] || '概览'
}
const currentRule = computed(() => tokens.elements.find(rule => rule.selector === selected.value && rule.page === currentPage()))
const selectedLabel = computed(() => tokens.elements.find(rule => rule.selector === selected.value)?.label || selected.value.split(' > ').at(-1) || '')

/* ---------- free-form element editing (same rule model as the layout workshop) ---------- */
function selectorOf(el: Element): string {
  const parts: string[] = []
  let node = el
  while (node && (node as HTMLElement).id !== 'app') {
    const tag = node.tagName.toLowerCase(), parent = node.parentElement
    if (!parent) break
    const cls = Array.from(node.classList).filter(c => !['chosen','selected','on','is-live','running','active','picked'].includes(c)).slice(0, 2).map(c => '.' + CSS.escape(c)).join('')
    const peers = Array.from(parent.children).filter(e => e.tagName === node.tagName)
    parts.unshift(tag + cls + (peers.length > 1 ? `:nth-of-type(${peers.indexOf(node) + 1})` : ''))
    node = parent
  }
  return '#app > ' + parts.join(' > ')
}
function labelOf(el: Element) { return el.getAttribute('aria-label') || (el.classList.length ? '.' + Array.from(el.classList).slice(0, 2).join('.') : el.tagName.toLowerCase()) }
const doc = () => frame.value?.contentDocument
function element() { try { return doc()?.querySelector<HTMLElement>(selected.value) || undefined } catch { return undefined } }
function outline() {
  const el = element()
  if (!el || !pick.value || !el.getClientRects().length) { box.value.visible = false; return }
  const rect = el.getBoundingClientRect()
  box.value = { x: rect.x, y: rect.y, w: rect.width, h: rect.height, visible: true }
}
function readValues() {
  const el = element(); if (!el) return
  const computed = el.ownerDocument.defaultView!.getComputedStyle(el)
  values.value = Object.fromEntries(elementFields.map(([key]) => [key!, currentRule.value?.styles[key!] ?? computed.getPropertyValue(key!)]))
  outline()
}
function select(el: HTMLElement) { selected.value = selectorOf(el); readValues() }
function clearSelection() { selected.value = ''; box.value.visible = false }
function setStyle(key: string, value: string, save = true) {
  const el = element(); if (!el) return
  if (/[{}]/.test(value)) { status.value = '属性值不能包含大括号'; return }
  let rule = currentRule.value
  if (!rule) { rule = { selector: selected.value, label: labelOf(el), page: currentPage(), styles: {} }; tokens.elements.push(rule) }
  if (value.trim()) rule.styles[key] = value.trim(); else delete rule.styles[key]
  if (!Object.keys(rule.styles).length) tokens.elements = tokens.elements.filter(item => item !== rule)
  if (key === 'left' || key === 'top') rule.styles.position = 'relative'
  apply(); if (save) persist()
}
function changeElement(key: string, event: Event) { setStyle(key, (event.target as HTMLInputElement).value) }
function resetElement() { tokens.elements = tokens.elements.filter(rule => !(rule.selector === selected.value && rule.page === currentPage())); apply(); persist(); readValues() }
function selectParent() { const parent = element()?.parentElement; if (parent && parent.id !== 'app') select(parent) }
let dragging:{x:number;y:number;left:number;top:number;moved:boolean} | undefined
function pointerDown(event: PointerEvent) {
  if (!pick.value || event.button !== 0) return
  const target = event.target as HTMLElement
  const host = target.closest('svg')?.parentElement
  if (host && host.closest('#app')) select(host)
  else if (target.closest('#app') && target.id !== 'app') select(target)
  event.preventDefault(); event.stopImmediatePropagation()
  const el = element(); if (!el) return
  const computed = el.ownerDocument.defaultView!.getComputedStyle(el)
  dragging = { x: event.clientX, y: event.clientY, left: parseFloat(computed.left) || 0, top: parseFloat(computed.top) || 0, moved: false }
}
function pointerMove(event: PointerEvent) {
  if (!dragging) return
  const dx = event.clientX - dragging.x, dy = event.clientY - dragging.y
  if (Math.abs(dx) + Math.abs(dy) < 4 && !dragging.moved) return
  dragging.moved = true
  setStyle('left', Math.round((dragging.left + dx) / 4) * 4 + 'px', false)
  setStyle('top', Math.round((dragging.top + dy) / 4) * 4 + 'px', false)
  readValues()
}
function pointerUp() { if (dragging?.moved) persist(); dragging = undefined }
function block(event: Event) { if (pick.value) { event.preventDefault(); event.stopImmediatePropagation() } }

/* ---------- token application into the preview ---------- */
function apply() {
  const root = doc()?.documentElement
  if (!root) return
  const style = root.style, theme = tokens.theme
  const values2: Record<string, string> = { ...theme, 'sidebar-text': theme.sidebarText, 'accent-ink': accentInk.value, tint: theme.selected, 'control-selected': theme.selected }
  for (const [key, value] of Object.entries(values2)) style.setProperty('--client-' + key, value)
  style.setProperty('--client-glass-chrome', readableCoverage(theme.sidebar, theme.sidebarText, 85) + '%')
  style.setProperty('--client-glass-panel', tokens.glass.panelOpacity + '%')
  root.dataset.clientTheme = 'custom'
  style.colorScheme = darkSurface.value ? 'dark' : 'light'
  if (tokens.glass.wallpaperImage) {
    root.dataset.wallpaper = 'on'
    style.setProperty('--wallpaper-image', `url("${tokens.glass.wallpaperImage}")`)
    style.setProperty('--wallpaper-shade', tokens.glass.wallpaperShade + '%')
  } else { delete root.dataset.wallpaper; style.removeProperty('--wallpaper-image'); style.removeProperty('--wallpaper-shade') }
  style.setProperty('--nav-height', tokens.dock.height + 'px')
  style.setProperty('--nav-radius', tokens.dock.radius + 'px')
  style.setProperty('--nav-blur', tokens.glass.dockBlur + 'px')
  style.setProperty('--nav-item-pad', tokens.dock.pad + 'px')
  style.setProperty('--nav-item-gap', tokens.dock.gap + 'px')
  style.setProperty('--nav-tint', tokens.glass.dockTint + '%')
  style.setProperty('--nav-slide-duration', tokens.dock.slideMs + 'ms')
  style.setProperty('--nav-press-scale', String(tokens.dock.press))
  style.setProperty('--nav-pop-scale', String(tokens.dock.pop))
  style.setProperty('--mobile-bottom', tokens.sim.safeBottom + 'px')
  const document = frame.value!.contentDocument!
  let tag = document.getElementById('android-ui-overrides') as HTMLStyleElement | null
  if (!tag) { tag = document.createElement('style'); tag.id = 'android-ui-overrides'; document.head.append(tag) }
  tag.textContent = overrideCss()
  outline()
}
function overrideCss() {
  const shape = tokens.shape
  const lines = [
    `  :root .desk .desk-card{border-radius:${shape.cardRadius}px;padding:${shape.cardPadding}px}`,
    `  :root .desk .desk-page-heading h1{font-size:${shape.h1Size}px}`,
    `  :root .desk .mobile-navigation>button{font-size:${shape.labelSize}px}`,
  ]
  for (const rule of tokens.elements) {
    const page = pageIds[pageNames.indexOf(rule.page as typeof pageNames[number])] || 'home'
    lines.push(`  body:has(.desk[data-ui-page="${page}"]) ${rule.selector}{${Object.entries(rule.styles).map(([key, value]) => `${key}:${value}!important;`).join('')}}`)
  }
  return lines.join('\n')
}
function persist() { try { localStorage.setItem(storageKey, JSON.stringify(tokens)); status.value = '已自动保存到本机' } catch { status.value = '浏览器存储已满，请导出工程' } }
watch(tokens, () => { persist(); apply() }, { deep: true })
watch([device, zoom, width, height], () => { apply() })
let observer: MutationObserver | undefined, cleanup: (() => void) | undefined
function loaded() {
  ready.value = true
  observer?.disconnect(); cleanup?.()
  const document = frame.value?.contentDocument
  if (!document) return
  const onScroll = () => outline()
  document.addEventListener('pointerdown', pointerDown, true)
  document.addEventListener('pointermove', pointerMove, true)
  document.addEventListener('pointerup', pointerUp, true)
  document.addEventListener('pointercancel', pointerUp, true)
  document.addEventListener('click', block, true)
  document.addEventListener('scroll', onScroll, true)
  cleanup = () => {
    document.removeEventListener('pointerdown', pointerDown, true)
    document.removeEventListener('pointermove', pointerMove, true)
    document.removeEventListener('pointerup', pointerUp, true)
    document.removeEventListener('pointercancel', pointerUp, true)
    document.removeEventListener('click', block, true)
    document.removeEventListener('scroll', onScroll, true)
  }
  observer = new MutationObserver(() => { if (pick.value) { clearSelection() } outline() })
  observer.observe(document.getElementById('app')!, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-ui-page'] })
  apply()
}
function usePreset(theme: ClientTheme) { Object.assign(tokens.theme, theme) }
function resetGroup(group: 'theme' | 'glass' | 'dock' | 'shape') {
  const fresh = defaults()
  if (group === 'theme') Object.assign(tokens.theme, fresh.theme)
  else Object.assign(tokens[group], fresh[group])
  status.value = '已恢复该组默认值'
}
function resetAll() { const fresh = defaults(); Object.assign(tokens, fresh); for (const key of Object.keys(tokens) as (keyof Tokens)[]) if (typeof tokens[key] === 'object') Object.assign(tokens[key], fresh[key]); clearSelection(); status.value = '已恢复全部默认值' }
function setColor(key: keyof ClientTheme, event: Event) {
  const value = (event.target as HTMLInputElement).value.trim()
  if (validHex(value)) tokens.theme[key] = value.toLowerCase()
  else status.value = '请输入六位十六进制颜色，例如 #7659d5'
}
function hexInput(event: Event) { const input = event.target as HTMLInputElement; input.value = tokens.theme[input.dataset.key as keyof ClientTheme] }
async function pickWallpaper(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) { status.value = '请选择图片文件'; return }
  if (file.size > 3_000_000) { status.value = '壁纸图片请小于 3 MB'; return }
  tokens.glass.wallpaperImage = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsDataURL(file) })
}
function clearWallpaper() { tokens.glass.wallpaperImage = '' }
function cssText() {
  const { theme, glass, dock, shape } = tokens
  const themeVars = Object.entries({ ...theme, 'sidebar-text': theme.sidebarText, 'accent-ink': accentInk.value, tint: theme.selected, 'control-selected': theme.selected })
    .map(([key, value]) => `  --client-${key}: ${value};`).join('\n')
  const dockVars = [
    ['--nav-height', dock.height + 'px'], ['--nav-radius', dock.radius + 'px'], ['--nav-blur', glass.dockBlur + 'px'],
    ['--nav-item-pad', dock.pad + 'px'], ['--nav-item-gap', dock.gap + 'px'], ['--nav-tint', glass.dockTint + '%'],
    ['--nav-slide-duration', dock.slideMs + 'ms'], ['--nav-press-scale', String(dock.press)], ['--nav-pop-scale', String(dock.pop)],
  ].map(([key, value]) => `  ${key}: ${value};`).join('\n')
  const elementPart = tokens.elements.length
    ? `\n\n/* 自由布局：元素级修改（按页面生效，值为 !important） */\n${tokens.elements.map(rule => {
        const page = pageIds[pageNames.indexOf(rule.page as typeof pageNames[number])] || 'home'
        return `/* ${rule.page} · ${rule.label.replace(/\*\//g, '')} */\nbody:has(.desk[data-ui-page="${page}"]) ${rule.selector} {\n${Object.entries(rule.styles).map(([key, value]) => `  ${key}: ${value} !important;`).join('\n')}\n}`
      }).join('\n')}` : ''
  const wallpaper = glass.wallpaperImage
    ? `\n/* 照片背景（数据较长；也可改为文件引用） */\n:root[data-wallpaper="on"]{\n  --wallpaper-image: url("${glass.wallpaperImage.slice(0, 96)}${glass.wallpaperImage.length > 96 ? '…' : ''}");\n  --wallpaper-shade: ${glass.wallpaperShade}%;\n}` : ''
  return `/* Clash Studio UI 工坊导出 · ${new Date().toLocaleString('zh-CN')} */\n:root[data-client-theme="custom"]{\n${themeVars}\n  --client-glass-chrome: ${readableCoverage(theme.sidebar, theme.sidebarText, 85)}%;\n  --client-glass-panel: ${glass.panelOpacity}%;\n}\n\n/* 底部 Dock（加载于 mobile.css 之后；桌面布局忽略） */\n:root{\n${dockVars}\n}${wallpaper}\n\n/* 卡片与排版 */\n:root .desk .desk-card{border-radius:${shape.cardRadius}px;padding:${shape.cardPadding}px}\n:root .desk .desk-page-heading h1{font-size:${shape.h1Size}px}\n:root .desk .mobile-navigation>button{font-size:${shape.labelSize}px}\n${elementPart}\n`
}
function saveFile(name: string, content: string, type: string) { const url = URL.createObjectURL(new Blob([content], { type })); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); status.value = '已导出 ' + name }
async function copyCss() { try { await navigator.clipboard.writeText(cssText()); status.value = 'CSS 已复制到剪贴板' } catch { status.value = '复制失败，请改用导出 CSS' } }
function exportProject() { saveFile('clash-studio-android-ui.json', JSON.stringify(tokens, null, 2), 'application/json') }
function exportCss() { saveFile('clash-studio-android-ui.css', cssText(), 'text/css') }
async function importProject(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  input.value = ''
  if (!file) return
  try { if (file.size > 6e6) throw new Error('工程文件超过 6 MB'); const parsed = JSON.parse(await file.text()); if (!validProject(parsed)) throw new Error('不是有效的 UI 工坊工程'); Object.assign(tokens, parsed); clearSelection(); status.value = '工程已导入' } catch (error) { status.value = (error as Error).message }
}
const keydown = (event: KeyboardEvent) => {
  if ((event.target as HTMLElement)?.closest('input,textarea,select')) return
  if (event.key === 'Escape') clearSelection()
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); exportProject() }
}
window.addEventListener('keydown', keydown)
window.addEventListener('pointerup', pointerUp)
onBeforeUnmount(() => { observer?.disconnect(); cleanup?.(); window.removeEventListener('keydown', keydown); window.removeEventListener('pointerup', pointerUp) })
</script>

<template>
  <div class="aui">
    <header class="aui-bar">
      <div class="aui-brand"><span class="aui-logo">A</span><div><strong>Clash Studio <em>UI 工坊</em></strong><small>令牌定制 + 自由布局 · 实时预览真实界面 · 导出即所用</small></div></div>
      <div class="aui-actions">
        <button @click="usePreset(lightTheme)">浅色预设</button><button @click="usePreset(darkTheme)">深色预设</button><i></i>
        <label class="aui-button"><Upload :size="14"/>导入工程<input type="file" accept=".json" hidden @change="importProject"></label>
        <button @click="exportProject"><Download :size="14"/>导出工程</button>
        <button @click="exportCss"><Download :size="14"/>导出 CSS</button>
        <button class="primary" @click="copyCss"><Copy :size="14"/>复制 CSS</button>
        <button class="danger" title="恢复全部默认值" @click="resetAll"><RotateCcw :size="14"/>全部重置</button>
      </div>
    </header>
    <div class="aui-body">
      <main :class="['aui-stage', stage]">
        <div class="aui-stage-bar">
          <div class="aui-segment" role="group" aria-label="预览模式">
            <button :class="{selected:mode==='mobile'}" @click="mode='mobile'"><Smartphone :size="13"/>移动端</button>
            <button :class="{selected:mode==='desktop'}" @click="mode='desktop'"><Monitor :size="13"/>桌面端</button>
          </div>
          <select v-model.number="device" :aria-label="'设备尺寸'"><option v-for="(item,i) in devices" :key="item.name" :value="i">{{ item.name }}</option></select>
          <div class="aui-size"><input type="number" min="240" max="2560" v-model.number="width" aria-label="预览宽度"> × <input type="number" min="320" max="2160" v-model.number="height" aria-label="预览高度"></div>
          <select v-model.number="zoom" aria-label="预览缩放"><option :value=".5">50%</option><option :value=".6">60%</option><option :value=".75">75%</option><option :value="1">100%</option></select>
          <select v-if="mode==='mobile'" v-model.number="tokens.sim.safeBottom" aria-label="模拟底部安全区"><option :value="0">直角屏</option><option :value="16">小手势条</option><option :value="24">手势条</option><option :value="34">大手势条</option></select>
          <div class="aui-right">
            <div class="aui-segment" role="group" aria-label="编辑方式">
              <button :class="{selected:pick}" @click="pick=!pick"><MousePointer2 :size="13"/>选择元素</button>
              <button :class="{selected:!pick}" @click="pick=false"><Hand :size="13"/>交互</button>
            </div>
            <i></i>
            <button :class="{selected:stage==='dots'}" @click="stage='dots'">点阵</button><button :class="{selected:stage==='dark'}" @click="stage='dark'">深色</button><button :class="{selected:stage==='photo'}" @click="stage='photo'">照片</button>
          </div>
        </div>
        <div class="aui-scroll">
          <div class="aui-caption"><span>{{ mode==='mobile'?'ANDROID PREVIEW':'DESKTOP PREVIEW' }} <b>{{ width }} × {{ height }}</b></span><span>{{ pick?'点击选择元素，拖动移动（4px 吸附）；Esc 取消':'预览使用示例数据；界面组件与正式版完全一致' }}</span></div>
          <div :class="['aui-phone', {desk:mode==='desktop'}]" :style="{width:width*zoom+'px',height:height*zoom+'px'}">
            <div class="aui-screen" :style="{width:width+'px',height:height+'px',transform:`scale(${zoom})`}">
              <iframe :key="mode" ref="frame" :src="frameSrc" title="Clash Studio 实时预览" @load="loaded"/>
              <div v-if="box.visible" class="aui-selectbox" :style="{left:box.x+'px',top:box.y+'px',width:box.w+'px',height:box.h+'px'}">
                <span class="aui-selectlabel">{{ selectedLabel }} · {{ Math.round(box.w) }} × {{ Math.round(box.h) }}</span>
              </div>
            </div>
          </div>
          <p class="aui-note">在预览中可直接操作：切换页面、点击卡片；开启「选择元素」后可点击任意按钮或板块，在右侧「自由布局」面板调整位置与尺寸。</p>
        </div>
      </main>
      <aside class="aui-panel">
        <nav class="aui-tabs">
          <button :class="{selected:tab==='color'}" @click="tab='color'"><Palette :size="14"/>配色</button>
          <button :class="{selected:tab==='glass'}" @click="tab='glass'"><Droplets :size="14"/>玻璃与背景</button>
          <button :class="{selected:tab==='dock'}" @click="tab='dock'"><Smartphone :size="14"/>底部 Dock</button>
          <button :class="{selected:tab==='shape'}" @click="tab='shape'"><Type :size="14"/>卡片与排版</button>
          <button :class="{selected:tab==='free'}" @click="tab='free'"><Crosshair :size="14"/>自由布局</button>
        </nav>
        <div class="aui-scroll">
          <section v-if="tab==='color'">
            <div class="aui-group-head"><h3>主题配色</h3><button @click="resetGroup('theme')"><RotateCcw :size="12"/>恢复默认</button></div>
            <p class="aui-hint">与正式版「外观设置」使用同一套颜色变量，对比度要求也一致。</p>
            <label v-for="field in themeFields" :key="field.key" class="aui-color">
              <input type="color" :value="tokens.theme[field.key]" :aria-label="field.label" @input="tokens.theme[field.key]=($event.target as HTMLInputElement).value.toUpperCase()">
              <span>{{ field.label }}</span>
              <input type="text" :value="tokens.theme[field.key]" :data-key="field.key" :aria-label="field.label+'十六进制'" spellcheck="false" @change="setColor(field.key,$event)" @focus="hexInput">
            </label>
            <p v-if="themeWarning" class="aui-warn"><TriangleAlert :size="13"/>{{ themeWarning }}</p>
          </section>
          <section v-else-if="tab==='glass'">
            <div class="aui-group-head"><h3>玻璃与背景</h3><button @click="resetGroup('glass')"><RotateCcw :size="12"/>恢复默认</button></div>
            <label v-for="[key,title,min,max,step,unit] in sliders[0]!.fields" :key="key" class="aui-slider">
              <span>{{ title }}</span><input type="range" :min="min" :max="max" :step="step" v-model.number="(tokens.glass as any)[key]"><b>{{ (tokens.glass as any)[key] }}{{ unit }}</b>
            </label>
            <div class="aui-divider"></div>
            <div class="aui-group-head"><h3>照片背景</h3></div>
            <p class="aui-hint">模拟正式版的照片背景：先选壁纸，再用「壁纸压暗程度」调节文字可读性。</p>
            <div class="aui-wallpaper">
              <label class="aui-button"><ImageIcon :size="14"/>选择壁纸图片<input type="file" accept="image/*" hidden @change="pickWallpaper"></label>
              <button v-if="tokens.glass.wallpaperImage" @click="clearWallpaper"><RotateCcw :size="14"/>移除壁纸</button>
              <span v-if="tokens.glass.wallpaperImage" class="aui-ok"><Check :size="13"/>已应用</span>
            </div>
            <img v-if="tokens.glass.wallpaperImage" class="aui-wallpaper-thumb" :src="tokens.glass.wallpaperImage" alt=""/>
          </section>
          <section v-else-if="tab==='dock'">
            <div class="aui-group-head"><h3>底部 Dock</h3><button @click="resetGroup('dock')"><RotateCcw :size="12"/>恢复默认</button></div>
            <p class="aui-hint">滑块、图标与按压动画参数即 Dock 动画优化的全部变量；桌面端布局不使用底部 Dock。</p>
            <label v-for="[key,title,min,max,step,unit] in sliders[1]!.fields" :key="key" class="aui-slider">
              <span>{{ title }}</span><input type="range" :min="min" :max="max" :step="step" v-model.number="(tokens.dock as any)[key]"><b>{{ (tokens.dock as any)[key] }}{{ unit }}</b>
            </label>
          </section>
          <section v-else-if="tab==='shape'">
            <div class="aui-group-head"><h3>卡片与排版</h3><button @click="resetGroup('shape')"><RotateCcw :size="12"/>恢复默认</button></div>
            <label v-for="[key,title,min,max,step,unit] in sliders[2]!.fields" :key="key" class="aui-slider">
              <span>{{ title }}</span><input type="range" :min="min" :max="max" :step="step" v-model.number="(tokens.shape as any)[key]"><b>{{ (tokens.shape as any)[key] }}{{ unit }}</b>
            </label>
            <div class="aui-divider"></div>
            <p class="aui-hint">这些规则同时作用于移动端与桌面端预览。</p>
          </section>
          <section v-else>
            <div class="aui-group-head"><h3>自由布局</h3><button v-if="selected" @click="resetElement"><RotateCcw :size="12"/>清除该元素修改</button></div>
            <div v-if="!selected" class="aui-empty"><Crosshair :size="30"/><h3>先选择一个元素</h3><p>在顶部开启「选择元素」，然后点击预览中的按钮、卡片或板块；拖动可移动，右侧调整尺寸与外观。</p><div>① 选择元素<br>② 拖动或填写数值<br>③ 「父级」可上溯容器<br>④ 导出 CSS 交回集成</div></div>
            <template v-else>
              <div class="aui-selected"><small>当前元素 · {{ currentPage() }} 页</small><code>{{ selected }}</code><div><button @click="selectParent"><ChevronUp :size="13"/>父级</button></div></div>
              <div class="aui-elem-group"><h4>位置与尺寸</h4><label v-for="[key,title] in elementFields.slice(0,4)" :key="key"><span>{{ title }}</span><input :value="values[key!]" :aria-label="title" spellcheck="false" placeholder="默认" @change="changeElement(key!,$event)"></label></div>
              <div class="aui-elem-group"><h4>外观</h4><label v-for="[key,title] in elementFields.slice(4)" :key="key"><span>{{ title }}</span><input :value="values[key!]" :aria-label="title" spellcheck="false" placeholder="默认" @change="changeElement(key!,$event)"></label></div>
              <p class="aui-hint">留空表示恢复该属性的默认样式；修改仅写入预览与导出的 CSS，不影响项目源码。</p>
            </template>
          </section>
        </div>
        <footer class="aui-foot"><span class="aui-ok"><Check :size="13"/>{{ status }}</span><span><i>·</i> {{ tokens.elements.length }} 个元素已修改 <i>·</i> Ctrl+S 导出工程</span></footer>
      </aside>
    </div>
  </div>
</template>
