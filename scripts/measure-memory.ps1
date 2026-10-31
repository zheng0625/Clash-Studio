<#
.SYNOPSIS
  Streams per-process working set and private commit for the Clash Studio app tree.
.DESCRIPTION
  Samples the desktop process, its descendants and optionally tree-external managed
  cores every interval. Rows are appended to CSV immediately. Role totals are kept
  per tick only, so the final summary is bounded by duration/interval, not by the
  number of processes or raw rows. Permission-denied processes are recorded as
  unreadable rather than zero. PID reuse is detectable through the created_at column.
#>
param(
  [int]$RootProcessId = 0,
  [string]$ProcessName = 'clash-studio',
  [int[]]$CoreProcessIds = @(),
  [int]$DurationSeconds = 300,
  [int]$WarmupSeconds = 120,
  [int]$IntervalSeconds = 2,
  [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not $OutputPath) {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $OutputPath = Join-Path $root "artifacts/memory/$stamp-role-sample"
}
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

function Resolve-RootProcess {
  if ($script:RootProcessId -gt 0) { return Get-Process -Id $script:RootProcessId -ErrorAction Stop }
  $candidates = Get-Process | Where-Object { $_.ProcessName -like '*clash*studio*' }
  if (-not $candidates) { throw "No Clash Studio desktop process found. Pass -RootProcessId." }
  if (@($candidates).Count -gt 1) {
    throw "Multiple candidate desktop processes: $($candidates.Id -join ', '). Pass -RootProcessId."
  }
  return $candidates
}

function Get-Role([string]$name, [string]$commandLine) {
  $lower = $name.ToLowerInvariant()
  if ($lower.StartsWith('mihomo')) {
    if ($commandLine -match '(?i)probe[\\/]data') { return 'core_probe' }
    return 'core_main'
  }
  if ($lower.StartsWith('python')) { return 'service' }
  if ($lower.StartsWith('msedgewebview2') -or $lower.StartsWith('webview2')) { return 'webview' }
  if ($lower.StartsWith('clash-studio') -or $lower.StartsWith('clashstudio') -or $lower.StartsWith('tauri')) { return 'desktop' }
  return 'other'
}

function Get-Snapshot {
  $rows = @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, Name, CreationDate, CommandLine)
  $meta = @{}
  foreach ($row in $rows) {
    $meta[[int]$row.ProcessId] = @{
      Name = [string]$row.Name
      Parent = [int]$row.ParentProcessId
      Created = if ($row.CreationDate) { ([datetime]$row.CreationDate).ToString('o') } else { '' }
      CommandLine = [string]$row.CommandLine
    }
  }
  return $meta
}

function Get-TreeIds([hashtable]$meta, [int]$rootPid, [int[]]$extraCores) {
  $children = @{}
  foreach ($procId in $meta.Keys) {
    $parent = $meta[$procId].Parent
    if (-not $children.ContainsKey($parent)) { $children[$parent] = New-Object System.Collections.Generic.List[int] }
    $children[$parent].Add($procId)
  }
  $found = New-Object System.Collections.Generic.List[int]
  $seen = New-Object System.Collections.Generic.HashSet[int]
  $todo = New-Object System.Collections.Generic.Stack[int]
  $todo.Push($rootPid)
  while ($todo.Count -gt 0) {
    $currentId = $todo.Pop()
    if (-not $seen.Add($currentId)) { continue }
    $found.Add($currentId)
    if ($children.ContainsKey($currentId)) { foreach ($child in $children[$currentId]) { $todo.Push($child) } }
  }
  foreach ($coreId in $extraCores) {
    if ($meta.ContainsKey($coreId) -and $meta[$coreId].Name.ToLowerInvariant().StartsWith('mihomo') -and $seen.Add($coreId)) {
      $found.Add($coreId)
    }
  }
  return $found
}

$rootProcess = Resolve-RootProcess
$csvPath = Join-Path $OutputPath 'samples.csv'
$writer = New-Object System.IO.StreamWriter($csvPath, $false, [System.Text.UTF8Encoding]::new($false))
$writer.WriteLine('at,elapsed_s,pid,created_at,role,name,working_set_bytes,private_bytes,threads,handles,readable')
$roles = @('desktop', 'webview', 'service', 'core_main', 'core_probe', 'other')
$workingSamples = @{}
$privateSamples = @{}
foreach ($role in $roles) {
  $workingSamples[$role] = New-Object System.Collections.Generic.List[double]
  $privateSamples[$role] = New-Object System.Collections.Generic.List[double]
}
$totalWorking = New-Object System.Collections.Generic.List[double]
$totalPrivate = New-Object System.Collections.Generic.List[double]
$partialTicks = 0
$started = Get-Date
$unreadable = 0
$lastMeta = $null
$lastMetaAt = [datetime]::MinValue
try {
  while (((Get-Date) - $started).TotalSeconds -lt $DurationSeconds) {
    $elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
    if ($null -eq $lastMeta -or ((Get-Date) - $lastMetaAt).TotalSeconds -ge 5) {
      $lastMeta = Get-Snapshot
      $lastMetaAt = Get-Date
    }
    $ids = Get-TreeIds -meta $lastMeta -rootPid $rootProcess.Id -extraCores $CoreProcessIds
    $at = (Get-Date).ToString('o')
    $tickWorking = @{}; $tickPrivate = @{}; $tickPartial = $false
    foreach ($role in $roles) { $tickWorking[$role] = 0.0; $tickPrivate[$role] = 0.0 }
    foreach ($procId in $ids) {
      $info = if ($lastMeta.ContainsKey($procId)) { $lastMeta[$procId] } else { @{ Name = ''; Created = ''; CommandLine = '' } }
      $role = Get-Role $info.Name $info.CommandLine
      $working = ''; $private = ''; $threads = ''; $handles = ''; $readable = 'false'
      try {
        $process = Get-Process -Id $procId -ErrorAction Stop
        $working = [int64]$process.WorkingSet64
        $private = [int64]$process.PrivateMemorySize64
        $threads = [int]$process.Threads.Count
        $handles = [int]$process.HandleCount
        $readable = 'true'
        $tickWorking[$role] += [double]$working
        $tickPrivate[$role] += [double]$private
      } catch {
        $unreadable++
        $tickPartial = $true
      }
      $writer.WriteLine("$at,$elapsed,$procId,$($info.Created),$role,$($info.Name),$working,$private,$threads,$handles,$readable")
    }
    if ($elapsed -ge $WarmupSeconds) {
      if ($tickPartial) { $partialTicks++ }
      $sumWorking = 0.0; $sumPrivate = 0.0
      foreach ($role in $roles) {
        $workingSamples[$role].Add($tickWorking[$role])
        $privateSamples[$role].Add($tickPrivate[$role])
        $sumWorking += $tickWorking[$role]
        $sumPrivate += $tickPrivate[$role]
      }
      $totalWorking.Add($sumWorking)
      $totalPrivate.Add($sumPrivate)
    }
    Start-Sleep -Seconds $IntervalSeconds
  }
} finally {
  $writer.Flush(); $writer.Dispose()
}

function Get-Percentile($values, [double]$p) {
  if (-not $values -or $values.Count -eq 0) { return $null }
  $sorted = @($values | Sort-Object)
  $index = [math]::Min($sorted.Count - 1, [math]::Floor($p * ($sorted.Count - 1)))
  return [int64]$sorted[[int]$index]
}
function Get-Median($values) { return Get-Percentile $values 0.5 }
function Describe-Role($working, $private) {
  return [ordered]@{
    samples = $working.Count
    working_median = Get-Median $working
    working_p95 = Get-Percentile $working 0.95
    private_median = Get-Median $private
    private_p95 = Get-Percentile $private 0.95
  }
}
$roleSummary = [ordered]@{}
foreach ($role in $roles) { $roleSummary[$role] = Describe-Role $workingSamples[$role] $privateSamples[$role] }
$roleSummary['total'] = Describe-Role $totalWorking $totalPrivate
$summary = [ordered]@{
  tool = 'measure-memory.ps1'
  version = 2
  created = (Get-Date).ToString('o')
  machine = $env:COMPUTERNAME
  os = [System.Environment]::OSVersion.VersionString
  ps_version = $PSVersionTable.PSVersion.ToString()
  root_pid = $rootProcess.Id
  root_name = $rootProcess.ProcessName
  extra_core_ids = @($CoreProcessIds)
  duration_s = $DurationSeconds
  warmup_s = $WarmupSeconds
  interval_s = $IntervalSeconds
  steady_ticks = $totalWorking.Count
  partial_ticks = $partialTicks
  unreadable_samples = $unreadable
  metric = 'per-tick role totals: working set + private commit (Win32)'
  note = 'Median/p95 are computed over per-tick role totals, not sums of per-process medians. Extra core IDs are only admitted when the process is still mihomo.'
  roles = $roleSummary
}
$summary | ConvertTo-Json -Depth 7 | Set-Content -Path (Join-Path $OutputPath 'summary.json') -Encoding utf8
$summary.roles.GetEnumerator() | ForEach-Object {
  [pscustomobject]@{ role = $_.Key; samples = $_.Value.samples; working_median = $_.Value.working_median; working_p95 = $_.Value.working_p95; private_median = $_.Value.private_median; private_p95 = $_.Value.private_p95 }
} | Format-Table -AutoSize
Write-Output "CSV: $csvPath"
Write-Output "Summary: $(Join-Path $OutputPath 'summary.json')"
