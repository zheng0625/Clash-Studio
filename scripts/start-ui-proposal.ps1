param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$proposalRoot = Split-Path -Parent $PSScriptRoot
$proposalFrontend = Join-Path $proposalRoot 'frontend'
$proposalUrl = 'http://127.0.0.1:5188/ui-proposal.html'
$proposalListening = Get-NetTCPConnection -LocalPort 5188 -State Listen -ErrorAction SilentlyContinue
if ($proposalListening) {
    $proposalResponse = Invoke-WebRequest -Uri $proposalUrl -TimeoutSec 3 -UseBasicParsing
    if ($proposalResponse.Content -notmatch '/src/ui-proposal/main.ts|UI 优化预览') { throw '端口 5188 已被其他服务使用。' }
    if (!$NoBrowser) { Start-Process $proposalUrl }
    Write-Output $proposalUrl
    exit 0
}

$proposalNodeCommand = Get-Command node -ErrorAction SilentlyContinue
$proposalNode = if ($proposalNodeCommand) { $proposalNodeCommand.Source } else { Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' }
if (!(Test-Path -LiteralPath $proposalNode)) { throw '未找到 Node.js，请先安装 Node.js。' }
if (!(Test-Path -LiteralPath (Join-Path $proposalFrontend 'node_modules/vite/bin/vite.js'))) { throw '请先在 frontend 目录执行 pnpm install。' }
$proposalProcess = Start-Process -FilePath $proposalNode -ArgumentList @('node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5188', '--strictPort') -WorkingDirectory $proposalFrontend -WindowStyle Hidden -PassThru
for ($proposalAttempt = 0; $proposalAttempt -lt 30; $proposalAttempt++) {
    Start-Sleep -Milliseconds 300
    if ($proposalProcess.HasExited) { throw '预览服务启动失败，请检查端口和前端依赖。' }
    try { $proposalReady = Invoke-WebRequest -Uri $proposalUrl -TimeoutSec 1 -UseBasicParsing } catch { continue }
    if ($proposalReady.Content -notmatch '/src/ui-proposal/main.ts|UI 优化预览') { throw '返回的页面不是 UI 优化预览。' }
    if (!$NoBrowser) { Start-Process $proposalUrl }
    Write-Output $proposalUrl
    exit 0
}
throw '预览服务启动超时，请检查前端依赖。'
