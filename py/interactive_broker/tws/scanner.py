from ib_insync import *
util.startLoop()  # uncomment this line when in a notebook

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)


sub = ScannerSubscription(
    numberOfRows=50,
    instrument='STK',
    locationCode='STK.US.MAJOR',
    scanCode='TOP_PERC_GAIN', marketCapAbove= 1_000_000 , abovePrice= 100, aboveVolume= 100000
)

scanData = ib.reqScannerData(sub)

df = util.df(scanData)


def display_with_stock_symbol(scanData):
    df = util.df(scanData)
    df["contract"] = df.apply( lambda l:l['contractDetails'].contract,axis=1)
    df["symbol"] = df.apply( lambda l:l['contract'].symbol,axis=1)
    return df[["rank","contractDetails","contract","symbol"]]

print(display_with_stock_symbol(scanData))


ticker_dict = {}

#delayed
ib.reqMarketDataType(3)

for contract in display_with_stock_symbol(scanData).contract.tolist():
    ticker_dict[contract] = ib.reqMktData(
        contract=contract,
        genericTickList="",
        snapshot=False,#True,
        regulatorySnapshot=False
    )
ib.sleep(2)

print(ticker_dict)