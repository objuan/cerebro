
import time
import json
import csv
import os
from typing import List, Dict, Any, Optional
import importlib
import traceback
import sys
import schedule
import argparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

MODULE_NAME = "fineco_module"  # nome del modulo senza .py
CHECK_INTERVAL = 1.0           # secondi tra un controllo e l’altro

URL = "https://tradingplatform.finecobank.com/"

div_name ='//*[@id="main-app"]/div[2]/div/div/div[5]'


class Context:
    module = None
ctx = Context()
last_mtime = None
driver = None

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

def login():
    driver.get(URL)
    wait = WebDriverWait(driver, 30)
    html = driver.page_source
    user_xpath = '//*[@id="login-app"]/div/form/input[1]'
    pwd_xpath = '//*[@id="login-app"]/div/form/input[2]'
    login_xpath = '//*[@id="login-app"]/div/form/button[1]'
    
    input_elem = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, user_xpath))
    )
    input_elem.send_keys("76909523")
    input_elem = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, pwd_xpath))
    )
    input_elem.send_keys("Alicepi7")
    btn_elem = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, login_xpath))
    )
    btn_elem.click()

def main():
    parser = argparse.ArgumentParser(description="Fineco live")
    parser.add_argument("-t", "--test", action="store_true", help="modo test", default=True)
    args = parser.parse_args()
    logger.info("Fineco Live")
    logger.info(f"TEST :{args.test}")
    
    global module
    global driver
    global ctx
    global last_mtime

    path = MODULE_NAME + ".py"
    if not os.path.exists(path):
        print(f"[Watcher] ERRORE: file {path} non trovato.")
        sys.exit(1)

    ctx.module = load_module()
    last_mtime = os.path.getmtime(path)

    driver = start_driver(headless=False)  # metti True se vuoi headless
    driver.get(URL)

    wait = WebDriverWait(driver, 30)

    #login()

    ctx.module.init(driver,args.test)

   # Timeout attesa per caricamento dinamico - puoi aumentare se la piattaforma è lenta
    try:
        # Aspetta che qualcosa di riconoscibile appaia: titolo, div principale, o tabella
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except Exception as e:
        print("Attenzione: la pagina potrebbe non aver caricato completamente:", e)

    time.sleep(2)  # piccolo ritardo extra per JS

    ########################################
    def job_1s():
        global ctx
        global last_mtime
        try:
            time.sleep(CHECK_INTERVAL)
            new_mtime = os.path.getmtime(path)
            if new_mtime != last_mtime:
                print(f"[Watcher] Rilevata modifica su {path}, ricarico...")
                last_mtime = new_mtime
                ctx.module = load_module()
                ctx.module.init(driver,args.test)

                if (args.test):
                    ctx.module.event_8_30()

            else:
                ctx.module.tick_1s()
                
            # Esempio: se il modulo espone una funzione main(), la puoi richiamare:
            if ctx.module and hasattr(ctx.module, "main"):
                try:
                    ctx.module.main()
                except Exception:
                    traceback.print_exc()

        except KeyboardInterrupt:
            print("\n[Watcher] Interrotto dall’utente, esco.")
        except Exception:
            traceback.print_exc()


    def job_8_30():
        try:
            global ctx
            logger.info("TASK 8:30")
            login()
            ctx.module.event_8_30()
        except:
            logger.error("job_8_30", exc_info=True)

    def job_18_00():
        global ctx
        logger.info("TASK 18:00")
        ctx.module.event_18_00()

        exit_xpath= '//*[@id="main-app"]/div[1]/div[3]/div/button[5]'
        ele = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, exit_xpath))
        )
        ele.click()
            
        confirm_xpath='/html/body/div[3]/div/div[4]/button[2]'
        ele = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, confirm_xpath))
        )
        ele.click()

        time.sleep(10)
        driver.get("https://www.google.com/")

    ########################################

    try:
        schedule.every(1).seconds.do(job_1s)
        schedule.every().day.at("08:55:00").do(job_8_30)
        schedule.every().day.at("18:00:00").do(job_18_00)

        #schedule.every().day.at("08:33:00").do(job_8_30)

        #schedule.every().day.at("16:09:00").do(job_8_30)
        #schedule.every().day.at("16:08:00").do(job_18_00)

        print("Scheduler avviato. Premi Ctrl+C per uscire.")

        if (args.test):
            job_8_30()
        

        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterruzione ricevuta. Uscita in corso...")

    finally:
        try:
            driver.quit()
            print("Browser chiuso correttamente.")
        except Exception:
            print("Browser già chiuso o non inizializzato.")


if __name__ == "__main__":
    main()