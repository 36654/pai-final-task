@echo off
chcp 65001 >nul
rem stage2_eval.bat act : stage 2 conditions C,A,B with the stage-2 ACT (names.conf S2_ACT30K; result s2_act2_*.txt).  stage2_eval.bat vla URL TOKEN : with the stage-2 SmolVLA.  Run after Gazebo is up (arm at home).
call "%~dp0cexec.bat" stage2_eval.sh %*
pause
