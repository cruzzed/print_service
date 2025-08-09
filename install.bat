@echo off
REM QR Print Client Installation Script for Windows
REM This script sets up a virtual environment and runs the print client

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "PYTHON_SCRIPT=%SCRIPT_DIR%gui_qr_print_service.py"
set "REQUIREMENTS=%SCRIPT_DIR%requirements.txt"

echo =========================================
echo QR Print Client Installation ^& Launcher
echo =========================================

REM Check if we're in a git repository and pull updates
if exist ".git" (
    echo Checking for updates...
    git fetch --quiet 2>nul
    if !errorlevel! equ 0 (
        for /f %%i in ('git rev-list HEAD...origin/HEAD --count 2^>nul') do set "UPDATES=%%i"
        if not defined UPDATES set "UPDATES=0"
        if !UPDATES! gtr 0 (
            echo Found !UPDATES! update^(s^). Pulling latest changes...
            git pull
            echo ✓ Updates applied
            
            REM Check if install script itself was updated, restart if so
            for /f %%i in ('git diff HEAD~!UPDATES! HEAD --name-only ^| findstr "install.bat"') do (
                echo Installer script updated. Restarting with new version...
                echo =========================================
                start "" "%~f0" %*
                exit /b 0
            )
        ) else (
            echo ✓ Already up to date
        )
    ) else (
        echo ✓ Git fetch failed, continuing with current version
    )
) else (
    echo ✓ Not a git repository, skipping update check
)

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo Error: Python is not installed or not in PATH
        echo Please install Python 3.8+ from https://python.org and try again
        pause
        exit /b 1
    ) else (
        set "PYTHON_CMD=py"
    )
) else (
    set "PYTHON_CMD=python"
)

echo Using Python: !PYTHON_CMD!

REM Check if virtual environment exists
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    !PYTHON_CMD! -m venv "%VENV_DIR%"
    echo ✓ Virtual environment created
) else (
    echo ✓ Virtual environment found
)

REM Activate virtual environment
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM Install/upgrade pip
echo Updating pip...
python -m pip install --upgrade pip >nul 2>&1

REM Install requirements
if exist "%REQUIREMENTS%" (
    echo Installing requirements...
    pip install -r "%REQUIREMENTS%" >nul 2>&1
    echo ✓ Requirements installed
) else (
    echo Installing requests library...
    pip install requests >nul 2>&1
    echo ✓ Dependencies installed
)

REM Check if the Python script exists
if not exist "%PYTHON_SCRIPT%" (
    echo Error: gui_qr_print_service.py not found!
    pause
    exit /b 1
)

echo ✓ Setup complete!
echo.
echo Starting QR Print Client...
echo =========================================

REM Run the application
python "%PYTHON_SCRIPT%"

echo.
echo QR Print Client has been closed.
echo.
echo To run again, double-click install.bat
echo Or activate the environment and run: python gui_qr_print_service.py
pause