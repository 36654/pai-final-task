@echo off
chcp 65001 >nul
rem video_WRITE.bat : builds the submission movie from video_plan.txt (clips from Drive results, side by side, captions, 2x speed as written in the plan).
rem Output: Desktop\outbox\PAI_movie_<date_time>.mp4 (a new file every time, nothing is overwritten). Originals are never changed.
rem The course opening / ending jingles go in the assets folder (next to this file); video_plan.txt refers to them with jingle|*OP.mp4 and jingle|*ED.mp4.
rem Edit video_plan.txt to change clips / captions, then run this file again. Needs the container (pai_ros2) running. No Gazebo needed.
setlocal
set "HERE=%~dp0"
set "DP=%HERE%drive_path.txt"
if not exist "%DP%" (echo drive_path.txt not found. Run drive_dir.bat first. & pause & exit /b 1)
if not exist "%HERE%video_plan.txt" (echo video_plan.txt not found next to this file. & pause & exit /b 1)
if not exist "%USERPROFILE%\Desktop\outbox" mkdir "%USERPROFILE%\Desktop\outbox"
set "WORK=%TEMP%\vid_in"
set "RES="
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "$r=(Get-Content -LiteralPath '%DP%' -TotalCount 1).Trim(); $x=Join-Path $r 'results'; if(Test-Path -LiteralPath $x){$x}else{$r}"`) do set "RES=%%A"
echo Results folder found.
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%tools\video_prep.ps1" -Plan "%HERE%video_plan.txt" -ResDir "%RES%" -Work "%WORK%" -Assets "%HERE%assets"
if errorlevel 1 (echo. & echo Preparation failed. Nothing was built. & pause & exit /b 1)
docker exec -u root pai_ros2 rm -rf /home/ubuntu/vid_in
docker cp "%WORK%\." pai_ros2:/home/ubuntu/vid_in
if errorlevel 1 (echo docker cp failed. Is the container running? & pause & exit /b 1)
docker cp "%HERE%tools\video_build.py" pai_ros2:/home/ubuntu/vid_in/video_build.py
echo Building (about 1 to 3 minutes) ...
docker exec -u root pai_ros2 python3 /home/ubuntu/vid_in/video_build.py /home/ubuntu/vid_in /home/ubuntu/vid_in/final.mp4 > "%USERPROFILE%\Desktop\outbox\video_build.txt" 2>&1
type "%USERPROFILE%\Desktop\outbox\video_build.txt"
findstr /c:"RESULT=" "%USERPROFILE%\Desktop\outbox\video_build.txt" >nul
if errorlevel 1 (echo. & echo Build did NOT finish. See Desktop\outbox\video_build.txt. & pause & exit /b 1)
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"`) do set "STAMP=%%T"
set "OUTF=%USERPROFILE%\Desktop\outbox\PAI_movie_%STAMP%.mp4"
docker cp pai_ros2:/home/ubuntu/vid_in/final.mp4 "%OUTF%"
if errorlevel 1 (echo copy of the result failed & pause & exit /b 1)
echo.
echo Output: %OUTF%
echo Watch it once from start to end before uploading (check the length and that no user name appears on screen).
pause
exit /b 0
