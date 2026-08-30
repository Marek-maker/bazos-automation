# Bazoš.sk automatizácia inzerátov

Automatické pridávanie inzerátov na Bazoš.sk pomocou Selenium.
Migrované z pôvodného pyautogui skriptu (pevné súradnice, Linux-only) na
Selenium – nezávislé od OS a rozlíšenia obrazovky.

## Štádiá projektu

- [x] Stádium 1: Migrácia skriptu na Selenium (report od Gemini – docs/)
- [x] Stádium 2: Pracovný priestor pre git (tento repozitár) + extrakcia
      obsahu z Gemini reportu do projektových súborov
- [ ] Stádium 3: GitHub – gh auth login + push repozitára
- [ ] Stádium 4: Extrakcia textov zo šablón inzerátov → automatické
      vyplnenie nadpisu/popisu/ceny
- [ ] Stádium 5: Produkčné odosielanie formulára (odoslat klik)

## Štruktúra

```
bazos-automation/
├── bazos_pridaj_inzerat.py   # hlavný skript (Selenium)
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

## Spustenie (test – bez odoslania)

```
.venv\Scripts\python bazos_pridaj_inzerat.py
```

Priebeh skriptu:

1. Otvorí Chrome (prípadne Edge) na `https://pc.bazos.sk/pridat-inzerat.php`.
2. Bazoš vyžaduje overenie mobilného telefónu – skript zaškrtne podmienky,
   vyplní `teloverit` číslom z `.env` (BAZOS_TELEFON) a odošle.
   Na telefón príde SMS kľúč.
3. Skript nájde pole pre SMS kód a v termináli sa Ťa spýta:
   `Zadaj kód z SMS:` – kód napíšeš do terminálu a skript ho vyplní a potvrdí.
4. Potom skript vyplní celý formulár inzerátu a počká na ENTER –
   inzerát sa NEODOŠLE (konštanta `DEBUG_CEKANIE = True`).

Fotka sa berie z `obrazky/server_foto1.jpg` (ak chýba, krok sa preskočí).

Overenie telefónu je viazané na reláciu prehliadača – pri každom spustení
príde nový SMS kľúč. Reálne elementy overovacieho formulára (zistené
29.8.2026): `formovereni`, `podminky`, `teloverit`, `Submit` – viď komentár
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
