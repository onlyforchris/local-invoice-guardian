@echo off
chcp 936 >nul
cd /d "%~dp0"
rem only stop a confirmed Invoice Manager; never kill an unrelated service on 8765
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_server.ps1"
if errorlevel 1 goto portbusy
ping -n 2 127.0.0.1 >nul
if exist ".venv\Scripts\python.exe" goto venv
if not exist "python_path.txt" goto chain
set /p PYCMD=<python_path.txt
if not defined PYCMD goto chain
start "" %PYCMD% app.py
exit /b 0

:venv
start "" ".venv\Scripts\python.exe" app.py
exit /b 0

:chain
if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" goto wb1
if exist "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe" goto wb2
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" goto py312
where py >nul 2>nul && (start "" py -3 app.py) || (start "" python app.py)
exit /b 0

:wb1
start "" "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" app.py
exit /b 0

:wb2
start "" "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe" app.py
exit /b 0

:py312
start "" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" app.py
exit /b 0

:portbusy
echo [失败] 端口 8765 已被其他程序占用，未结束该程序。请先关闭占用程序后重试。
pause
exit /b 1
