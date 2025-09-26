@echo off
title FIXED PC terminal
mode con: cols=80 lines=25
powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.AppActivate('FIXED PC') | Out-Null; Start-Sleep -Milliseconds 500; $wshell.SendKeys('% ') | Out-Null"

@REM REM Move window to left side of screen using PowerShell
@REM powershell -command "$sig = '[DllImport(\"user32.dll\")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);'; Add-Type -MemberDefinition $sig -Name NativeMethods -Namespace Win32; $hwnd = (Get-Process | Where-Object { $_.MainWindowTitle -eq 'FIXED PC' }).MainWindowHandle; [Win32.NativeMethods]::MoveWindow($hwnd, 0, 0, 800, 600, $true) | Out-Null"

setlocal
pushd "%~dp0"
call "D:\HERMES\venv\Scripts\activate.bat" 
set "PYTHONUNBUFFERED=1"
set "PYTHONPATH=%~dp0"

REM Default args = Local DOTs preset
set "DEFAULT_ARGS=--experiment project=AidFOG site=Leuven subject=1 group=FR session=01 medication=ON --config_file configs/AidFOG/terminal.yml"

if "%~1"=="" (
  set "ARGS=%DEFAULT_ARGS%"
) else (
  set "ARGS=%*"
)

python -u main.py %ARGS%

set "EXITCODE=%ERRORLEVEL%"
echo(
pause >nul
popd
endlocal & exit /b %EXITCODE%
