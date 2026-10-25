import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  build: { rollupOptions: { input: { app: 'index.html', editor: 'ui-editor.html', preview: 'ui-preview.html', android: 'ui-android.html' } } },
  server: { host: '127.0.0.1', proxy: { '/api': 'http://127.0.0.1:8870', '/sub': 'http://127.0.0.1:8870' } },
})
