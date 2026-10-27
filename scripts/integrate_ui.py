"""One-time migration of the alpha shell to a unified desktop workspace."""
from pathlib import Path
import colorsys
import re

root = Path(__file__).resolve().parents[1]
path = root / "frontend/src/Client.vue"
s = path.read_text(encoding="utf-8")
s = s.replace("mixed_port:mixedPort.value});localStorage", "mixed_port:mixedPort.value,tun:tunDesired.value,tun_stack:tunStack.value});localStorage")
for old, new in (("工作台", "概览"), ("订阅中心", "订阅"), ("代理策略", "代理"), ("连接诊断", "连接"), ("配置编辑", "配置工作台")):
    s = s.replace(f"label:'{old}'", f"label:'{new}'")
s = s.replace("?'CONFIGURE WITH INTENTION'", "?'CLASH STUDIO'").replace("?'一切流量，各就其位'", "?'概览'")
s = s.replace("从订阅到策略，让每一次修改都有迹可循。", "管理订阅配置、分流模块与本机代理。")
s = s.replace("0.1.0-alpha", "0.2.0")
s = s.replace("本机测试版使用显式代理；TUN 与系统级断网保护尚未接入。", "TUN 需要管理员权限；系统级断网保护仍需单独实现。")
s = s.replace('<span class="version-tag">WINDOWS / X64</span>', '<span class="version-tag">{{ isDesktop?\'TAURI 2 / WINDOWS\':\'WEB PREVIEW / WINDOWS\' }}</span>')
start = s.index('        <template v-if="page===\'studio\'">')
end = s.index('</template>', start) + len('</template>')
s = s[:start] + '''        <template v-if="page==='studio'">
          <div class="section-toolbar"><label class="inline-select">当前订阅<select :value="selected" @change="choose(($event.target as HTMLSelectElement).value)"><option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.title }}</option></select></label><span>编辑草稿 → 保存发布 → 应用配置</span></div>
          <ConfigEditor v-if="detail" :key="detail.id" :subscription="detail" :backend-base="backendBase" @saved="editorSaved" @dirty="editorDirty=$event" @notice="notify"/>
          <div v-else class="desk-card desk-empty"><FileCode2 :size="36"/><h3>选择或导入一份订阅开始编辑</h3><button class="desk-btn primary" @click="importOpen=true">导入订阅</button></div>
        </template>''' + s[end:]
old = 'TUN 接管</strong><small>测试版未接入，需要后续设计权限和恢复机制。</small></div><span class="small-badge">暂不支持</span>'
assert old in s
s = s.replace(old, '''TUN 接管</strong><small>{{ runtime.tun?.admin?'创建虚拟网卡，接管系统路由与 DNS。':'需要管理员身份；会修改系统路由和 DNS。' }}</small></div><button :class="['desk-switch',{on:runtime.running?runtime.tun?.enabled:tunDesired}]" role="switch" :aria-checked="runtime.running?runtime.tun?.enabled:tunDesired" aria-label="TUN 接管" :disabled="!!busy" @click="toggleTun"><span></span></button>''')
idx = s.index('<div class="proxy-address">')
s = s[:idx] + '''<div class="tun-settings"><label class="desk-field">TUN 协议栈<select v-model="tunStack"><option value="mixed">Mixed · 混合协议栈</option><option value="system">System · 系统协议栈</option><option value="gvisor">gVisor · 用户空间协议栈</option></select></label><p v-if="runtime.tun?.conflicts.length" class="inline-note">其他内核运行中：{{ runtime.tun.conflicts.join('、') }}。启用 TUN 前请先关闭，以避免路由冲突。</p><button v-if="!runtime.tun?.admin" class="desk-btn" :disabled="!!busy" @click="elevate"><ShieldCheck :size="15"/>以管理员身份重新启动</button><p class="small-explanation">驱动：{{ runtime.tun?.driver_installed?'Wintun 已就绪':'Wintun 缺失' }} · 网卡名称 ClashStudio</p></div>''' + s[idx:]
path.write_text(s, encoding="utf-8")

css = (root / "frontend/src/client.css").read_text(encoding="utf-8")

def shift(match):
    token = match.group(1)
    if len(token) not in (6, 8):
        return match.group(0)
    r, g, b = (int(token[i:i+2], 16)/255 for i in (0, 2, 4))
    h, l, sat = colorsys.rgb_to_hls(r, g, b)
    if 0.17 <= h <= 0.5:
        r, g, b = colorsys.hls_to_rgb(0.70, l, sat)
    return '#' + ''.join(f'{round(v*255):02x}' for v in (r, g, b)) + token[6:]

css = re.sub(r'#([0-9a-fA-F]{8}|[0-9a-fA-F]{6})(?![0-9a-fA-F])', shift, css)
css = re.sub(r'\.studio-frame\{[^}]*\}', '', css)
(root / "frontend/src/verge.css").write_text(css, encoding="utf-8")
print("Integrated workspace shell and base desktop theme")
