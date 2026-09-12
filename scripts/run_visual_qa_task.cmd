@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=%QA_ROOT%\build\visual-qa-task-physics-clean"
pushd "%QA_ROOT%"
if not exist "%QA_OUTPUT%" mkdir "%QA_OUTPUT%"
echo [%date% %time%] Starting Fluent launcher. > "%QA_OUTPUT%\task-run.log"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\launch_fluent.py" --fluent-root "D:\games\ANSYS Inc\ANSYS Student\v261\fluent" --capture-output "%QA_OUTPUT%" -- 3d -t1 >> "%QA_OUTPUT%\task-run.log" 2>&1
echo [%date% %time%] Launcher exit code: %ERRORLEVEL% >> "%QA_OUTPUT%\task-run.log"
echo [%date% %time%] Starting physics-ribbon navigation. >> "%QA_OUTPUT%\task-run.log"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\navigate_fluent_visual_qa.py" --mode physics-ribbon --trace-file "%QA_OUTPUT%\navigation-trace.json" >> "%QA_OUTPUT%\task-run.log" 2>&1
echo [%date% %time%] Navigation exit code: %ERRORLEVEL% >> "%QA_OUTPUT%\task-run.log"
popd
endlocal
