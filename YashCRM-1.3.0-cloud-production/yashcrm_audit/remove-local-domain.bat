@echo off
setlocal EnableExtensions
set "HOSTS=%SystemRoot%\System32\drivers\etc\hosts"
net session >nul 2>&1
if errorlevel 1 (
  echo Administrator permission is required to remove yashcrm.local.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=$env:SystemRoot+'\System32\drivers\etc\hosts'; $c=Get-Content -LiteralPath $p; $c ^| Where-Object { $_ -notmatch '^\s*127\.0\.0\.1\s+yashcrm\.local(?:\s|$)' } ^| Set-Content -LiteralPath $p -Encoding ascii"
ipconfig /flushdns >nul
echo Removed yashcrm.local mapping.
