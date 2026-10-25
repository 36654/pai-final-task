@echo off
chcp 65001 >nul
docker cp "%~dp0tools" pai_ros2:/home/ubuntu/
docker exec -u ubuntu pai_ros2 bash /home/ubuntu/tools/grab.sh
docker cp pai_ros2:/home/ubuntu/cam.png "%USERPROFILE%\Desktop\cam.png"
docker cp pai_ros2:/home/ubuntu/cam_side.png "%USERPROFILE%\Desktop\cam_side.png"
echo.
echo Desktop の cam.png(天井)と cam_side.png(動画用の斜めカメラ)を送ってください。届かないときは Gazebo とロボットを起動し直してください。
pause
