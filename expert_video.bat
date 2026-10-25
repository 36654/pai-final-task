@echo off
chcp 65001 >nul
rem 記録済みの専門家デモ(npz)から確認用の動画を作る。Gazeboは不要。例: expert_video.bat test 4 2   (名前 件数 倍速)
call "%~dp0cexec.bat" expert_video.sh %*
echo.
echo Desktop\outbox の 名前_demo.mp4 を見てください
pause
