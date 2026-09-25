@echo off
setlocal
set "QA_ROOT=%~dp0.."
pushd "%QA_ROOT%"
"D:\Python312\python.exe" "%QA_ROOT%\scripts\wait_for_fluent_exit.py" ^
  --fluent-root "D:\games\ANSYS Inc\ANSYS Student\v261\fluent" ^
  --source-case "C:\Users\lol\Documents\bioreactor_2026R1_test_setup.cas.h5" ^
  --source-sha256 "985153dc7d8fffedcbace4b21920aaff4ef148cd963d4db094c5cca0c86783c7" ^
  --output-root "C:\Users\lol\Documents\FluentVisualQA\bioreactor" > "C:\Users\lol\Documents\FluentVisualQA\bioreactor\queued-rerun.log" 2>&1
popd
endlocal
