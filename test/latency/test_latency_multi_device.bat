@echo on
call ..\..\.venv\Scripts\activate

set DURATION=30

@REM --- Configuration for remote slave device. Match with the values in master.yml ---
set REMOTE_USER=a
set REMOTE_HOST=10.220.25.100
set LOCAL_HOST=10.220.25.103
@REM Desktop/KDD2026/hermes -- OS-independent
set REMOTE_BASE_DIR=C:/Users/a/Desktop/KDD2026/hermes
@REM "linux" or "windows" -- no quotes
set REMOTE_OS=windows

echo Testing application-level network floor between 2 devices...
setlocal enabledelayedexpansion
@REM python utils\zmq_net_profiler.py !REMOTE_OS! !REMOTE_USER! !REMOTE_HOST! !REMOTE_BASE_DIR!/test !LOCAL_HOST! 300 100
endlocal

set HERMES_EXP_NUM_BYTES=1000
setlocal enabledelayedexpansion
set counter=0
< "net_floor.txt" set /p "ONE_WAY_FLOOR="
for %%n in (100) do (
  set HERMES_EXP_RATE=%%n
  set "REMOTE_PATH=!REMOTE_BASE_DIR!/data/latency/multi_device/run_latency_vs_frequency/trial_!counter!"
  set "LOCAL_PATH=data\latency\multi_device\run_latency_vs_frequency\trial_!counter!"

  @REM echo Injecting environment variables into slave device configuration...
  @REM python utils\inject_envs.py ..\config\slave_src.yml ..\config\slave.yml

  @REM echo Starting experiment !counter!...
  @REM hermes-cli -o data\latency\multi_device -d !DURATION! --experiment run=latency_vs_frequency trial=!counter! -f ..\config\master.yml

  @REM echo Copying results from remote device...
  @REM scp !REMOTE_USER!@!REMOTE_HOST!:!REMOTE_PATH!/* !LOCAL_PATH!

  echo Calculating latency between devices...
  python utils\calc_latency_multi_device.py data\latency\multi_device !counter! %%n 1 !ONE_WAY_FLOOR!
  set /a counter+=1
  echo Completed experiment !counter!

  @REM echo Removing log data from local device...
  @REM rmdir /s /q !LOCAL_PATH!

  @REM echo Removing log data from remote device...
  @REM if /i "!REMOTE_OS!" == "linux" (
  @REM   ssh !REMOTE_USER!@!REMOTE_HOST! "rm -r !REMOTE_PATH!"
  @REM ) else if /i "!REMOTE_OS!" == "windows" (
  @REM   set "REMOTE_WIN_PATH=!REMOTE_PATH:/=\!"
  @REM   ssh !REMOTE_USER!@!REMOTE_HOST! "rmdir /s /q !REMOTE_WIN_PATH!"
  @REM )
  @REM echo.
)
endlocal

@REM set HERMES_EXP_RATE=100
@REM setlocal enabledelayedexpansion
@REM set counter=0
@REM for %%n in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000) do (
@REM   set HERMES_EXP_NUM_BYTES=%%n
@REM   set "REMOTE_PATH=!REMOTE_BASE_DIR!/data/latency/multi_device/run_latency_vs_msgsize/trial_!counter!"
@REM   set "LOCAL_PATH=data\latency\multi_device\run_latency_vs_msgsize\trial_!counter!"

@REM   echo Injecting environment variables into slave device configuration...
@REM   python utils\inject_envs.py ..\config\slave_src.yml ..\config\slave.yml

@REM   echo Starting experiment !counter!...
@REM   hermes-cli -o data\latency\multi_device -d !DURATION! --experiment run=latency_vs_msgsize trial=!counter! -f ..\config\master.yml

@REM   echo Copying results from remote device...
@REM   scp !REMOTE_USER!@!REMOTE_HOST!:!REMOTE_PATH!/* !LOCAL_PATH!

@REM   echo Calculating latency between devices...
@REM   python utils\calc_latency_multi_device.py data\latency\multi_device !counter! %%n 0 %ONE_WAY_FLOOR%
@REM   set /a counter+=1
@REM   echo Completed experiment !counter!

@REM   echo Removing log data from local device...
@REM   rmdir /s /q !LOCAL_PATH!

@REM   echo Removing log data from remote device...
@REM   if /i "!REMOTE_OS!" == "linux" (
@REM     ssh !REMOTE_USER!@!REMOTE_HOST! "rm -r !REMOTE_PATH!"
@REM   ) else if /i "!REMOTE_OS!" == "windows" (
@REM     set "REMOTE_WIN_PATH=!REMOTE_PATH:/=\!"
@REM     ssh !REMOTE_USER!@!REMOTE_HOST! "rmdir /s /q !REMOTE_WIN_PATH!"
@REM   )
@REM   echo.
@REM )
@REM endlocal
