@echo off
chcp 65001 >nul
rem Desktop\outbox の中身を、Drive の PAI2026 Workspace\results\日付_名前 へ移す(次の実行で上書きされないように)。
rem usage: save_outbox.bat 名前     例: save_outbox.bat eval_base_prefix
setlocal
if "%~1"=="" (echo usage: save_outbox.bat 名前 & pause & exit /b 1)
if not exist "%USERPROFILE%\Desktop\outbox" (echo Desktop\outbox がありません & pause & exit /b 1)
call "%~dp0drive_dir.bat" || (pause & exit /b 1)
for /f %%D in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%D"
set "DST=%DRIVE_SYNC%\results\%TODAY%_%~1"
mkdir "%DST%" 2>nul
move /Y "%USERPROFILE%\Desktop\outbox\*" "%DST%\" >nul
echo 保存しました: %DST%
dir /b "%DST%"
pause
