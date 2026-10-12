@echo off
rem This Source Code Form is subject to the terms of the Mozilla Public
rem License, v. 2.0. If a copy of the MPL was not distributed with this
rem file, You can obtain one at https://mozilla.org/MPL/2.0/.
rem SPDX-License-Identifier: MPL-2.0
rem
rem install_on_windows.cmd
rem
rem Installs VeraGrid on a Windows desktop system by:
rem - Creating a dedicated virtual environment in %LOCALAPPDATA%\VeraGrid\venv.
rem - Installing the veragrid package into the virtual environment.
rem - Installing the application icon into %LOCALAPPDATA%\VeraGrid\VeraGrid.ico.
rem - Creating Start Menu and Desktop shortcuts to launch VeraGrid.
rem - Associating .veragrid and .gridcal files with VeraGrid in HKCU\Software\Classes.

setlocal EnableDelayedExpansion

rem Default configuration values
set "VENV_DIR=%LOCALAPPDATA%\VeraGrid\venv"
set "APP_DIR=%LOCALAPPDATA%\VeraGrid"
set "PACKAGE_TARGET=veragrid"
set "PYTHON_BIN="
set "SYSTEM_SITE_PACKAGES=1"
set "SKIP_PIP=0"
set "ASSOCIATE_MIME=1"

rem Parse command-line parameters
:parse_args
if "%~1"=="" (
    goto :args_done
) else (
    if /i "%~1"=="--venv-dir" (
        set "VENV_DIR=%~2"
        shift
        shift
        goto :parse_args
    ) else (
        if /i "%~1"=="--package" (
            set "PACKAGE_TARGET=%~2"
            shift
            shift
            goto :parse_args
        ) else (
            if /i "%~1"=="--python" (
                set "PYTHON_BIN=%~2"
                shift
                shift
                goto :parse_args
            ) else (
                if /i "%~1"=="--no-system-site-packages" (
                    set "SYSTEM_SITE_PACKAGES=0"
                    shift
                    goto :parse_args
                ) else (
                    if /i "%~1"=="--skip-pip" (
                        set "SKIP_PIP=1"
                        shift
                        goto :parse_args
                    ) else (
                        if /i "%~1"=="--no-mime" (
                            set "ASSOCIATE_MIME=0"
                            shift
                            goto :parse_args
                        ) else (
                            if /i "%~1"=="-h" (
                                goto :show_help
                            ) else (
                                if /i "%~1"=="--help" (
                                    goto :show_help
                                ) else (
                                    if /i "%~1"=="/?" (
                                        goto :show_help
                                    ) else (
                                        echo Error: Unknown argument: %~1
                                        exit /b 1
                                    )
                                )
                            )
                        )
                    )
                )
            )
        )
    )
)

:show_help
echo Usage: install_on_windows.cmd [options]
echo Options:
echo   --venv-dir DIR             Virtual environment directory (default: %%LOCALAPPDATA%%\VeraGrid\venv)
echo   --package TARGET           Pip package specification (default: 'veragrid')
echo   --python PATH              Base Python executable
echo   --no-system-site-packages  Do not include system site packages
echo   --skip-pip                 Skip pip package installation
echo   --no-mime                  Skip .veragrid and .gridcal file association
echo   -h, --help                 Show this help message
exit /b 0

:args_done
echo ============================================================
echo Starting VeraGrid Windows Installation
echo ============================================================

rem Step 1: Detect working Python interpreter if not explicitly passed
if not defined PYTHON_BIN (
    rem Check Python Launcher py -3
    where py.exe >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
            if exist "%%I" (
                set "PYTHON_BIN=%%I"
            ) else (
                rem Python executable path invalid
            )
        )
    ) else (
        rem py launcher not found
    )
) else (
    rem User specified python interpreter
)

if not defined PYTHON_BIN (
    rem Check python.exe in PATH
    where python.exe >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)" 2^>nul') do (
            if exist "%%I" (
                set "PYTHON_BIN=%%I"
            ) else (
                rem python in PATH invalid
            )
        )
    ) else (
        rem python.exe not in PATH
    )
) else (
    rem Python binary already resolved
)

if not defined PYTHON_BIN (
    echo Error: Could not locate a working Python 3 installation on this system.
    echo Please install Python from https://www.python.org or the Microsoft Store.
    exit /b 1
) else (
    echo Using base Python interpreter: !PYTHON_BIN!
)

rem Step 2: Ensure application and target directories exist
if not exist "!APP_DIR!" (
    mkdir "!APP_DIR!"
) else (
    rem Application directory already present
)

rem Step 3: Create Python virtual environment
echo Creating virtual environment at: !VENV_DIR!
if "!SYSTEM_SITE_PACKAGES!"=="1" (
    "!PYTHON_BIN!" -m venv --system-site-packages "!VENV_DIR!"
) else (
    "!PYTHON_BIN!" -m venv "!VENV_DIR!"
)

if !errorlevel! neq 0 (
    echo Error: Virtual environment creation failed with exit code !errorlevel!.
    exit /b 2
) else (
    echo Virtual environment created successfully at: !VENV_DIR!
)

set "VENV_PYTHON=!VENV_DIR!\Scripts\python.exe"
set "VERAGRID_EXE=!VENV_DIR!\Scripts\veragrid.exe"

rem Step 4: Install package via pip unless skipped
if "!SKIP_PIP!"=="0" (
    echo Upgrading pip in the virtual environment...
    "!VENV_PYTHON!" -m pip install --upgrade pip
    if !errorlevel! neq 0 (
        echo Notice: pip upgrade did not complete successfully; continuing with package installation.
    ) else (
        echo pip is up to date.
    )

    echo Installing '!PACKAGE_TARGET!' into the virtual environment...
    "!VENV_PYTHON!" -m pip install --no-user --disable-pip-version-check "!PACKAGE_TARGET!"
    if !errorlevel! neq 0 (
        echo Warning: pip install failed for '!PACKAGE_TARGET!'.
    ) else (
        echo Successfully installed '!PACKAGE_TARGET!' into the virtual environment.
    )
) else (
    echo Skipping pip package installation as requested.
)

rem Step 5: Locate and copy application icon
set "DEST_ICON=!APP_DIR!\VeraGrid.ico"
set "SRC_ICON="

set "SCRIPT_DIR=%~dp0"
if exist "!SCRIPT_DIR!..\pics\VeraGrid_icon.ico" (
    set "SRC_ICON=!SCRIPT_DIR!..\pics\VeraGrid_icon.ico"
) else (
    if exist "!SCRIPT_DIR!VeraGrid\data\VeraGrid.ico" (
        set "SRC_ICON=!SCRIPT_DIR!VeraGrid\data\VeraGrid.ico"
    ) else (
        if exist "!DEST_ICON!" (
            set "SRC_ICON=!DEST_ICON!"
        ) else (
            rem Icon source not found
        )
    )
)

if defined SRC_ICON (
    if not "!SRC_ICON!"=="!DEST_ICON!" (
        copy /y "!SRC_ICON!" "!DEST_ICON!" >nul
    ) else (
        rem Already at destination
    )
    echo Application icon configured at: !DEST_ICON!
) else (
    echo Warning: Could not locate VeraGrid icon file.
)

rem Step 6: Create Windows shortcuts on Desktop and Start Menu
set "START_MENU_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
set "START_MENU_SHORTCUT=!START_MENU_DIR!\VeraGrid.lnk"
set "DESKTOP_SHORTCUT=%USERPROFILE%\Desktop\VeraGrid.lnk"

rem Determine shortcut target executable
if exist "!VERAGRID_EXE!" (
    set "SHORTCUT_TARGET=!VERAGRID_EXE!"
) else (
    set "SHORTCUT_TARGET=!VENV_PYTHON!"
)

echo Creating shortcuts for VeraGrid...
powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$s1 = $ws.CreateShortcut('!START_MENU_SHORTCUT!'); " ^
    "$s1.TargetPath = '!SHORTCUT_TARGET!'; " ^
    "if ('!SHORTCUT_TARGET!' -like '*python.exe*') { $s1.Arguments = '-c \"from VeraGrid.ExecuteVeraGrid import runVeraGrid; runVeraGrid()\"'; } " ^
    "if (Test-Path '!DEST_ICON!') { $s1.IconLocation = '!DEST_ICON!'; } " ^
    "$s1.Description = 'VeraGrid Power Systems Simulator'; " ^
    "$s1.Save(); " ^
    "$s2 = $ws.CreateShortcut('!DESKTOP_SHORTCUT!'); " ^
    "$s2.TargetPath = '!SHORTCUT_TARGET!'; " ^
    "if ('!SHORTCUT_TARGET!' -like '*python.exe*') { $s2.Arguments = '-c \"from VeraGrid.ExecuteVeraGrid import runVeraGrid; runVeraGrid()\"'; } " ^
    "if (Test-Path '!DEST_ICON!') { $s2.IconLocation = '!DEST_ICON!'; } " ^
    "$s2.Description = 'VeraGrid Power Systems Simulator'; " ^
    "$s2.Save();"

if exist "!START_MENU_SHORTCUT!" (
    echo Created Start Menu shortcut: !START_MENU_SHORTCUT!
) else (
    echo Notice: Could not create Start Menu shortcut.
)

if exist "!DESKTOP_SHORTCUT!" (
    echo Created Desktop shortcut:    !DESKTOP_SHORTCUT!
) else (
    echo Notice: Could not create Desktop shortcut.
)

rem Step 7: Associate .veragrid and .gridcal files in HKCU\Software\Classes
if "!ASSOCIATE_MIME!"=="1" (
    echo Registering .veragrid and .gridcal file associations...

    reg add "HKCU\Software\Classes\.veragrid" /ve /d "VeraGrid.Project" /f >nul 2>&1
    reg add "HKCU\Software\Classes\.gridcal" /ve /d "VeraGrid.Project" /f >nul 2>&1
    reg add "HKCU\Software\Classes\.dgridcal" /ve /d "VeraGrid.Project" /f >nul 2>&1
    reg add "HKCU\Software\Classes\VeraGrid.Project" /ve /d "VeraGrid Project" /f >nul 2>&1

    if exist "!DEST_ICON!" (
        reg add "HKCU\Software\Classes\VeraGrid.Project\DefaultIcon" /ve /d "!DEST_ICON!,0" /f >nul 2>&1
    ) else (
        rem Icon not available for registry
    )

    if exist "!VERAGRID_EXE!" (
        reg add "HKCU\Software\Classes\VeraGrid.Project\shell\open\command" /ve /d "\"!VERAGRID_EXE!\" \"%%1\"" /f >nul 2>&1
    ) else (
        reg add "HKCU\Software\Classes\VeraGrid.Project\shell\open\command" /ve /d "\"!VENV_PYTHON!\" -c \"from VeraGrid.ExecuteVeraGrid import runVeraGrid; runVeraGrid()\" \"%%1\"" /f >nul 2>&1
    )

    echo Registered file associations successfully in HKCU\Software\Classes.
) else (
    echo Skipping file association registration as requested.
)

echo ============================================================
echo VeraGrid Windows Installation Completed Successfully!
echo Virtual environment: !VENV_DIR!
echo Shortcuts:           Start Menu and Desktop
echo File associations:   .veragrid, .gridcal -^> VeraGrid
echo ============================================================

exit /b 0
