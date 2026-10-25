@echo off
chcp 65001 >nul
rem see README.txt
rem see README.txt
setlocal
docker version >nul 2>&1 || (echo Start Docker Desktop, then run again & pause & exit /b 1)

docker container inspect pai_ros2 >nul 2>&1
if errorlevel 1 (
  echo [1/4] Creating the container (first time only, image download takes a while)
  set "WS=%~dp0"
  docker run -d --name pai_ros2 -p 6080:80 --shm-size=512m -p 9090:9090 -p 9876:9876 -v "%~dp0.:/workspace" airobotbook/ros2-desktop-ai-robot-book-humble:latest
) else (
  echo [1/4] Container already exists. Starting it
  docker start pai_ros2
)
timeout /t 8 /nobreak >nul

echo [2/4] Copying the tools
docker cp "%~dp0tools" pai_ros2:/home/ubuntu/
docker exec -u root pai_ros2 chown -R ubuntu:ubuntu /home/ubuntu/tools
docker exec -u ubuntu pai_ros2 mkdir -p /home/ubuntu/outbox /home/ubuntu/dataset /home/ubuntu/checkpoints

echo [3/4] Adding the cameras to the Gazebo world (safe if already added)
docker exec -u ubuntu pai_ros2 bash /home/ubuntu/tools/set_camera.sh 0.15 0 1.55

echo [3b] Raising the finger friction (safe if already done)
docker exec -u ubuntu pai_ros2 bash /home/ubuntu/tools/finger_friction.sh 1.5

echo [4/4] Checking the training environment
docker exec -u ubuntu pai_ros2 bash -c "ls -d /home/ubuntu/pai_training && /home/ubuntu/.pixi/bin/pixi --version"
echo.
echo Done. To import data: xfer_WRITE.bat in ckpt NAME (see README).
echo Browser desktop: http://localhost:6080
pause
