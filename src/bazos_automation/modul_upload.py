"""Modul: nahrávanie fotiek inzerátu na Bazoš (Dropzone).

Dropzone nahráva súbory cez XHR po pridaní do <input type="file">.
Fotky sa nahrávajú JEDNA ZA DRUHOU – po každej sa čaká na dokončenie
(.dz-success a žiadny .dz-uploading) skôr, než sa pridá ďalšia.
"""
import os
import time
import logging

from selenium.webdriver.common.by import By

SELECTOR_INPUT = "#dropzonea input[type='file']"
PRIPONY = (".jpg", ".jpeg", ".png", ".webp")


def najdi_fotky(zlozka):
    """Všetky fotky (jpg/jpeg/png/webp) v zložke, zoradené podľa názvu."""
    try:
        return [os.path.join(zlozka, s) for s in sorted(os.listdir(zlozka))
                if s.lower().endswith(PRIPONY)]
    except OSError:
        return []


def pockaj_na_upload(driver, pocet_ocakavanych, casovy_limit=60):
    """Čaká, kým Dropzone dokončí upload.

    Podmienka: počet .dz-success >= pocet_ocakavanych, žiadny
    .dz-uploading (nič nebeží), žiadna .dz-error. Vráti True pri úspechu.
    """
    zaciatok = time.time()
    while time.time() - zaciatok < casovy_limit:
        try:
            uspech = len(driver.find_elements(By.CSS_SELECTOR, "#dropzonea .dz-success"))
            bezi = len(driver.find_elements(By.CSS_SELECTOR, "#dropzonea .dz-uploading"))
            chyba = len(driver.find_elements(By.CSS_SELECTOR, "#dropzonea .dz-error"))
            if chyba:
                logging.warning("Dropzone nahlásil chybu pri nahrávaní.")
                return False
            if uspech >= pocet_ocakavanych and bezi == 0:
                return True
        except Exception:
            pass
        time.sleep(1)
    logging.warning(f"Čakanie na upload vypršalo ({casovy_limit} s).")
    return False


def nahraj_fotky(driver, zlozka, casovy_limit=60):
    """Nahrá VŠETKY fotky zo zložky jednu za druhou.

    Po každej fotke čaká na dokončenie uploadu (Dropzone XHR) –
    inak by sa inzerát odoslal bez časti fotiek.
    Vráti počet úspešne nahratých fotiek.
    """
    fotky = najdi_fotky(zlozka)
    if not fotky:
        logging.warning(f"V {zlozka} nie sú žiadne fotky.")
        return 0

    nahrate = 0
    for i, fotka in enumerate(fotky, 1):
        try:
            upload_input = driver.find_element(By.CSS_SELECTOR, SELECTOR_INPUT)
        except Exception:
            upload_input = driver.find_element(By.XPATH, "//input[@type='file']")
        upload_input.send_keys(fotka)
        logging.info(f"[{i}/{len(fotky)}] Odosielam fotku: {os.path.basename(fotka)}")
        if pockaj_na_upload(driver, pocet_ocakavanych=i, casovy_limit=casovy_limit):
            nahrate += 1
            logging.info(f"[{i}/{len(fotky)}] Upload dokončený.")
        else:
            logging.warning(f"[{i}/{len(fotky)}] Upload nepotvrdený – pokračujem ďalšou.")
    return nahrate
