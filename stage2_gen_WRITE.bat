@echo off
chcp 65001 >nul
rem usage: stage2_gen_WRITE.bat [N | convert | pair | pairconvert | mix | mixconvert]
rem stage2_gen_WRITE.bat : stage-2 demos -> LeRobot dataset -> Drive. Run after Gazebo is up (arm at home) for generation modes (none / N / pair).
rem   (none)/N : S2DATA, about 2.6 hours.  pair : S2PAIR (swapped-target demos added), about 2.4 hours.  mix : S2MIX (S2PAIR + stage-1 single-block demos, links only), no Gazebo, about 10 minutes.
rem   convert / pairconvert / mixconvert : demos already exist, only convert + upload.
rem Names come from tools\names.conf. Never overwrites: stops if the dataset already exists. Generation stops by itself if the first 10 demos succeed less than 70 percent.
setlocal
set "KEY=S2DATA"
if /i "%~1"=="pair" set "KEY=S2PAIR"
if /i "%~1"=="pairconvert" set "KEY=S2PAIR"
if /i "%~1"=="mix" set "KEY=S2MIX"
if /i "%~1"=="mixconvert" set "KEY=S2MIX"
set "DSNAME="
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b "%KEY%=" "%~dp0tools\names.conf"`) do set "DSNAME=%%B"
if "%DSNAME%"=="" (echo %KEY% not found in tools\names.conf & pause & exit /b 1)
echo Dataset name: %DSNAME%
rem the dataset folder must be writable by the container user (a past copy made it root-owned)
docker exec -u root pai_ros2 chown -R ubuntu:ubuntu /home/ubuntu/dataset
del "%USERPROFILE%\Desktop\outbox\stage2_gen.txt" 2>nul
call "%~dp0cexec.bat" stage2_gen.sh %*
findstr /c:"RESULT=OK" "%USERPROFILE%\Desktop\outbox\stage2_gen.txt" >nul
if errorlevel 1 (echo.& echo Generation or conversion did NOT finish OK. See Desktop\outbox\stage2_gen.txt and stage2_gen_expert.txt. Nothing was uploaded.& pause & exit /b 1)
echo.
echo Conversion OK. Uploading the dataset to Drive (add-only). Type YES when asked.
call "%~dp0xfer_WRITE.bat" out data %DSNAME%
exit /b 0
