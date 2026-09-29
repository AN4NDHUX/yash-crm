@echo off
rem Builds YashCRM.exe (one file, no Python needed to run it) and adds a desktop shortcut.
cd /d "%~dp0"

set "PY="
for %%V in (3.12) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3.12 was not found. Install Python 3.12 from https://www.python.org/downloads/ and run this again.
  pause
  exit /b 1
)

%PY% -c "import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)" || (
  echo The Python found here is not the required Python 3.12.
  echo Install Python 3.12 from https://www.python.org/downloads/ alongside it and run this again.
  pause
  exit /b 1
)
echo Using:
%PY% --version

echo Installing build tools and dependencies...
%PY% -m pip install --quiet --upgrade pyinstaller -r requirements.txt || goto :fail

echo Building YashCRM.exe (this takes a minute or two)...
%PY% -m PyInstaller --noconfirm --clean --onefile --name YashCRM --icon "static\icons\app.ico" --version-file "version_info.txt" ^
  --add-data "static;static" --add-data "templates;templates" --add-data "public;public" ^
  --collect-submodules uvicorn --collect-submodules sqlalchemy ^
  --hidden-import pymysql --hidden-import multipart --hidden-import python_multipart ^
  yashcrm_app.py || goto :fail

copy /y "dist\YashCRM.exe" "YashCRM.exe" >nul || goto :fail

echo.
echo Done. YashCRM.exe is in dist\ and copied to this folder.
echo Your data is stored in yashcrm.db next to YashCRM.exe.
if /i not "%~1"=="--no-pause" pause
exit /b 0

:fail
echo.
echo The build failed. Scroll up for the error message.
if /i not "%~1"=="--no-pause" pause
exit /b 1
