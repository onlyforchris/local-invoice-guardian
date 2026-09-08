@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 正在创建本地运行环境...
  where py >nul 2>nul && (py -3 -m venv .venv) || (
    where python >nul 2>nul && (python -m venv .venv) || goto :missing
  )
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)
start "" ".venv\Scripts\python.exe" app.py
exit /b 0
:missing
echo 未找到 Python，请先安装 Python 3.10 或更高版本，并勾选 Add Python to PATH。
pause
exit /b 1
:error
echo 安装失败，请检查网络和 Python 安装。
pause
exit /b 1
