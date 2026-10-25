@echo off
chcp 65001 >nul
rem Google Drive の同期フォルダを自動検出して drive_path.txt に保存する(sync_in / sync_out が呼ぶ)
rem 検出し直したいとき: drive_dir.bat reset    手動指定: drive_path.txt の1行目を書き換える
if /i "%~1"=="reset" del "%~dp0drive_path.txt" 2>nul
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0drive_dir.ps1"`) do set "DRIVE_SYNC=%%P"
if "%DRIVE_SYNC%"=="" (
  echo Google Drive の同期フォルダが見つかりません。Google Drive for desktop をインストールしてログインするか、
  echo drive_path.txt に同期先フォルダのフルパスを1行で書いてください。
  exit /b 1
)
echo Google Drive 同期フォルダ: %DRIVE_SYNC%
exit /b 0
