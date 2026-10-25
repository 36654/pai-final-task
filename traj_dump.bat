@echo off
chcp 65001 >nul
rem traj_dump.bat - prints command/joint time series of the last ACT evaluations (and the expert demos for replay runs). Changes nothing. Gazebo not needed.
setlocal
if not exist "%~dp0cexec.bat" (echo Put this file in the pai_tools folder, next to cexec.bat & pause & exit /b 1)
docker start pai_ros2 >nul 2>&1
if errorlevel 1 (echo Docker Desktop is not running & pause & exit /b 1)
docker cp "%~dp0tools" pai_ros2:/home/ubuntu/
docker exec -u ubuntu pai_ros2 bash -c "mkdir -p /home/ubuntu/outbox && rm -f /home/ubuntu/outbox/traj_dump.txt"
docker exec -it -u ubuntu pai_ros2 bash /home/ubuntu/tools/traj_dump.sh %*
if not exist "%USERPROFILE%\Desktop\outbox_ckpt" mkdir "%USERPROFILE%\Desktop\outbox_ckpt"
docker cp pai_ros2:/home/ubuntu/outbox/traj_dump.txt "%USERPROFILE%\Desktop\outbox_ckpt\traj_dump.txt"
echo.
echo Done. Do not select text in this window while it runs. Paste the screen text above (or Desktop\outbox_ckpt\traj_dump.txt).
pause
exit /b 0
