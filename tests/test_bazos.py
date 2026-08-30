r"""Canonical testy pre Bazoš automatizáciu (pytest).

Spustenie (koreň projektu):
    .venv\Scripts\python -m pytest
"""
import os
import py_compile

import bazos_pridaj_inzerat as b

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- štruktúra modulu ----------

def test_syntax():
    py_compile.compile(os.path.join(PROJ, "bazos_pridaj_inzerat.py"), doraise=True)


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
    for name in ("ziskaj_prehliadac", "odsuhlas_cookies", "najdi_pole_kodu",
                 "naviguj_na_pridanie", "over_telefon", "vypln_inzerat",
                 "pridaj_inzerat_bazos"):
        assert callable(getattr(b, name, None)), f"chýba funkcia: {name}"


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
