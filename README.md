# Bazoš.sk automatizácia inzerátov

Automatické pridávanie inzerátov na Bazoš.sk pomocou Selenium. Migrované z
pôvodného pyautogui skriptu (pevné súradnice, Linux-only) na Selenium –
nezávislé od OS a rozlíšenia obrazovky. Prehliadač: Microsoft Edge (Chrome
sa nepoužíva). Distribuované ako Python balík `bazos-automation`.

## Štádiá projektu

- [x] Stádium 1: Migrácia skriptu na Selenium (report od Gemini – docs/)
- [x] Stádium 2: Pracovný priestor pre git + extrakcia obsahu z Gemini
      reportu do projektových súborov
- [x] Stádium 2b: Overenie telefónu (SMS kľúč) + navigácia cez menu
- [x] Stádium 2c: Canonical testy (pytest) + Edge-only
- [x] Stádium 2d: Python balík (src layout, príkaz `bazos`)
- [ ] Stádium 3: GitHub – gh auth login + push repozitára
- [ ] Stádium 4: Extrakcia textov zo šablón inzerátov → automatické
      vyplnenie nadpisu/popisu/ceny
- [ ] Stádium 5: Produkčné odosielanie formulára (odoslat klik)

## Štruktúra

```
bazos-automation/
├── pyproject.toml             # balík (hatchling, príkaz `bazos`)
├── src/bazos_automation/
│   ├── __init__.py            # verzia + verejné API
│   ├── bazos_pridaj_inzerat.py  # orchestrátor (CLI, Selenium, Edge)
│   ├── modul_sablona.py       # šablóna ###ID:hodnota -> polia
│   └── modul_upload.py        # Dropzone upload fotiek jedna za druhou
├── tests/
│   ├── conftest.py            # src/ v sys.path
│   └── test_bazos.py          # canonical pytest testy
├── sablona_inzeratu.txt       # REÁLNE dáta (GITIGNORED – len lokálne)
├── sablona_inzeratu.example.txt  # dummy dáta (v gite)
├── obrazky/                   # fotky (gitignored)
├── edge_profile/              # persistentný Edge profil (gitignored)
└── docs/
    ├── gemini-report-bazos-migracia.md  # pôvodný report (bez hesla)
    └── REPORT-PROJEKTU.md              # handover report
```

Dáta (šablóna, fotky, profil) žijú MIMO balíka a hľadajú sa v poradí:
1. env `BAZOS_DATA_DIR` (ak je nastavený),
2. aktuálny adresár (ak obsahuje `sablona_inzeratu.txt`),
3. `~/.bazos-automation` (vytvorí sa).

## Inštalácia (Windows)

Vytvorenie prostredia a inštalácia balíka (editable):

```
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

Konfigurácia (prvý beh):

```
copy sablona_inzeratu.example.txt sablona_inzeratu.txt
```

Do `sablona_inzeratu.txt` vyplň ###01–###09 (###01 kategória, ###02 nadpis,
###03 popis, ###04 cena, ###05 PSČ, ###06 meno, ###07 telefón, ###08 heslo
k inzerátu, ###09 e-mail voliteľný). Prvý beh vytvorí `edge_profile/`
a vyžiada SMS overenie – ďalšie behy už nie.

## Spustenie

Konzolový príkaz (odkiaľkoľvek v rámci adresára s dátami):

```
bazos --debug
```

Alebo priamo cez Python (rovnaké správanie):

```
.venv\Scripts\python -m bazos_automation.bazos_pridaj_inzerat --debug
```

Priebeh skriptu:

1. Otvorí Edge na kategórii PC (`https://pc.bazos.sk/`) a cez menu
   "Pridať inzerát" prejde na formulár – navigácia ako bežný používateľ.
2. Bazoš vyžaduje overenie mobilného telefónu – skript zaškrtne podmienky,
   vyplní `teloverit` číslom z `###07` a odošle. Na telefón príde SMS kľúč.
   S persistentným profilom sa overenie preskočí.
3. Skript nájde pole pre SMS kód a v termináli sa Ťa spýta:
   `Zadaj kód z SMS:` – kód napíšeš do terminálu a skript ho vyplní a potvrdí.
4. Potom skript vyplní celý formulár inzerátu a počká na ENTER –
   inzerát sa NEODOŠLE (konštanta `DEBUG_CEKANIE = True`).

Fotky sa berú z `obrazky/` (všetky jpg/jpeg/png/webp, zoradené podľa názvu).

Ak Bazoš neukáže formulár (bot-detekcia a pod.), skript zaloguje aktuálnu
URL, titulok a nájdené inputy – pošli tento log na analýzu.

## Testy (canonical)

Canonical príkaz pre overenie projektu:

```
.venv\Scripts\python -m pytest
```

Testy overujú: syntaktickú validitu, konštanty, URL, Edge-only režim,
ochranu citlivých údajov (telefón nesmie byť v gite), dynamickú detekciu
poľa pre SMS kód a fallback na cached driver.

## Ladenie (predĺžené časy a podrobný log)

```
bazos --debug
```

Čo `--debug` robí:
- logovacia úroveň DEBUG – pri čakaní na SMS kód vypíše stav stránky
  každú sekundu (aké inputy sú na stránke)
- čakanie na SMS kód predĺžené na 300 s (štandard 120 s)
- limity načítania formulárov predĺžené (overenie 45 s, inzerát 90 s)
- po odoslaní overenia zaloguje viditeľný text stránky – tam je vidno
  hlášky Bazoša (napr. limit na SMS, "už overené", chybné číslo)

Vlastný limit čakania na SMS kód (sekundy):

```
bazos --sms-timeout 600
```

Poznámka: ak Bazoš hlási limit na SMS overenia (po viacerých pokusoch
za deň), flag to neobíde – ide o serverový limit, treba počkať (zvyčajne
do ďalšieho dňa).

## URL (zistené 29.8.2026)

- `https://pc.bazos.sk/pridat-inzerat.php` – UPLOAD formulár (overenie
  telefónu, potom formulár inzerátu)
- `https://www.bazos.sk/pridat-inzerat.php` – NEVIE upload (vracia prehľad)
- `https://pc.bazos.sk/` – prehľad kategórie PC
- `https://www.bazos.sk/` – hlavná stránka

Reálne elementy overovacieho formulára: `formovereni`, `podminky`,
`teloverit`, `Submit` (scoping!). Pole pre SMS kód: `klic` (deteguje sa aj
dynamicky). Viď komentár v `bazos_pridaj_inzerat.py`.

## Produkčné odoslanie

V `src/bazos_automation/bazos_pridaj_inzerat.py` nastav `DEBUG_CEKANIE = False`.

## GitHub (neskôr)

```
gh auth login
gh repo create bazos-automation --public --source=. --push
```

Pozor: `sablona_inzeratu.txt` je v `.gitignore` – reálne údaje sa do gitu
nikdy nedostanú.
