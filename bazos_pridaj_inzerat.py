#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bazoš.sk – automatizácia pridávania inzerátov (Selenium).

Migrácia z pyautogui (pevné súradnice pixelov, Linux-only) na Selenium:
    - nezávislé od OS a rozlíšenia obrazovky
    - vyhľadávanie elementov cez HTML DOM (By.NAME, XPath)
    - priame nahrávanie fotiek do <input type="file"> (bez OS dialógu)
    - citlivé údaje v .env (gitignored)

Verzia 2: podpora overenia telefónu (SMS kľúč) – Bazoš ho vyžaduje PRED
zobrazením formulára inzerátu; SMS kód zadáva používateľ interaktívne.

Verzia 3:
    - výhradne Microsoft Edge (bez Chrome / bez inštalácie Chrome driveru)
    - navigácia cez menu kategórie ako bežný používateľ (priamy vstup na
      /pridat-inzerat.php môže Bazoš obslúžiť prehľadom kategórie)
    - pri nezobrazenej forme sa presne zaloguje, čo stránka vrátila

Zdroj: docs/gemini-report-bazos-migracia.md (report od Gemini)
"""
import os
import time
import logging
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Edge driver cez explicitný webdriver-manager (obchádza zamrznutie
# natívneho Selenium Manageru na Windows)
from selenium.webdriver.edge.service import Service as EdgeService
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
# 2a. URL (zistené 29.8.2026 – curl + reálny prehliadač)
# ==========================================
#   https://pc.bazos.sk/pridat-inzerat.php  – UPLOAD (overenie → formulár inzerátu)
#   https://www.bazos.sk/pridat-inzerat.php – NEVIE upload (vracia prehľad)
#   https://pc.bazos.sk/                    – prehľad kategórie PC
#   https://www.bazos.sk/                   – hlavná stránka
# Pozor: priamy vstup na /pridat-inzerat.php bez plných hlavičiek vracia
# prehľad kategórie namiesto formulára → navigujeme cez menu ako bežný
# používateľ (referrer + cookies sa nastavia prirodzene).
URL_KATEGORIA_PC = "https://pc.bazos.sk/"
URL_PRIDAT_INZERAT = "https://pc.bazos.sk/pridat-inzerat.php"

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

# Ako dlho čakať na pole pre SMS kód po odoslaní overenia (sekundy).
# SMS z Bazoša môže prísť aj po 1 minúte.
SMS_CEKANIE_SEKUND = 120

# ==========================================
# 2c. REÁLNE ELEMENTY STRÁNKY (zistené 29.8.2026)
# ==========================================
# A) OVERENIE TELEFÓNU – zobrazí sa PRED formulárom inzerátu:
#    form  name="formovereni"  action="/pridat-inzerat.php"
#    input name="podminky"  id="podminky"  type="checkbox"  – súhlas s podmienkami
#    input name="teloverit" id="teloverit" type="text"      – telefónne číslo
#    input name="Submit"    type="submit"  value="Odoslať"  – odoslať SMS kľúč
#
# Po odoslaní príde na telefón SMS kľúč a stránka zobrazí pole pre kód.
# Jeho názov stránka nedáva dopredu poznať – skript ho DETEKUJE dynamicky
# (prvý nový viditeľný textový input, ktorý nie je teloverit).
#
# B) FORMULÁR INZERÁTU – objaví sa až po úspešnom overení telefónu:
#    nadpis, popis, cena, psc, jmeno, telefon, heslo
#    + input[type="file"] pre fotky + tlačidlo na odoslanie inzerátu

# ==========================================
# 3. SPUSTENIE PREHLIADAČA (EDGE, BEZ CHROME)
# ==========================================
def ziskaj_prehliadac():
    """Spustí Microsoft Edge cez explicitný webdriver-manager (bez Chrome)."""
    logging.info("Sťahujem/overujem Edge driver cez webdriver-manager...")
    try:
        cesta_k_driveru = EdgeChromiumDriverManager().install()
        options = webdriver.EdgeOptions()
        options.add_argument("--lang=sk-SK")  # slovenský Accept-Language
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        return webdriver.Edge(service=EdgeService(cesta_k_driveru), options=options)
    except Exception as e:
        logging.error(f"Kritická chyba: Edge sa nepodarilo spustiť. Log: {e}")
        raise

# ==========================================
# 4. NAVIGÁCIA (CEZ MENU – AKO BEŽNÝ POUŽÍVATEĽ)
# ==========================================
def odsuhlas_cookies(driver):
    """Najlepšie úsilie: klikne na tlačidlo 'Súhlasím' v cookie dialógu, ak existuje."""
    try:
        for tlacidlo in driver.find_elements(By.TAG_NAME, "button"):
            text = (tlacidlo.text or "").lower()
            if "súhlas" in text or "souhlas" in text:
                tlacidlo.click()
                logging.info("Cookie dialóg: kliknuté na súhlas.")
                return
    except Exception:
        pass


def naviguj_na_pridanie(driver):
    """Otvori kategóriu PC a klikne na 'Pridať inzerát' v hlavičke.

    Priamy driver.get() na /pridat-inzerat.php môže Bazoš obslúžiť prehľadom
    kategórie namiesto formulára – navigácia cez menu tomu predchádza.
    """
    logging.info(f"Otvaram kategóriu PC: {URL_KATEGORIA_PC}")
    driver.get(URL_KATEGORIA_PC)
    odsuhlas_cookies(driver)

    odkaz = None
    for a in driver.find_elements(By.TAG_NAME, "a"):
        if (a.text or "").strip() == "Pridať inzerát":
            odkaz = a
            break

    if odkaz is None:
        logging.warning("Odkaz 'Pridať inzerát' sa v hlavičke nenašiel – idem priamo na URL.")
        driver.get(URL_PRIDAT_INZERAT)
    else:
        logging.info(f"Klikám na 'Pridať inzerát' ({odkaz.get_attribute('href')})")
        odkaz.click()


# ==========================================
# 5. OVERENIE TELEFÓNU (SMS KĽÚČ)
# ==========================================
def najdi_pole_kodu(driver, casovy_limit=SMS_CEKANIE_SEKUND):
    """Dynamicky nájde pole pre SMS kód (prvý nový textový input ≠ teloverit).

    Vráti element, alebo None po vypršaní limitu.
    """
    koniec = time.time() + casovy_limit
    while time.time() < koniec:
        try:
            # Ak sa objavil rovno formulár inzerátu, overenie netreba riešiť
            if driver.find_elements(By.NAME, "nadpis"):
                return None
            for inp in driver.find_elements(By.TAG_NAME, "input"):
                typ = (inp.get_attribute("type") or "text").lower()
                meno = (inp.get_attribute("name") or "").lower()
                if typ in ("text", "tel", "number") and "teloverit" not in meno and inp.is_displayed():
                    return inp
        except Exception:
            pass
        time.sleep(1)
    return None


def over_telefon(driver, wait, telefon):
    """Vyplní Bazoš overovací formulár a nechá používateľa zadať SMS kód.

    Vráti True, ak prebehlo overenie (alebo už bolo hotové), False pri chybe.
    """
    odsuhlas_cookies(driver)

    try:
        pole = wait.until(EC.presence_of_element_located((By.NAME, "teloverit")))
    except TimeoutException:
        # Už overené – rovno formulár inzerátu?
        if driver.find_elements(By.NAME, "nadpis"):
            logging.info("Overenie telefónu sa nevyžaduje – formulár inzerátu je k dispozícii.")
            return True
        # Diagnostika: čo nám Bazoš vlastne vrátil?
        try:
            nazvy = [i.get_attribute("name") or "?" for i in driver.find_elements(By.TAG_NAME, "input")][:15]
        except Exception:
            nazvy = []
        logging.error(f"Neočakávaná stránka – URL: {driver.current_url}")
        logging.error(f"Titulok: {driver.title}")
        logging.error(f"Nájdené inputy: {nazvy}")
        raise RuntimeError(
            "Bazoš neukázal overovací formulár (teloverit) ani formulár inzerátu (nadpis) – "
            "pravdepodobne bot-detekcia. Pošli log vyššie na analýzu."
        )

    logging.info("Bazoš vyžaduje overenie mobilného telefónu – vyplňujem overovací formulár...")
    try:
        driver.find_element(By.NAME, "podminky").click()
        logging.info("Zaškrtnutý súhlas s podmienkami.")
    except Exception as e:
        logging.warning(f"Checkbox podmienok sa nepodarilo zaškrtnúť: {e}")

    pole.clear()
    pole.send_keys(telefon)
    logging.info(f"Telefón {telefon} zadaný. Odosielam overenie – SMS kľúč príde na toto číslo.")
    driver.find_element(By.NAME, "Submit").click()

    logging.info(f"Čakám na pole pre SMS kód (limit {SMS_CEKANIE_SEKUND}s)...")
    pole_kodu = najdi_pole_kodu(driver)

    if pole_kodu is None:
        # Skontrolujeme, či stránka nenahlásila chybu
        try:
            text_stranky = driver.find_element(By.TAG_NAME, "body").text.lower()
            if any(s in text_stranky for s in ("chybné telefónne", "chyba", "neplatné")):
                logging.error("Bazoš nahlásil chybu pri overení telefónu – skontroluj číslo v .env.")
                return False
        except Exception:
            pass
        logging.warning("Pole pre SMS kód sa nenašlo automaticky.")
        input("[MANUÁLNE] Ak sa v prehliadači objavilo pole pre kód, zadaj kód RUČNE "
              "a potvrď ho, potom stlač ENTER...")
        return True

    logging.info(f"Našiel som pole pre SMS kód (name='{pole_kodu.get_attribute('name') or '?'}').")
    kod = input(f"[SMS] Kód prišiel na číslo {telefon}. Zadaj ho sem a stlač ENTER: ").strip()
    if not kod:
        logging.warning("Nezadaný kód – skúšam pokračovať bez neho.")
    pole_kodu.send_keys(kod)
    logging.info("Kód vyplnený, potvrdzujem odoslanie...")

    try:
        # Potvrdzovacie tlačidlo hľadáme v tom istom formulári ako pole kódu
        form = pole_kodu.find_element(By.XPATH, "./ancestor::form")
        tlacidlo = form.find_element(By.XPATH, ".//input[@type='submit'] | .//button[@type='submit']")
        tlacidlo.click()
    except Exception as e:
        logging.warning(f"Tlačidlo na potvrdenie kódu sa nenašlo automaticky ({e}).")
        input("[MANUÁLNE] Potvrď kód v prehliadači a stlač ENTER...")
    return True


# ==========================================
# 6. VYPLNENIE FORMULÁRA INZERÁTU
# ==========================================
def vypln_inzerat(driver, wait):
    """Počká na formulár inzerátu a vyplní ho (aj fotku)."""
    logging.info("Čakám na formulár inzerátu (element 'nadpis')...")
    wait.until(EC.presence_of_element_located((By.NAME, "nadpis")))

    logging.info("Vyplňujem textové polia inzerátu...")
    driver.find_element(By.NAME, "nadpis").send_keys(INZERAT_NADPIS)
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


# ==========================================
# 7. HLAVNÝ EXEKUČNÝ BLOK
# ==========================================
def pridaj_inzerat_bazos():
    driver = None
    try:
        driver = ziskaj_prehliadac()
        driver.maximize_window()

        # Navigácia cez menu (kategória PC -> Pridať inzerát)
        naviguj_na_pridanie(driver)

        wait = WebDriverWait(driver, 15)

        # 1) Overenie telefónu (ak ho Bazoš vyžaduje)
        if not over_telefon(driver, wait, TELEFON):
            return

        # 2) Vyplnenie formulára inzerátu (po overení sa objaví)
        vypln_inzerat(driver, WebDriverWait(driver, 30))

        if DEBUG_CEKANIE:
            input("\n[DEBUG] Stlač ENTER pre ukončenie testu...\n")
        else:
            # Pre produkčné nasadenie odomknúť:
            # driver.find_element(By.NAME, "odeslat").click()
            pass

    except TimeoutException:
        logging.error("SKRIPT ZAMRZOL: Vypršal limit pre načítanie stránky alebo elementu.")
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
