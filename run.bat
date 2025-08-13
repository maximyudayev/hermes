@echo off
setlocal
pushd "%~dp0"

set "PYTHONUNBUFFERED=1"
set "PYTHONPATH=%~dp0"

REM Default args = Local DOTs preset
set "DEFAULT_ARGS=--experiment project=Tests site=Leuven subject=1 group=FR session=01 medication=ON --config_file configs/test/local_dots.yml"

if "%~1"=="" (
  set "ARGS=%DEFAULT_ARGS%"
) else (
  set "ARGS=%*"
)

py -3 -u main.py %ARGS%

set "EXITCODE=%ERRORLEVEL%"
echo(
pause >nul
popd
endlocal & exit /b %EXITCODE%
