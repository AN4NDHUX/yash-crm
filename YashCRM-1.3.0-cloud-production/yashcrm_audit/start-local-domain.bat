@echo off
cd /d "%~dp0"
findstr /I /C:"yashcrm.local" "%SystemRoot%\System32\drivers\etc\hosts" >nul 2>&1
if errorlevel 1 (
  echo yashcrm.local is not configured yet.
  echo Running one-time local-domain setup...
  call setup-local-domain.bat
)
call start.bat %*
