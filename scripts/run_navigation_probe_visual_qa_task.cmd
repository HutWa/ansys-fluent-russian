@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=%QA_ROOT%\build\visual-qa-navigation-probe"
pushd "%QA_ROOT%"
if not exist "%QA_OUTPUT%" mkdir "%QA_OUTPUT%"
echo [%date% %time%] Inspecting Fluent navigation tree through UIA only; no input is sent. > "%QA_OUTPUT%\task-run.log"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\inspect_fluent_uia.py" --target materials --output "%QA_OUTPUT%\materials.json" >> "%QA_OUTPUT%\task-run.log" 2>&1
"D:\Python312\python.exe" "%QA_ROOT%\scripts\inspect_fluent_uia.py" --target cell-zone-conditions --output "%QA_OUTPUT%\cell-zone-conditions.json" >> "%QA_OUTPUT%\task-run.log" 2>&1
"D:\Python312\python.exe" "%QA_ROOT%\scripts\inspect_fluent_uia.py" --target solution-initialization --output "%QA_OUTPUT%\solution-initialization.json" >> "%QA_OUTPUT%\task-run.log" 2>&1
echo [%date% %time%] Inspection exit code: %ERRORLEVEL% >> "%QA_OUTPUT%\task-run.log"
popd
endlocal
