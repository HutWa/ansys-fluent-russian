@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=%QA_ROOT%\build\visual-qa-task-run-calculation"
pushd "%QA_ROOT%"
if not exist "%QA_OUTPUT%" mkdir "%QA_OUTPUT%"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\navigate_fluent_uia.py" --target run-calculation --trace-file "%QA_OUTPUT%\uia-navigation-trace.json" > "%QA_OUTPUT%\uia-navigation-run.log" 2>&1
popd
endlocal
