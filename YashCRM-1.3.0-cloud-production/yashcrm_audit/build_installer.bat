@echo off
setlocal
cd /d "%~dp0"
call build_exe.bat --no-pause
if errorlevel 1 exit /b 1
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup 6 compiler not found. Install Inno Setup 6, then rerun this script.
  exit /b 1
)
"%ISCC%" "installer\YashCRM.iss"
if errorlevel 1 exit /b 1
echo Installer created under release\
endlocal
