import requests

TOKEN = "8608036065:AAHJbCC91f40pBeeP7jJtP2J1TPu0OgJUjY"
CHAT_ID = "5831322272"

NAME="@Cerebro"
USER ="objuan_bot"

def send_telegram_message(message):
    #messaggio = "Ciao! Questo messaggio viene da Python 🚀"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
 
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message
    })

    #print(response.json())