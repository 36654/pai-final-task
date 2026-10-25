@echo off
chcp 65001 >nul
rem 既存のデモから、範囲内の成功件だけを新しい名前にコピーする。例: pick_region.bat s1_train s1_region --skip 103
call "%~dp0cexec.bat" pick_region.sh %*
echo.
echo Desktop\outbox の pick_region.txt の中身を送ってください
pause
