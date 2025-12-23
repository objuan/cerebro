from ib_insync import *

# Create an IB object
ib = IB()

# Connect to TWS (use '127.0.0.1' and port 7497 for demo, 7496 for live trading)
ib.connect('127.0.0.1', 7497, clientId=1)

# Define a contract (VALE stock on SMART exchange, traded in USD)
#contract = Stock('VALE', 'SMART', 'USD')

def onBar1Update(bars, bar):
    print('AAPL', bars[-1], bar)

def onBar2Update(bars, bar):
    print('MSFT', bars[-1], bar)

contract1 = Stock('AAPL', 'SMART', 'USD')
contract2 = Stock('MSFT', 'SMART', 'USD')

bars1 = ib.reqHistoricalData(contract1, endDateTime='', durationStr='1 D'
    , barSizeSetting='5 secs', whatToShow='TRADES', useRTH=False, keepUpToDate=True)
bars2 = ib.reqHistoricalData(contract2, endDateTime='', durationStr='1 D'
    , barSizeSetting='5 secs', whatToShow='TRADES', useRTH=False, keepUpToDate=True)
bars1.updateEvent += onBar1Update
bars2.updateEvent += onBar2Update