@echo off
REM ===================================================================
REM start.bat - starts NovaMind and opens it in your browser.
REM Keep this window open while you use the app. Close it to stop.
REM (Ollama normally runs by itself in the Windows tray after install.)
REM ===================================================================
cd /d "%~dp0backend"
call .venv\Scripts\activate

REM Wait 4 seconds so the server is ready, then open the browser.
start "" cmd /c "timeout /t 4 >nul & start http://127.0.0.1:8000"

python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
