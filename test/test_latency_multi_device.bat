@echo on
call ..\.venv\Scripts\activate

rmdir /s /q ".\data\latency\run_latency_vs_frequency"
rmdir /s /q ".\data\latency\run_latency_vs_msgsize"

@REM --- Configuration for remote copy. Get these values from your test_latency_master.yml ---
set REMOTE_USER=a
set REMOTE_HOST=10.220.25.100
set REMOTE_BASE_DIR=Documents/revalexo
set REMOTE_OS=windows

set HERMES_EXP_NUM_BYTES=1000
setlocal enabledelayedexpansion
set counter=0
for %%n in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000) do (
  set HERMES_EXP_RATE=%%n
  set "REMOTE_PATH=!REMOTE_BASE_DIR!/data/run_latency_vs_frequency/trial_!counter!"
  set "LOCAL_PATH=.\data\latency\run_latency_vs_frequency\trial_!counter!"

  echo Injecting environment variables into slave device configuration...
  python dist_utils.py test_latency_slave_tmp.yml test_latency_slave.yml

  echo Starting experiment !counter!...
  hermes-cli -o data\latency -d 60 --experiment run=latency_vs_frequency trial=!counter! -f test_latency_master.yml

  echo Copying results from remote device...
  scp !REMOTE_USER!@!REMOTE_HOST!:!REMOTE_PATH!/* !LOCAL_PATH!

  echo Calculating latency between devices...
  python latency.py !counter! %%n 1
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
  set "REMOTE_PATH=!REMOTE_BASE_DIR!/data/run_latency_vs_msgsize/trial_!counter!"
  set "LOCAL_PATH=.\data\latency\run_latency_vs_msgsize\trial_!counter!"

  echo Injecting environment variables into slave device configuration...
  python dist_utils.py test_latency_slave_tmp.yml test_latency_slave.yml

  echo Starting experiment !counter!...
  hermes-cli -o data\latency -d 60 --experiment run=latency_vs_msgsize trial=!counter! -f test_latency_master.yml

  echo Copying results from remote device...
  scp !REMOTE_USER!@!REMOTE_HOST!:!REMOTE_PATH!/* !LOCAL_PATH!

  echo Calculating latency between devices...
  python latency.py !counter! %%n 0
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
