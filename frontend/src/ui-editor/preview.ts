// This entry is isolated from the desktop entry. Preview requests never reach the backend.
const nodes = ['香港 · 01', '日本 · 02', '新加坡 · 03', '美国 · 04'].map((name, i) => ({ name, type: 'ss', server: 'node.example.invalid', port: 443 + i, cipher: 'aes-128-gcm', password: 'preview-only' }))
const config = { proxies: nodes, 'proxy-groups': [{ name: '自动选择', type: 'select', proxies: nodes.map(n => n.name) }], rules: ['DOMAIN-SUFFIX,example.com,自动选择', 'GEOIP,CN,DIRECT', 'MATCH,自动选择'] }
const preview = { config, yaml: '# UI 预览示例\nproxies: []\nrules:\n  - MATCH,DIRECT\n', errors: [], warnings: [], module_rules: [], workspace_revision: 1, profile_revision: 1, published_conflict: false }
const profile = { id: 'ui-preview', title: 'Studio · 示例订阅', source_type: 'demo', source_host: 'example.invalid', revision: 1, enabled: true, interval_minutes: 60, created_at: '2026-10-24T09:00:00+08:00', updated_at: '2026-10-24T09:00:00+08:00', refreshed_at: '2026-10-24T09:00:00+08:00', last_error: '', proxy_count: 4, group_count: 1, rule_count: 3, usage: { used: 32 * 1024 ** 3, total: 200 * 1024 ** 3, remaining: 168 * 1024 ** 3, percent: 16 }, source_url: '', source: config, source_yaml: preview.yaml, subscription_path: '/sub/ui-preview', preview, edits: { proxy_renames: {}, excluded_proxies: [], group_overrides: {}, deleted_groups: [], new_groups: [], removed_rules: [], added_rules: [], rule_order: [], ai_routing: null } }
const proxies = Object.fromEntries([...nodes.map((n,i) => [n.name, { name: n.name, type: 'Shadowsocks', history: [{ delay: 38 + i * 24 }] }]), ['自动选择', { name: '自动选择', type: 'Selector', all: nodes.map(n => n.name), now: nodes[0]!.name }]])
const runtime = { running: true, installed: true, active: { profile_id: 'ui-preview', title: profile.title, revision: 1, workspace_revision: 1, mixed_port: 17890, hash: 'ui-preview' }, routing_mode: 'rule', proxy: { supported: true, owned: true }, events: [{ time: '09:00:00', message: '设计预览：以下为示例数据。' }], tun: { supported: true, admin: false, enabled: false, stack: 'mixed', device: 'Clash Studio', driver_installed: true, conflicts: [] } }
const settings = { settings: { allow_lan: false, ipv6: true, lan_auth: false, mixed_port: 17890, lan_username: '', lan_password: '', dns_override: { enabled: false, mode: 'fake-ip', nameserver: [], fallback: [], bootstrap: [], proxy_nameserver: [], fake_ip_filter: [] } }, lan_addresses: ['192.168.1.100'], core_version: 'Mihomo · UI 预览', geodata: { busy: false, phase: 'idle', completed: 0, total: 4, file: '', message: '', files: [] } }
window.fetch = async (input, init) => {
  const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.href)
  if (!url.pathname.startsWith('/api/')) return new Response('Preview only', { status: 403 })
  let value: unknown
  const p = url.pathname
  if (p === '/api/client/tray/context') return Response.json({ ok: true })
  if ((init?.method || 'GET') !== 'GET') return Response.json({ detail: '设计预览仅用于调整界面，操作不会提交。' }, { status: 400 })
  if (p === '/api/subscriptions') value = [profile]
  else if (p === '/api/subscriptions/ui-preview') value = profile
  else if (p === '/api/subscriptions/ui-preview/history') value = []
  else if (p === '/api/presets/ai' || p === '/api/ai/catalogue' || p === '/api/ai-routing/catalogue') value = { version: 'preview', group_name: 'AI 服务', service_count: 0, rule_count: 0, services: [] }
  else if (p === '/api/network') value = { enabled: false, port: 8767, selected_host: '', addresses: [], running: false, base_url: '', error: '' }
  else if (p === '/api/client/preview/ui-preview') value = preview
  else if (p === '/api/client/runtime/proxies') value = { proxies }
  else if (p === '/api/client/proxy-catalog') value = { proxies, key: 'preview', live: true, has_providers: false, profile_revision: 1, workspace_revision: 1 }
  else if (p === '/api/client/runtime/connections') value = { connections: ['example.com','cdn.example.com','api.example.com'].map((host,i) => ({ id: String(i), metadata: { host, destinationIP: '192.0.2.' + (i+1), destinationPort: '443', process: 'browser.exe', network: 'tcp' }, rule: 'DomainSuffix', rulePayload: 'example.com', chains: ['自动选择', nodes[0]!.name], upload: 1048576, download: 8388608 })), uploadTotal: 3145728, downloadTotal: 25165824 }
  else if (p === '/api/client/workspace') value = { revision: 1, modules: [{ id: 'demo', name: 'AI 服务专线', target: '自动选择', strict: true, matches: [{ kind: 'DOMAIN-SUFFIX', value: 'example.com' }] }], plans: { 'ui-preview': { module_ids: ['demo'], default_target: '自动选择' } } }
  else if (p === '/api/client/settings') value = settings
  else if (p === '/api/client/runtime') value = runtime
  else if (p === '/api/client/tray') value = { context_configured: false, proxy_mode: 'system', tun_stack: 'mixed', profile_id: '' }
  else if (p === '/api/client/platform') value = { os: 'windows', arch: 'x64' }
  else if (p === '/api/client/network/traffic') value = { running: true, session: 'preview', upload: 3145728, download: 25165824, connections: 3 }
  else if (p === '/api/client/network/ip') value = { ip: '192.0.2.24', country: '设计预览', region: '示例位置', city: '', isp: '示例网络 · 非真实数据', asn: 'AS0000', checked_at: new Date().toISOString(), elapsed_ms: 0, cached: true, message: '' }
  else if (p.includes('logs')) value = { entries: [], logs: [], events: [] }
  else return Response.json({ detail: '此内容需要真实数据；请在正式软件中查看。' }, { status: 400 })
  return Response.json(value)
}
void import('../main')
