@echo on
setlocal
call .venv\Scripts\activate
set PYTHONPATH="%cd%"

:prompt_subject
set "SUBJECT_ID="
set /p "SUBJECT_ID=Enter Subject ID: "
if "%SUBJECT_ID%"=="" (
    echo Error: Subject ID cannot be empty.
    goto prompt_subject
)

set "FILE=.\run\trial_auto_id_%SUBJECT_ID%.txt"
if exist "%FILE%" (
    < "%FILE%" set /p "TRIAL_ID="
    set /a TRIAL_ID=%TRIAL_ID% + 1
) else (
    set "TRIAL_ID=0"
)
> "%FILE%" echo %TRIAL_ID%

call hermes-cli -o .\data -f .\examples\dummy.yml -e project=Test subject=%SUBJECT_ID% trial=%TRIAL_ID%
endlocal
