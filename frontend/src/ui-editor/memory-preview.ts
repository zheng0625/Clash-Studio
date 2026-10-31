// Memory-focused preview: 16 proxy groups x 100 nodes and 5,000 connections.
// Requests never reach the backend; counters are exposed for browser acceptance.
const NODES = 100, GROUPS = 16
const nodes = Array.from({ length: NODES }, (_, i) => ({ name: `节点 ${i}`, type: 'ss', server: 'node.example.invalid', port: 443 }))
const proxies: Record<string, any> = {}
for (let g = 0; g < GROUPS; g++) {
  const group = `策略组 ${g}`
  proxies[group] = { name: group, type: 'Selector', all: nodes.map(n => n.name), now: nodes[0]!.name }
}
for (const node of nodes) proxies[node.name] = { name: node.name, type: 'Shadowsocks', history: [{ delay: 42 }] }
const config = { proxies: nodes, 'proxy-groups': Array.from({ length: GROUPS }, (_, g) => ({ name: `策略组 ${g}`, type: 'select', proxies: nodes.map(n => n.name) })), rules: ['MATCH,策略组 0'] }
const preview = { config, yaml: '# memory preview\nproxies: []\n', errors: [], warnings: [], module_rules: [], workspace_revision: 1, profile_revision: 1, published_conflict: false }
const profile = { id: 'memory-preview', title: 'Memory stress preview', source_type: 'demo', source_host: 'example.invalid', revision: 1, enabled: true, interval_minutes: 60, created_at: '2026-10-29T09:00:00+08:00', updated_at: '2026-10-29T09:00:00+08:00', refreshed_at: '2026-10-29T09:00:00+08:00', last_error: '', proxy_count: NODES, group_count: GROUPS, rule_count: 1, usage: { used: 0, total: 0, remaining: 0, percent: 0 }, source_url: '', source: config, source_yaml: preview.yaml, subscription_path: '/sub/memory-preview', preview, edits: { proxy_renames: {}, excluded_proxies: [], group_overrides: {}, deleted_groups: [], new_groups: [], removed_rules: [], added_rules: [], rule_order: [], ai_routing: null } }
const runtime = { running: true, installed: true, active: { profile_id: profile.id, title: profile.title, revision: 1, workspace_revision: 1, mixed_port: 17890, hash: 'memory-preview' }, routing_mode: 'rule', proxy: { supported: true, owned: true }, events: [{ time: '09:00:00', message: 'Memory stress preview.' }], tun: { supported: true, admin: false, enabled: false, stack: 'mixed', device: 'Clash Studio', driver_installed: true, conflicts: [] } }
const settings = { settings: { allow_lan: false, ipv6: true, lan_auth: false, mixed_port: 17890, lan_username: '', lan_password: '', dns_override: { enabled: false, mode: 'fake-ip', nameserver: [], fallback: [], bootstrap: [], proxy_nameserver: [], fake_ip_filter: [] } }, lan_addresses: [], core_version: 'Mihomo · memory preview', geodata: { busy: false, phase: 'idle', completed: 0, total: 4, file: '', message: '', files: [] } }
const connections = Array.from({ length: 5000 }, (_, i) => ({ id: String(i), metadata: { host: `host-${i}.example.invalid`, destinationIP: '192.0.2.1', destinationPort: '443', process: 'browser.exe', network: 'tcp' }, rule: 'DomainSuffix', rulePayload: 'example.invalid', chains: ['策略组 0', nodes[0]!.name], upload: 1024, download: 2048 }))
const probe = { traffic: 0, runtime: 0, resource: 0, connections: 0, by_path: {} as Record<string, number> }
;(window as any).__memoryProbe = probe
// DOM mirror: the CUA isolated world cannot read page globals, but it can read this node.
const probeNode = document.createElement('pre')
probeNode.id = 'memory-probe'
probeNode.style.cssText = 'position:fixed;left:-9999px;top:0;width:1px;height:1px;overflow:hidden'
document.body.appendChild(probeNode)
setInterval(() => { probeNode.textContent = JSON.stringify(probe) }, 200)
// Test-only visibility control; the component reads document.hidden and the event.
const hiddenState = { value: false }
Object.defineProperty(document, 'hidden', { configurable: true, get: () => hiddenState.value })
const hiddenToggle = document.createElement('button')
hiddenToggle.id = 'memory-hidden-toggle'
hiddenToggle.type = 'button'
hiddenToggle.textContent = 'toggle hidden'
hiddenToggle.style.cssText = 'position:fixed;left:8px;bottom:8px;z-index:9999'
hiddenToggle.onclick = () => {
  hiddenState.value = !hiddenState.value
  document.dispatchEvent(new Event('visibilitychange'))
}
document.body.appendChild(hiddenToggle)
window.fetch = async (input, init) => {
  const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.href)
  const p = url.pathname
  if (!p.startsWith('/api/')) return new Response('Memory preview only', { status: 403 })
  probe.by_path[p] = (probe.by_path[p] || 0) + 1
  if (p === '/api/client/network/traffic') { probe.traffic++; return Response.json({ running: true, session: 'memory', upload: 1048576 * probe.traffic, download: 4194304 * probe.traffic, connections: 5000 }) }
  if (p === '/api/client/runtime') { probe.runtime++; return Response.json(runtime) }
  if (p === '/api/client/resources/memory') { probe.resource++; return Response.json({ status: 'ok', total_bytes: 157286400, private_total_bytes: 125829120, private_method: 'private_commit_sum', sampled_at: Date.now() / 1000, processes: [{ kind: 'desktop', bytes: 33554432, private_bytes: 20971520, process_count: 1, unreadable_count: 0 }, { kind: 'webview', bytes: 46137344, private_bytes: 35651584, process_count: 3, unreadable_count: 0 }, { kind: 'service', bytes: 44040192, private_bytes: 37748736, process_count: 1, unreadable_count: 0 }, { kind: 'core', bytes: 33554432, private_bytes: 31457280, process_count: 1, unreadable_count: 0 }, { kind: 'probe', bytes: 0, private_bytes: 0, process_count: 0, unreadable_count: 0 }, { kind: 'other', bytes: 0, private_bytes: 0, process_count: 0, unreadable_count: 0 }] }) }
  if (p === '/api/client/runtime/connections') { probe.connections++; return Response.json({ connections, uploadTotal: 3145728, downloadTotal: 25165824, sampled_at: Date.now() / 1000 }) }
  if (init?.method && init.method !== 'GET') return Response.json({ detail: 'Memory preview does not submit.' }, { status: 400 })
  let value: unknown
  if (p === '/api/subscriptions') value = [profile]
  else if (p === '/api/subscriptions/memory-preview') value = profile
  else if (p === '/api/subscriptions/memory-preview/history') value = []
  else if (p === '/api/presets/ai') value = { version: 'preview', group_name: 'AI', service_count: 0, rule_count: 0, services: [] }
  else if (p === '/api/network') value = { enabled: false, port: 8767, selected_host: '', addresses: [], running: false, base_url: '', error: '' }
  else if (p === '/api/client/preview/memory-preview') value = preview
  else if (p === '/api/client/proxy-catalog') value = { proxies, key: 'memory-preview', live: true, has_providers: false, profile_revision: 1, workspace_revision: 1 }
  else if (p === '/api/client/runtime/proxies') value = { proxies }
  else if (p === '/api/client/workspace') value = { revision: 1, modules: [], plans: { 'memory-preview': { module_ids: [], default_target: '策略组 0' } } }
  else if (p === '/api/client/settings') value = settings
  else if (p === '/api/client/tray') value = { context_configured: false, proxy_mode: 'system', tun_stack: 'mixed', profile_id: '' }
  else if (p === '/api/client/platform') value = { os: 'windows', arch: 'x64' }
  else if (p === '/api/client/network/ip') value = { status: 'ok', provider: 'ippure.com', is_residential: false, is_broadcast: false, ip: '192.0.2.24', country: 'Preview', region: '', city: '', isp: '', asn: 'AS0', checked_at: new Date().toISOString(), elapsed_ms: 0, cached: true, message: '' }
  else if (p.includes('logs')) value = { entries: [], logs: [], events: [] }
  else return Response.json({ detail: 'Not available in memory preview.' }, { status: 400 })
  return Response.json(value)
}
void import('../main')

export {}
