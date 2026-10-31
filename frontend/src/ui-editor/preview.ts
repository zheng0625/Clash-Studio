// This entry is isolated from the desktop entry. Preview requests never reach the backend.
export {}
const nodes = ['香港 · 01', '日本 · 02', '新加坡 · 03', '美国 · 04'].map((name, i) => ({ name, type: 'ss', server: 'node.example.invalid', port: 443 + i, cipher: 'aes-128-gcm', password: 'preview-only' }))
const config = { proxies: nodes, 'proxy-groups': [{ name: '自动选择', type: 'select', proxies: nodes.map(n => n.name) }], rules: ['DOMAIN-SUFFIX,example.com,自动选择', 'GEOIP,CN,DIRECT', 'MATCH,自动选择'] }
const preview = { config, yaml: '# UI 预览示例\nproxies: []\nrules:\n  - MATCH,DIRECT\n', errors: [], warnings: [], module_rules: [], workspace_revision: 1, profile_revision: 1, published_conflict: false }
const profile = { id: 'ui-preview', title: 'Studio · 示例订阅', source_type: 'demo', source_host: 'example.invalid', revision: 1, enabled: true, interval_minutes: 60, created_at: '2026-10-24T09:00:00+08:00', updated_at: '2026-10-24T09:00:00+08:00', refreshed_at: '2026-10-24T09:00:00+08:00', last_error: '', proxy_count: 4, group_count: 1, rule_count: 3, usage: { used: 32 * 1024 ** 3, total: 200 * 1024 ** 3, remaining: 168 * 1024 ** 3, percent: 16 }, source_url: '', source: config, source_yaml: preview.yaml, subscription_path: '/sub/ui-preview', preview, edits: { proxy_renames: {}, excluded_proxies: [], group_overrides: {}, deleted_groups: [], new_groups: [], removed_rules: [], added_rules: [], rule_order: [], ai_routing: null } }
const proxies = Object.fromEntries([...nodes.map((n,i) => [n.name, { name: n.name, type: 'Shadowsocks', history: [{ delay: 38 + i * 24 }] }]), ['自动选择', { name: '自动选择', type: 'Selector', all: nodes.map(n => n.name), now: nodes[0]!.name }]])
const runtime = { running: true, installed: true, active: { profile_id: 'ui-preview', title: profile.title, revision: 1, workspace_revision: 1, mixed_port: 17890, hash: 'ui-preview' }, routing_mode: 'rule', proxy: { supported: true, owned: true }, events: [{ time: '09:00:00', message: '设计预览：以下为示例数据。' }], tun: { supported: true, admin: false, enabled: false, stack: 'mixed', device: 'Clash Studio', driver_installed: true, conflicts: [] } }
const settings = { settings: { allow_lan: false, ipv6: true, lan_auth: false, mixed_port: 17890, lan_username: '', lan_password: '', dns_override: { enabled: false, mode: 'fake-ip', nameserver: [], fallback: [], bootstrap: [], proxy_nameserver: [], fake_ip_filter: [] } }, lan_addresses: ['192.168.1.100'], core_version: 'Mihomo · UI 预览', geodata: { busy: false, phase: 'idle', completed: 0, total: 4, file: '', message: '', files: [] } }
const lab=new URLSearchParams(location.search)
const inLab=location.pathname.endsWith('/ui-component-frame.html')
const labScene=inLab?lab.get('scene'):null
const labComponent=inLab?lab.get('component'):null
if(inLab){
  profile.source_type='url'
  runtime.running=labComponent==='kernel'?!['待启动','未导入'].includes(labScene||''):true
  if(labScene==='待应用')runtime.active.workspace_revision=0
  if(labScene==='全局模式')runtime.routing_mode='global'
  if(labScene==='直连模式')runtime.routing_mode='direct'
  if(labScene==='待启动')runtime.running=false
  if(labScene==='TUN 待授权')runtime.tun.enabled=true
  if(labScene==='直连')runtime.routing_mode='direct'
  if(labScene==='自动选择')proxies['自动选择'].type='URLTest'
  if(['usage','config'].includes(labComponent||'')){
    if(labScene==='即将用尽'||labScene==='已用尽'){const percent=labScene==='即将用尽'?95:100;profile.usage={used:percent*2*1024**3,total:200*1024**3,remaining:(200-percent*2)*1024**3,percent}}
    if(labScene==='总量未知')Object.assign(profile.usage,{total:null,remaining:null,percent:null})
    if(labScene==='无数据')Object.assign(profile,{usage:null})
  }
}
window.fetch = async (input, init) => {
  const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.href)
  if (!url.pathname.startsWith('/api/')) return new Response('Preview only', { status: 403 })
  let value: unknown
  const p = url.pathname
  if(inLab&&p==='/api/client/proxy-catalog'){
    if(labScene==='读取失败'&&labComponent==='selection')return Response.json({detail:'暂时无法读取策略组'},{status:503})
    if(labScene==='加载中')return new Promise<Response>(()=>{})
  }
  if(inLab&&p==='/api/client/resources/memory'){
    const status=labScene==='部分可读'?'partial':labScene==='读取失败'?'unavailable':'ok'
    return Response.json({status,ram_method:'private_working_set_sum',private_working_set_status:status,private_working_set_total_bytes:status==='unavailable'?null:184.6*1024**2,total_bytes:420*1024**2,sampled_at:Date.now()/1000,processes:['desktop','webview','service','core'].map((kind,i)=>({kind,bytes:(i+1)*18.46*1024**2,private_working_set_bytes:status==='unavailable'?null:(i+1)*18.46*1024**2,process_count:1,unreadable_count:0}))})
  }
  if(inLab&&lab.get('platform')==='android'&&p==='/api/client/runtime/apply'){
    if(labScene==='应用中')return new Promise<Response>(()=>{})
    if(labScene==='应用失败')return Response.json({detail:'示例应用失败，可重试'},{status:503})
  }
  if(inLab&&labComponent==='routing-list'&&p==='/api/android/routing'){
    if(labScene==='加载中')return new Promise<Response>(()=>{})
    if(labScene==='读取失败')return Response.json({detail:'示例规则暂时无法读取'},{status:503})
  }
  if (p === '/api/client/tray/context') return Response.json({ ok: true })
  if(inLab&&p==='/api/subscriptions/ui-preview/preview')return Response.json(preview)
  if (p === '/api/client/runtime/delay') return Response.json({ name: '', endpoint: 'cloudflare', status: 'ok', delay_ms: 48 + Math.round(Math.random() * 320), checked_at: new Date().toISOString() })
  if ((init?.method || 'GET') !== 'GET') return Response.json({ detail: '设计预览仅用于调整界面，操作不会提交。' }, { status: 400 })
  if (p === '/api/subscriptions') value = labScene==='未导入'?[]:[profile]
  else if (p === '/api/subscriptions/ui-preview') value = profile
  else if (p === '/api/subscriptions/ui-preview/history') value = inLab?[{id:1,label:'工坊示例快照',created_at:'2026-10-30T09:00:00+08:00',size:2048}]:[]
  else if (inLab&&p === '/api/subscriptions/ui-preview/history/1') value = {id:1,label:'工坊示例快照',yaml:preview.yaml}
  else if (p === '/api/presets/ai' || p === '/api/ai/catalogue' || p === '/api/ai-routing/catalogue') value = { version: 'preview', group_name: 'AI 服务', service_count: 0, rule_count: 0, services: [] }
  else if (p === '/api/network') value = { enabled: false, port: 8767, selected_host: '', addresses: [], running: false, base_url: '', error: '' }
  else if (p === '/api/client/preview/ui-preview') value = preview
  else if (p === '/api/client/runtime/proxies') value = { proxies }
  else if (p === '/api/client/proxy-catalog') value = { proxies, key: 'preview', live: true, has_providers: false, profile_revision: 1, workspace_revision: 1 }
  else if (p === '/api/client/runtime/connections') value = { connections: Array.from({length:inLab&&labComponent?.startsWith('connection-')?230:3},(_,i)=>'service-'+i+'.example.invalid').map((host,i) => ({ id: String(i), metadata: { host, destinationIP: '192.0.2.' + (i%250+1), destinationPort: '443', process: 'browser.exe', network: 'tcp' }, rule: 'DomainSuffix', rulePayload: 'example.com', chains: ['自动选择', nodes[0]!.name], upload: 1048576, download: 8388608 })), uploadTotal: 3145728, downloadTotal: 25165824 }
  else if (p === '/api/client/workspace') value = { revision: 1, modules: [{ id: 'demo', name: 'AI 服务专线', target: '自动选择', strict: true, matches: [{ kind: 'DOMAIN-SUFFIX', value: 'example.com' }] }], plans: { 'ui-preview': { module_ids: ['demo'], default_target: '自动选择' } } }
  else if (p === '/api/android/routing') value = { revision: 1, targets: ['DIRECT', 'REJECT', '自动选择'], rules: Array.from({ length: inLab&&labComponent==='routing-list'?(labScene==='空列表'?0:labScene==='大量规则'?237:24):24 }, (_, i) => ({ kind: i % 5 === 0 ? 'PROCESS-NAME' : 'DOMAIN-SUFFIX', value: i % 5 === 0 ? 'com.example.app' + i : 'service-' + (i + 1) + '.example.invalid', target: i % 3 === 0 ? 'DIRECT' : '自动选择', enabled: i % 7 !== 0 })) }
  else if (p === '/api/android/permissions') value = { camera: false, notifications: false, vpn: false }
  else if (p === '/api/android/apps') value = [{ package: 'com.example.app0', label: '示例浏览器' }, { package: 'com.example.app5', label: '示例音乐' }, { package: 'com.example.app10', label: 'Example Video' }]
  else if (p === '/api/client/settings') value = settings
  else if (p === '/api/client/runtime') value = runtime
  else if (p === '/api/client/tray') value = { context_configured: false, proxy_mode: 'system', tun_stack: 'mixed', profile_id: '' }
  else if (p === '/api/client/platform') value = new URLSearchParams(location.search).get('platform') === 'android'
    ? { os: 'android', arch: 'arm64-v8a', capabilities: { validation: false, development: true, native_insets: true, subscriptions: true, modules: false, ai: false, lan_share: false, autostart: false, core: true, vpn: true } }
    : { os: 'windows', arch: 'x64', capabilities:{autostart:true} }
  else if (p === '/api/client/resources/memory') value = { status: 'ok', total_bytes: 154560102, sampled_at: Date.now()/1000, processes: [{kind:'interface',bytes:71722598,process_count:4,unreadable_count:0},{kind:'service',bytes:44879053,process_count:1,unreadable_count:0},{kind:'core',bytes:37958451,process_count:1,unreadable_count:0}] }
  else if (p === '/api/client/network/traffic') {const seconds=inLab?performance.now()/1000:0;value = { running: runtime.running, session: 'preview', upload: 3145728+Math.round(seconds*128*1024), download: 25165824+Math.round(seconds*2*1024**2), connections: 3, sampled_at:Date.now()/1000 }}
  else if (p === '/api/client/network/dns-summary') value = { status: 'ok', nameservers: ['https://dns.example.invalid'], source: 'runtime', profile_id: profile.id, config_hash: 'ui-preview' }
  else if (p === '/api/client/network/ip') value = { status: 'ok', provider: 'ippure.com', is_residential: false, is_broadcast: false, ip: '192.0.2.24', country: '设计预览', region: '示例位置', city: '', isp: '示例网络 · 非真实数据', asn: 'AS0000', checked_at: new Date().toISOString(), elapsed_ms: 0, cached: true, message: '' }
  else if (p.includes('logs')) value = { entries: [], logs: [], events: [] }
  else return Response.json({ detail: '此内容需要真实数据；请在正式软件中查看。' }, { status: 400 })
  return Response.json(value)
}
void import('../main')
