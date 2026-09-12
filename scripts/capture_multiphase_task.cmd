@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=%QA_ROOT%\build\visual-qa-task-multiphase"
pushd "%QA_ROOT%"
if not exist "%QA_OUTPUT%" mkdir "%QA_OUTPUT%"
echo [%date% %time%] Capturing visible Fluent window. > "%QA_OUTPUT%\capture-run.log"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\capture_fluent_window.py" --title-contains "Multiphase" --output-dir "%QA_OUTPUT%" >> "%QA_OUTPUT%\capture-run.log" 2>&1
echo [%date% %time%] Capture exit code: %ERRORLEVEL% >> "%QA_OUTPUT%\capture-run.log"
popd
endlocal
