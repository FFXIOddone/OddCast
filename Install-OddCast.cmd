@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-OddCast.ps1" %*
if errorlevel 1 (
  echo.
  echo OddCast was not changed. Review the error above.
  pause
  exit /b 1
)
echo.
echo OddCast install or update completed successfully.
pause
