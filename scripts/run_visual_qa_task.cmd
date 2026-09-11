@echo off
setlocal
set "QA_ROOT=%~dp0.."
pushd "%QA_ROOT%"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\launch_fluent.py" --fluent-root "D:\games\ANSYS Inc\ANSYS Student\v261\fluent" --capture-output "%QA_ROOT%\build\visual-qa-task-open" -- 3d -t1
"D:\Python312\python.exe" "%QA_ROOT%\scripts\navigate_fluent_visual_qa.py" --trace-file "%QA_ROOT%\build\visual-qa-task-open\navigation-trace.json"
popd
endlocal
