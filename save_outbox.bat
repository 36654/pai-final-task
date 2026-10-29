@echo off
rem save_outbox.bat NAME : move Desktop\outbox\* to Drive: PAI2026 Workspace\results\DATE_NAME  (ASCII only on purpose)
setlocal
if "%~1"=="" (echo usage: save_outbox.bat NAME & pause & exit /b 1)
if not exist "%USERPROFILE%\Desktop\outbox" (echo Desktop\outbox not found & pause & exit /b 1)
call "%~dp0drive_dir.bat" || (pause & exit /b 1)
for /f %%D in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%D"
set "DST=%DRIVE_SYNC%\results\%TODAY%_%~1"
mkdir "%DST%" 2>nul
move /Y "%USERPROFILE%\Desktop\outbox\*" "%DST%\" >nul
echo saved: %DST%
dir /b "%DST%"
pause
