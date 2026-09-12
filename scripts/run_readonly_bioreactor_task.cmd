@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=C:\Users\lol\Documents\FluentVisualQA\bioreactor"
pushd "%QA_ROOT%"
if not exist "%QA_OUTPUT%" mkdir "%QA_OUTPUT%"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\launch_readonly_case.py" --fluent-root "D:\games\ANSYS Inc\ANSYS Student\v261\fluent" --source-case "C:\Users\lol\Documents\bioreactor_2026R1_test_setup.cas.h5" --output-dir "%QA_OUTPUT%" > "%QA_OUTPUT%\task-run.log" 2>&1
popd
endlocal
