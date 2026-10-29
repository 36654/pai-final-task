@echo off
rem act_close.bat [name-pattern] : where the ACT closed its gripper in stage 2A/2B (target / other block / midpoint). No Gazebo, changes nothing. Result: Desktop\outbox\act_close.txt
call "%~dp0cexec.bat" act_close.sh %*
pause
