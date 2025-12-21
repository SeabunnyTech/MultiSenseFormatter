@echo off
CALL vars.bat

rem Activate the Python environment
CALL "%CondaPath%\Scripts\activate" "%envpath%"

rem --- Generate a reliable timestamp for the log file ---
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set "dt=%%a"
set "timestamp=%dt:~0,8%_%dt:~8,6%"
set "log_filename=split_excel_by_location_log_%timestamp%.log"

set "log_dir=logs"
if not exist "%log_dir%" (
    mkdir "%log_dir%"
)

set "log_path=%log_dir%\%log_filename%"

echo.
echo ====================================================================
echo  Executing split_excel_by_location.py
echo  Log will be saved to: %log_path%
echo ====================================================================
echo.

rem Execute the Python script and redirect output to log file
python ".\split_excel_by_location.py" %PolicyPath% > "%log_path%" 2>&1

echo.
echo ====================================================================
echo  Script finished.
echo  Log file is available at: %log_path%
echo ====================================================================
echo.

pause