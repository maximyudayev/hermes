@echo on
call .venv\Scripts\activate

set "FILE=.\examples\trial_auto_id.txt"
if exist "%FILE%" (
    < "%FILE%" set /p "TRIAL_ID="
) else (
    set "TRIAL_ID=0"
)
set /a TRIAL_ID=%TRIAL_ID% + 1
echo %TRIAL_ID% > "%FILE%"

call hermes-cli -o .\data --config_file .\examples\dummy.yml --experiment project=Test type=Dummy trial=%TRIAL_ID%
