@echo off
chcp 65001 >nul
rem 学習済みACTでロボットを動かす(Gazeboを起動してから)。止めるには Ctrl+C。例: infer_act.bat s1_region
call "%~dp0cexec.bat" infer_img.sh %*
pause
