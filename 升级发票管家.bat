@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Invoice Manager Updater
echo ============================================
echo   发票管家 - 在线升级
echo ============================================
echo.
set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
if defined PYEXE goto run
if exist "python_path.txt" set /p PYEXE=<python_path.txt
if defined PYEXE goto run
where py >nul 2>nul && set "PYEXE=py -3"
if defined PYEXE goto run
set "PYEXE=python"
:run
%PYEXE% update.py %1 %2
if errorlevel 1 goto fail
echo 正在检查升级后的依赖...
%PYEXE% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 %PYEXE% -m pip install -r requirements.txt
if errorlevel 1 goto fail
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_server.ps1"
if errorlevel 1 goto portbusy
ping -n 2 127.0.0.1 >nul
start "" %PYEXE% app.py
echo.
echo 升级完成，发票管家已重启，浏览器将自动打开。
exit /b 0

:fail
echo.
echo 升级未完成。若提示网络问题，可先设置代理再重试：
echo   1. 打开 cmd 执行:  set HTTPS_PROXY=http://127.0.0.1:7890  （端口按实际填）
echo   2. 在同一个 cmd 窗口里重新运行本升级脚本
echo.
pause
exit /b 1

:portbusy
echo.
echo 代码已更新，但端口 8765 被其他程序占用，未结束该程序。请关闭占用程序后双击“启动发票管家.bat”。
pause
exit /b 1
