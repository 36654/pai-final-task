@echo off
chcp 65001 >nul
rem see README.txt
rem usage: xfer_WRITE.bat in|out ckpt|data|lay
rem see README.txt
setlocal
if "%~3"=="" (echo usage: xfer_WRITE.bat in^|out ckpt^|data^|lay NAME & pause & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\xfer.ps1" -Here "%~dp0." -Dir "%~1" -Kind "%~2" -Name "%~3"
echo.
pause
exit /b 0
