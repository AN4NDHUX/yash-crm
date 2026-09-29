@echo off
rem Double-click to start Yash CRM on Windows.
cd /d "%~dp0"

rem Prefer a tested Python (3.12 first). Very new releases can break the dependencies.
set "PY="
for %%V in (3.12) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY where python >nul 2>nul && set "PY=python"

if not defined PY (
  echo Python 3.12 is required. Install Python 3.12 from https://www.python.org/downloads/ and run this again.
  goto :done
)

%PY% launch.py %*

:done
pause
