# REPORT PRE HERMES AGENTA: Migrácia a stabilizácia automatizačného skriptu (Bazoš.sk)

> Poznámka: heslo a telefón z pôvodného reportu sú v tomto súbore z bezpečnostných
> dôvodov nahradené – reálne hodnoty žijú len v lokálnom `.env` (gitignored).

## 1. Kontext a cieľ

Pôvodný skript využíval na automatizáciu pridávania inzerátov knižnicu pyautogui. Bol nestabilný, pretože sa spoliehal na:

- Pevné súradnice pixelov (X, Y), závislé od rozlíšenia.
- Operačný systém Linux (volanie xdotool, správca pcman).
- Hardcodované citlivé údaje a cesty k súborom.

Cieľom bolo migrovať bota na knižnicu Selenium, čím sa zabezpečila nezávislosť od operačného systému, presné vyhľadávanie HTML elementov a bezpečné ukladanie hesiel.

## 2. Zistené problémy a riešenia počas vývoja

Počas migrácie na OS Windows došlo k tichému zamrznutiu skriptu pri inicializácii prehliadača (proces zostal visieť na _winapi.CreateProcess).

- Príčina: Natívny Selenium Manager sa pokúšal na pozadí stiahnuť chromedriver.exe, čo systém (pravdepodobne Windows Defender / Firewall) potichu zablokoval v sandboxe.
- Aplikované riešenie: Nasadenie explicitnej knižnice webdriver-manager, ktorá driver sťahuje štandardnou HTTP požiadavkou a predchádza blokovaniu na úrovni OS. Pridaný bol aj robustný chybový výstup pomocou modulu logging.

## 3. Inštrukcie na nasadenie (Deployment)

Krok 1: Inicializácia prostredia
```
python -m venv .venv
.venv\Scripts\activate
```

Krok 2: Inštalácia závislostí
```
pip install selenium webdriver-manager python-dotenv
```

Krok 3: Konfigurácia citlivých dát (.env)
V koreňovom adresári projektu je nutné vytvoriť súbor .env (a pridať ho do .gitignore). Formát súboru:
```
BAZOS_MENO=Peter
BAZOS_TELEFON=09********
BAZOS_HESLO=********
BAZOS_PSC=91305
```

## 4. Finálny produkčný kód

Finálny kód žije v `../bazos_pridaj_inzerat.py`. Obsahuje dynamické hľadanie ciest,
ošetrenie zásekov prehliadača a priame nahrávanie súborov do DOM stromu:

- `ziskaj_prehliadac()` – Chrome s fallbackom na Edge cez webdriver-manager
- `pridaj_inzerat_bazos()` – vyplnenie formulára (nadpis, popis, cena, psc, jmeno, telefon, heslo)
- upload fotky priamo do `<input type="file">` (obchádza OS dialóg)
- `DEBUG_CEKANIE` – v test režime čaká na ENTER, neodosiela
