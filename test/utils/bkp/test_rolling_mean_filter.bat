@echo on
call ..\.venv\Scripts\activate

set DURATION=30

@REM --- Configuration for remote slave device. Match with the values in master.yml ---
set REMOTE_USER=a
set REMOTE_HOST=10.220.25.100
set LOCAL_HOST=10.220.25.103
@REM Desktop/KDD2026/hermes -- OS-independent
set REMOTE_BASE_DIR=C:/Users/a/Desktop/KDD2026/hermes
@REM "linux" or "windows" -- no quotes
set REMOTE_OS=windows

@REM echo Testing application-level network floor between 2 devices...
@REM setlocal enabledelayedexpansion
@REM python utils\zmq_net_profiler.py !REMOTE_OS! !REMOTE_USER! !REMOTE_HOST! !REMOTE_BASE_DIR!/test !LOCAL_HOST! 300 100
@REM endlocal

set HERMES_EXP_NUM_BYTES=1000
setlocal enabledelayedexpansion
set counter=4
< "net_floor.txt" set /p "ONE_WAY_FLOOR="
for %%n in (5000) do (
  set HERMES_EXP_RATE=%%n
  set "REMOTE_PATH=!REMOTE_BASE_DIR!/data/latency/multi_device/run_latency_vs_frequency/trial_!counter!"
  set "LOCAL_PATH=.\data\latency\multi_device\run_latency_vs_frequency\trial_!counter!"

  echo Injecting environment variables into slave device configuration...
  python utils\inject_envs.py config\slave_src.yml config\slave.yml

  echo Starting experiment !counter!...
  hermes-cli -o data\latency\multi_device -d !DURATION! --experiment run=latency_vs_frequency trial=!counter! -f config\master.yml

  echo Copying results from remote device...
  scp !REMOTE_USER!@!REMOTE_HOST!:!REMOTE_PATH!/* !LOCAL_PATH!

  @REM echo Calculating latency between devices...
  @REM python utils\calc_latency_multi_device.py .\data\latency\multi_device !counter! %%n 1 !ONE_WAY_FLOOR!
  @REM set /a counter+=1
  @REM echo Completed experiment !counter!
  @REM .\data\latency\multi_device 4 5000 1 0.000693850
)
endlocal

@REM TODO: generate plot of the raw vs rolling mean latency.
