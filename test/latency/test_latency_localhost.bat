@echo on
call ..\..\.venv\Scripts\activate

set DURATION=60

setlocal enabledelayedexpansion
for %%b in (100, 1000, 5000, 10000) do (
  set counter=0
  set HERMES_EXP_NUM_BYTES=%%b
  set "OUTPUT_PATH=data\latency\localhost\bytes_!HERMES_EXP_NUM_BYTES!"
  rmdir /s /q "!OUTPUT_PATH!\run_latency_vs_frequency"

  for %%r in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000) do (
    set HERMES_EXP_RATE=%%r

    echo Starting experiment !counter! of 14: HERMES_EXP_NUM_BYTES=%%b, HERMES_EXP_RATE=%%r...
    hermes-cli -o !OUTPUT_PATH! -d !DURATION! --experiment run=latency_vs_frequency trial=!counter! --config_file ..\config\localhost.yml

    python utils\calc_latency.py !OUTPUT_PATH! !counter! %%r %%b 1
    rmdir /s /q "!OUTPUT_PATH!\run_latency_vs_frequency\trial_!counter!"

    echo Completed experiment !counter! of 14: HERMES_EXP_NUM_BYTES=%%b, HERMES_EXP_RATE=%%r...
    set /a counter+=1
    echo.
  )
  rmdir /s /q "!OUTPUT_PATH!\run_latency_vs_frequency"
)
endlocal


setlocal enabledelayedexpansion
for %%r in (1, 10, 100, 1000) do (
  set counter=0
  set HERMES_EXP_RATE=%%r
  set "OUTPUT_PATH=data\latency\localhost\rate_!HERMES_EXP_RATE!"
  rmdir /s /q "!OUTPUT_PATH!\run_latency_vs_msgsize"

  for %%b in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000) do (
    set HERMES_EXP_NUM_BYTES=%%b

    echo Starting experiment !counter! of 15: HERMES_EXP_RATE=%%r, HERMES_EXP_NUM_BYTES=%%b...
    hermes-cli -o !OUTPUT_PATH! -d !DURATION! --experiment run=latency_vs_msgsize trial=!counter! --config_file ..\config\localhost.yml

    python utils\calc_latency.py !OUTPUT_PATH! !counter! %%r %%b 0
    rmdir /s /q "!OUTPUT_PATH!\run_latency_vs_msgsize\trial_!counter!"

    echo Completed experiment !counter! of 15: HERMES_EXP_RATE=%%r, HERMES_EXP_NUM_BYTES=%%b...
    set /a counter+=1
    echo.
  )
  rmdir /s /q "!OUTPUT_PATH!\run_latency_vs_msgsize"
)
endlocal
