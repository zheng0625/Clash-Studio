import { computed, ref, watch } from 'vue'
import desktopEnglish from './locales/en.json'
import studioEnglish from './studio/locales/en.json'

export type Language = 'auto' | 'zh-CN' | 'en'
const key = 'clash-studio-language-v1'
function saved(): Language {
  try { const value = localStorage.getItem(key); return value === 'en' || value === 'zh-CN' ? value : 'auto' } catch { return 'auto' }
}
declare global { interface Window { __CLASH_SYSTEM_LANGUAGE__?: string } }
const detected = () => window.__CLASH_SYSTEM_LANGUAGE__ || navigator.languages?.[0] || navigator.language || 'en'
export const language = ref<Language>(saved())
export const systemLanguage = ref(detected())
export const locale = computed(() => language.value === 'auto' ? (systemLanguage.value.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en') : language.value)
const catalogue: Record<string, string> = { ...studioEnglish, ...desktopEnglish }
const format = (text: string, args: unknown[]) => text.replace(/\{(\d+)\}/g, (whole, index) => args[Number(index)] === undefined ? whole : String(args[Number(index)]))
export function t(source: string, args: unknown[] = []): string { return format(locale.value === 'en' ? catalogue[source] ?? source : source, args) }
const patterns = Object.entries(catalogue).filter(([source]) => /\{\d+\}/.test(source)).sort((a, b) => b[0].length - a[0].length).map(([source, target]) => {
  const indices: number[] = []
  const pattern = source.split(/(\{\d+\})/g).map(part => /^\{\d+\}$/.test(part) ? (indices.push(Number(part.slice(1, -1))), '([\\s\\S]*?)') : part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('')
  return { regex: new RegExp('^' + pattern + '$'), target, indices }
})
/** Only for application diagnostics, never subscription names, nodes, YAML, or credentials. */
export function message(value: string | null | undefined): string {
  const source = value || ''
  if (locale.value !== 'en' || !source) return source
  if (catalogue[source]) return catalogue[source]
  for (const p of patterns) { const match = source.match(p.regex); if (match) { const args: unknown[] = []; p.indices.forEach((index, i) => { args[index] = match[i + 1] }); return format(p.target, args) } }
  if (source.includes('；')) return source.split('；').map(message).join('; ')
  return source
}
export async function initializeLanguage() {
  if ('__TAURI_INTERNALS__' in window) {
    try { const { invoke } = await import('@tauri-apps/api/core'); systemLanguage.value = await invoke<string>('system_locale'); await invoke('set_desktop_language', { language: language.value }) } catch { /* Browser locale remains the fallback. */ }
  }
}
watch(language, async value => {
  if ('__TAURI_INTERNALS__' in window) {
    try { const { invoke } = await import('@tauri-apps/api/core'); await invoke('set_desktop_language', { language: value }) }
    catch (error) { console.error('Unable to synchronize tray language', error) }
  }
}, { flush: 'sync' })
window.addEventListener('languagechange', () => { if (!('__TAURI_INTERNALS__' in window)) systemLanguage.value = detected() })
window.addEventListener('storage', event => { if (event.key === key) language.value = saved() })
watch(language, value => { try { localStorage.setItem(key, value) } catch { /* Current session still switches. */ } }, { flush: 'sync' })
watch(locale, value => { document.documentElement.lang = value; document.title = 'Clash Studio' }, { immediate: true, flush: 'sync' })
