@echo off
chcp 65001 >nul
rem see README.txt
rem usage: smolvla_all.bat URL TOKEN [fresh]
rem see README.txt
setlocal
if not exist "%~dp0cexec.bat" (echo Put this file in the pai_tools folder, next to cexec.bat & pause & exit /b 1)
rem see README.txt
docker start pai_ros2 >nul 2>&1
if errorlevel 1 (echo Docker Desktop is not running. Start it, wait until it is green, then run again & pause & exit /b 1)
rem see README.txt
docker exec pai_ros2 pgrep -f "[g]rid_all.sh" >nul 2>&1
if not errorlevel 1 (echo Another measurement (grid_all) is running. Run again after it finishes & pause & exit /b 1)
docker exec pai_ros2 pgrep -f "[e]val_act.py|[e]xpert_episode.py" >nul 2>&1
if not errorlevel 1 (echo Another evaluation (eval_act) is running. Run again after it finishes & pause & exit /b 1)
rem see README.txt
if exist "%USERPROFILE%\Desktop\outbox" powershell -NoProfile -Command "$d=Join-Path $env:USERPROFILE 'Desktop\outbox_old'; New-Item -ItemType Directory -Force $d | Out-Null; Move-Item -LiteralPath (Join-Path $env:USERPROFILE 'Desktop\outbox') -Destination (Join-Path $d (Get-Date -Format yyyyMMdd_HHmmss))"
docker cp "%~dp0tools" pai_ros2:/home/ubuntu/
docker exec -u ubuntu pai_ros2 bash -c "mkdir -p /home/ubuntu/outbox"
docker exec -it -u ubuntu pai_ros2 bash /home/ubuntu/tools/smolvla_all.sh %*
docker cp pai_ros2:/home/ubuntu/outbox "%USERPROFILE%\Desktop"
echo.
echo Done. Files in Desktop\outbox: smolvla_1_main20.txt smolvla_2_grid.txt smolvla_3_expert20.txt smolvla_4_grid_report.txt smolvla_5_trace_stats.txt
pause
exit /b 0
