@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  start "" ".venv\Scripts\python.exe" app.py
) else if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
  start "" "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" app.py
) else if exist "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe" (
  start "" "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe" app.py
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  start "" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" app.py
) else (
  where py >nul 2>nul && (start "" py -3 app.py) || (start "" python app.py)
)
