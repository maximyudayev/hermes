@echo on
call ..\.venv\Scripts\activate

rmdir /s /q ".\data\latency\multi_device\run_latency_vs_frequency"
rmdir /s /q ".\data\latency\multi_device\run_latency_vs_msgsize"

@REM --- Configuration for remote slave device. Match with the values in master.yml ---
set REMOTE_USER=<slave_username>
set REMOTE_HOST=<slave_ip_address>
set REMOTE_BASE_DIR=<slave_hermes_project_path>  @REM Desktop/KDD2026/hermes -- OS-independent
set REMOTE_OS=<slave_os>  @REM "linux" or "windows"
set DURATION=60

set HERMES_EXP_NUM_BYTES=1000
setlocal enabledelayedexpansion
set counter=0
for %%n in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000) do (
  set HERMES_EXP_RATE=%%n
  set "REMOTE_PATH=!REMOTE_BASE_DIR!/data/latency/multi_device/run_latency_vs_frequency/trial_!counter!"
  set "LOCAL_PATH=.\data\latency\multi_device\run_latency_vs_frequency\trial_!counter!"

  echo Injecting environment variables into slave device configuration...
  python dist_utils.py slave_src.yml slave.yml

  echo Starting experiment !counter!...
  hermes-cli -o data\latency\multi_device -d !DURATION! --experiment run=latency_vs_frequency trial=!counter! -f master.yml

  echo Copying results from remote device...
  scp !REMOTE_USER!@!REMOTE_HOST!:!REMOTE_PATH!/* !LOCAL_PATH!

  echo Calculating latency between devices...
  python latency.py .\data\latency\multi_device !counter! %%n 1
  set /a counter+=1
  echo Completed experiment !counter!

  echo Removing log data from local device...
  rmdir /s /q !LOCAL_PATH!

  echo Removing log data from remote device...
  if /i "!REMOTE_OS!" == "linux" (
    ssh !REMOTE_USER!@!REMOTE_HOST! "rm -r !REMOTE_PATH!"
  ) else if /i "!REMOTE_OS!" == "windows" (
    set "REMOTE_WIN_PATH=!REMOTE_PATH:/=\!"
    ssh !REMOTE_USER!@!REMOTE_HOST! "rmdir /s /q !REMOTE_WIN_PATH!"
  )
  echo.
)
endlocal

set HERMES_EXP_RATE=100
setlocal enabledelayedexpansion
set counter=0
for %%n in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000) do (
  set HERMES_EXP_NUM_BYTES=%%n
  set "REMOTE_PATH=!REMOTE_BASE_DIR!/data/latency/multi_device/run_latency_vs_msgsize/trial_!counter!"
  set "LOCAL_PATH=.\data\latency\multi_device\run_latency_vs_msgsize\trial_!counter!"

  echo Injecting environment variables into slave device configuration...
  python dist_utils.py slave_src.yml slave.yml

  echo Starting experiment !counter!...
  hermes-cli -o data\latency\multi_device -d !DURATION! --experiment run=latency_vs_msgsize trial=!counter! -f master.yml

  echo Copying results from remote device...
  scp !REMOTE_USER!@!REMOTE_HOST!:!REMOTE_PATH!/* !LOCAL_PATH!

  echo Calculating latency between devices...
  python latency.py .\data\latency\multi_device !counter! %%n 0
  set /a counter+=1
  echo Completed experiment !counter!

  echo Removing log data from local device...
  rmdir /s /q !LOCAL_PATH!

  echo Removing log data from remote device...
  if /i "!REMOTE_OS!" == "linux" (
    ssh !REMOTE_USER!@!REMOTE_HOST! "rm -r !REMOTE_PATH!"
  ) else if /i "!REMOTE_OS!" == "windows" (
    set "REMOTE_WIN_PATH=!REMOTE_PATH:/=\!"
    ssh !REMOTE_USER!@!REMOTE_HOST! "rmdir /s /q !REMOTE_WIN_PATH!"
  )
  echo.
)
endlocal
