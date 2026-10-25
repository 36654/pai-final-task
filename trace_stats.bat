@echo off
chcp 65001 >nul
rem eval_act が記録した指令を専門家のデモと比べる(Gazebo不要)。usage: trace_stats.bat [評価名]
call "%~dp0cexec.bat" trace_stats.sh %*
echo Desktop\outbox の trace_stats.txt を貼り付けてください
pause
