@echo off
setlocal EnableExtensions
set "HOSTS=%SystemRoot%\System32\drivers\etc\hosts"
set "ENTRY=127.0.0.1 yashcrm.local"

net session >nul 2>&1
if errorlevel 1 (
  echo Administrator permission is required to configure yashcrm.local.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

findstr /R /C:"^[ ]*127\.0\.0\.1[ ][ ]*yashcrm\.local\([ ]\|$\)" "%HOSTS%" >nul 2>&1
if not errorlevel 1 (
  echo yashcrm.local is already configured.
  ipconfig /flushdns >nul
  exit /b 0
)

echo.>>"%HOSTS%"
echo %ENTRY%>>"%HOSTS%"
ipconfig /flushdns >nul
echo Configured: http://yashcrm.local
exit /b 0
