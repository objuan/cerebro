from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import threading
import time

HOST = "127.0.0.1"
PORT = 7497      # 7497 = TWS paper, 7496 = TWS live
CLIENT_ID = 1001


class TestApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId: int):
        print("Connected. Requesting scanner parameters...")
        self.reqScannerParameters()

    def scannerParameters(self, xml: str):
        path = r"scanner.xml"
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)
        print(f"Scanner parameters saved to {path}")

        # chiudi connessione dopo aver ricevuto i dati
        self.disconnect()


def run_loop(app):
    app.run()


if __name__ == "__main__":
    app = TestApp()
    app.connect(HOST, PORT, CLIENT_ID)

    # IB API DEVE girare in un thread separato
    api_thread = threading.Thread(target=run_loop, args=(app,), daemon=True)
    api_thread.start()

    # attesa minima per stabilizzare la connessione
    time.sleep(1)

    while app.isConnected():
        time.sleep(1)