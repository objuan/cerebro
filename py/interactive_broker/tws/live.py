from ib_insync import *

# Create an IB object
ib = IB()

# Connect to TWS (use '127.0.0.1' and port 7497 for demo, 7496 for live trading)
ib.connect('127.0.0.1', 7496, clientId=1)

# Define a contract (VALE stock on SMART exchange, traded in USD)
contract = Stock('VALE', 'SMART', 'USD')

# Request market data for the contract
market_data = ib.reqMktData(contract)

# Function to print market data
def print_data():
    if market_data:
        print(f"Bid: {market_data.bid}, Ask: {market_data.ask}, Last: {market_data.last}")
    else:
        print("No market data received.")

# Stream market data in a loop
try:
    while True:
        ib.sleep(1)  # Sleep for 1 second and wait for updates
        print_data()  # Print the latest market data
except KeyboardInterrupt:
    # Gracefully disconnect on exit
    print("Disconnecting from TWS...")
    ib.disconnect()