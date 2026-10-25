@echo off
chcp 65001 >nul
rem Gazeboをいつもの方法で起動し、アームがhomeの状態で実行。専門家のデモを生成して記録する。例: expert_episode.bat 3 --name test (3件で約2分)
call "%~dp0cexec.bat" expert_episode.sh %*
echo.
echo Desktop\outbox の expert_episode.txt と episodes_preview.png を送ってください
pause
