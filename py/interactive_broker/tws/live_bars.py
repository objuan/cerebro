from ib_insync import *
import asyncio
util.startLoop()   # 🔑 IMPORTANTISSIMO

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

contract = Stock('AAPL', 'SMART', 'USD')
ib.qualifyContracts(contract)

bars = ib.reqRealTimeBars(
    contract,
    barSize=5,
    whatToShow='TRADES',
    useRTH=True
)

def onBarUpdate(bars, hasNewBar):
    if hasNewBar:
        bar = bars[-1]
        print(bar.time, bar.close)

bars.updateEvent += onBarUpdate

ib.run()