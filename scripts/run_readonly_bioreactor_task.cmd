@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=C:\Users\lol\Documents\FluentVisualQA\bioreactor"
pushd "%QA_ROOT%"
if not exist "%QA_OUTPUT%" mkdir "%QA_OUTPUT%"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\launch_readonly_case.py" --fluent-root "D:\games\ANSYS Inc\ANSYS Student\v261\fluent" --source-case "C:\Users\lol\Documents\bioreactor_2026R1_test_setup.cas.h5" --output-dir "%QA_OUTPUT%" --runtime-dir "%QA_OUTPUT%" > "%QA_OUTPUT%\task-run.log" 2>&1
"D:\Python312\python.exe" "%QA_ROOT%\scripts\wait_for_readonly_case_ready.py" --case-title-fragment "bioreactor_2026R1_test_setup" --runtime-dir "%QA_OUTPUT%" --status-file "%QA_OUTPUT%\startup-status.json" >> "%QA_OUTPUT%\task-run.log" 2>&1
set "QA_EXIT=%ERRORLEVEL%"
popd
endlocal & exit /b %QA_EXIT%
