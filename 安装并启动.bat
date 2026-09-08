@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Invoice Manager Installer

set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
if defined PYEXE goto deps

echo ==================================================
echo   发票管家 - 一键安装并启动
echo ==================================================
echo.
echo [1/4] 检测可用的 Python（自动跳过微软商店占位程序）...

call :detectpy
if errorlevel 1 goto winget
echo       使用 Python: %PYEXE%
goto venv

:winget
echo [1/4] 没有找到现成 Python，尝试用 winget 自动安装（约 2-5 分钟，无需管理员）...
where winget >nul 2>nul || goto nopython
winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto nopython
call :detectpy
if errorlevel 1 goto nopython
echo       使用 Python: %PYEXE%

:venv
echo.
echo [2/4] 创建独立运行环境 .venv（如被安全软件拦截请选择允许）...
%PYEXE% -m venv .venv
if errorlevel 1 goto venvfail
set "PYEXE=.venv\Scripts\python.exe"
goto deps

:venvfail
echo [注意] .venv 创建失败或残留不完整，已清理，改用 --user 模式（免管理员）重试 ...
rmdir /s /q .venv 2>nul
set "PIPARGS=--user"
set "MODE=user"
call :detectpy
if errorlevel 1 goto nopython

:deps
if "%MODE%"=="user" goto depcheck
if not "%PYEXE%"==".venv\Scripts\python.exe" goto depcheck
%PYEXE% -m pip --version >nul 2>nul
if errorlevel 1 goto venvfail
:depcheck
echo.
echo [3/4] 检查并安装依赖（优先清华镜像，失败回退官方源）...
%PYEXE% -m pip show pypdf >nul 2>nul
if errorlevel 1 goto installdeps
%PYEXE% -m pip show openpyxl >nul 2>nul
if errorlevel 1 goto installdeps
goto already
:installdeps
%PYEXE% -m pip install %PIPARGS% -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if not errorlevel 1 goto start
echo       清华镜像安装失败，改用官方源重试 ...
%PYEXE% -m pip install %PIPARGS% -r requirements.txt
if not errorlevel 1 goto start
goto pipfail

:already
echo       依赖已安装过，跳过安装。

:start
>python_path.txt echo %PYEXE%
rem kill previous server listening on port 8765
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>nul
timeout /t 1 >nul
echo.
echo [4/4] 启动发票管家 ...
echo       服务地址 http://127.0.0.1:8765 ，浏览器将自动打开。
start "" %PYEXE% app.py
echo 完成！本窗口可以关闭，以后启动请双击 启动发票管家.bat。
timeout /t 6 >nul
exit /b 0

:pipfail
echo.
echo [失败] 依赖安装未完成，一般是网络原因（两处镜像源都连不上）。
echo.
echo   关于代理：本脚本不会自动配置代理。如果您电脑需要代理才能上网：
echo     1. 打开 cmd，先执行下面两行（端口换成您自己的，如 7890）:
echo        set HTTP_PROXY=http://127.0.0.1:7890
echo        set HTTPS_PROXY=http://127.0.0.1:7890
echo     2. 在同一个 cmd 窗口里重新运行本脚本。
echo   如果不需要代理：请暂时关闭防火墙/安全软件，或换手机热点后再试。
echo.
pause
exit /b 1

:nopython
echo.
echo [失败] 没有找到可用的 Python（需要 3.8 或更高版本）。
echo.
echo   情况一：电脑上确实没有安装 Python
echo     请到 https://www.python.org/downloads/windows/ 下载安装，
echo     安装第一步务必勾选 "Add python.exe to PATH"，装完重新运行本脚本。
echo.
echo   情况二：装了 Python，但一运行就跳出微软商店
echo     这是商店占位程序在捣乱。打开 Windows 设置 ^> 应用 ^> 高级应用设置
echo     ^> 应用执行别名，把 python.exe 与 python3.exe 两个开关关掉，
echo     再重新运行本脚本（本脚本会自动找到真正的 Python）。
echo.
pause
exit /b 1

:detectpy
call :trycmd py -3
if errorlevel 1 call :trycmd python
if errorlevel 1 call :trypath "%LocalAppData%\Programs\Python\Python313\python.exe"
if errorlevel 1 call :trypath "%LocalAppData%\Programs\Python\Python312\python.exe"
if errorlevel 1 call :trypath "%LocalAppData%\Programs\Python\Python311\python.exe"
if errorlevel 1 call :trypath "%LocalAppData%\Programs\Python\Python310\python.exe"
if errorlevel 1 call :trypath "%ProgramFiles%\Python313\python.exe"
if errorlevel 1 call :trypath "%ProgramFiles%\Python312\python.exe"
if errorlevel 1 call :trypath "%ProgramFiles%\Python311\python.exe"
if errorlevel 1 call :trypath "%ProgramFiles%\Python310\python.exe"
if errorlevel 1 call :trypath "C:\Python313\python.exe"
if errorlevel 1 call :trypath "C:\Python312\python.exe"
if errorlevel 1 exit /b 1
exit /b 0

:trycmd
%* -c "import sys;sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul
if errorlevel 1 exit /b 1
set "PYEXE=%*"
exit /b 0

:trypath
if not exist %1 exit /b 1
%1 -c "import sys;sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul
if errorlevel 1 exit /b 1
set "PYEXE=%1"
exit /b 0
