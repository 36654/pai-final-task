# video_prep.ps1 : video_WRITE.bat helper. Reads video_plan.txt, copies the needed clips from Drive results to a work folder
# (originals are never changed), and writes plan.txt for video_build.py.
param([string]$Plan, [string]$ResDir, [string]$Work, [string]$Assets)
$ErrorActionPreference = 'Stop'
$sep = [string][IO.Path]::DirectorySeparatorChar
if (-not (Test-Path -LiteralPath $Plan)) { Write-Host ('STOP: plan not found: ' + $Plan); exit 1 }
if (-not (Test-Path -LiteralPath $ResDir)) { Write-Host ('STOP: results folder not found: ' + $ResDir); exit 1 }
if (Test-Path -LiteralPath $Work) { Remove-Item -LiteralPath $Work -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Work | Out-Null
$out = New-Object System.Collections.Generic.List[string]
$n = 0; $miss = 0; $j = 0; $im = 0
foreach ($l in (Get-Content -LiteralPath $Plan -Encoding UTF8)) {
  $t = $l.Trim()
  if ($t -eq '' -or $t.StartsWith('#')) { continue }
  $p = $t.Split('|') | ForEach-Object { $_.Trim() }
  if ($p[0] -eq 'card' -or $p[0] -eq 'diagram') { $out.Add($t); continue }
  if ($p[0] -eq 'image') {
    $f = Join-Path (Join-Path $Assets 'slides') $p[2]
    if (-not (Test-Path -LiteralPath $f)) { Write-Host ('STOP: slide not found: ' + $f); exit 1 }
    $im++; $iid = '{0:D2}' -f $im
    Copy-Item -LiteralPath $f -Destination (Join-Path $Work ('image' + $iid + '.png'))
    $out.Add('image|' + $p[1] + '|' + $iid); continue
  }
  if ($p[0] -eq 'jingle') {
    $m = @(Get-ChildItem -LiteralPath $Assets -Filter $p[1] -ErrorAction SilentlyContinue)
    if ($m.Count -ne 1) { Write-Host ('STOP: jingle file "' + $p[1] + '" must match exactly one file in ' + $Assets + ' (found ' + $m.Count + ')'); exit 1 }
    $j++; $jid = '{0:D2}' -f $j
    Copy-Item -LiteralPath $m[0].FullName -Destination (Join-Path $Work ('jingle' + $jid + '.mp4'))
    $out.Add('jingle|' + $jid); continue
  }
  if ($p[0] -ne 'clip' -or $p.Count -lt 6) { Write-Host ('STOP: cannot read this plan line: ' + $t); exit 1 }
  $n++; $id = '{0:D2}' -f $n
  foreach ($v in @('front', 'overhead')) {
    $src = Join-Path (Join-Path $ResDir $p[1]) ($p[2] + '_' + $v + '.mp4')
    if (-not (Test-Path -LiteralPath $src)) { Write-Host ('MISSING: ' + $src.Substring($ResDir.Length).TrimStart($sep)); $miss++; continue }
    Copy-Item -LiteralPath $src -Destination (Join-Path $Work ('clip' + $id + '_' + $v + '.mp4'))
  }
  $out.Add(('clip|{0}|{1}|{2}|{3}' -f $id, $p[3], $p[4], $p[5]))
}
if ($miss -gt 0) { Write-Host ('STOP: ' + $miss + ' clip file(s) missing'); exit 1 }
[IO.File]::WriteAllLines((Join-Path $Work 'plan.txt'), $out, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ('prepared: ' + $n + ' clips')
exit 0
