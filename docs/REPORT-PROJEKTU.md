# Bazoš automatizácia – Projektový report (handover)

> Stav: 30.8.2026. Report pre iného agenta / budúcu session.
> POZOR: tento súbor je commitnutý – NESMIE obsahovať žiadne reálne
> telefónne čísla, PSČ ani heslá. Reálne dáta žijú len v gitignored
> sablona_inzeratu.txt.

## 1. Cieľ projektu

Automatické pridávanie inzerátov na Bazoš.sk (PC kategória) cez Selenium +
Microsoft Edge. Migrácia z pôvodného pyautogui skriptu (pevné súradnice,
Linux-only, nestabilný). Všetko v `C:\Users\ratze\bazos-automation`.

## 2. Aktuálny stav

FUNGUJE (overené reálnymi behmi 30.8.2026):
- navigácia cez menu (kategória PC -> "Pridať inzerát")
- overenie telefónu: checkbox podmienok, teloverit, submit scoping,
  SMS kód (pole `klic`) – kód bol reálne prijatý, formulár inzerátu sa otvoril
- persistentný Edge profil (`edge_profile/`, gitignored) – overenie telefónu
  prežije medzi behmi, nevyčerpáva sa SMS limit; POTVRDENÉ funkčné
- formulár inzerátu podľa reálneho HTML (kategória, nadpis, popis, cena,
  lokalita/PSČ s autocomplete, Dropzone fotky, jmeno, telefoni, heslobazar,
  maili voliteľný)
- upload VŠETKÝCH fotiek z `obrazky/` jedna za druhou s čakaním na dokončenie
- odoslanie inzerátu: PRODUKČNÉ (`DEBUG_CEKANIE = False`) – prvý reálny
  inzerát vložený 31.8.2026 (Bazoš potvrdil "Inzerát bol vložený/zmenený",
  aktívny do 10 minút; overenie POTVRDENÉ v logu)

TESTY: 53 passed (`pytest`, pyproject.toml, testpaths=tests).
GIT: 25 commitov, pracovný strom čistý, remote = Marek-maker/bazos-automation.

## 3. Architektúra

```
bazos-automation/
├── pyproject.toml            # balík (hatchling src-layout, príkaz `bazos`)
├── src/bazos_automation/
│   ├── __init__.py           # verzia + verejné API
│   ├── bazos_pridaj_inzerat.py  # orchestrátor (Verzia 10, main() = CLI)
│   ├── modul_sablona.py      # šablóna ###ID:hodnota -> polia (MAPPING)
│   └── modul_upload.py       # Dropzone upload všetkých fotiek jedna za druhou
├── sablona_inzeratu.txt      # REÁLNE dáta (GITIGNORED)
├── sablona_inzeratu.example.txt  # dummy dáta (v gite)
├── obrazky/                  # fotky (gitignored: *.jpg/png/webp)
├── edge_profile/             # persistentný Edge profil (gitignored)
├── tests/test_bazos.py       # 40 testov
├── requirements.txt (selenium, webdriver-manager, pytest)
└── docs/
    ├── gemini-report-bazos-migracia.md   # pôvodný report (heslo vymazané)
    └── REPORT-PROJEKTU.md                # tento súbor
```

DÁTA MIMO BALÍKA: `sablona_inzeratu.txt`, `obrazky/`, `edge_profile/` sa
hľadajú v poradí: env `BAZOS_DATA_DIR` -> aktuálny adresár (ak obsahuje
šablónu) -> `~/.bazos-automation` (vytvorí sa). Z koreňa repa sa teda
použijú lokálne dáta a overený profil – bez presúvania.

Flow: `ziskaj_prehliadac` (Edge + user-data-dir) -> `naviguj_na_pridanie`
(menu) -> `over_telefon` (SMS, ak treba) -> `vypln_inzerat` (kategória,
texty zo šablóny, lokalita autocomplete, `nahraj_fotky`) -> `odosli_inzerat`
(len pri DEBUG_CEKANIE=False).

## 4. Kľúčové zistenia o reálnej stránke (29.–30.8.2026)

URL:
- `https://pc.bazos.sk/pridat-inzerat.php` = UPLOAD formulár
- `https://www.bazos.sk/pridat-inzerat.php` = NEVIE upload (vracia prehľad)
- `https://pc.bazos.sk/` = prehľad kategórie PC
- priamy driver.get() na upload URL môže vrátiť prehľad kategórie
  (závisí od hlavičiek) -> vždy navigovať cez menu

Overenie telefónu (PRED formulárom inzerátu):
- form `name="formovereni"`, checkbox `name="podminky"`, pole `name="teloverit"`
- submit `name="Submit"` – POZOR: duplicitný názov, scoping do formovereni
- po odoslaní: pole pre SMS kód `name="klic"` (zistené reálne)
- ak Bazoš overenie neprijme -> presmeruje na prehľad kategórie
  (signatúra: "Stránka: 1 2 3 ..." v texte)

Formulár inzerátu (reálne názvy polí!):
- select `category` (kategória sa vyberá DYNAMICKY podľa textu možnosti)
- `nadpis`, `popis` (textarea), `cena` (+ select `cenavyber`)
- `lokalita` = PSČ/obec s autocomplete (`naseptavacpscinsert`,
  návrhy v `#vysledekpscinsert`) – po zadaní PSČ vybrať návrh
- fotky: Dropzone (`#dropzonea`), upload cez XHR – čakať na `.dz-success`
- `jmeno`, `telefoni` (NIE "telefon"), `heslobazar` (NIE "heslo"),
  `maili` (voliteľný)
- odoslanie: submit `name="Submit"` – scoping do formulára inzerátu
  (kotva: element `nadpis` -> ancestor form)

PRAVIDLO SCROPINGU: name="Submit" majú vyhľadávací, overovací aj inzertný
formulár. Každý submit sa kliká výhradne v rámci správneho formulára.

## 5. Bezpečnosť (KRITICKÉ)

- `sablona_inzeratu.txt` (reálne údaje: kategória, nadpis, popis, cena,
  PSČ, meno, telefón, heslo, e-mail) je GITIGNORED. Do gitu ide LEN
  `sablona_inzeratu.example.txt` s dummy dátami (0900000000, 00000, ...).
- `.env` sa už NEPOUŽÍVA (Verzia 10) – všetko ide zo šablóny. Súbor .env
  na disku možno zmazať.
- Telefón používateľa: NIKDY nebol v git histórii (overené scanom
  `git rev-list --all | xargs git grep -E "09[0-9]{8}"` – jediné zhody sú
  dummy 0900000000).
- REÁLNE PSČ (hodnota ###05) ostalo v starom commite 8b30114 (šablóna bola
  kedysi commitnutá) – ROZHODNUTIE POUŽÍVATEĽA: história sa neprepisuje.
  PRED PUSHOM NA GITHUB zvážiť `git filter-branch --index-filter "git rm
  --cached --ignore-unmatch sablona_inzeratu.txt"` (repo zatiaľ nemá remote).
- Testy strážia: žiadny telefón v histórii ani v trackovaných súboroch,
  example neobsahuje reálne hodnoty (čítajú sa dynamicky z reálnej šablóny).
- Do tohto reportu ani do iných commitnutých súborov NIKDY nepísať reálne
  čísla/heslá.

## 6. Ako spustiť

```
cd C:\Users\ratze\bazos-automation
.venv\Scripts\python -m pip install -e ".[dev]"     # inštalácia balíka (raz)
.venv\Scripts\python -m pytest                      # testy (canonical)
.venv\Scripts\bazos --debug                         # skript (test režim)
bazos --sms-timeout 600
bazos --neodosli --debug                            # test režim: vyplní, NEODOŠLE
```

PRODUKČNÁ INŠTALÁCIA na čistom stroji (bez editable, z TestPyPI):
```
python -m venv .venv
.venv\Scripts\python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ bazos-automation
```
Potom nastaviť BAZOS_DATA_DIR (alebo spúšťať z adresára so šablónou)
a `copy sablona_inzeratu.example.txt sablona_inzeratu.txt` – viď README.

Konfigurácia na novom stroji:
```
bazos --init
```
a vyplniť ###01–###09 (###01 kategória, ###02 nadpis, ###03 popis,
###04 cena, ###05 PSČ, ###06 meno, ###07 telefón, ###08 heslo k inzerátu,
###09 e-mail voliteľný). Dátový adresár: `--data-dir CESTA` > env
`BAZOS_DATA_DIR` > aktuálny adresár (so šablónou) > `~/.bazos-automation`.
Prvý beh vytvorí edge_profile/ a vyžiada SMS overenie – ďalšie behy už nie.

Flagy: `--debug` (predĺžené limity: SMS 300 s, upload 120 s + DEBUG log),
`--sms-timeout N` (vlastný limit čakania na SMS kód).

## 7. Známe obmedzenia / pozor

- Bazoš má denný limit SMS overení na číslo – persistentný profil to obchádza
  (overenie sa uchová v cookies profilu). Ak sa profil vymaže, treba nové SMS.
- Ak je edge_profile/ zamknutý (beží Edge), skript skončí s jasnou hláškou.
- Autocomplete PSČ (lokalita): ak sa návrh neobjaví, PSČ ostane v poli
  (best-effort) – beh nespadne.
- Dropzone: fotky sa nahrávajú jedna za druhou; chyba uploadu sa zaloguje
  a pokračuje sa ďalšou.
- jmeno/telefoni/heslobazar/maili môžu v budúcnosti zmeniť názvy – na
  začiatku behu sa vypíše diagnostika "Elementy formulára (N): ...".
- webdriver-manager považuje cache drivera za expirovanú po 1 DNI
  (valid_range=1) a znova sťahuje – 31.8.2026 download spadol na "Could not
  reach host". FIX: `DriverCacheManager(valid_range=365)` + fallback
  `najdi_cached_driver()` (najnovší msedgedriver.exe z ~/.wdm) v
  `ziskaj_cestu_drivera()`.
- Dropzone: `#dropzonea input[type='file']` zmizne z DOM po prvej fotke –
  od 2. fotky nahráva fallback `//input[@type='file']` (funguje, robí DEBUG
  šum s 404 stacktrace).
- `maximize_window()` je best-effort (31.8.2026: read timeout 120 s pri
  slabom pripojení zabil beh pred navigáciou) – pri chybe varuje a pokračuje.
- TESTPYPI SIMPLE-INDEX LAG (31.8.2026, empiricky): po twine uploadе JSON
  API aj stránka projektu ukážu novú verziu OKAMŽITE, ale simple index
  (čo číta pip) sa aktualizuje ONESKORENE – pip nainštaluje staršiu verziu
  aj s `--upgrade`. FIX: pinovať verziu explicitne (`bazos-automation==0.1.2`)
  alebo inštalovať z lokálneho wheelu (`pip install --force-reinstall
  cesta\bazos_automation-0.1.2-py3-none-any.whl`).
- TIEŇOVANIE PRÍKAZU `bazos` (31.8.2026): na stroji s viacerými Pythonmi
  sa `bazos` v PowerShell bral z user-site Scripts MS Store Pythonu
  (stará 0.1.0 na PATH), NIE z .venv – príznak: `--init`/`--data-dir`
  neznáme aj po upgrade. FIX: vždy `.venv\Scripts\bazos` (alebo aktivácia
  venv) + overenie verzie `python -c "import bazos_automation; print(...)"`.
- POWERSHELL `set X=Y` je alias na Set-Variable, NIE env var – env var sa
  nastavuje `$env:X = "Y"` (cmd: `set X=Y`). Reálny zádrhel 31.8.2026
  (BAZOS_DATA_DIR sa nenastavil).

## 8. Ďalšie kroky (roadmap)

1. REÁLNY PRIECHOD: spustiť skript s reálnou šablónou (profil overený ->
   bez SMS), skontrolovať log ("Kategória vybraná", "Upload fotky dokončený",
   "Chýbajúce polia"). [HOTOVÉ 31.8.2026]
2. PRODUKČNÉ ODOSLANIE: `DEBUG_CEKANIE = False` v bazos_pridaj_inzerat.py
   (odosli_inzerat už je scoping do formulára). [HOTOVÉ 31.8.2026 – prvý
   inzerát vložený, overenie POTVRDENÉ v odosli_inzerat]
3. GITHUB: `gh auth login` + `gh repo create bazos-automation --source=. --push`
   [HOTOVÉ 31.8.2026 – repo Marek-maker/bazos-automation (verejné), história
   očistená filter-branch od reálneho PSČ; git email = noreply
   59760649+Marek-maker; gh device-flow poll visí na sieti – push cez GH_TOKEN]
4. TESTPYPI: [HOTOVÉ 31.8.2026 – bazos-automation 0.1.0 (wheel + sdist)
   na https://test.pypi.org/project/bazos-automation/0.1.0/; inštalácia:
   pip install --index-url https://test.pypi.org/simple/ --extra-index-url
   https://pypi.org/simple/ bazos-automation==0.1.0]
5. EXTRÁKCIA TEXTOV z iných šablón inzerátov: modul_sablona už parsuje
   ###ID:hodnota – stačí rozšíriť MAPPING / vytvoriť viac šablón.
6. AUTONÓMIA: po overení profilu možno skript spúšťať neinteraktívne
   (vstup je EOF-safe).

## 9. Preferencie používateľa (Marek)

- Slovak primárne, štruktúrovaný výstup (tabuľky, kroky), debugging visibility.
- Nezahŕňať bundled `rm -rf` do príkazov – temp súbory nechávať, reportovať cesty.
- Úlohy riešiť samostatne, overovať medzi krokmi (rád spúšťa plány ako sériu
  subagentov).
- CITLIVÉ DÁTA: nikdy na git – toto je tvrdá požiadavka.
- Python: vždy .venv/Scripts/python.exe -m pip (inak hrozí wheel pollution).
- Docs: každý príkaz na jeden riadok, žiadne backslash pokračovania.

## 10. Cheat-sheet (rýchle fakty)

| Vec | Hodnota |
|---|---|
| Upload URL | pc.bazos.sk/pridat-inzerat.php |
| Overenie | formovereni, podminky, teloverit, Submit (scoping!) |
| SMS kód | name="klic" |
| Formulár | category, nadpis, popis, cena, lokalita, jmeno, telefoni, heslobazar, maili |
| PSČ | pole lokalita (autocomplete) |
| Fotky | Dropzone #dropzonea, čakať na .dz-success |
| Šablóna | ###ID:hodnota, MAPPING v modul_sablona.py |
| Testy | .venv\Scripts\python -m pytest (53) |
| Verzia | 0.1.2 (TestPyPI; pinovať ==0.1.2 – lag indexu) |
| Profil | edge_profile/ (user-data-dir) |
| Odoslanie | PRODUKČNÉ – odosli_inzerat() + POTVRDENÉ; test režim: --neodosli |
