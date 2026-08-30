r"""Canonical testy pre Bazoš automatizáciu (pytest).

Spustenie (koreň projektu):
    .venv\Scripts\python -m pytest
"""
import os
import py_compile

import bazos_pridaj_inzerat as b
import modul_sablona
import modul_upload

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- štruktúra modulov ----------

def test_syntax():
    for rel in ("bazos_pridaj_inzerat.py", "modul_sablona.py", "modul_upload.py"):
        py_compile.compile(os.path.join(PROJ, rel), doraise=True)


def test_konstanty():
    assert b.SMS_CEKANIE_SEKUND > 0
    assert b.DEBUG_CEKANIE is True
    assert b.TELEFON


def test_url_constanty():
    assert b.URL_KATEGORIA_PC == "https://pc.bazos.sk/"
    assert b.URL_PRIDAT_INZERAT == "https://pc.bazos.sk/pridat-inzerat.php"


def test_edge_only_bez_chrome():
    src = open(os.path.join(PROJ, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "ChromeDriverManager" not in src
    assert "EdgeChromiumDriverManager" in src


def test_funkcie_existuju():
    for name in ("parse_args", "aktivuj_debug", "log_viditelny_text", "vstup",
                 "je_kategoria_prehlad", "ziskaj_prehliadac", "odsuhlas_cookies",
                 "najdi_pole_kodu", "naviguj_na_pridanie", "over_telefon",
                 "vyber_kategoriu", "vypis_elementy_formulara",
                 "vypln_inzerat", "odosli_inzerat", "pridaj_inzerat_bazos"):
        assert callable(getattr(b, name, None)), f"chýba funkcia: {name}"


def test_vylucene_polia():
    for meno in ("teloverit", "hledat", "hlokalita", "humkreis", "cenaod", "cenado"):
        assert meno in b.VYLUCENE_POLIA


def test_overenie_klika_v_ramci_formovereni():
    """Submit overenia MUSÍ byť scoping do formovereni – inak sa odošle
    vyhľadávací formulár (oba majú name='Submit'). Regresný test."""
    src = open(os.path.join(PROJ, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert 'find_element(By.NAME, "formovereni")' in src
    assert './/input[@type=\'submit\']' in src or './/input[@type="submit"]' in src


def test_persistentny_profil():
    """Overenie telefónu sa uchová medzi behmi cez --user-data-dir."""
    src = open(os.path.join(PROJ, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "PROFIL_EDGE" in src and "user-data-dir" in src


def test_hlavny_skript_pouziva_moduly():
    """Hlavný skript musí používať modul šablóny aj modul uploadu."""
    src = open(os.path.join(PROJ, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "from modul_sablona import" in src
    assert "from modul_upload import" in src
    assert "sablona_inzeratu.txt" in src


def test_odoslanie_scoping_do_formulara():
    """Odoslanie inzerátu musí byť scoping do formulára s nadpisom –
    name='Submit' majú vyhľadávací aj overovací formulár."""
    src = open(os.path.join(PROJ, "bazos_pridaj_inzerat.py"), encoding="utf-8").read()
    assert "def odosli_inzerat" in src
    assert 'find_element(By.NAME, "nadpis")' in src
    assert "./ancestor::form" in src


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
    """Reálna šablóna v repo sa načíta správne (###01..###05)."""
    s = modul_sablona.nacitaj_sablona(os.path.join(PROJ, "sablona_inzeratu.txt"))
    assert s.get("###01") == "PC, Počítače"
    assert s.get("###02") == "Repasovaný Dell PowerEdge Server - Záruka"
    assert s.get("###05") == "00000"
    assert len(s) >= 5


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
    src = open(os.path.join(PROJ, "modul_upload.py"), encoding="utf-8").read()
    assert "pockaj_na_upload" in src and "dz-success" in src
    assert "dz-uploading" in src and "dz-error" in src


# ---------- flagy príkazového riadka ----------

def test_parse_args_vychodzie():
    args = b.parse_args([])
    assert args.debug is False
    assert args.sms_timeout is None


def test_parse_args_debug_flag():
    assert b.parse_args(["--debug"]).debug is True


def test_parse_args_sms_timeout():
    args = b.parse_args(["--sms-timeout", "600"])
    assert args.sms_timeout == 600


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
