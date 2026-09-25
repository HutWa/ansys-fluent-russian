@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=%QA_ROOT%\build\visual-qa-models-tree"
pushd "%QA_ROOT%"
if not exist "%QA_OUTPUT%" mkdir "%QA_OUTPUT%"
echo [%date% %time%] Expanding only the visible Models tree node through its UIA name. > "%QA_OUTPUT%\task-run.log"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\navigate_fluent_uia.py" --target models-tree --trace-file "%QA_OUTPUT%\navigation-trace.json" >> "%QA_OUTPUT%\task-run.log" 2>&1
echo [%date% %time%] Navigation exit code: %ERRORLEVEL% >> "%QA_OUTPUT%\task-run.log"
if not errorlevel 1 (
  "D:\Python312\python.exe" "%QA_ROOT%\scripts\capture_fluent_window.py" --title-contains "Fluent@Home" --output-dir "%QA_OUTPUT%" >> "%QA_OUTPUT%\task-run.log" 2>&1
  echo [%date% %time%] Capture exit code: %ERRORLEVEL% >> "%QA_OUTPUT%\task-run.log"
)
popd
endlocal
