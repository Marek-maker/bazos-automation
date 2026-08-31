"""bazos_automation – automatizácia pridávania inzerátov na Bazoš.sk.

Balík obsahuje:
    bazos_pridaj_inzerat.py – orchestrátor (CLI, Selenium + Edge)
    modul_sablona.py       – šablóna ###ID:hodnota -> polia formulára
    modul_upload.py        – Dropzone upload fotiek jedna za druhou

Dáta (sablona_inzeratu.txt, obrazky/, edge_profile/) NIE sú súčasťou balíka –
hľadajú sa v poradí: env BAZOS_DATA_DIR -> aktuálny adresár -> ~/.bazos-automation.
"""

__version__ = "0.1.1"

from .modul_sablona import MAPPING, nacitaj_sablona
from .modul_upload import nahraj_fotky
from .bazos_pridaj_inzerat import main

__all__ = ["MAPPING", "nacitaj_sablona", "nahraj_fotky", "main", "__version__"]
