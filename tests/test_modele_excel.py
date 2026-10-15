"""Le modèle Excel (outils/modele_excel.py) doit rester d'accord avec l'outil : mêmes titres, mêmes familles."""

import importlib.util
import re

import pytest
from conftest import RACINE

openpyxl = pytest.importorskip("openpyxl")

HTML = (RACINE / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def modele(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("modele_excel", RACINE / "outils" / "modele_excel.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    chemin = tmp_path_factory.mktemp("modele") / "modele.xlsx"
    module.fabriquer().save(chemin)
    return openpyxl.load_workbook(chemin)


def familles_de_l_outil():
    """Familles de départ dans l'ordre, lues dans index.html."""
    trouvees = re.findall(r"id: '(fam-[a-z]+)', nom: '([^']+)', ordre: (\d+)", HTML)
    return [(identifiant, nom) for identifiant, nom, _ in sorted(trouvees, key=lambda x: int(x[2]))]


def test_modele_a_les_titres_de_l_export_csv_de_l_outil(modele):
    assert modele.sheetnames == ["Forfaits", "Listes", "Mode d'emploi"]
    assert modele.active.title == "Forfaits"  # Excel n'enregistre en CSV que l'onglet actif
    titres = [c.value for c in modele["Forfaits"][1]]
    assert titres == ["Référence", "Désignation", "Prix HT", "Prix TTC", *[nom for _, nom in familles_de_l_outil()]]


def test_modele_a_les_listes_de_depart_de_l_outil(modele):
    attendu = {identifiant: [] for identifiant, _ in familles_de_l_outil()}
    for famille, nom in re.findall(r"el\('elt-[a-z0-9-]+', '(fam-[a-z]+)', '([^']+)'\)", HTML):  # sans les exemples
        attendu[famille].append(nom)
    listes = modele["Listes"]
    for colonne, (identifiant, nom) in enumerate(familles_de_l_outil(), start=1):
        assert listes.cell(row=1, column=colonne).value == nom
        valeurs = [c.value for c in listes[openpyxl.utils.get_column_letter(colonne)][1:] if c.value]
        assert valeurs == attendu[identifiant], nom


def test_modele_est_vide_et_controle_les_saisies(modele):
    forfaits = modele["Forfaits"]
    assert not [c for ligne in forfaits.iter_rows(min_row=2) for c in ligne if c.value is not None]  # rien à importer par erreur
    validations = forfaits.data_validations.dataValidation
    assert len(validations) == len(familles_de_l_outil())
    assert all(v.type == "list" and "Listes!" in v.formula1 and v.showErrorMessage for v in validations)
    assert {str(v.sqref).split(":")[0] for v in validations} == {"E2", "F2", "G2", "H2", "I2"}
    regles = sum(len(plage.rules) for plage in forfaits.conditional_formatting)
    assert regles == 5  # cases vides (référence, HT, TTC), référence en double, TTC différent de HT + 20 %
