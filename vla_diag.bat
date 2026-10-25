@echo off
rem vla_diag.bat URL TOKEN : SmolVLA diagnosis (no Gazebo, changes nothing, about 5 minutes). Result: Desktop\outbox\vla_diag.txt
call "%~dp0cexec.bat" vla_diag.sh %*
