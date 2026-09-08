@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Local Invoice Guardian Installer

echo ==================================================
echo   Local Invoice Guardian - 一键安装并启动
echo ==================================================
echo.

set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
if defined PYEXE goto deps

echo [1/4] 检测 Python ...
where py >nul 2>nul && set "PYEXE=py -3"
if defined PYEXE goto venv
where python >nul 2>nul && set "PYEXE=python"
if defined PYEXE goto venv

echo [1/4] 未检测到 Python，尝试用 winget 自动安装（约 1-3 分钟，免管理员）...
where winget >nul 2>nul || goto nopython
winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto nopython
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PYEXE%" goto venv
set "PYEXE=%ProgramFiles%\Python312\python.exe"
if exist "%PYEXE%" goto venv
where py >nul 2>nul && set "PYEXE=py -3"
if defined PYEXE goto venv
goto nopython

:venv
echo [2/4] 创建独立运行环境 .venv ...
if exist ".venv\Scripts\python.exe" goto deps
%PYEXE% -m venv .venv
if errorlevel 1 goto error
set "PYEXE=.venv\Scripts\python.exe"

:deps
set "PYEXE=.venv\Scripts\python.exe"
".venv\Scripts\python.exe" -m pip show pypdf >nul 2>nul && goto start
echo [3/4] 安装依赖（优先清华镜像，失败自动回退官方源）...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if not errorlevel 1 goto start
echo 镜像安装失败，改用官方源重试 ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
goto start

:start
echo [4/4] 启动发票管家，浏览器将自动打开 http://127.0.0.1:8765 ...
start "" ".venv\Scripts\python.exe" app.py
echo 完成。以后可直接双击 启动发票管家.bat。
exit /b 0

:error
echo.
echo [失败] 安装未完成。请检查网络或代理后重试；也可手动执行：
echo   python -m pip install -r requirements.txt
pause
exit /b 1

:nopython
echo.
echo [失败] 未找到 Python，且 winget 自动安装未成功。
echo 请到 https://www.python.org/downloads/windows/ 安装 Python 3.10 以上版本，
echo 安装时勾选 Add Python to PATH，然后重新运行本脚本。
pause
exit /b 1
