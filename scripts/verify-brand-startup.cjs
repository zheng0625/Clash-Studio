// Production-bundle browser check; no real backend, VPN or system proxy is used.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const base = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:5198';
  const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'chrome' });
  const results = [];
  try {
    for (const mode of ['android', 'android-origin', 'desktop', 'android-load-failure']) {
      const native = mode !== 'desktop';
      const context = await browser.newContext({ viewport: native ? { width: 393, height: 873 } : { width: 840, height: 760 } });
      if (native && mode !== 'android-origin') await context.addInitScript(() => { window.ClashAndroid = { postMessage() {}, onmessage: null }; });
      const page = await context.newPage();
      let releaseShell;
      const shellGate = new Promise(resolve => { releaseShell = resolve; });
      let release;
      const gate = new Promise(resolve => { release = resolve; });
      let reached;
      const requested = new Promise(resolve => { reached = resolve; });
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.pathname.startsWith('/assets/') && url.pathname.endsWith('.js')) await shellGate;
        if (/\/Client-[^/]+\.js$/.test(url.pathname)) {
          reached();
          await gate;
          if (mode === 'android-load-failure') return route.abort();
        }
        if (url.pathname.startsWith('/api/')) return route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Isolated browser test"}' });
        const response = await route.fetch({ url: base + url.pathname + url.search });
        try { await route.fulfill({ response }); } catch (error) { if (!page.isClosed()) console.error('Route closed:', error.message); }
      });
      const origin = mode === 'android-origin' ? 'https://appassets.androidplatform.net' : base;
      await page.goto(origin + '/', { waitUntil: 'commit' });
      await page.locator('#boot-label').waitFor({ state: 'attached' });
      assert.equal(await page.locator('#boot-label').isVisible(), !native, mode + ': static startup screen');
      releaseShell();
      await requested;
      await page.waitForFunction(() => document.querySelector('#app')?.hasAttribute('data-v-app'));
      assert.equal(await page.locator('.boot-screen').count(), native ? 0 : 1, mode + ': Vue preparation screen');
      if (mode === 'desktop') {
        assert.equal(await page.locator('.boot-screen').isVisible(), true);
      }
      release();
      if (mode === 'android-load-failure') {
        await page.locator('.boot-screen[role="status"]').waitFor();
        assert.equal(await page.locator('.boot-progress').count(), 0);
      } else {
        await page.locator('.desk').waitFor();
        assert.equal(await page.locator('.boot-screen').count(), 0);
      }
      results.push({ mode, passed: true });
      await context.close();
    }
    const out = path.resolve(__dirname, '../test-output/brand-startup-20261031.json');
    fs.writeFileSync(out, JSON.stringify({ scope: 'Production bundle; mocked Android bridge and API errors', results }, null, 2));
    console.log(JSON.stringify(results));
  } catch (error) { console.error('Browser assertion:', error); throw error; }
  finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
