"""Modul: extrakcia textových polí inzerátu z preddefinovanej šablóny.

Formát šablóny (sablona_inzeratu.txt) – jeden riadok na pole:
    ###ID:hodnota

Príklad:
    ###01:PC, Počítače
    ###02:Repasovaný Dell PowerEdge Server - Záruka
    ###03:Plne funkčný, vyčistený a pretestovaný enterprise server...
    ###04:250
    ###05:00000

Mapovanie ID -> pole formulára Bazoša:
    ###01  category   (select – hodnota sa nájde podľa textu možnosti)
    ###02  nadpis
    ###03  popis
    ###04  cena
    ###05  lokalita   (PSČ/obec s autocomplete)
    ###06  jmeno      (ak chýba, použije sa BAZOS_MENO)
    ###07  telefoni   (ak chýba, použije sa BAZOS_TELEFON)
    ###08  heslobazar (ak chýba, použije sa BAZOS_HESLO)
    ###09  maili      (voliteľný)
"""
import re
import logging

MAPPING = {
    "###01": "category",
    "###02": "nadpis",
    "###03": "popis",
    "###04": "cena",
    "###05": "lokalita",
    "###06": "jmeno",
    "###07": "telefoni",
    "###08": "heslobazar",
    "###09": "maili",
}

_RIADOK = re.compile(r"^(###\d+):(.*)$")


def nacitaj_sablona(cesta):
    """Načíta šablónu a vráti dict {###ID: hodnota}.

    Neexistujúci súbor alebo nezrozumiteľné riadky sa preskočia
    s varovaním – volajúci má fallback na .env / predvolené hodnoty.
    """
    vysledok = {}
    try:
        with open(cesta, encoding="utf-8") as f:
            for cislo, riadok in enumerate(f, 1):
                zhod = _RIADOK.match(riadok.strip())
                if not zhod:
                    logging.warning(f"Šablóna riadok {cislo}: nezrozumiteľný – preskočený.")
                    continue
                vysledok[zhod.group(1)] = zhod.group(2).strip()
    except OSError as e:
        logging.warning(f"Šablóna {cesta} sa nepodarilo načítať: {e}")
    return vysledok
