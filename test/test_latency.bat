@echo on
call ..\.venv\Scripts\activate

rmdir /s /q ".\data\latency\run_latency_vs_frequency"
rmdir /s /q ".\data\latency\run_latency_vs_msgsize"

set HERMES_EXP_NUM_BYTES=1000
setlocal enabledelayedexpansion
set counter=0
for %%n in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000) do (
  set HERMES_EXP_RATE=%%n
  echo Starting experiment !counter!...
  hermes-cli -o data\latency -d 30 --experiment run=latency_vs_frequency --config_file test_latency.yml
  set /a counter+=1
  python latency.py %%n 1
  echo Completed experiment !counter!
  rmdir /s /q ".\data\latency\run_latency_vs_frequency"
  echo.
)
endlocal

set HERMES_EXP_RATE=100
setlocal enabledelayedexpansion
set counter=0
for %%n in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000) do (
  set HERMES_EXP_NUM_BYTES=%%n
  echo Starting experiment !counter!...
  hermes-cli -o data\latency -d 30 --experiment run=latency_vs_msgsize --config_file test_latency.yml
  set /a counter+=1
  python latency.py %%n 0
  echo Completed experiment !counter!
  rmdir /s /q ".\data\latency\run_latency_vs_msgsize"
  echo.
)
endlocal
