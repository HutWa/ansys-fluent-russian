@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=%QA_ROOT%\build\visual-qa-task-multiphase"
pushd "%QA_ROOT%"
if not exist "%QA_OUTPUT%" mkdir "%QA_OUTPUT%"
echo [%date% %time%] Starting multiphase-dialog navigation. > "%QA_OUTPUT%\navigation-run.log"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\navigate_fluent_visual_qa.py" --mode multiphase-tree --trace-file "%QA_OUTPUT%\navigation-trace.json" >> "%QA_OUTPUT%\navigation-run.log" 2>&1
echo [%date% %time%] Navigation exit code: %ERRORLEVEL% >> "%QA_OUTPUT%\navigation-run.log"
popd
endlocal
