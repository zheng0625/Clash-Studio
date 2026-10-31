<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef } from 'vue'
import type { Component } from 'vue'
import { isDesktop, quitDesktop } from './api'
import { t } from './i18n'

const client = shallowRef<Component>(), failed = ref(false)
// Android owns its local service lifecycle; skip the desktop preparation screen.
const nativeAndroid = !!window.ClashAndroid || location.hostname === 'appassets.androidplatform.net'
const icon = new URL('./assets/brand.svg', import.meta.url).href
let disposed = false, timer: ReturnType<typeof setTimeout> | undefined
let wake: (() => void) | undefined
function pause() { return new Promise<void>(resolve => { wake = resolve; timer = setTimeout(() => { wake = undefined; resolve() }, 200) }) }
async function ready() {
  if (!isDesktop) return
  const { invoke } = await import('@tauri-apps/api/core')
  const until = performance.now() + 32_000
  while (!disposed) {
    const state = await invoke<{phase: 'starting' | 'ready' | 'error'}>('startup_status')
    if (state.phase === 'ready') return
    if (state.phase === 'error' || performance.now() > until) throw new Error('Backend unavailable')
    await pause()
  }
}
async function close() { if (isDesktop) await quitDesktop() }
onMounted(async () => {
  performance.mark('clash-studio-shell')
  try {
    const [module] = await Promise.all([import('./Client.vue'), ready()])
    if (!disposed) { client.value = module.default; performance.mark('clash-studio-client-ready') }
  } catch { if (!disposed) failed.value = true }
})
onUnmounted(() => { disposed = true; clearTimeout(timer); wake?.() })
</script>
<template>
  <component :is="client" v-if="client"/>
  <section v-else-if="!nativeAndroid || failed" class="boot-screen" data-tauri-drag-region role="status" aria-live="polite">
    <img :src="icon" alt=""/><h1>Clash Studio</h1>
    <span v-if="!failed" class="boot-progress" aria-hidden="true"/>
    <p>{{ failed?t('启动未完成'):t('正在启动本地服务…') }}</p>
    <small v-if="failed && !nativeAndroid">{{ t('本地配置服务启动失败，请查看 data/tauri-backend.log 后重新打开软件。') }}</small>
    <button v-if="isDesktop" class="boot-close" :aria-label="t('关闭软件')" @click="close">×</button>
  </section>
</template>
