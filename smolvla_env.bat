@echo off
chcp 65001 >nul
rem SmolVLA用の別環境を作って確認する(初回は10〜20分)。pai_training には触りません。
if not exist "%USERPROFILE%\Desktop\outbox" mkdir "%USERPROFILE%\Desktop\outbox"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv > "%USERPROFILE%\Desktop\outbox\host_gpu.txt" 2>&1
call "%~dp0cexec.bat" smolvla_env.sh
echo.
echo Desktop\outbox の smolvla_env.txt と host_gpu.txt を貼り付け(添付)してください
pause
