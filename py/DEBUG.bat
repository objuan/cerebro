@echo off
REM ======================================
REM Binance Ticker OHLC Stream Launcher
REM ======================================

REM Vai nella cartella del progetto
cd /d "C:\\Lavoro\\cerebro\\py\\APP"

REM Attiva virtualenv
call ..\.venv\Scripts\activate.bat

REM Avvia script
echo Starting ...
uvicorn webapp:app  --reload

REM Se crasha, logga
echo Process exited at %date% %time% >> "%LOGFILE%"
pause