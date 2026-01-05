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
echo ====================================================================
echo.

set PYTHONIOENCODING=UTF-8

rem Check if --force or -f flag is present
set "FORCE_MODE=0"
for %%a in (%*) do (
    if "%%a"=="--force" set "FORCE_MODE=1"
    if "%%a"=="-f" set "FORCE_MODE=1"
)

if "%FORCE_MODE%"=="1" (
    rem Force mode: use Tee-Object for logging
    echo  Mode: Force [logging to: %log_path%]
    echo ====================================================================
    echo.
    powershell -Command "$OutputEncoding = [System.Text.Encoding]::UTF8; python -u -m run_processor %* 2>&1 | Tee-Object -FilePath \"%log_path%\""
) else (
    rem Interactive mode: run directly without Tee-Object
    echo  Mode: Interactive [no logging]
    echo  Tip: Use --force to enable logging
    echo ====================================================================
    echo.
    python -u -m run_processor %*
)

rem --- Check for errors and display summary ---
if %ERRORLEVEL% neq 0 (
    echo.
    echo ===================== SCRIPT FINISHED WITH NON-ZERO EXIT CODE ======================
    echo An error occurred during script execution. Please review the output above.
    echo ====================================================================================
) else (
    echo.
    echo ====================================================================
    echo  Script finished successfully.
    echo ====================================================================
)
echo.
pause
