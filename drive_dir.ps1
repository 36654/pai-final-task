# Google Drive 同期フォルダを探して標準出力に1行で返す。見つけたパスは drive_path.txt に保存する。
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$save = Join-Path $here 'drive_path.txt'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
if (Test-Path -LiteralPath $save) {
  $p = (Get-Content -LiteralPath $save -Encoding UTF8 | Select-Object -First 1).Trim()
  if ($p -and (Test-Path -LiteralPath $p)) { Write-Output $p; exit 0 }
}
$mydrive = -join ([char[]](0x30DE,0x30A4,0x30C9,0x30E9,0x30A4,0x30D6))   # マイドライブ
$roots = @()
foreach ($d in (Get-PSDrive -PSProvider FileSystem)) {
  foreach ($n in @($mydrive, 'My Drive')) {
    $c = Join-Path $d.Root $n
    if (Test-Path -LiteralPath $c) { $roots += $c }
  }
}
foreach ($n in @('My Drive', $mydrive, 'Google Drive')) {
  $c = Join-Path $env:USERPROFILE $n
  if (Test-Path -LiteralPath $c) { $roots += $c }
}
$found = $null
foreach ($r in $roots) {
  $c = Join-Path $r 'PAI2026 Workspace'
  if (Test-Path -LiteralPath $c) { $found = $c; break }
}
if (-not $found -and $roots.Count -gt 0) {
  $found = Join-Path $roots[0] 'PAI2026 Workspace'
  New-Item -ItemType Directory -Force -Path $found | Out-Null
}
if (-not $found) { exit 1 }
Set-Content -LiteralPath $save -Value $found -Encoding UTF8
Write-Output $found
