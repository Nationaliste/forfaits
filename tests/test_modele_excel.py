"""Le modèle Excel (outils/modele_excel.py) doit rester d'accord avec l'outil : mêmes titres, mêmes familles."""

import importlib.util
import re
import sys

import pytest
from conftest import RACINE

openpyxl = pytest.importorskip("openpyxl")

HTML = (RACINE / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def module_modele():
    spec = importlib.util.spec_from_file_location("modele_excel", RACINE / "outils" / "modele_excel.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def modele(module_modele, tmp_path_factory):
    chemin = tmp_path_factory.mktemp("modele") / "modele.xlsx"
    module_modele.fabriquer().save(chemin)
    return openpyxl.load_workbook(chemin)


def test_outil_n_ecrase_jamais_un_fichier_existant(module_modele, tmp_path, monkeypatch):
    rempli = tmp_path / "rempli.xlsx"
    rempli.write_bytes(b"saisie de l'utilisateur")
    monkeypatch.setattr(sys, "argv", ["modele_excel.py", str(rempli)])
    with pytest.raises(SystemExit) as refus:
        module_modele.main()
    assert "existe déjà" in str(refus.value)
    assert rempli.read_bytes() == b"saisie de l'utilisateur"  # intact
    neuf = tmp_path / "dossier" / "neuf.xlsx"
    monkeypatch.setattr(sys, "argv", ["modele_excel.py", str(neuf)])
    module_modele.main()  # un chemin libre marche toujours
    assert neuf.is_file()


def familles_de_l_outil():
    """Familles de départ dans l'ordre, lues dans index.html."""
    trouvees = re.findall(r"id: '(fam-[a-z]+)', nom: '([^']+)', ordre: (\d+)", HTML)
    return [(identifiant, nom) for identifiant, nom, _ in sorted(trouvees, key=lambda x: int(x[2]))]


def test_modele_a_les_titres_de_l_export_csv_de_l_outil(modele):
    assert modele.sheetnames == ["Forfaits", "Listes", "Mode d'emploi"]
    assert modele.active.title == "Forfaits"  # Excel n'enregistre en CSV que l'onglet actif
    titres = [c.value for c in modele["Forfaits"][1]]
    assert titres[:4] == ["Référence", "Désignation", "Prix HT", "Prix TTC"]
    # Mêmes familles que l'outil ; l'ordre est libre (l'import lit les colonnes par leur titre).
    assert sorted(titres[4:]) == sorted(nom for _, nom in familles_de_l_outil())
    assert titres[-2:] == ["Boîtier", "Installation"]  # les deux qui servent rarement, à droite


def test_modele_a_les_listes_de_depart_de_l_outil(modele):
    attendu = {identifiant: [] for identifiant, _ in familles_de_l_outil()}
    for famille, nom in re.findall(r"el\('elt-[a-z0-9-]+', '(fam-[a-z]+)', '([^']+)'\)", HTML):  # sans les exemples
        attendu[famille].append(nom)
    attendu_par_nom = {nom: attendu[identifiant] for identifiant, nom in familles_de_l_outil()}
    listes = modele["Listes"]
    titres_forfaits = [c.value for c in modele["Forfaits"][1]][4:]
    for colonne, nom in enumerate(titres_forfaits, start=1):
        assert listes.cell(row=1, column=colonne).value == nom  # même ordre que les colonnes de l'onglet Forfaits
        valeurs = [c.value for c in listes[openpyxl.utils.get_column_letter(colonne)][1:] if c.value]
        assert valeurs == ["/", *attendu_par_nom[nom]], nom  # « / » (pas de données) en tête, puis les éléments de départ


def test_modele_est_vide_et_controle_les_saisies(modele):
    forfaits = modele["Forfaits"]
    assert not [c for ligne in forfaits.iter_rows(min_row=2) for c in ligne if c.value is not None]  # rien à importer par erreur
    validations = forfaits.data_validations.dataValidation
    assert len(validations) == len(familles_de_l_outil())
    assert all(v.type == "list" and "Listes!" in v.formula1 and v.showErrorMessage for v in validations)
    assert {v.errorStyle for v in validations} == {"warning"}  # un élément nouveau se tape : l'outil le crée à l'import
    assert {str(v.sqref).split(":")[0] for v in validations} == {"E2", "F2", "G2", "H2", "I2"}
    regles = sum(len(plage.rules) for plage in forfaits.conditional_formatting)
    assert regles == 5  # cases vides (référence, HT, TTC), référence en double, TTC différent de HT + 20 %
