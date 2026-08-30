# Bazoš.sk automatizácia inzerátov

Automatické pridávanie inzerátov na Bazoš.sk pomocou Selenium.
Migrované z pôvodného pyautogui skriptu (pevné súradnice, Linux-only) na
Selenium – nezávislé od OS a rozlíšenia obrazovky. Prehliadač: Microsoft
Edge (Chrome sa nepoužíva).

## Štádiá projektu

- [x] Stádium 1: Migrácia skriptu na Selenium (report od Gemini – docs/)
- [x] Stádium 2: Pracovný priestor pre git + extrakcia obsahu z Gemini
      reportu do projektových súborov
- [x] Stádium 2b: Overenie telefónu (SMS kľúč) + navigácia cez menu
- [x] Stádium 2c: Canonical testy (pytest) + Edge-only
- [ ] Stádium 3: GitHub – gh auth login + push repozitára
- [ ] Stádium 4: Extrakcia textov zo šablón inzerátov → automatické
      vyplnenie nadpisu/popisu/ceny
- [ ] Stádium 5: Produkčné odosielanie formulára (odoslat klik)

## Štruktúra

```
bazos-automation/
├── bazos_pridaj_inzerat.py   # hlavný skript (Selenium, Edge)
├── tests/
│   ├── conftest.py           # sys.path pre importy
│   └── test_bazos.py         # canonical pytest testy
├── requirements.txt          # závislosti
├── .env                      # citlivé údaje (gitignored – NEcommittovať!)
├── .env.example              # vzor konfigurácie
├── obrazky/                  # fotky inzerátov (server_foto1.jpg, ...)
└── docs/
    └── gemini-report-bazos-migracia.md  # pôvodný report (bez hesla)
```

## Inštalácia (Windows)

Vytvorenie prostredia:
```
python -m venv .venv
.venv\Scripts\activate
```

Inštalácia závislostí:
```
pip install -r requirements.txt
```

Konfigurácia:
```
copy .env.example .env
```

Do `.env` doplň svoje údaje (meno, telefón, heslo, PSČ).

## Testy (canonical)

Canonical príkaz pre overenie projektu:
```
.venv\Scripts\python -m pytest
```

Testy overujú: syntaktickú validitu, konštanty, URL, Edge-only režim
a dynamickú detekciu poľa pre SMS kód (scenáre na simulovaných stránkach).

## Spustenie (test – bez odoslania)

```
.venv\Scripts\python bazos_pridaj_inzerat.py
```

Priebeh skriptu:

1. Otvorí Edge na kategórii PC (`https://pc.bazos.sk/`) a cez menu
   "Pridať inzerát" prejde na formulár – navigácia ako bežný používateľ.
2. Bazoš vyžaduje overenie mobilného telefónu – skript zaškrtne podmienky,
   vyplní `teloverit` číslom z `.env` (BAZOS_TELEFON) a odošle.
   Na telefón príde SMS kľúč.
3. Skript nájde pole pre SMS kód a v termináli sa Ťa spýta:
   `Zadaj kód z SMS:` – kód napíšeš do terminálu a skript ho vyplní a potvrdí.
4. Potom skript vyplní celý formulár inzerátu a počká na ENTER –
   inzerát sa NEODOŠLE (konštanta `DEBUG_CEKANIE = True`).

Fotka sa berie z `obrazky/server_foto1.jpg` (ak chýba, krok sa preskočí).

Ak Bazoš neukáže formulár (bot-detekcia a pod.), skript zaloguje aktuálnu
URL, titulok a nájdené inputy – pošli tento log na analýzu.

## URL (zistené 29.8.2026)

- `https://pc.bazos.sk/pridat-inzerat.php` – UPLOAD formulár (overenie
  telefónu, potom formulár inzerátu)
- `https://www.bazos.sk/pridat-inzerat.php` – NEVIE upload (vracia prehľad)
- `https://pc.bazos.sk/` – prehľad kategórie PC
- `https://www.bazos.sk/` – hlavná stránka

Overenie telefónu je viazané na reláciu prehliadača – pri každom spustení
príde nový SMS kľúč. Reálne elementy overovacieho formulára:
`formovereni`, `podminky`, `teloverit`, `Submit` – viď komentár
v `bazos_pridaj_inzerat.py`. Pole pre SMS kód nemá dopredu známy názov,
skript ho deteguje dynamicky (prvý nový textový input).

## Produkčné odoslanie

V `bazos_pridaj_inzerat.py`:
1. Nastav `DEBUG_CEKANIE = False`.
2. Odomkni riadok `# driver.find_element(By.NAME, "odeslat").click()`.

## GitHub (neskôr)

```
gh auth login
gh repo create bazos-automation --public --source=. --push
```

Pozor: `.env` je v `.gitignore` – heslo sa do gitu nikdy nedostane.
