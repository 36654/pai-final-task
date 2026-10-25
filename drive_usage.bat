@echo off
chcp 65001 >nul
rem PAI2026 Workspace の中で、どのフォルダが容量を使っているかを大きい順に出す(読むだけ。何も消さない)
setlocal
call "%~dp0drive_dir.bat" || (pause & exit /b 1)
set "ROOT=%DRIVE_SYNC%"
echo 対象: %ROOT%
echo 集計中(ファイルが多いと1〜2分かかる)...
powershell -NoProfile -Command "$r='%ROOT%'; $rows=@(); foreach($d in Get-ChildItem -LiteralPath $r -Directory){ foreach($e in @($d) + @(Get-ChildItem -LiteralPath $d.FullName -Directory -ErrorAction SilentlyContinue)){ $s=(Get-ChildItem -LiteralPath $e.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; $rows += [pscustomobject]@{GB=[math]::Round($s/1GB,2); Path=$e.FullName.Substring($r.Length)} } }; $files=(Get-ChildItem -LiteralPath $r -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; $rows | Sort-Object GB -Descending | Select-Object -First 40 | Format-Table -AutoSize; $t=(Get-ChildItem -LiteralPath $r -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; Write-Host ('合計: ' + [math]::Round($t/1GB,2) + ' GB')"
pause
