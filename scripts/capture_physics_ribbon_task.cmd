@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=%QA_ROOT%\build\visual-qa-task-physics-clean"
pushd "%QA_ROOT%"
echo [%date% %time%] Capturing visible Fluent window. > "%QA_OUTPUT%\physics-capture.log"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\capture_fluent_window.py" --output-dir "%QA_OUTPUT%" >> "%QA_OUTPUT%\physics-capture.log" 2>&1
echo [%date% %time%] Capture exit code: %ERRORLEVEL% >> "%QA_OUTPUT%\physics-capture.log"
popd
endlocal
