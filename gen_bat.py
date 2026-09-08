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
    "rem kill previous server listening on port 8765",
    "for /f \"tokens=5\" %%a in ('netstat -ano ^| findstr \":8765\" ^| findstr \"LISTENING\"') do taskkill /f /pid %%a >nul 2>nul",
    "timeout /t 1 >nul",
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

# 升级脚本：UTF-8 无 BOM + chcp 65001，中文仅在 echo 文本
UPDATER = [
    "@echo off",
    "chcp 65001 >nul",
    'cd /d "%~dp0"',
    "title Invoice Manager Updater",
    "echo ============================================",
    "echo   发票管家 - 在线升级",
    "echo ============================================",
    "echo.",
    'set "PYEXE="',
    'if exist ".venv\\Scripts\\python.exe" set "PYEXE=.venv\\Scripts\\python.exe"',
    "if defined PYEXE goto run",
    'if exist "python_path.txt" set /p PYEXE=<python_path.txt',
    "if defined PYEXE goto run",
    'where py >nul 2>nul && set "PYEXE=py -3"',
    "if defined PYEXE goto run",
    'set "PYEXE=python"',
    ":run",
    "%PYEXE% update.py %1 %2",
    "if errorlevel 1 goto fail",
    "for /f \"tokens=5\" %%a in ('netstat -ano ^| findstr \":8765\" ^| findstr \"LISTENING\"') do taskkill /f /pid %%a >nul 2>nul",
    "timeout /t 1 >nul",
    'start "" %PYEXE% app.py',
    "echo.",
    "echo 升级完成，发票管家已重启，浏览器将自动打开。",
    "exit /b 0",
    "",
    ":fail",
    "echo.",
    "echo 升级未完成。若提示网络问题，可先设置代理再重试：",
    "echo   1. 打开 cmd 执行:  set HTTPS_PROXY=http://127.0.0.1:7890  （端口按实际填）",
    "echo   2. 在同一个 cmd 窗口里重新运行本升级脚本",
    "echo.",
    "pause",
    "exit /b 1",
    "",
]
upd = ("\r\n".join(UPDATER)).encode("utf-8")
assert not upd.startswith(b"\xef\xbb\xbf")
with open(APP / "升级发票管家.bat", "wb") as f:
    f.write(upd)
print("已生成: 升级发票管家.bat (UTF-8无BOM+CRLF)", len(upd), "bytes")
