@echo off
chcp 65001 >nul
rem ロボットの摩擦係数(元は0.2)を書き換える。例: finger_friction.bat 1.5   元に戻す: finger_friction.bat --restore
rem 反映するには、Gazeboとロボットをいつもの方法で起動し直す。Gazeboは動いていなくてもよい。
call "%~dp0cexec.bat" finger_friction.sh %*
echo.
echo 反映するには、Gazeboとロボットを起動し直してください
pause
