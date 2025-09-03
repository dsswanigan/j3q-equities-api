@echo off
setlocal enabledelayedexpansion

REM ============================
REM CONFIGURATION
REM ============================
set API_DIR=C:\J3Q\API
set API_FILE=J3Qapi:app
set API_PORT=8000
set TEST_SCRIPT=api_test.py

REM ============================
REM STEP 1: Kill any existing API server on this port
REM ============================
echo Killing any process using port %API_PORT%...
FOR /F "tokens=5" %%P IN ('netstat -ano ^| findstr :%API_PORT% ^| findstr LISTENING') DO taskkill /F /PID %%P >nul 2>&1

REM ============================
REM STEP 2: Change to API directory
REM ============================
cd /d %API_DIR%

REM ============================
REM STEP 3: Install dependencies (optional)
REM ============================
pip install fastapi uvicorn pandas requests >nul

REM ============================
REM STEP 4: Start API server in background
REM ============================
echo Starting API server...
start "" /B python -m uvicorn %API_FILE% --host 0.0.0.0 --port %API_PORT%
REM Give it a few seconds to start
timeout /t 5 /nobreak >nul

REM ============================
REM STEP 5: Run API tests
REM ============================
echo Running API tests...
python "%TEST_SCRIPT%"
set TEST_RESULT=%ERRORLEVEL%

REM ============================
REM STEP 6: Shut down API server
REM ============================
echo Stopping API server...
FOR /F "tokens=5" %%P IN ('netstat -ano ^| findstr :%API_PORT% ^| findstr LISTENING') DO taskkill /F /PID %%P >nul 2>&1

REM ============================
REM STEP 7: Print summary
REM ============================
if "%TEST_RESULT%"=="0" (
    echo 🎉 All API tests completed successfully — no errors or warnings.
) else (
    echo ⚠ Some API tests failed. Check the output above.
)

pause
endlocal
