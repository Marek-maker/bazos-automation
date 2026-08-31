r"""Canonical testy pre Bazoš automatizáciu (pytest).

Spustenie (koreň projektu):
    .venv\Scripts\python -m pytest
"""
import os
import subprocess
import py_compile
import pytest

import bazos_automation.bazos_pridaj_inzerat as b
from bazos_automation import modul_sablona, modul_upload

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PKG = os.path.join(PROJ, "src", "bazos_automation")


# ---------- štruktúra modulov ----------

def test_syntax():
    for rel in ("bazos_pridaj_inzerat.py", "modul_sablona.py", "modul_upload.py"):
        py_compile.compile(os.path.join(SRC_PKG, rel), doraise=True)


def test_konstanty():
    assert b.SMS_CEKANIE_SEKUND > 0
    # PRODUKČNÝ STAV (31.8.2026, rozhodnutie používateľa): formulár sa odošle.
    # Ak sa vráti test režim, tento assert sa prepne na True.
    assert b.DEBUG_CEKANIE is False


def test_url_constanty():
    assert b.URL_KATEGORIA_PC == "https://pc.bazos.sk/"
    assert b.URL_PRIDAT_INZERAT == "https://pc.bazos.sk/pridat-inzerat.php"


def test_edge_only_bez_chrome():
    src = open(os.path.join(SRC_PKG, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "ChromeDriverManager" not in src
    assert "EdgeChromiumDriverManager" in src


def test_ziadny_env_v_kode():
    """Skript nesmie používať .env – všetko ide zo šablóny (###ID)."""
    src = open(os.path.join(SRC_PKG, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "dotenv" not in src and "os.getenv" not in src


def test_funkcie_existuju():
    for name in ("parse_args", "aktivuj_debug", "log_viditelny_text", "vstup",
                 "je_kategoria_prehlad", "ziskaj_prehliadac", "odsuhlas_cookies",
                 "najdi_pole_kodu", "naviguj_na_pridanie", "over_telefon",
                 "vyber_kategoriu", "vypis_elementy_formulara", "vypln_inzerat",
                 "odosli_inzerat", "skontroluj_sablona", "pridaj_inzerat_bazos",
                 "rozhodni_odoslat", "inicializuj_sablona"):
        assert callable(getattr(b, name, None)), f"chýba funkcia: {name}"


def test_vylucene_polia():
    for meno in ("teloverit", "hledat", "hlokalita", "humkreis", "cenaod", "cenado"):
        assert meno in b.VYLUCENE_POLIA


def test_overenie_klika_v_ramci_formovereni():
    """Submit overenia MUSÍ byť scoping do formovereni – inak sa odošle
    vyhľadávací formulár (oba majú name='Submit'). Regresný test."""
    src = open(os.path.join(SRC_PKG, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert 'find_element(By.NAME, "formovereni")' in src
    assert './/input[@type=\'submit\']' in src or './/input[@type="submit"]' in src


def test_persistentny_profil():
    """Overenie telefónu sa uchová medzi behmi cez --user-data-dir."""
    src = open(os.path.join(SRC_PKG, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "PROFIL_EDGE" in src and "user-data-dir" in src


def test_maximalizacia_okna_best_effort():
    """maximize_window nesmie zabiť celý beh – 31.8.2026 visel 120 s
    (read timeout pri slabom pripojení) a run spadol pred navigáciou.
    Regresný test: maximalizácia je v try/except s varovaním."""
    src = open(os.path.join(SRC_PKG, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "driver.maximize_window()" in src
    assert "pokračujem bez nej" in src


def test_wdm_cache_valid_range_365():
    """webdriver-manager po 1 dni považuje cache za expirovanú a znova sťahuje
    driver (reálny bug 31.8.2026: download spadol na 'Could not reach host').
    valid_range=365 zabezpečí použitie existujúcej cache. Regresný test."""
    src = open(os.path.join(SRC_PKG, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "DriverCacheManager(valid_range=365)" in src


def test_fallback_na_lokalnu_cache():
    """Ak install() zlyhá (výpadok siete), použije sa najnovší driver z cache."""
    src = open(os.path.join(SRC_PKG, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "def najdi_cached_driver" in src
    assert "def ziskaj_cestu_drivera" in src
    assert "ziskaj_cestu_drivera()" in src


def test_najdi_cached_driver_vrati_najnovsi(tmp_path):
    import os as _os
    stara = tmp_path / "drivers" / "edgedriver" / "win64" / "151.0.0.0"
    nova = tmp_path / "drivers" / "edgedriver" / "win64" / "152.0.0.0"
    stara.mkdir(parents=True)
    nova.mkdir(parents=True)
    (stara / "msedgedriver.exe").write_bytes(b"x")
    (nova / "msedgedriver.exe").write_bytes(b"y")
    _os.utime(stara / "msedgedriver.exe", (1_000_000, 1_000_000))
    _os.utime(nova / "msedgedriver.exe", (2_000_000, 2_000_000))
    vysledok = b.najdi_cached_driver(koren=str(tmp_path))
    assert vysledok is not None
    assert vysledok.endswith("152.0.0.0" + _os.sep + "msedgedriver.exe")


def test_najdi_cached_driver_prazdna_cache(tmp_path):
    assert b.najdi_cached_driver(koren=str(tmp_path)) is None


def test_hlavny_skript_pouziva_moduly():
    """Hlavný skript musí používať modul šablóny aj modul uploadu."""
    src = open(os.path.join(PROJ, "src", "bazos_automation", "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "from .modul_sablona import" in src
    assert "from .modul_upload import" in src


def test_odoslanie_scoping_do_formulara():
    """Odoslanie inzerátu musí byť scoping do formulára s nadpisom –
    name='Submit' majú vyhľadávací aj overovací formulár."""
    src = open(os.path.join(SRC_PKG, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "def odosli_inzerat" in src
    assert 'find_element(By.NAME, "nadpis")' in src
    assert "./ancestor::form" in src


def test_odoslanie_overuje_potvrdenie():
    """Po odoslaní sa overí, či Bazoš potvrdil vloženie inzerátu
    (úspešné/chybové markery v texte stránky) – inak by sme nevedeli,
    či inzerát naozaj vznikol. Regresný test."""
    src = open(os.path.join(SRC_PKG, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "POTVRDENÉ" in src
    assert "vložený" in src


# ---------- ochrana citlivých údajov ----------

def test_realna_sablona_nie_je_v_gite():
    """sablona_inzeratu.txt (reálne údaje) NESMIE byť trackovaná gitom."""
    sledovane = subprocess.run(
        ["git", "-C", PROJ, "ls-files"], capture_output=True, text=True).stdout.splitlines()
    assert "sablona_inzeratu.txt" not in sledovane
    assert "sablona_inzeratu.example.txt" in sledovane  # example áno


def test_gitignore_chrani_sablona():
    gitignore = open(os.path.join(PROJ, ".gitignore"), encoding="utf-8").read()
    assert "sablona_inzeratu.txt" in gitignore


def _realna_sablona():
    """Načíta reálnu (gitignored) šablónu – None, ak neexistuje."""
    cesta = os.path.join(PROJ, "sablona_inzeratu.txt")
    if not os.path.exists(cesta):
        return None
    return modul_sablona.nacitaj_sablona(cesta)


def test_example_nema_realne_udaje():
    """Example šablóna má len dummy dáta – reálne hodnoty (telefón, PSČ,
    heslo) z pracovnej šablóny sa v example nesmú vyskytnúť."""
    realna = _realna_sablona()
    obsah = open(os.path.join(PROJ, "sablona_inzeratu.example.txt"), encoding="utf-8").read()
    assert "0900000000" in obsah  # dummy telefón
    if realna:
        for id_ in ("###05", "###07", "###08"):
            if realna.get(id_):
                assert realna[id_] not in obsah, f"reálna hodnota {id_} unikla do example!"


def test_history_nema_telefon():
    """História gitu nesmie obsahovať reálny telefón zo šablóny.
    (Reálne PSČ bolo z histórie odstránené filter-branch 31.8.2026 –
    hodnota je strážená testom test_trackovane_subory_nemaju_psc.)"""
    realna = _realna_sablona()
    telefon = realna.get("###07") if realna else None
    if not telefon:
        pytest.skip("reálna šablóna nie je k dispozícii")
    vysledok = subprocess.run(
        ["git", "-C", PROJ, "log", "--all", "--oneline", "-S", telefon],
        capture_output=True, text=True)
    assert vysledok.stdout.strip() == "", "telefón je v histórii!"


def test_trackovane_subory_nemaju_telefon():
    """Žiadny gitom sledovaný súbor nesmie obsahovať reálny telefón."""
    realna = _realna_sablona()
    telefon = realna.get("###07") if realna else None
    if not telefon:
        pytest.skip("reálna šablóna nie je k dispozícii")
    sledovane = subprocess.run(
        ["git", "-C", PROJ, "ls-files"], capture_output=True, text=True).stdout.splitlines()
    for rel in sledovane:
        cesta = os.path.join(PROJ, rel)
        if os.path.isfile(cesta):
            obsah = open(cesta, encoding="utf-8", errors="ignore").read()
            assert telefon not in obsah, f"telefón je v trackovanom súbore: {rel}"


def test_psc_nie_je_v_gite():
    """Reálne PSČ (###05) nesmie byť v trackovaných súboroch ANI v histórii.

    Regresný test: reálne PSČ uniklo do docstringu modul_sablona.py
    a komentára v testoch (31.8.2026) – telefón bol strážený, PSČ nie.
    Z histórie odstránené filter-branch 31.8.2026."""
    realna = _realna_sablona()
    psc = realna.get("###05") if realna else None
    if not psc:
        pytest.skip("reálna šablóna nie je k dispozícii")
    sledovane = subprocess.run(
        ["git", "-C", PROJ, "ls-files"], capture_output=True, text=True).stdout.splitlines()
    for rel in sledovane:
        cesta = os.path.join(PROJ, rel)
        if os.path.isfile(cesta):
            obsah = open(cesta, encoding="utf-8", errors="ignore").read()
            assert psc not in obsah, f"reálne PSČ je v trackovanom súbore: {rel}"
    vysledok = subprocess.run(
        ["git", "-C", PROJ, "log", "--all", "--oneline", "-S", psc],
        capture_output=True, text=True)
    assert vysledok.stdout.strip() == "", "reálne PSČ je v histórii!"


# ---------- modul_sablona ----------

def test_mapping_id_na_pole():
    assert modul_sablona.MAPPING["###01"] == "category"
    assert modul_sablona.MAPPING["###02"] == "nadpis"
    assert modul_sablona.MAPPING["###03"] == "popis"
    assert modul_sablona.MAPPING["###04"] == "cena"
    assert modul_sablona.MAPPING["###05"] == "lokalita"
    assert modul_sablona.MAPPING["###07"] == "telefoni"
    assert modul_sablona.MAPPING["###08"] == "heslobazar"


def test_nacitaj_sablona_zo_suboru():
    """Example šablóna sa načíta správne (###01..###09)."""
    s = modul_sablona.nacitaj_sablona(os.path.join(PROJ, "sablona_inzeratu.example.txt"))
    assert s.get("###01") == "PC, Počítače"
    assert s.get("###02") == "Príklad nadpisu inzerátu"
    assert s.get("###05") == "00000"
    assert s.get("###07") == "0900000000"
    assert len(s) >= 8


def test_nacitaj_sablona_preskoci_zly_riadok(tmp_path):
    """Nezrozumiteľné riadky sa preskočia, dobré sa načítajú."""
    subor = tmp_path / "sablona.txt"
    subor.write_text("###01:PC, Počítače\nblabla bez id\n###02:Nadpis\n", encoding="utf-8")
    s = modul_sablona.nacitaj_sablona(str(subor))
    assert s == {"###01": "PC, Počítače", "###02": "Nadpis"}


def test_nacitaj_sablona_chybajuci_subor(tmp_path):
    assert modul_sablona.nacitaj_sablona(str(tmp_path / "neexistuje.txt")) == {}


# ---------- modul_upload ----------

def test_najdi_fotky_vrati_vsetky_obrazky():
    fotky = modul_upload.najdi_fotky(os.path.join(PROJ, "obrazky"))
    assert len(fotky) >= 1
    for f in fotky:
        assert f.lower().endswith(modul_upload.PRIPONY)


def test_najdi_fotky_chybajuca_zlozka(tmp_path):
    assert modul_upload.najdi_fotky(str(tmp_path / "nic")) == []


def test_upload_ceka_na_dokoncenie():
    """Dropzone nahráva cez XHR – pred odoslaním treba počkať na dz-success."""
    src = open(os.path.join(SRC_PKG, "modul_upload.py"), encoding="utf-8").read()
    assert "pockaj_na_upload" in src and "dz-success" in src
    assert "dz-uploading" in src and "dz-error" in src


# ---------- flagy príkazového riadka ----------

def test_parse_args_vychodzie():
    args = b.parse_args([])
    assert args.debug is False
    assert args.sms_timeout is None
    assert args.neodosli is False
    assert args.init is False
    assert args.data_dir is None


def test_parse_args_debug_flag():
    assert b.parse_args(["--debug"]).debug is True


def test_parse_args_sms_timeout():
    args = b.parse_args(["--sms-timeout", "600"])
    assert args.sms_timeout == 600


def test_parse_args_neodosli_flag():
    assert b.parse_args(["--neodosli"]).neodosli is True


def test_parse_args_init_flag():
    assert b.parse_args(["--init"]).init is True


def test_parse_args_data_dir():
    assert b.parse_args(["--data-dir", "C:/moje/data"]).data_dir == "C:/moje/data"


def test_inicializuj_sablona(tmp_path, monkeypatch):
    """bazos --init vytvorí šablónu z example do dátového adresára;
    existujúcu šablónu NEPREPÍŠE (regresný test: čistá inštalácia
    z PyPI nemá example súbor z gitu, preto je zabalený v balíku)."""
    monkeypatch.setattr(b, "DATA_DIR", str(tmp_path))
    assert b.inicializuj_sablona() == 0
    ciel = tmp_path / "sablona_inzeratu.txt"
    assert ciel.exists()
    obsah = ciel.read_text(encoding="utf-8")
    assert "###01:" in obsah and "###07:" in obsah
    povodne = obsah
    assert b.inicializuj_sablona() == 1  # už existuje – neprepisuje
    assert ciel.read_text(encoding="utf-8") == povodne


def test_zisti_data_dir_explicit_má_prednosť(monkeypatch, tmp_path):
    """--data-dir má prednosť pred env aj aktuálnym adresárom."""
    monkeypatch.setenv("BAZOS_DATA_DIR", str(tmp_path / "env"))
    monkeypatch.chdir(tmp_path)
    assert b.zisti_data_dir(str(tmp_path / "flag")) == str(tmp_path / "flag")


def test_zisti_data_dir_env_pred_cwd(monkeypatch, tmp_path):
    """BAZOS_DATA_DIR má prednosť pred aktuálnym adresárom."""
    (tmp_path / "sablona_inzeratu.txt").write_text("###01:x\n", encoding="utf-8")
    monkeypatch.setenv("BAZOS_DATA_DIR", str(tmp_path / "env"))
    monkeypatch.chdir(tmp_path)
    assert b.zisti_data_dir() == str(tmp_path / "env")


def test_zisti_data_dir_cwd_s_šablónou(monkeypatch, tmp_path):
    """Bez env sa použije aktuálny adresár, ak má šablónu."""
    (tmp_path / "sablona_inzeratu.txt").write_text("###01:x\n", encoding="utf-8")
    monkeypatch.delenv("BAZOS_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert b.zisti_data_dir() == str(tmp_path)


def test_zisti_data_dir_domov_fallback(monkeypatch, tmp_path):
    """Fallback: ~/.bazos-automation (portable – bez použitia usera)."""
    monkeypatch.delenv("BAZOS_DATA_DIR", raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / "nic").mkdir()
    monkeypatch.chdir(tmp_path / "nic")
    assert b.zisti_data_dir() == str(tmp_path / ".bazos-automation")


def test_nastav_data_dir(monkeypatch, tmp_path):
    """--data-dir prepne globály (DATA_DIR, cesty, SABLONA, TELEFON)."""
    sablona = ("###01:PC, Počítače\n###02:Titulok\n###05:00000\n###07:0900000000\n")
    (tmp_path / "sablona_inzeratu.txt").write_text(sablona, encoding="utf-8")
    b.nastav_data_dir(str(tmp_path))
    assert b.DATA_DIR == str(tmp_path)
    assert b.CESTA_K_SABLONE == str(tmp_path / "sablona_inzeratu.txt")
    assert b.PROFIL_EDGE == str(tmp_path / "edge_profile")
    assert b.SABLONA.get("###02") == "Titulok"
    assert b.TELEFON == "0900000000"


def test_rozhodni_odoslat(monkeypatch):
    """Flag --neodosli aj DEBUG_CEKANIE rozhodujú: ktokoľvek zapnutý = neodoslať."""
    monkeypatch.setattr(b, "DEBUG_CEKANIE", False)
    assert b.rozhodni_odoslat(False) is True    # produkcia: odošle
    assert b.rozhodni_odoslat(True) is False    # --neodosli: neodošle
    monkeypatch.setattr(b, "DEBUG_CEKANIE", True)
    assert b.rozhodni_odoslat(False) is False   # DEBUG_CEKANIE=True: neodošle
    assert b.rozhodni_odoslat(True) is False    # oboje: neodošle


def test_debug_mode_vypnuty_standardne():
    assert b.DEBUG_MODE is False


def test_debug_limity_su_dlhsie():
    assert b.DEBUG_SMS_CEKANIE_SEKUND > b.SMS_CEKANIE_SEKUND
    assert b.DEBUG_LIMIT_NACITANIA > b.LIMIT_NACITANIA
    assert b.DEBUG_LIMIT_FORMULARA_INZERATU > b.LIMIT_FORMULARA_INZERATU
    assert b.DEBUG_LIMIT_UPLOAD_SEKUND > b.LIMIT_UPLOAD_SEKUND


# ---------- detekcia prehľadu kategórie ----------

class FakeBody:
    def __init__(self, text):
        self._t = text

    @property
    def text(self):
        return self._t


class FakeBodyDriver:
    def __init__(self, text):
        self.body_text = text

    def find_element(self, by, val):
        if by == "tag name" and val == "body":
            return FakeBody(self.body_text)
        raise RuntimeError("neočakávané volanie find_element")


def test_kategoria_rozpoznana_podla_strankovania():
    d = FakeBodyDriver("Inzeráty PC celkom ... Stránka: 1 2 3 4 5 Ďalšia ...")
    assert b.je_kategoria_prehlad(d) is True


def test_overovaci_formular_nie_je_kategoria():
    d = FakeBodyDriver("Pred pridaním inzerátu je nutné overenie mobilného telefónu")
    assert b.je_kategoria_prehlad(d) is False


# ---------- dynamická detekcia poľa pre SMS kód ----------

class FakeInput:
    def __init__(self, name, typ="text", visible=True):
        self._n, self._t, self._v = name, typ, visible

    def get_attribute(self, a):
        return {"name": self._n, "type": self._t}.get(a)

    def is_displayed(self):
        return self._v


class FakeDriver:
    """By.NAME == 'name', By.TAG_NAME == 'tag name' (Selenium 4 stringy)."""

    def __init__(self, state_fn):
        self.state_fn = state_fn
        self.log = []

    def find_elements(self, by, val):
        has_nadpis, inputs = self.state_fn()
        self.log.append((by, val))
        if by == "name" and val == "nadpis":
            return [object()] if has_nadpis else []
        if by == "tag name" and val == "input":
            return inputs
        return []


class StateOnlyTeloverit:
    def __call__(self):
        return False, [FakeInput("teloverit")]


class StateCodeAppears:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls == 1:
            return False, [FakeInput("teloverit")]
        return False, [FakeInput("teloverit"), FakeInput("overovacikod")]


class StateAdForm:
    def __call__(self):
        return True, [FakeInput("nadpis"), FakeInput("popis")]


class StateSearchOnly:
    def __call__(self):
        return False, [FakeInput("hledat", typ="search"), FakeInput("teloverit")]


class StateSearchTextFields:
    """Regresný test: vyhľadávací formulár má aj textové polia (humkreis,
    cenaod, cenado) – bez vylúčenia by sa brali ako pole pre SMS kód."""

    def __call__(self):
        return False, [FakeInput("hledat", typ="search"), FakeInput("hlokalita", typ="search"),
                       FakeInput("humkreis", typ="text"), FakeInput("cenaod", typ="text"),
                       FakeInput("cenado", typ="text"), FakeInput("teloverit", typ="text")]


def test_detekcia_len_teloverit_vrati_none():
    r = b.najdi_pole_kodu(FakeDriver(StateOnlyTeloverit()), casovy_limit=2)
    assert r is None


def test_detekcia_najde_pole_kodu():
    r = b.najdi_pole_kodu(FakeDriver(StateCodeAppears()), casovy_limit=5)
    assert r is not None
    assert r.get_attribute("name") == "overovacikod"


def test_detekcia_rovno_formular_inzeratu():
    fd = FakeDriver(StateAdForm())
    r = b.najdi_pole_kodu(fd, casovy_limit=3)
    assert r is None
    assert len(fd.log) == 1  # okamžite, bez čakania


def test_detekcia_ignoruje_search_polia():
    r = b.najdi_pole_kodu(FakeDriver(StateSearchOnly()), casovy_limit=2)
    assert r is None


def test_detekcia_ignoruje_search_text_polia():
    """humkreis/cenaod/cenado sú type=text, ale NESMIA byť pole pre kód."""
    r = b.najdi_pole_kodu(FakeDriver(StateSearchTextFields()), casovy_limit=2)
    assert r is None


class KlicFakeDriver:
    """Stránka s už známym poľom pre kód (name='klic' – zistené 30.8.2026)."""

    def find_elements(self, by, val):
        if by == "name" and val == "klic":
            return [FakeInput("klic")]
        return []


def test_detekcia_preferuje_zname_pole_klic():
    r = b.najdi_pole_kodu(KlicFakeDriver(), casovy_limit=2)
    assert r is not None
    assert r.get_attribute("name") == "klic"
