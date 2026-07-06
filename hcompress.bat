@echo off
setlocal

:: ============================================================
::  hcompress.bat — Canonical Huffman 压缩 / 解压 命令行入口
:: ============================================================
::  用法:
::    hcompress.bat c <file> [-o out] [--level 0-9] [-f]
::    hcompress.bat d <file> [-o out] [-f]
::    hcompress.bat info <file>
::    hcompress.bat bench <file> [-n N]
::    hcompress.bat gui                      → 启动图形界面
::
::  拖文件到这个 bat 上 → 自动压缩 (.hcf 自动解压)
:: ============================================================

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

:: 无参数 → 显示帮助
if "%~1"=="" (
    echo.
    echo     hcompress  v0.1.0
    echo     Canonical Huffman Compression Tool
    echo.
    echo   用法：
    echo     hcompress c ^<file^> [-o out] [--level 0-9] [-f]     压缩
    echo     hcompress d ^<file^> [-o out] [-f]                    解压
    echo     hcompress info ^<file^>                                文件信息
    echo     hcompress bench ^<file^> [-n N]                       性能测试
    echo     hcompress gui                                         图形界面
    echo.
    echo   直接把文件拖到这个 bat 图标上 → 自动处理
    echo.
    pause
    goto :eof
)

:: 拖入文件自动检测：argv[1] 是文件路径且不是命令
set "ARG=%~1"
if /i "%ARG%"=="c"    goto :run_cli
if /i "%ARG%"=="d"    goto :run_cli
if /i "%ARG%"=="info" goto :run_cli
if /i "%ARG%"=="bench" goto :run_cli
if /i "%ARG%"=="gui"  goto :run_gui

:: 不是命令 → 当作文件拖入
if /i "%~x1"==".hcf" (
    echo [hcompress] .hcf 文件拖入 → 自动解压...
    python -m hcompress d "%~1" -f
) else (
    echo [hcompress] 文件拖入 → 自动压缩...
    python -m hcompress c "%~1" -f
)
echo.
echo 按任意键关闭...
pause >nul
goto :eof

:run_gui
start "" python -m hcompress gui
goto :eof

:run_cli
python -m hcompress %*
if not defined SESSIONNAME pause >nul
goto :eof
