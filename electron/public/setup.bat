@echo off
:: hcompress v2 — 一键安装脚本
:: 解压便携包后双击此文件，自动创建桌面快捷方式

cd /d "%~dp0"

echo.
echo   hcompress v2 安装
echo   ─────────────────
echo.

:: 创建桌面快捷方式
set "TARGET=%~dp0hcompress.exe"
set "ICON=%~dp0hcompress.ico"
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\hcompress.lnk"

if not exist "%TARGET%" (
    echo [错误] 未找到 hcompress.exe，请将本脚本放在程序目录下运行。
    pause
    exit /b 1
)

powershell -Command "^
$ws = New-Object -ComObject WScript.Shell;^
$sc = $ws.CreateShortcut('%SHORTCUT%');^
$sc.TargetPath = '%TARGET%';^
$sc.WorkingDirectory = '%~dp0';^
if (Test-Path '%ICON%') { $sc.IconLocation = '%ICON%'; }^
$sc.Description = 'hcompress v2 — Canonical Huffman 压缩工具';^
$sc.Save()^
"

echo   桌面快捷方式已创建: %SHORTCUT%
echo.
echo   双击桌面上的 hcompress 图标即可启动。
echo.
pause
