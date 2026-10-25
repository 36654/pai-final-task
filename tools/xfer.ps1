# xfer.ps1 : ADD-ONLY transfer between Drive (PAI2026 Workspace) and the container pai_ros2.
# usage: xfer_WRITE.bat in|out ckpt|data|lay NAME
#   in  = Drive -> container      out = container -> Drive
# Never overwrites and never deletes. If the destination already exists:
#   identical (size + sha256 of model.safetensors) -> reports SAME and does nothing
#   different -> copies to NAME__from_drive_<stamp> / NAME__from_pc_<stamp> (both sides keep their own)
param([string]$Here, [string]$Dir, [string]$Kind, [string]$Name)
$ErrorActionPreference = 'Stop'
$user = $env:USERNAME
function Mask([string]$s) { if ($user) { return $s.Replace($user, '<user>') } else { return $s } }
function Fail([string]$m) { Write-Host ('STOP: ' + $m) -ForegroundColor Red; exit 1 }
$log = New-Object System.Collections.Generic.List[string]
function Say([string]$m) { Write-Host $m; $log.Add($m) }
function Save-Log {
  try {
    $od = Join-Path ([Environment]::GetFolderPath('Desktop')) 'outbox_ckpt'
    New-Item -ItemType Directory -Force -Path $od | Out-Null
    Set-Content -LiteralPath (Join-Path $od 'xfer_result.txt') -Value ($log | ForEach-Object { Mask $_ }) -Encoding UTF8
  } catch { }
}
if (-not $Dir -or -not $Kind -or -not $Name) { Write-Host 'usage: xfer_WRITE.bat in|out ckpt|data|lay NAME   (example: xfer_WRITE.bat in ckpt s1_region_act30k_1021)'; exit 1 }
if ($Dir -ne 'in' -and $Dir -ne 'out') { Fail 'first argument must be in or out' }
if ($Name -match '\.\.') { Fail 'NAME must not contain ..' }
$Here = $Here.TrimEnd('\')

# --- Drive root
$root = $null
$dp = Join-Path $Here 'drive_path.txt'
if (Test-Path -LiteralPath $dp) {
  $c = (Get-Content -LiteralPath $dp -Encoding UTF8 -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($c) { $c = $c.Trim() }
  if ($c -and (Test-Path -LiteralPath $c)) { $root = $c }
}
if (-not $root) {
  $md = -join ([char[]](0x30DE,0x30A4,0x30C9,0x30E9,0x30A4,0x30D6))
  foreach ($dr in (Get-PSDrive -PSProvider FileSystem)) {
    foreach ($nm in @('My Drive', $md)) {
      $cand = Join-Path (Join-Path $dr.Root $nm) 'PAI2026 Workspace'
      if (-not $root -and (Test-Path -LiteralPath $cand)) { $root = $cand }
    }
  }
}
if (-not $root) { Fail 'Drive workspace (PAI2026 Workspace) not found' }

# --- paths
$relW = $Name -replace '/', '\'
$relU = $Name -replace '\\', '/'
switch ($Kind) {
  'ckpt' { $dRel = 'checkpoints\train\' + $relW; $cPath = '/home/ubuntu/checkpoints/train/' + $relU }
  'data' { $dRel = 'lerobot_dataset\' + $relW;   $cPath = '/home/ubuntu/dataset/lerobot_dataset/' + $relU }
  'lay'  { $dRel = 'layouts\' + $relW;           $cPath = '/home/ubuntu/dataset/layouts/' + $relU }
  default { Fail 'second argument must be ckpt, data or lay' }
}
$dPath = Join-Path $root $dRel
$leaf = Split-Path -Leaf $dPath
$stamp = Get-Date -Format 'yyyyMMdd_HHmm'

# --- container helpers
$names = & docker ps --format '{{.Names}}' 2>$null
if (-not ($names -contains 'pai_ros2')) { Fail 'container pai_ros2 is not running (start Docker Desktop and the container)' }
function CExists([string]$p) { & docker exec pai_ros2 test -e $p; return ($LASTEXITCODE -eq 0) }
function CSize([string]$p) {
  $tpl = "find 'PATH' -type f -printf '%s\n' | awk '{s+=" + '$1' + "} END{print s+0}'"
  $o = & docker exec pai_ros2 bash -c ($tpl.Replace('PATH', $p))
  return [int64]("$o".Trim())
}
function CHash([string]$p) { $o = & docker exec pai_ros2 bash -c "if [ -f '$p/model.safetensors' ]; then sha256sum '$p/model.safetensors' | cut -c1-16; fi"; return "$o".Trim() }
function DSize([string]$p) { $s = (Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; if ($null -eq $s) { return [int64]0 } else { return [int64]$s } }
function DHash([string]$p) { $f = Join-Path $p 'model.safetensors'; if (Test-Path -LiteralPath $f) { return (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLower().Substring(0,16) } else { return '' } }

Say ('== xfer ' + $Dir + ' ' + $Kind + ' ' + $Name + ' (add-only) ==')
$tmpRoot = Join-Path $env:TEMP 'xfer'
if (Test-Path -LiteralPath $tmpRoot) { Remove-Item -LiteralPath $tmpRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
$tmp = Join-Path $tmpRoot $leaf

if ($Dir -eq 'in') {
  if (-not (Test-Path -LiteralPath $dPath)) { Fail ('not found on Drive: ' + $dRel + ' (Drive sync may not be finished)') }
  $srcSize = DSize $dPath; $srcHash = DHash $dPath
  Say ('  source (Drive): ' + $dRel + '  size=' + $srcSize + '  sha16=' + $(if ($srcHash) { $srcHash } else { '(none)' }))
  $target = $cPath
  if (CExists $cPath) {
    $dstSize = CSize $cPath; $dstHash = CHash $cPath
    if ($dstSize -eq $srcSize -and $dstHash -eq $srcHash) { Say '  SAME: the container already has an identical copy. Nothing to do.'; Say 'RESULT=OK'; Save-Log; exit 0 }
    $target = $cPath + '__from_drive_' + $stamp
    Say ('  container already has a DIFFERENT ' + $cPath + ' (size=' + $dstSize + ' sha16=' + $dstHash + '). It is kept. Copying as: ' + $target)
  }
  Say '  [1/3] Drive -> local temp'
  & robocopy $dPath $tmp /E /R:10 /W:10 /NP /NJH /NJS | Out-Null
  if ($LASTEXITCODE -ge 8) { Fail 'robocopy failed' }
  if ((DSize $tmp) -ne $srcSize) { Fail ('local copy size mismatch (' + (DSize $tmp) + ' vs ' + $srcSize + '). Drive may still be downloading; run again later') }
  Say '  [2/3] local temp -> container'
  $parent = $target.Substring(0, $target.LastIndexOf('/'))
  & docker exec -u ubuntu pai_ros2 mkdir -p $parent
  & docker cp $tmp ("pai_ros2:" + $target)
  if ($LASTEXITCODE -ne 0) { Fail 'docker cp failed' }
  & docker exec -u root pai_ros2 chown -R ubuntu:ubuntu $target
  Say '  [3/3] verify inside the container'
  $vs = CSize $target; $vh = CHash $target
  Say ('  container: ' + $target + '  size=' + $vs + '  sha16=' + $(if ($vh) { $vh } else { '(none)' }))
  if ($vs -ne $srcSize -or $vh -ne $srcHash) { Say 'RESULT=MISMATCH'; Save-Log; Fail 'verification mismatch' }
} else {
  $src = $cPath
  if ($Kind -eq 'lay') {
    & docker exec pai_ros2 bash -c "rm -rf /tmp/xl; mkdir -p /tmp/xl; cp /home/ubuntu/dataset/expert_npz/'$relU'/*.json /tmp/xl/ 2>/dev/null; ls /tmp/xl | wc -l"
    $src = '/tmp/xl'
  }
  if (-not (CExists $src)) { Fail ('not found in the container: ' + $src) }
  $srcSize = CSize $src; $srcHash = CHash $src
  Say ('  source (container): ' + $src + '  size=' + $srcSize + '  sha16=' + $(if ($srcHash) { $srcHash } else { '(none)' }))
  if ($srcSize -le 0) { Fail 'the source is empty' }
  $target = $dPath
  if (Test-Path -LiteralPath $dPath) {
    $dstSize = DSize $dPath; $dstHash = DHash $dPath
    if ($dstSize -eq $srcSize -and $dstHash -eq $srcHash) { Say '  SAME: Drive already has an identical copy. Nothing to do.'; Say 'RESULT=OK'; Save-Log; exit 0 }
    $target = $dPath + '__from_pc_' + $stamp
    Say ('  Drive already has a DIFFERENT ' + $dRel + ' (size=' + $dstSize + ' sha16=' + $dstHash + '). It is kept. Copying as: ' + (Split-Path -Leaf $target))
  }
  Say '  [1/3] container -> local temp'
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  & docker cp ("pai_ros2:" + $src + "/.") $tmp
  if ($LASTEXITCODE -ne 0) { Fail 'docker cp failed' }
  if ((DSize $tmp) -ne $srcSize) { Fail ('local copy size mismatch (' + (DSize $tmp) + ' vs ' + $srcSize + ')') }
  Say '  [2/3] local temp -> Drive'
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
  & robocopy $tmp $target /E /R:10 /W:10 /NP /NJH /NJS | Out-Null
  if ($LASTEXITCODE -ge 8) { Fail 'robocopy failed' }
  Say '  [3/3] verify on Drive (size; Drive may need a moment to finish syncing)'
  $vs = DSize $target; $vh = DHash $target
  Say ('  Drive: ' + (Split-Path -Leaf $target) + '  size=' + $vs + '  sha16=' + $(if ($vh) { $vh } else { '(none)' }))
  if ($vs -ne $srcSize -or $vh -ne $srcHash) { Say 'RESULT=MISMATCH'; Save-Log; Fail 'verification mismatch' }
}
Remove-Item -LiteralPath $tmpRoot -Recurse -Force -ErrorAction SilentlyContinue
Say 'RESULT=OK  (nothing was overwritten or deleted)'
Save-Log
