"""Tests de synchro sautés quand le cloud ne démarre pas : la raison doit se voir (audit du 10/11/2026, roadmap 750)."""

import tomllib

import conftest
import pytest
from conftest import RACINE


def test_la_raison_des_tests_sautes_s_affiche():
    """Avec « -q » seul, 30 tests de synchro sautés ne laissaient qu'un « s » perdu dans la ligne de points."""
    options = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]["addopts"]
    assert "-rs" in options.split()


def test_synchro_exigee_fait_echouer_au_lieu_de_sauter(monkeypatch):
    monkeypatch.setattr(conftest, "SYNCHRO_EXIGEE", False)
    with pytest.raises(pytest.skip.Exception, match="wrangler absent"):
        conftest.sauter_ou_echouer("wrangler absent")
    monkeypatch.setattr(conftest, "SYNCHRO_EXIGEE", True)
    with pytest.raises(pytest.fail.Exception, match="wrangler absent"):
        conftest.sauter_ou_echouer("wrangler absent")
