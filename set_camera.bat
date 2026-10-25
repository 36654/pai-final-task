@echo off
chcp 65001 >nul
rem usage: set_camera.bat X Y Z   (example: set_camera.bat 0.15 0 1.55)
docker cp "%~dp0tools" pai_ros2:/home/ubuntu/
docker exec -u ubuntu pai_ros2 bash /home/ubuntu/tools/set_camera.sh %*
echo.
echo Restart Gazebo to apply.
pause
