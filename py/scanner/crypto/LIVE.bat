@echo off
REM ======================================
REM Binance Ticker OHLC Stream Launcher
REM ======================================

REM Vai nella cartella del progetto
cd /d "C:\\Lavoro\\cerebro\\py"

REM Crea cartella log se non esiste
if not exist logs (
    mkdir logs
)

REM Timestamp per log
for /f "tokens=1-3 delims=/- " %%a in ("%date%") do (
    set DATE=%%c-%%b-%%a
)
for /f "tokens=1-2 delims=: " %%a in ("%time%") do (
    set TIME=%%a%%b
)

set LOGFILE=logs\crypto_stream_%DATE%_%TIME%.log

REM Attiva virtualenv
call .venv\Scripts\activate.bat

REM Avvia script
echo Starting Binance stream...
python scanner/crypto/binance_all_tickers_ws.py 
rem >> "%LOGFILE%" 2>&1

REM Se crasha, logga
echo Process exited at %date% %time% >> "%LOGFILE%"
pause