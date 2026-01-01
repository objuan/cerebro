@echo off
REM ======================================
REM 
REM ======================================

REM Vai nella cartella del progetto
cd /d "C:\\Lavoro\\cerebro\\py\\frontend"


REM Avvia script
echo Starting ...
npm  run serve

REM Se crasha, logga
echo Process exited at %date% %time% >> "%LOGFILE%"
pause