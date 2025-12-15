from ib_insync import IB, Stock

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)
# 7497 = TWS paper trading
# 7496 = TWS reale

contract = Stock('AAPL', 'SMART', 'USD')
ib.qualifyContracts(contract)

ticker = ib.reqMktData(contract)

ib.sleep(2)
print("Last:", ticker.last)
print("Bid:", ticker.bid)
print("Ask:", ticker.ask)