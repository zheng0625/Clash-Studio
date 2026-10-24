$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $PSScriptRoot
$frontendPath = Join-Path $studioRoot 'frontend'
$editorUrl = 'http://127.0.0.1:5178/ui-editor.html'
try {
    $existing = Invoke-WebRequest -Uri $editorUrl -TimeoutSec 2 -UseBasicParsing
    if ($existing.Content -notmatch 'UI 布局工坊') { throw '端口 5178 已被其他服务使用。' }
    Start-Process $editorUrl
    exit 0
} catch {
    if (Get-NetTCPConnection -LocalPort 5178 -State Listen -ErrorAction SilentlyContinue) {
        throw '端口 5178 已被其他服务使用，请先释放该端口。'
    }
}
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$nodePath = if ($nodeCommand) { $nodeCommand.Source } else { Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' }
if (!(Test-Path -LiteralPath $nodePath)) { throw '未找到 Node.js，请安装 Node.js 后重试。' }
if (!(Test-Path -LiteralPath (Join-Path $frontendPath 'node_modules/vite/bin/vite.js'))) { throw '请先在 frontend 目录运行 pnpm install。' }
$serverProcess = Start-Process -FilePath $nodePath -WorkingDirectory $frontendPath -ArgumentList @('node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5178', '--strictPort') -WindowStyle Hidden -PassThru
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 300
    if ($serverProcess.HasExited) { throw '布局工坊启动失败，请检查端口及项目依赖。' }
    try { $null = Invoke-WebRequest -Uri $editorUrl -TimeoutSec 1 -UseBasicParsing; Start-Process $editorUrl; exit 0 } catch { }
}
throw '布局工坊启动超时，请检查项目依赖。'
