@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=%QA_ROOT%\build\visual-qa-task-solution-initialization"
pushd "%QA_ROOT%"
if not exist "%QA_OUTPUT%" mkdir "%QA_OUTPUT%"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\navigate_fluent_visual_qa.py" --mode solution-initialization --trace-file "%QA_OUTPUT%\navigation-trace.json" > "%QA_OUTPUT%\navigation-run.log" 2>&1
popd
endlocal
