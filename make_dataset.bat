@echo off
chcp 65001 >nul
rem expert_episode が作った npz を LeRobot 形式に変換する。例: make_dataset.bat test "put the red block in the box"
call "%~dp0cexec.bat" make_dataset.sh %*
pause
