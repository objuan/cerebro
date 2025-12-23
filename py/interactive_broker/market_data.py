import requests
import urllib3
# Disabilita warning HTTPS non verificato (tipico di IBKR localhost)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Base URL IBKR Client Portal Gateway
baseUrl = "https://localhost:5000/v1/api"

# Endpoint scanner params
request_url = f"{baseUrl}/iserver/marketdata/snapshot?conids=265598,8314&fields=31,84,86"


# Sessione (OBBLIGATORIA per mantenere i cookie)
session = requests.Session()

# ⚠️ Se usi HTTPS self-signed (default IBKR)
response = session.get(
    url=request_url,
    verify=False  # necessario con certificato IBKR
)

# Controllo risposta
if response.status_code == 200:
    output_file = "aa.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(response.text)

    print(f"Scanner parameters salvati in {output_file}")
else:
    print("Errore nella richiesta")
    print("Status:", response.status_code)
    print("Response:", response.text)