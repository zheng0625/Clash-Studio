// Paint a localized, themed fallback before the Vue module graph is loaded.
(() => {
  // Run in <head> so the desktop fallback never paints in the native Android host.
  if (window.ClashAndroid || location.hostname === 'appassets.androidplatform.net') document.documentElement.classList.add('native-android');
  try {
    const preference = localStorage.getItem('clash-studio-language-v1');
    const system = window.__CLASH_SYSTEM_LANGUAGE__ || navigator.languages?.[0] || navigator.language || 'en';
    const chinese = preference === 'zh-CN' || (preference !== 'en' && system.toLowerCase().startsWith('zh'));
    document.documentElement.lang = chinese ? 'zh-CN' : 'en';
    const localize = () => {
      const label = document.getElementById('boot-label');
      if (label) label.textContent = chinese ? '正在加载界面…' : 'Loading the interface…';
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', localize, { once: true });
    else localize();
    const theme = JSON.parse(localStorage.getItem('clash-studio-client-theme-v1') || 'null');
    if (theme && /^#[\da-f]{6}$/i.test(theme.background) && /^#[\da-f]{6}$/i.test(theme.text)) {
      document.documentElement.style.setProperty('--boot-bg', theme.background);
      document.documentElement.style.setProperty('--boot-text', theme.text);
    }
  } catch { /* The static loading view remains visible if storage is unavailable. */ }
})();
