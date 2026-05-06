@echo off
setlocal

for /f "usebackq tokens=*" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 4000,5173,8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"`) do (
  if not "%%P"=="" (
    taskkill /PID %%P /F >nul 2>nul
  )
)

echo Turbo Blog local service stopped if it was running.
endlocal
