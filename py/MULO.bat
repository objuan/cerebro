@echo off
REM ======================================
REM Binance Ticker OHLC Stream Launcher
REM ======================================

REM Vai nella cartella del progetto
cd /d "C:\\Lavoro\\cerebro\\py"

REM Attiva virtualenv
call .\venv\Scripts\activate.bat

REM Avvia script
echo Starting ...
C:/Lavoro/cerebro/py/.venv/Scripts/python.exe c:/Lavoro/cerebro/py/app/tws_batch.py

REM Se crasha, logga
echo Process exited at %date% %time% >> "%LOGFILE%"
pause