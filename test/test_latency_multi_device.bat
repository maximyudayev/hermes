@echo on
call ..\.venv\Scripts\activate

rmdir /s /q ".\data\latency\multi_device\run_latency_vs_frequency"
rmdir /s /q ".\data\latency\multi_device\run_latency_vs_msgsize"

@REM --- Configuration for remote slave device. Match with the values in master.yml ---
set REMOTE_USER=a
set REMOTE_HOST=10.220.25.100
@REM Desktop/KDD2026/hermes -- OS-independent
set REMOTE_BASE_DIR=Desktop/KDD2026/hermes
@REM "linux" or "windows" -- no quotes
set REMOTE_OS=windows
set DURATION=60

set HERMES_EXP_NUM_BYTES=1000
setlocal enabledelayedexpansion
set counter=0
for %%n in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000) do (
  set HERMES_EXP_RATE=%%n
  set "REMOTE_PATH=!REMOTE_BASE_DIR!/data/latency/multi_device/run_latency_vs_frequency/trial_!counter!"
  set "LOCAL_PATH=.\data\latency\multi_device\run_latency_vs_frequency\trial_!counter!"

  echo Injecting environment variables into slave device configuration...
  python utils\inject_envs.py config\slave_src.yml config\slave.yml

  echo Starting experiment !counter!...
  hermes-cli -o data\latency\multi_device -d !DURATION! --experiment run=latency_vs_frequency trial=!counter! -f config\master.yml

  echo Copying results from remote device...
  scp !REMOTE_USER!@!REMOTE_HOST!:!REMOTE_PATH!/* !LOCAL_PATH!

  echo Calculating latency between devices...
  python utils\calc_latency_multi_device.py .\data\latency\multi_device !counter! %%n 1 0.001148900
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
  python utils\inject_envs.py config\slave_src.yml config\slave.yml

  echo Starting experiment !counter!...
  hermes-cli -o data\latency\multi_device -d !DURATION! --experiment run=latency_vs_msgsize trial=!counter! -f config\master.yml

  echo Copying results from remote device...
  scp !REMOTE_USER!@!REMOTE_HOST!:!REMOTE_PATH!/* !LOCAL_PATH!

  echo Calculating latency between devices...
  python utils\calc_latency_multi_device.py .\data\latency\multi_device !counter! %%n 0 0.001148900
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
