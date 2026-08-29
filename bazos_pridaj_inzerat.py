#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bazoš.sk – automatizácia pridávania inzerátov (Selenium).

Migrácia z pyautogui (pevné súradnice pixelov, Linux-only) na Selenium:
    - nezávislé od OS a rozlíšenia obrazovky
    - vyhľadávanie elementov cez HTML DOM (By.NAME, XPath)
    - priame nahrávanie fotiek do <input type="file"> (bez OS dialógu)
    - citlivé údaje v .env (gitignored)

Zdroj: docs/gemini-report-bazos-migracia.md (report od Gemini)
"""
import os
import logging
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Explicitný webdriver-manager (obchádza zamrznutie natívneho Selenium Manageru)
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# ==========================================
# 1. KONFIGURÁCIA LOGOVANIA
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# ==========================================
# 2. NAČÍTANIE PREMENNÝCH Z .env
# ==========================================
load_dotenv()
MENO = os.getenv("BAZOS_MENO")
TELEFON = os.getenv("BAZOS_TELEFON")
HESLO = os.getenv("BAZOS_HESLO")
PSC = os.getenv("BAZOS_PSC")

if not all([MENO, TELEFON, HESLO, PSC]):
    logging.warning("Niektoré hodnoty v .env chýbajú (BAZOS_MENO / BAZOS_TELEFON / BAZOS_HESLO / BAZOS_PSC)!")

# Dynamické cesty (nezávislé od OS / aktuálneho adresára)
AKTUALNA_ZLOZKA = os.path.dirname(os.path.abspath(__file__))
CESTA_K_FOTKE = os.path.join(AKTUALNA_ZLOZKA, "obrazky", "server_foto1.jpg")

# ==========================================
# 2b. TESTOVACIE DÁTA INZERÁTU
# (v ďalšej fáze nahradené parsovaním šablónových textov inzerátov)
# ==========================================
INZERAT_NADPIS = "Repasovaný Dell PowerEdge Server - Záruka"
INZERAT_POPIS = "Plne funkčný, vyčistený a pretestovaný enterprise server vhodný do racku."
INZERAT_CENA = "250"

# [DEBUG] True  = formulár sa vyplní a čaká na ENTER (inzerát sa NEODOŠLE).
#         False = odošle formulár (production režim).
DEBUG_CEKANIE = True

# ==========================================
# 3. SPUSTENIE PREHLIADAČA (BYPASS WINAPI BUGU)
# ==========================================
def ziskaj_prehliadac():
    """Pokúsi sa spustiť Chrome (fallback Edge) cez explicitný webdriver-manager."""
    logging.info("Sťahujem/overujem ovládače cez webdriver-manager...")

    try:
        logging.info("Skúšam inicializovať Chrome...")
        cesta_k_driveru = ChromeDriverManager().install()
        return webdriver.Chrome(service=ChromeService(cesta_k_driveru))
    except Exception as e:
        logging.warning(f"Chrome zlyhal: {e}")

    try:
        logging.info("Skúšam inicializovať Edge...")
        cesta_k_driveru = EdgeChromiumDriverManager().install()
        return webdriver.Edge(service=EdgeService(cesta_k_driveru))
    except Exception as e:
        logging.error(f"Kritická chyba: Žiadny prehliadač sa nepodarilo spustiť. Log: {e}")
        raise

# ==========================================
# 4. HLAVNÝ EXEKUČNÝ BLOK
# ==========================================
def pridaj_inzerat_bazos():
    driver = None
    try:
        driver = ziskaj_prehliadac()
        driver.maximize_window()

        logging.info("Navigujem priamo na URL formulára Bazoš.sk (PC kategória)...")
        driver.get("https://pc.bazos.sk/pridat-inzerat.php")

        wait = WebDriverWait(driver, 10)

        logging.info("Čakám na DOM element 'nadpis'...")
        nadpis_element = wait.until(EC.presence_of_element_located((By.NAME, "nadpis")))

        logging.info("Vyplňujem textové polia inzerátu...")
        nadpis_element.send_keys(INZERAT_NADPIS)
        driver.find_element(By.NAME, "popis").send_keys(INZERAT_POPIS)
        driver.find_element(By.NAME, "cena").send_keys(INZERAT_CENA)
        driver.find_element(By.NAME, "psc").send_keys(PSC)
        driver.find_element(By.NAME, "jmeno").send_keys(MENO)
        driver.find_element(By.NAME, "telefon").send_keys(TELEFON)
        driver.find_element(By.NAME, "heslo").send_keys(HESLO)

        logging.info(f"Odosielam súbor z cesty: {CESTA_K_FOTKE}")
        if os.path.exists(CESTA_K_FOTKE):
            # Nahrávanie obchádza OS dialóg – vkladá sa priamo do input tagu.
            upload_input = driver.find_element(By.XPATH, "//input[@type='file']")
            upload_input.send_keys(CESTA_K_FOTKE)
            logging.info("Fotka bola úspešne priradená k formuláru.")
        else:
            logging.warning("Súbor s fotkou NEEXISTUJE! Krok s fotkou bol preskočený.")

        logging.info("DOKONČENÉ: Formulár bol úspešne vyplnený.")

        if DEBUG_CEKANIE:
            input("\n[DEBUG] Stlač ENTER pre ukončenie testu...\n")
        else:
            # Pre produkčné nasadenie odomknúť:
            # driver.find_element(By.NAME, "odeslat").click()
            pass

    except TimeoutException:
        logging.error("SKRIPT ZAMRZOL: Vypršal 10s limit pre načítanie stránky alebo elementu.")
    except NoSuchElementException as e:
        logging.error(f"SKRIPT ZAMRZOL: Element nebol v DOM štruktúre nájdený. Detaily: {e.msg}")
    except Exception as e:
        logging.error(f"Neočakávaná chyba pri exekúcii: {e}")
    finally:
        if driver:
            logging.info("Bezpečne ukončujem inštanciu WebDrivera...")
            driver.quit()

if __name__ == "__main__":
    pridaj_inzerat_bazos()
