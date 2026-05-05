@echo off
REM ======================================
REM 
REM ======================================

REM Vai nella cartella del progetto
cd /d "C:\\Lavoro\\cerebro\\py\\frontend"


REM Avvia script
echo Starting ...
set VUE_APP_API_URL=localhost:9000&&set VUE_APP_MODE=BINANCE&& npm  run serve -- --port 9080

REM Se crasha, logga
echo Process exited at %date% %time% >> "%LOGFILE%"
pause