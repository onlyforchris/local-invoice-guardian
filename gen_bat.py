# -*- coding: utf-8 -*-
"""生成可移动的 Windows 双击启动脚本（GBK+CRLF，纯 ASCII）。

启动顺序：
1. .venv 存在 → 直接用；
2. python_path.txt 存在（安装脚本写入的检测结果）→ 用它；
3. 兜底：本机 WorkBuddy Python → Python312 常见路径 → py -3 → python。
"""
from pathlib import Path

APP = Path(__file__).resolve().parent
lines = [
    "@echo off",
    "chcp 65001 >nul",
    'cd /d "%~dp0"',
    'if exist ".venv\\Scripts\\python.exe" goto venv',
    'if not exist "python_path.txt" goto chain',
    "set /p PYCMD=<python_path.txt",
    "if not defined PYCMD goto chain",
    'start "" %PYCMD% app.py',
    "exit /b 0",
    "",
    ":venv",
    'start "" ".venv\\Scripts\\python.exe" app.py',
    "exit /b 0",
    "",
    ":chain",
    'if exist "%USERPROFILE%\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe" goto wb1',
    'if exist "%USERPROFILE%\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\python.exe" goto wb2',
    'if exist "%LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe" goto py312',
    'where py >nul 2>nul && (start "" py -3 app.py) || (start "" python app.py)',
    "exit /b 0",
    "",
    ":wb1",
    'start "" "%USERPROFILE%\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe" app.py',
    "exit /b 0",
    "",
    ":wb2",
    'start "" "%USERPROFILE%\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\python.exe" app.py',
    "exit /b 0",
    "",
    ":py312",
    'start "" "%LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe" app.py',
    "exit /b 0",
    "",
]
content = "\r\n".join(lines)
with open(APP / "启动发票管家.bat", "wb") as f:
    f.write(content.encode("gbk"))
print("已生成: 启动发票管家.bat (GBK+CRLF)", len(content), "chars")
