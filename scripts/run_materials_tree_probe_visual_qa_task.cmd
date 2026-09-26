@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=%QA_ROOT%\build\visual-qa-materials-tree-probe"
pushd "%QA_ROOT%"
if not exist "%QA_OUTPUT%" mkdir "%QA_OUTPUT%"
echo [%date% %time%] Expanding only the Materials tree branch through UIA. > "%QA_OUTPUT%\task-run.log"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\navigate_fluent_uia.py" --target materials --expand --trace-file "%QA_OUTPUT%\expand-trace.json" >> "%QA_OUTPUT%\task-run.log" 2>&1
if errorlevel 1 goto :done
"D:\Python312\python.exe" "%QA_ROOT%\scripts\inspect_fluent_uia.py" --target materials --output "%QA_OUTPUT%\materials-expanded.json" >> "%QA_OUTPUT%\task-run.log" 2>&1
:done
echo [%date% %time%] Tree probe exit code: %ERRORLEVEL% >> "%QA_OUTPUT%\task-run.log"
popd
endlocal
