@echo off
chcp 936 >nul
cd /d "%~dp0"
echo ============================================
echo   安装本地识别组件（RapidOCR）
echo ============================================
echo.
echo 装好后，图片发票和扫描件可在自己电脑上识别，
echo 不需要 API Key，票据也不会上传到任何网站。
echo 大约需要下载 100MB 左右，请保持网络畅通。
echo.

if exist ".venv\Scripts\python.exe" goto venv
if exist "python_path.txt" goto pypath
goto syspy

:venv
set "PYCMD=.venv\Scripts\python.exe"
goto install

:pypath
set /p PYCMD=<python_path.txt
if not defined PYCMD goto syspy
goto install

:syspy
where py >nul 2>nul && (set "PYCMD=py -3") || (set "PYCMD=python")
goto install

:install
echo [1/2] 正在安装，请稍候（约 1-3 分钟）...
%PYCMD% -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple rapidocr-onnxruntime
if errorlevel 1 (
  echo.
  echo [重试] 清华源失败，改用官方源...
  %PYCMD% -m pip install rapidocr-onnxruntime
)
if errorlevel 1 goto fail

echo.
echo [2/2] 正在检查...
%PYCMD% -c "import app; print('OK' if app.local_ocr_ready() else 'NOT_READY')" > _ocr_check.txt 2>nul
set /p OCRCHK=<_ocr_check.txt
del _ocr_check.txt >nul 2>nul
if "%OCRCHK%"=="OK" goto ok
echo [!] 组件已安装但未能加载，请关闭本窗口后重新双击「启动发票管家.bat」。
goto end

:ok
echo.
echo ============================================
echo   安装完成！
echo   请重新双击「启动发票管家.bat」，
echo   界面上看到「本机 OCR 已就绪」即可使用。
echo ============================================
goto end

:fail
echo.
echo [失败] 安装未完成，请检查网络后重新双击本文件。
echo 不影响使用：未装时图片票仍可用 AI 识别（需配置 Key）。

:end
echo.
pause
