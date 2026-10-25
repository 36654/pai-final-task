@echo off
chcp 65001 >nul
rem usage: cexec.bat SCRIPT.sh [args]   e.g.  cexec.bat record_episode.sh bow_img
if "%~1"=="" (
  echo usage: cexec.bat SCRIPT.sh [args]
  goto :eof
)
docker cp "%~dp0tools" pai_ros2:/home/ubuntu/
rem 毎回、コンテナ内の outbox を空にしてから実行する(これをしないと、デスクトップ側で消した古いファイルが、コピーで復活する)
docker exec -u ubuntu pai_ros2 bash -c "mkdir -p /home/ubuntu/outbox && rm -rf /home/ubuntu/outbox/*"
docker exec -it -u ubuntu pai_ros2 bash /home/ubuntu/tools/%*
docker cp pai_ros2:/home/ubuntu/outbox "%USERPROFILE%\Desktop"
