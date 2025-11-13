
import time
import json
import csv
import os
from typing import List, Dict, Any, Optional
import importlib
import traceback
import sys
import schedule

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd

MODULE_NAME = "fineco_module"  # nome del modulo senza .py
CHECK_INTERVAL = 1.0           # secondi tra un controllo e l’altro

URL = "https://tradingplatform.finecobank.com/"

div_name ='//*[@id="main-app"]/div[2]/div/div/div[5]'

def load_module():
    """Importa o ricarica dinamicamente il modulo."""
    try:
        if MODULE_NAME in sys.modules:
            print(f"[Watcher] Ricarico modulo '{MODULE_NAME}'...")
            return importlib.reload(sys.modules[MODULE_NAME])
        else:
            print(f"[Watcher] Importo modulo '{MODULE_NAME}'...")
            return importlib.import_module(MODULE_NAME)
    except Exception as e:
        print(f"[Watcher] Errore durante il caricamento del modulo: {e}")
        traceback.print_exc()
        return None


def start_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")   # headless moderno
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    # evita detection banale
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)
    # optionally reduce telemetry
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """
    })
    return driver

def main():
    path = MODULE_NAME + ".py"
    if not os.path.exists(path):
        print(f"[Watcher] ERRORE: file {path} non trovato.")
        sys.exit(1)

    module = load_module()
    last_mtime = os.path.getmtime(path)

    driver = start_driver(headless=False)  # metti True se vuoi headless
    driver.get(URL)

    wait = WebDriverWait(driver, 30)

    module.init(driver)
    # Timeout attesa per caricamento dinamico - puoi aumentare se la piattaforma è lenta
    try:
        # Aspetta che qualcosa di riconoscibile appaia: titolo, div principale, o tabella
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except Exception as e:
        print("Attenzione: la pagina potrebbe non aver caricato completamente:", e)

    time.sleep(2)  # piccolo ritardo extra per JS

    html = driver.page_source
    #soup = BeautifulSoup(html, "html.parser")

    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            new_mtime = os.path.getmtime(path)
            if new_mtime != last_mtime:
                print(f"[Watcher] Rilevata modifica su {path}, ricarico...")
                last_mtime = new_mtime
                module = load_module()
                module.init(driver)
            else:
                module.tick()
                
            # Esempio: se il modulo espone una funzione main(), la puoi richiamare:
            if module and hasattr(module, "main"):
                try:
                    module.main()
                except Exception:
                    traceback.print_exc()

        except KeyboardInterrupt:
            print("\n[Watcher] Interrotto dall’utente, esco.")
            break
        except Exception:
            traceback.print_exc()

if __name__ == "__main__":
    main()