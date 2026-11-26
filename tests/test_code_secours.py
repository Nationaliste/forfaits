"""outils/code_secours.py : le code tiré passe le minimum du cloud et se recopie sans confusion."""

import importlib.util
import re

from conftest import RACINE

_spec = importlib.util.spec_from_file_location("code_secours", RACINE / "outils" / "code_secours.py")
code_secours = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(code_secours)


def test_le_code_tire_passe_le_minimum_du_cloud():
    minimum = int(re.search(r"CODE_SECOURS_MIN = (\d+)", (RACINE / "cloud" / "src" / "index.js").read_text(encoding="utf-8"))[1])
    codes = {code_secours.code_secours() for _ in range(200)}
    assert len(codes) == 200  # tiré au hasard
    for code in codes:
        assert len(code) >= minimum
        assert re.fullmatch(r"([A-HJKMNP-Z2-9]{5}-){4}[A-HJKMNP-Z2-9]{5}", code), code  # ni 0/O, ni 1/I/L
