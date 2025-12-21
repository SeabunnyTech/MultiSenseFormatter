@echo off
chcp 65001 > nul
CALL vars.bat

rem Activate the Python environment
CALL "%CondaPath%\Scripts\activate" "%envpath%"

rem --- Generate a reliable timestamp for the log file ---
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set "dt=%%a"
set "timestamp=%dt:~0,8%_%dt:~8,6%"
set "log_filename=processor_log_%timestamp%.log"

set "log_dir=logs"
if not exist "%log_dir%" (
    mkdir "%log_dir%"
)

set "log_path=%log_dir%\%log_filename%"

echo.
echo ====================================================================
echo  Executing run_processor.py
echo  Settings will be loaded from vars.py
echo  Output will be shown here and logged to: %log_path%
echo ====================================================================
echo.

rem Set Python IO encoding to UTF-8 and execute via PowerShell, ensuring all parts handle UTF-8
set PYTHONIOENCODING=UTF-8
powershell -Command "$OutputEncoding = [System.Text.Encoding]::UTF8; python -u -m run_processor 2>&1 | Tee-Object -FilePath \"%log_path%\""

rem --- Check for errors and display summary ---
if %ERRORLEVEL% neq 0 (
    echo.
    echo ===================== SCRIPT FINISHED WITH NON-ZERO EXIT CODE ======================
    echo An error occurred during script execution. Please review the output above and the log file for details.
    echo ====================================================================================
) else (
    echo.
    echo ====================================================================
    echo  Script finished successfully.
    echo ====================================================================
)
echo.
pause
