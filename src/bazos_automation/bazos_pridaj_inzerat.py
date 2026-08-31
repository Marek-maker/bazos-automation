#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bazoš.sk – automatizácia pridávania inzerátov (Selenium).

Migrácia z pyautogui (pevné súradnice pixelov, Linux-only) na Selenium:
    - nezávislé od OS a rozlíšenia obrazovky
    - vyhľadávanie elementov cez HTML DOM (By.NAME, XPath)
    - priame nahrávanie fotiek do upload elementu (bez OS dialógu)

Verzia 2: podpora overenia telefónu (SMS kľúč) – Bazoš ho vyžaduje PRED
zobrazením formulára inzerátu; SMS kód zadáva používateľ interaktívne.
Verzia 3: Edge-only + navigácia cez menu + logovanie nezobrazenej formy.
Verzia 4: flag --debug (predĺžené limity + DEBUG log), --sms-timeout.
Verzia 5: vylúčené vyhľadávacie polia z detekcie kódu, detekcia
         presmerovania na kategóriu, EOF-safe vstup.
Verzia 6: submit overenia scoping do formovereni, preferovaný názov poľa
         pre kód (klic), formulár inzerátu podľa reálneho HTML.
Verzia 7: persistentný Edge profil (edge_profile/), čakanie na dokončenie
         uploadu fotky (dz-success), auto-výber fotky z obrazky/.
Verzia 8: kontaktné polia podľa reálneho HTML (telefoni, heslobazar,
         maili), odoslanie inzerátu scoping do formulára.
Verzia 9: modulárne – modul_sablona.py (texty zo šablóny ###ID),
         modul_upload.py (fotky jedna za druhou s čakaním).
Verzia 10:
    - VŠETKY údaje inzerátu (kategória, nadpis, popis, cena, PSČ, meno,
      telefón, heslo, e-mail) sa berú JEN zo sablona_inzeratu.txt
      (###ID:hodnota) – .env sa už nepoužíva
    - sablona_inzeratu.txt je GITIGNORED (tvoje reálne údaje); do gitu
      ide len sablona_inzeratu.example.txt s dummy dátami

Moduly:
    modul_sablona.py – načítanie šablóny ###ID:hodnota + mapovanie
    modul_upload.py  – Dropzone upload všetkých fotiek jedna za druhou

Zdroj: docs/gemini-report-bazos-migracia.md (report od Gemini)
"""
import os
import sys
import time
import shutil
import logging
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Edge driver cez explicitný webdriver-manager (obchádza zamrznutie
# natívneho Selenium Manageru na Windows)
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager

# Vlastné moduly
from .modul_sablona import MAPPING, nacitaj_sablona
from .modul_upload import nahraj_fotky

# ==========================================
# 1. KONFIGURÁCIA LOGOVANIA
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# ==========================================
# 2. ŠABLÓNA INZERÁTU (JEDINÝ ZDROJ ÚDAJOV)
# ==========================================
# Všetky údaje inzerátu žijú v sablona_inzeratu.txt (###ID:hodnota).
# Tento súbor je GITIGNORED – do gitu ide len sablona_inzeratu.example.txt
# s dummy dátami. Mapovanie ID -> pole: modul_sablona.MAPPING.
# Dáta inzerátu žijú MIMO balíka: sablona_inzeratu.txt, obrazky/,
# edge_profile/ sa hľadajú v poradí: env BAZOS_DATA_DIR -> aktuálny adresár
# (ak obsahuje šablónu) -> ~/.bazos-automation. Takže inštalovaný balík
# nájde tvoje reálne dáta a overený edge_profile bez presúvania.
def zisti_data_dir(explicit=None):
    """Adresár s dátami (sablona_inzeratu.txt, obrazky/, edge_profile/).

    Poradie: explicit (--data-dir) -> env BAZOS_DATA_DIR -> aktuálny adresár
    (ak obsahuje šablónu) -> ~/.bazos-automation (vytvorí sa).
    """
    env = explicit or os.environ.get("BAZOS_DATA_DIR")
    if env:
        return env
    if os.path.exists(os.path.join(os.getcwd(), "sablona_inzeratu.txt")):
        return os.getcwd()
    domov = os.path.join(os.path.expanduser("~"), ".bazos-automation")
    os.makedirs(domov, exist_ok=True)
    return domov


DATA_DIR = zisti_data_dir()
ZLOZKA_OBRAZKOV = os.path.join(DATA_DIR, "obrazky")
CESTA_K_SABLONE = os.path.join(DATA_DIR, "sablona_inzeratu.txt")
PROFIL_EDGE = os.path.join(DATA_DIR, "edge_profile")

SABLONA = nacitaj_sablona(CESTA_K_SABLONE)
TELEFON = SABLONA.get("###07")  # telefón pre overenie aj kontaktné pole

# Povinné polia šablóny – bez nich skript nemá zmysel spúšťať
POVINNE_V_SABLONE = ("###01", "###02", "###03", "###04", "###05", "###06", "###07", "###08")

# [PRODUKČNÝ REŽIM] False = formulár sa odošle (inzerát vznikne na Bazoši).
#         True  = formulár sa vyplní a čaká na ENTER (inzerát sa NEODOŠLE).
DEBUG_CEKANIE = False

# ==========================================
# 2a. URL (zistené 29.8.2026 – curl + reálny prehliadač)
# ==========================================
#   https://pc.bazos.sk/pridat-inzerat.php  – UPLOAD (overenie → formulár inzerátu)
#   https://www.bazos.sk/pridat-inzerat.php – NEVIE upload (vracia prehľad)
#   https://pc.bazos.sk/                    – prehľad kategórie PC
#   https://www.bazos.sk/                   – hlavná stránka
URL_KATEGORIA_PC = "https://pc.bazos.sk/"
URL_PRIDAT_INZERAT = "https://pc.bazos.sk/pridat-inzerat.php"

# ==========================================
# 2b. ČASOVÉ LIMITY (sekundy)
# ==========================================
SMS_CEKANIE_SEKUND = 120           # čakanie na pole pre SMS kód (štandard)
DEBUG_SMS_CEKANIE_SEKUND = 300     # čakanie na pole pre SMS kód s --debug
LIMIT_NACITANIA = 15               # WebDriverWait: overovací formulár
DEBUG_LIMIT_NACITANIA = 45         # s --debug
LIMIT_FORMULARA_INZERATU = 30      # WebDriverWait: formulár inzerátu
DEBUG_LIMIT_FORMULARA_INZERATU = 90  # s --debug
LIMIT_UPLOAD_SEKUND = 60           # čakanie na dokončenie uploadu (na fotku)
DEBUG_LIMIT_UPLOAD_SEKUND = 120    # s --debug
DEBUG_MODE = False                 # zapína flag --debug

# ==========================================
# 2c. REÁLNE ELEMENTY STRÁNKY (zistené 29.–30.8.2026)
# ==========================================
# A) OVERENIE TELEFÓNU – zobrazí sa PRED formulárom inzerátu:
#    form  name="formovereni"  action="/pridat-inzerat.php"
#    input name="podminky"  id="podminky"  type="checkbox"  – súhlas s podmienkami
#    input name="teloverit" id="teloverit" type="text"      – telefónne číslo
#    input name="Submit"    type="submit"  value="Odoslať"  – odoslať SMS kľúč
#    (POZOR: vyhľadávací formulár má tiež input name="Submit" – submit
#     overenia sa kliká VÝHRADNE v rámci formovereni)
#
# Po odoslaní príde na telefón SMS kľúč a stránka zobrazí pole pre kód:
#    input name="klic" – mobilný kľúč (názov zistený reálnym behom)
#
# B) FORMULÁR INZERÁTU – objaví sa až po úspešnom overení telefónu
#    (reálne HTML zistené 30.8.2026):
#    select   name="category"  – kategória (vyberá sa podľa textu zo šablóny)
#    input    name="nadpis"    – nadpis inzerátu
#    textarea name="popis"     – text inzerátu
#    input    name="cena"      – cena v € (+ select name="cenavyber")
#    input    name="lokalita"  – PSČ/obec s autocomplete (naseptavacpscinsert)
#    fotky: Dropzone (button#uploadbutton, div#dropzonea) – JS upload,
#           po každej fotke sa čaká na .dz-success (modul_upload)
#
# C) KONTAKTNÉ ÚDAJE (spodná časť formulára inzerátu, 30.8.2026):
#    input  name="jmeno"      – meno predávajúceho
#    input  name="telefoni"   – telefón (pozor: nie "telefon"!)
#    input  name="maili"      – e-mail (voliteľný, ###09)
#    input  name="heslobazar" – heslo k inzerátu (pozor: nie "heslo"!)
#    odoslanie: input name="Submit" value="Odoslať" – scoping do formulára
#    inzerátu (odosli_inzerat), lebo name="Submit" majú aj iné formuláre

# Polia, ktoré NIE sú poľom pre SMS kód. Vyhľadávací formulár (formt) je na
# KAŽDEJ stránke Bazoša – bez vylúčenia by sa humkreis ("Okolie v km") bral
# ako pole pre kód (reálny bug zistený pri behu 30.8.2026).
VYLUCENE_POLIA = ("teloverit", "hledat", "hlokalita", "humkreis", "cenaod", "cenado")

# ==========================================
# 2d. ARGUMENTY PRÍKAZOVÉHO RIADKA
# ==========================================
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Bazoš automatizácia inzerátov (Selenium, Edge)")
    parser.add_argument("--debug", action="store_true",
                        help="Predĺžené časové limity (SMS čakanie 300 s) a podrobný DEBUG log")
    parser.add_argument("--sms-timeout", type=int, default=None, metavar="SEK",
                        help="Vlastný limit čakania na SMS kód v sekundách (štandardne 120)")
    parser.add_argument("--neodosli", action="store_true",
                        help="Test režim: formulár sa vyplní, inzerát sa NEODOŠLE "
                             "(prepína produkčný režim na tento beh)")
    parser.add_argument("--init", action="store_true",
                        help="Vytvorí sablona_inzeratu.txt z vstavanej example šablóny "
                             "do dátového adresára (ak ešte neexistuje)")
    parser.add_argument("--data-dir", default=None, metavar="CESTA",
                        help="Adresár s dátami (sablona, obrazky, edge_profile). "
                             "Má prednosť pred env BAZOS_DATA_DIR a aktuálnym adresárom.")
    return parser.parse_args(argv)


def nastav_data_dir(adresar):
    """Prepne dátový adresár (flag --data-dir) a prečíta šablónu z neho."""
    global DATA_DIR, ZLOZKA_OBRAZKOV, CESTA_K_SABLONE, PROFIL_EDGE, SABLONA, TELEFON
    DATA_DIR = zisti_data_dir(adresar)
    ZLOZKA_OBRAZKOV = os.path.join(DATA_DIR, "obrazky")
    CESTA_K_SABLONE = os.path.join(DATA_DIR, "sablona_inzeratu.txt")
    PROFIL_EDGE = os.path.join(DATA_DIR, "edge_profile")
    SABLONA = nacitaj_sablona(CESTA_K_SABLONE)
    TELEFON = SABLONA.get("###07")


def inicializuj_sablona(data_dir=None):
    """Vytvorí sablona_inzeratu.txt z example (súčasť balíka) do dátového adresára.

    Example šablóna je zabalená v balíku – čistá inštalácia z PyPI nemá
    súbory z gitu, preto sa šablóna generuje týmto príkazom.
    Vráti 0 pri úspechu, 1 ak už existuje alebo sa kopírovanie nepodarilo.
    """
    data_dir = data_dir or DATA_DIR
    ciel = os.path.join(data_dir, "sablona_inzeratu.txt")
    if os.path.exists(ciel):
        logging.warning(f"Šablóna už existuje: {ciel} – neprepisujem.")
        return 1
    zdroj = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "sablona_inzeratu.example.txt")
    try:
        shutil.copyfile(zdroj, ciel)
    except OSError as e:
        logging.error(f"Šablónu sa nepodarilo vytvoriť: {e}")
        return 1
    logging.info(f"Vytvorená šablóna: {ciel}")
    logging.info("Vyplň ###01–###09 (kategória, nadpis, popis, cena, PSČ, meno, "
                 "telefón, heslo, e-mail) a spusti bazos znova.")
    return 0


def rozhodni_odoslat(neodosli_flag):
    """True = inzerát sa odošle; False = test režim (iba vyplniť).

    Rozhoduje flag --neodosli a konštanta DEBUG_CEKANIE (ktokoľvek z nich
    zapnutý = neodosiela sa).
    """
    return not (DEBUG_CEKANIE or neodosli_flag)


def aktivuj_debug():
    """Zapne DEBUG režim: predĺžené limity a logovacia úroveň DEBUG."""
    global DEBUG_MODE
    DEBUG_MODE = True
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("DEBUG režim: predĺžené časové limity + podrobný log.")


def log_viditelny_text(driver, kontext):
    """Zaloguje viditeľný text stránky (na zachytenie hlášok Bazoša)."""
    try:
        text = " ".join(driver.find_element(By.TAG_NAME, "body").text.split())
        logging.info(f"[{kontext}] Text stránky ({len(text)} zn.): {text[:600]}")
    except Exception as e:
        logging.warning(f"[{kontext}] Text stránky sa nepodarilo načítať: {e}")


def vstup(text):
    """input() s ošetrením EOF – vráti None v neinteraktívnom režime."""
    try:
        return input(text).strip()
    except EOFError:
        return None


def je_kategoria_prehlad(driver):
    """True, ak stránka vyzerá ako prehľad kategórie (zoznam inzerátov).

    Signatúra: stránkovanie 'Stránka: 1 2 3 ...' – na overovacom formulári
    sa nevyskytuje. Bazoš naň presmeruje, keď overenie neprijme.
    """
    try:
        text = driver.find_element(By.TAG_NAME, "body").text.lower()
        return "stránka:" in text
    except Exception:
        return False

# ==========================================
# 3. SPUSTENIE PREHLIADAČA (EDGE, BEZ CHROME)
# ==========================================
def najdi_cached_driver(koren=None):
    """Najnovší msedgedriver.exe v lokálnej cache webdriver-manageru.

    Fallback, keď install() zlyhá (napr. výpadok siete) – cache z predošlých
    behov zvyčajne obsahuje funkčný driver správnej verzie.
    """
    import glob
    koren = koren or os.path.join(os.path.expanduser("~"), ".wdm")
    kandidati = glob.glob(
        os.path.join(koren, "drivers", "edgedriver", "win64", "*", "msedgedriver.exe"))
    if not kandidati:
        return None
    return max(kandidati, key=os.path.getmtime)


def ziskaj_cestu_drivera():
    """Vráti cestu k Edge driveru.

    webdriver-manager s cache valid_range=365 dní (bez toho po 1 dni považuje
    cache za expirovanú a znova sťahuje – reálny bug 31.8.2026, download spadol
    na 'Could not reach host'). Pri zlyhaní install() (výpadok siete) sa použije
    najnovší driver z lokálnej cache.
    """
    try:
        return EdgeChromiumDriverManager(
            cache_manager=DriverCacheManager(valid_range=365)).install()
    except Exception as e:
        logging.warning(f"webdriver-manager zlyhal ({e}) – hľadám driver v lokálnej cache...")
        cesta = najdi_cached_driver()
        if cesta is None:
            logging.error("V cache nie je žiadny msedgedriver.exe – "
                          "skontroluj pripojenie a skús znova.")
            raise
        logging.info(f"Používam driver z lokálnej cache: {cesta}")
        return cesta


def ziskaj_prehliadac():
    """Spustí Microsoft Edge cez explicitný webdriver-manager (bez Chrome)."""
    logging.info("Sťahujem/overujem Edge driver cez webdriver-manager...")
    try:
        cesta_k_driveru = ziskaj_cestu_drivera()
        options = webdriver.EdgeOptions()
        options.add_argument("--lang=sk-SK")  # slovenský Accept-Language
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # Persistentný profil = overenie telefónu (cookies) prežije medzi behmi
        options.add_argument(f"--user-data-dir={PROFIL_EDGE}")
        logging.info(f"Edge profil: {PROFIL_EDGE}")
        return webdriver.Edge(service=EdgeService(cesta_k_driveru), options=options)
    except Exception as e:
        logging.error(f"Kritická chyba: Edge sa nepodarilo spustiť. Log: {e}")
        logging.error(f"Poznámka: ak je profil {PROFIL_EDGE} zamknutý (beží Edge), zatvor ho a skús znova.")
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
    """Dynamicky nájde pole pre SMS kód (prvý nový textový input).

    Vylúčené sú polia vyhľadávacieho formulára (VYLUCENE_POLIA) – tie sú na
    každej stránke a NIE sú to polia pre kód. Vráti element, alebo None.
    """
    zaciatok = time.time()
    koniec = zaciatok + casovy_limit
    while time.time() < koniec:
        try:
            # Ak sa objavil rovno formulár inzerátu, overenie netreba riešiť
            if driver.find_elements(By.NAME, "nadpis"):
                logging.info(f"Objavil sa formulár inzerátu – overenie netreba ({int(time.time() - zaciatok)} s).")
                return None
            # Známy názov poľa pre kód (zistený reálnym behom 30.8.2026) – preferujeme ho
            for meno_zname in ("klic",):
                prvky = driver.find_elements(By.NAME, meno_zname)
                if prvky and prvky[0].is_displayed():
                    logging.info(f"Pole pre SMS kód nájdené po {int(time.time() - zaciatok)} s (name='{meno_zname}').")
                    return prvky[0]
            inputs = driver.find_elements(By.TAG_NAME, "input")
            logging.debug(f"Čakám na SMS kód ({int(time.time() - zaciatok)} s): "
                          + ", ".join(f"{i.get_attribute('name') or '?'}:{i.get_attribute('type') or '?'}"
                                      for i in inputs))
            for inp in inputs:
                typ = (inp.get_attribute("type") or "text").lower()
                meno = (inp.get_attribute("name") or "").lower()
                if typ in ("text", "tel", "number") and meno not in VYLUCENE_POLIA and inp.is_displayed():
                    logging.info(f"Pole pre SMS kód nájdené po {int(time.time() - zaciatok)} s.")
                    return inp
        except Exception:
            pass
        time.sleep(1)
    return None


def over_telefon(driver, wait, telefon, sms_limit=SMS_CEKANIE_SEKUND):
    """Vyplní Bazoš overovací formulár a nechá používateľa zadať SMS kód.

    S persistentným profilom sa overenie uchová medzi behmi – ak je
    telefón už overený, formulár inzerátu sa objaví rovno.

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
        log_viditelny_text(driver, "neočakávaná stránka")
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
    # POZOR: vyhľadávací aj overovací formulár majú input name="Submit" a
    # vyhľadávací je v DOM skôr – bez scoping by sa odoslal "Hľadať" namiesto
    # overenia (reálny bug zistený pri behu 30.8.2026). Klikáme VÝHRADNE
    # v rámci overovacieho formulára (formovereni).
    form_overeni = driver.find_element(By.NAME, "formovereni")
    form_overeni.find_element(By.XPATH, ".//input[@type='submit']").click()
    logging.info(f"Overenie odoslané – aktuálna URL: {driver.current_url}")
    time.sleep(3)  # krátke okno na zachytenie hlášky Bazoša po odoslaní
    log_viditelny_text(driver, "po odoslaní overenia")

    # Bazoš občas overenie neprijme a presmeruje na prehľad kategórie –
    # netreba potom čakať na kód, ktorý nikdy nepríde
    if je_kategoria_prehlad(driver):
        logging.error("Bazoš po odoslaní overenia presmeroval na prehľad kategórie – "
                      "overenie sa neprijalo. Skontroluj ###07 v šablóne a limity SMS.")
        return False

    logging.info(f"Čakám na pole pre SMS kód (limit {sms_limit}s)...")
    pole_kodu = najdi_pole_kodu(driver, casovy_limit=sms_limit)

    if pole_kodu is None:
        log_viditelny_text(driver, "kód neprišiel – text stránky")
        # Skontrolujeme, či stránka nenahlásila chybu (rozšírené kľúčové slová)
        try:
            text_stranky = driver.find_element(By.TAG_NAME, "body").text.lower()
            chybove_vzory = ("chybné telefónne", "chyba", "neplatné", "limit",
                             "prekročen", "už overené", "nepodarilo", "neskôr",
                             "blokovan", "odoslať neskôr")
            if any(s in text_stranky for s in chybove_vzory):
                logging.error("Bazoš nahlásil chybu pri overení telefónu – skontroluj "
                              "###07 v šablóne a limity SMS. Text stránky vyššie ukáže detaily.")
                return False
        except Exception:
            pass
        logging.warning("Pole pre SMS kód sa nenašlo automaticky (SMS možno neprišla).")
        if vstup("[MANUÁLNE] Ak sa v prehliadači objavilo pole pre kód, zadaj kód RUČNE "
                 "a potvrď ho, potom stlač ENTER...") is None:
            return False
        return True

    logging.info(f"Našiel som pole pre SMS kód (name='{pole_kodu.get_attribute('name') or '?'}').")
    kod = vstup(f"[SMS] Kód prišiel na číslo {telefon}. Zadaj ho sem a stlač ENTER: ")
    if kod is None:
        logging.error("Neinteraktívny režim – vstup z terminálu nie je dostupný. "
                      "Spusti skript v bežnom termináli a zadaj kód.")
        return False
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
        if vstup("[MANUÁLNE] Potvrď kód v prehliadači a stlač ENTER...") is None:
            return False
    return True


# ==========================================
# 6. VYPLNENIE FORMULÁRA INZERÁTU
# ==========================================
def vyber_kategoriu(driver, nazov_alebo_hodnota):
    """Vyberie kategóriu v selecte 'category' podľa textu možnosti.

    Ak je zadaná číselná hodnota, vyberie sa priamo. Vráti True pri úspechu.
    """
    vyber = Select(driver.find_element(By.NAME, "category"))
    for opt in vyber.options:
        if opt.text.strip().lower() == nazov_alebo_hodnota.lower():
            vyber.select_by_value(opt.get_attribute("value"))
            logging.info(f"Kategória vybraná: '{opt.text.strip()}' (value={opt.get_attribute('value')}).")
            return True
    if nazov_alebo_hodnota.isdigit():
        vyber.select_by_value(nazov_alebo_hodnota)
        logging.info(f"Kategória vybraná podľa hodnoty: {nazov_alebo_hodnota}.")
        return True
    return False


def vypis_elementy_formulara(driver):
    """Diagnostika: vypíše všetky inputy/selecty/textarey stránky (name:typ).

    Reálne názvy polí Bazoš mení – tento výpis ukáže, ako sa pole volá
    naozaj, keď sa niektorý známy názov nenájde.
    """
    try:
        polia = []
        for tag in ("input", "select", "textarea"):
            for el in driver.find_elements(By.TAG_NAME, tag):
                meno = el.get_attribute("name") or "?"
                typ = el.get_attribute("type") or tag
                polia.append(f"{meno}:{typ}")
        logging.info(f"Elementy formulára ({len(polia)}): " + ", ".join(polia))
    except Exception as e:
        logging.warning(f"Elementy formulára sa nepodarilo načítať: {e}")


def vypln_inzerat(driver, wait):
    """Počká na formulár inzerátu a vyplní ho (texty zo šablóny, fotky z modulu).

    Neznáme názvy polí sa preskočia s varovaním – beh nespadne.
    """
    logging.info("Čakám na formulár inzerátu (element 'nadpis')...")
    wait.until(EC.presence_of_element_located((By.NAME, "nadpis")))
    vypis_elementy_formulara(driver)  # diagnostika reálnych názvov polí

    # 1) Kategória – ###01, dynamický výber podľa textu v selecte
    kategoria = SABLONA.get("###01")
    if kategoria:
        if not vyber_kategoriu(driver, kategoria):
            logging.warning(f"Kategória '{kategoria}' sa v selecte nenašla.")
    else:
        logging.warning("Kategória (###01) nie je v šablóne – nenastavujem.")

    # 2) Textové polia – všetko zo šablóny (###02..###09)
    logging.info("Vyplňujem textové polia inzerátu...")
    polia = [
        ("nadpis", SABLONA.get("###02")),
        ("popis", SABLONA.get("###03")),
        ("cena", SABLONA.get("###04")),
        ("jmeno", SABLONA.get("###06")),
        ("telefoni", SABLONA.get("###07")),
        ("heslobazar", SABLONA.get("###08")),
    ]
    if SABLONA.get("###09"):
        polia.append(("maili", SABLONA["###09"]))
    chybajuce = []
    for meno, hodnota in polia:
        if not hodnota:
            continue
        try:
            el = driver.find_element(By.NAME, meno)
            logging.debug(f"Vyplňujem pole '{meno}'...")
            el.send_keys(hodnota)
        except NoSuchElementException:
            chybajuce.append(meno)
            logging.warning(f"Pole '{meno}' sa na stránke nenašlo – preskakujem.")
    if chybajuce:
        logging.warning(f"Chýbajúce polia: {chybajuce} – porovnaj s výpisom elementov vyššie.")
    logging.info(f"Vyplnených {len(polia) - len(chybajuce)}/{len(polia)} textových polí.")

    # 3) PSČ/obec – ###05, pole 'lokalita' s autocomplete (treba vybrať návrh)
    psc = SABLONA.get("###05")
    if psc:
        try:
            lokalita = driver.find_element(By.NAME, "lokalita")
            lokalita.clear()
            lokalita.send_keys(psc)
            logging.info(f"PSČ {psc} zadané do poľa 'lokalita', čakám na návrh...")
            try:
                navrhy = WebDriverWait(driver, 4).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, "#vysledekpscinsert *"))
                for navrh in navrhy[:3]:
                    if navrh.is_displayed():
                        logging.info(f"Vyberám návrh PSČ: {navrh.text.strip()[:40]}")
                        navrh.click()
                        break
            except Exception:
                logging.warning("Návrh PSČ sa neobjavil – nechávam zadané PSČ v poli.")
        except NoSuchElementException:
            logging.warning("Pole 'lokalita' sa nenašlo – PSČ sa nezadáva.")
    else:
        logging.warning("PSČ (###05) nie je v šablóne – nezadávam.")

    # 4) Fotky – modul_upload: všetky z obrazky/, jedna za druhou,
    #    po každej sa čaká na dokončenie uploadu (Dropzone XHR)
    logging.info(f"Nahrávam fotky z: {ZLOZKA_OBRAZKOV}")
    upload_limit = DEBUG_LIMIT_UPLOAD_SEKUND if DEBUG_MODE else LIMIT_UPLOAD_SEKUND
    pocet = nahraj_fotky(driver, ZLOZKA_OBRAZKOV, casovy_limit=upload_limit)
    logging.info(f"Nahratých fotiek: {pocet}.")

    logging.info("DOKONČENÉ: Formulár bol úspešne vyplnený.")


def odosli_inzerat(driver):
    """Klikne 'Odoslať' v rámci formulára inzerátu a overí potvrdenie Bazoša.

    name="Submit" majú vyhľadávací, overovací aj inzertný formulár –
    bez scoping by sa odoslal nesprávny. Kotva: element 'nadpis'.
    """
    form = driver.find_element(By.NAME, "nadpis").find_element(By.XPATH, "./ancestor::form")
    tlacidlo = form.find_element(By.XPATH, ".//input[@type='submit'] | .//button[@type='submit']")
    tlacidlo.click()
    logging.info("Inzerát odoslaný – čakám na potvrdenie Bazoša...")
    time.sleep(4)
    log_viditelny_text(driver, "po odoslaní inzerátu")
    try:
        text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if any(s in text for s in ("vložený", "ďakujeme", "bol pridaný", "úspešne")):
            logging.info("POTVRDENÉ: Bazoš potvrdil vloženie inzerátu.")
        elif any(s in text for s in ("chyba", "chybné", "nepodarilo", "nebol", "limit",
                                     "blokovan", "neskôr")):
            logging.error("Bazoš nahlásil chybu pri odoslaní – text stránky vyššie.")
        else:
            logging.warning("Neznámy stav po odoslaní – skontroluj text stránky vyššie.")
    except Exception as e:
        logging.warning(f"Potvrdenie sa nepodarilo overiť: {e}")


# ==========================================
# 7. HLAVNÝ EXEKUČNÝ BLOK
# ==========================================
def skontroluj_sablona():
    """Overí, že šablóna obsahuje povinné polia – inak ukončí skript."""
    chybajuce = [i for i in POVINNE_V_SABLONE if not SABLONA.get(i)]
    if chybajuce:
        logging.error(f"Šablóna {CESTA_K_SABLONE} nemá povinné polia: {chybajuce}")
        logging.error("Skopíruj sablona_inzeratu.example.txt -> sablona_inzeratu.txt "
                      "a vyplň svoje údaje (###ID:hodnota).")
        return False
    return True


def pridaj_inzerat_bazos(sms_limit=None, neodosli=False):
    driver = None
    try:
        driver = ziskaj_prehliadac()
        try:
            driver.maximize_window()
        except Exception as e:
            logging.warning(f"Maximalizácia okna sa nepodarila ({e}) – pokračujem bez nej.")

        # Navigácia cez menu (kategória PC -> Pridať inzerát)
        naviguj_na_pridanie(driver)

        # Efektívne limity: --sms-timeout > --debug > štandard
        if sms_limit is None:
            sms_limit = DEBUG_SMS_CEKANIE_SEKUND if DEBUG_MODE else SMS_CEKANIE_SEKUND
        limit_nacitania = DEBUG_LIMIT_NACITANIA if DEBUG_MODE else LIMIT_NACITANIA
        limit_inzerat = DEBUG_LIMIT_FORMULARA_INZERATU if DEBUG_MODE else LIMIT_FORMULARA_INZERATU
        logging.info(f"Limity: overenie {limit_nacitania}s, SMS kód {sms_limit}s, formulár inzerátu {limit_inzerat}s.")

        wait = WebDriverWait(driver, limit_nacitania)

        # 1) Overenie telefónu (ak ho Bazoš vyžaduje)
        if not over_telefon(driver, wait, TELEFON, sms_limit=sms_limit):
            return

        # 2) Vyplnenie formulára inzerátu (po overení sa objaví)
        vypln_inzerat(driver, WebDriverWait(driver, limit_inzerat))

        if not rozhodni_odoslat(neodosli):
            logging.info("TEST režim: formulár vyplnený, inzerát sa NEODOŠLE.")
            if vstup("\n[TEST] Stlač ENTER pre ukončenie testu...\n") is None:
                logging.info("Neinteraktívny režim – končím test.")
        else:
            logging.info("PRODUKČNÝ režim: odosielam inzerát...")
            odosli_inzerat(driver)

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

def main(argv=None):
    """Vstupný bod konzolového príkazu 'bazos'."""
    args = parse_args(argv)
    if args.data_dir:
        nastav_data_dir(args.data_dir)
    if args.init:
        return inicializuj_sablona()
    if args.debug:
        aktivuj_debug()
    if not skontroluj_sablona():
        return 1
    pridaj_inzerat_bazos(sms_limit=args.sms_timeout, neodosli=args.neodosli)
    return 0


if __name__ == "__main__":
    sys.exit(main())
