@echo off
chcp 65001 >nul
rem 学習済みACTを、毎回ちがう配置で N 回走らせて成功率を測る(Gazebo起動・アームhomeのあとで)。
rem usage: eval_act.bat NAME [--n 10] [--seed 2000] [--block-th -90 -30] [--box-th 30 80] ...   例: eval_act.bat s1_region --n 3
call "%~dp0cexec.bat" eval_act.sh %*
echo Desktop\outbox の eval_act.txt と eval_*.mp4 を確認してください
pause
