import requests

# Base URL IBKR Client Portal Gateway
baseUrl = "https://localhost:5000/v1/api"

# Endpoint scanner params
request_url = f"{baseUrl}/iserver/scanner/params"

# Sessione (OBBLIGATORIA per mantenere i cookie)
session = requests.Session()

# ⚠️ Se usi HTTPS self-signed (default IBKR)
response = session.get(
    url=request_url,
    verify=False  # necessario con certificato IBKR
)

# Controllo risposta
if response.status_code == 200:
    output_file = "scanner_params.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(response.text)

    print(f"Scanner parameters salvati in {output_file}")
else:
    print("Errore nella richiesta")
    print("Status:", response.status_code)
    print("Response:", response.text)