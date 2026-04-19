@echo on
call ..\.venv\Scripts\activate

rmdir /s /q ".\data\latency\localhost\run_latency_vs_frequency"
rmdir /s /q ".\data\latency\localhost\run_latency_vs_msgsize"

set DURATION=60

set HERMES_EXP_NUM_BYTES=1000
setlocal enabledelayedexpansion
set counter=0
for %%n in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000) do (
  set HERMES_EXP_RATE=%%n

  echo Starting experiment !counter!...
  hermes-cli -o data\latency\localhost -d !DURATION! --experiment run=latency_vs_frequency trial=!counter! --config_file localhost.yml

  python latency.py !counter! %%n 1
  rmdir /s /q ".\data\latency\localhost\run_latency_vs_frequency\trial_!counter!"

  set /a counter+=1
  echo Completed experiment !counter!
  echo.
)
endlocal

set HERMES_EXP_RATE=100
setlocal enabledelayedexpansion
set counter=0
for %%n in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000) do (
  set HERMES_EXP_NUM_BYTES=%%n

  echo Starting experiment !counter!...
  hermes-cli -o data\latency\localhost -d !DURATION! --experiment run=latency_vs_msgsize trial=!counter! --config_file localhost.yml

  python latency.py !counter! %%n 0
  rmdir /s /q ".\data\latency\localhost\run_latency_vs_msgsize\trial_!counter!"

  set /a counter+=1
  echo Completed experiment !counter!
  echo.
)
endlocal
