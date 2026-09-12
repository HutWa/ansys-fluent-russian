@echo off
setlocal
set "QA_ROOT=%~dp0.."
set "QA_OUTPUT=%QA_ROOT%\build\visual-qa-case-dialog"
pushd "%QA_ROOT%"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\capture_fluent_window.py" --list-windows > "%QA_OUTPUT%\visible-windows.log" 2>&1
popd
endlocal
