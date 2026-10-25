@echo off
chcp 65001 >nul
rem 指の摩擦がGazeboに反映されているかを確かめる(Gazebo起動中に実行)。何も変更しない
call "%~dp0cexec.bat" env_check.sh %*
echo.
echo Desktop\outbox の env_check.txt を貼り付けてください
pause
