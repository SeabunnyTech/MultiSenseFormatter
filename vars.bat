@echo off
chcp 65001 > nul

REM -- Set the path to the conda environment definition
SET envpath="%~dp0.env"

REM -- Find Conda installation
SET "CondaPath=C:\ProgramData\miniconda3"
SET "UserCondaPath=%USERPROFILE%\miniconda3"

if exist "%UserCondaPath%\Scripts\activate.bat" (
    SET "CondaPath=%UserCondaPath%"
)

REM -- Activate the environment
echo Activating Conda environment: %envpath%
CALL "%CondaPath%\Scripts\activate.bat" %envpath%
