@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "VENV_PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %ERRORLEVEL%==0 (
  echo Turbo Blog Django is already running.
  echo Blog: http://localhost:5173
  echo Health: http://localhost:5173/api/health
  echo.
  echo If you want to restart it, run stop-blog.bat first.
  goto :end
)

if exist "%VENV_PYTHON%" (
  cd /d "%PROJECT_DIR%"
  "%VENV_PYTHON%" -m pip show django >nul 2>nul
  if not %ERRORLEVEL%==0 (
    "%VENV_PYTHON%" -m pip install -r requirements.txt
  )
  "%VENV_PYTHON%" manage.py migrate --noinput
  "%VENV_PYTHON%" manage.py seed_initial_data
  "%VENV_PYTHON%" manage.py runserver [::]:5173
  goto :end
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  cd /d "%PROJECT_DIR%"
  python -m pip show django >nul 2>nul
  if not %ERRORLEVEL%==0 (
    python -m pip install -r requirements.txt
  )
  python manage.py migrate --noinput
  python manage.py seed_initial_data
  python manage.py runserver [::]:5173
  goto :end
)

echo Cannot find Python.
echo Please install Python 3.11+ and run start-blog.bat again.
pause

:end
endlocal
