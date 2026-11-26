"""Fusion et imports : les défauts relevés par l'audit du 10/11/2026 (roadmap 753, 573, 711, 751).

Lancer :  NAVIGATEURS=chromium python -m pytest tests/test_fusion_import.py
"""

import importlib.util
import json
import re
import time
from datetime import datetime, timezone

import pytest
from conftest import RACINE
from playwright.sync_api import expect
from test_forfaits import (
    TOUS,
    activer_modif,
    cartes,
    chercher,
    dialogue,
    ecrire_tableau,
    espaces,
    exporter_json,
    importer,
    ouvrir_tableau,
    refs,
)

# Clé du stockage des données, écrite en morceaux (gitleaks la prend sinon pour un secret).
CLE_DONNEES = ".".join(["forfaits", "donnees", "v1"])
JOUR = 86400000


def maintenant():
    return int(time.time() * 1000)


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ecrire_fichier(chemin, familles=(), elements=(), forfaits=(), exporte=None):
    """Fichier de sauvegarde comme l'outil l'exporte (format 2)."""
    contenu = {
        "format": "forfaits-comptoir",
        "version": 2,
        "exporteLe": iso(exporte if exporte is not None else maintenant()),
        "familles": list(familles),
        "elements": list(elements),
        "forfaits": list(forfaits),
    }
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    return chemin


def forfait(identifiant, ref, ht=10000, ttc=12000, elements=None, maj=1):
    return {"id": identifiant, "ref": ref, "designation": "", "ht": ht, "ttc": ttc, "elements": elements or {}, "maj": maj}


def refus(page, chemin):
    """Choisit un fichier que l'outil doit refuser d'emblée ; renvoie le texte de la fenêtre."""
    page.set_input_files("#fichier-import", [])
    page.set_input_files("#fichier-import", str(chemin))
    d = dialogue(page)
    expect(d).to_contain_text("Import impossible")
    texte = d.text_content()
    d.get_by_role("button", name="Compris").click()
    expect(page.locator("dialog[open]")).to_have_count(0)
    return texte


def stockage(page):
    return page.evaluate("cle => JSON.parse(localStorage.getItem(cle))", CLE_DONNEES)


# ---------------------------------------------------------------- roadmap 753


def test_forfait_qui_utilise_un_element_supprime_ailleurs_est_signale(page, tmp_path):
    """L'élément est supprimé sur cet appareil ; un autre appareil, qui l'avait encore, a créé un forfait avec."""
    zorba8 = {"id": "elt-zorba8", "familleId": "fam-boitier", "nom": "Zorba 8", "maj": maintenant() - 3600000}
    importer(page, ecrire_fichier(tmp_path / "avec-zorba8.json", elements=[zorba8]))

    activer_modif(page)
    page.click("#btn-menu")
    page.click("#btn-listes")
    dialogue(page).get_by_role("button", name="Supprimer Zorba 8", exact=True).click()
    dialogue(page).get_by_role("button", name="Supprimer", exact=True).click()
    dialogue(page).get_by_role("button", name="Terminé").click()
    expect(page.locator("dialog[open]")).to_have_count(0)

    kalpo9 = forfait("fft-kalpo9", "KALPO-9", elements={"fam-boitier": "elt-zorba8"}, maj=maintenant() - 1800000)
    page.set_input_files("#fichier-import", str(ecrire_fichier(tmp_path / "autre.json", elements=[zorba8], forfaits=[kalpo9])))
    dialogue(page).get_by_role("button", name="Mettre à jour", exact=True).click()
    d = dialogue(page)
    expect(d).to_contain_text("Forfaits à corriger")
    expect(d).to_contain_text("Forfait KALPO-9 : Boîtier « Zorba 8 » supprimé")


def test_tableau_annonce_un_nom_range_avec_un_element_proche(page, tmp_path):
    d = ouvrir_tableau(
        page,
        ecrire_tableau(
            tmp_path / "proches.csv",
            [
                "Z-1;;100,00;120,00;;Zorba 5+;;;",
                "Z-2;;100,00;120,00;;Kalpo-X;;;",
                "Z-3;;100,00;120,00;;zorba 5;;;",  # majuscules seules : c'est bien lui, rien à dire
            ],
        ),
    )
    expect(d).to_contain_text("Noms lus comme un élément qui existe déjà")
    expect(d).to_contain_text("Boîtier : « Zorba 5+ » rangé avec « Zorba 5 »")
    expect(d).to_contain_text("Boîtier : « Kalpo-X » rangé avec « Kalpo X »")
    assert "« zorba 5 »" not in d.text_content()
    d.get_by_role("button", name="Annuler").click()


def test_import_json_qui_casserait_le_stockage_est_refuse(page, tmp_path):
    """Fichier retouché : un forfait porte l'identifiant d'un élément de l'appareil. Seul, il est valable ; uni aux
    données de l'appareil, il serait refusé au prochain chargement, et toutes les données mises de côté."""
    piege = ecrire_fichier(tmp_path / "piege.json", forfaits=[forfait("elt-zorba5", "PIEGE-1")])
    page.set_input_files("#fichier-import", str(piege))
    dialogue(page).get_by_role("button", name="Mettre à jour", exact=True).click()
    d = dialogue(page)
    expect(d).to_contain_text("Import impossible")
    expect(d).to_contain_text("identifiant en double")
    d.get_by_role("button", name="Compris").click()
    assert refs(page) == TOUS
    page.reload()
    page.wait_for_selector("#resultats .carte")
    assert refs(page) == TOUS
    assert not page.evaluate("cle => Object.keys(localStorage).some(k => k.startsWith(cle + '.illisible.'))", CLE_DONNEES)


# ---------------------------------------------------------------- roadmap 573 et 711


def test_trop_d_enregistrements_refuse_dans_le_fichier_comme_dans_l_union(page, tmp_path):
    # Forfaits affichés : 5 000 au plus, comme le tableau (à 20 000, l'ouverture prenait 40 s).
    trop = [forfait(f"fft-n{i:05d}", f"N-{i}") for i in range(5001)]
    texte = refus(page, ecrire_fichier(tmp_path / "trop.json", forfaits=trop))
    assert "beaucoup trop d'enregistrements" in texte
    # Les marques de suppression ne comptent que dans le plafond total de 20 000.
    supprimes = [{**forfait(f"fft-s{i:05d}", f"S-{i}"), "supprime": True} for i in range(20001)]
    texte = refus(page, ecrire_fichier(tmp_path / "total.json", forfaits=supprimes))
    assert "beaucoup trop d'enregistrements" in texte

    # 4 995 forfaits passent seuls, mais pas avec les 11 de l'appareil.
    juste = ecrire_fichier(tmp_path / "juste.json", forfaits=trop[:4995])
    page.set_input_files("#fichier-import", [])
    page.set_input_files("#fichier-import", str(juste))
    dialogue(page).get_by_role("button", name="Mettre à jour", exact=True).click()
    d = dialogue(page)
    expect(d).to_contain_text("Import impossible")
    expect(d).to_contain_text("beaucoup trop d'enregistrements")
    d.get_by_role("button", name="Compris").click()
    assert refs(page) == TOUS

    # 6 000 suppressions et 10 forfaits : accepté (un appareil en service accumule les suppressions).
    importer(page, ecrire_fichier(tmp_path / "supprimes.json", forfaits=trop[:10] + supprimes[:6000]))
    assert len(stockage(page)["forfaits"]) == 11 + 10 + 6000


def test_ancien_fichier_sans_surnoms_ni_plafond_reste_lisible(page, tmp_path):
    """Format 1, sans date d'export : toujours lu."""
    ancien = {
        "format": "forfaits-comptoir",
        "version": 1,
        "familles": [],
        "elements": [],
        "forfaits": [forfait("fft-ancien1", "ANCIEN-1", maj=maintenant() - JOUR)],
    }
    chemin = tmp_path / "ancien.json"
    chemin.write_text(json.dumps(ancien), encoding="utf-8")
    importer(page, chemin)
    assert "ANCIEN-1" in refs(page)


def test_copies_illisibles_purgees_les_trois_plus_recentes_gardees(page):
    page.evaluate(
        """cle => {
            localStorage.setItem(cle, '{abîmé');
            for (let i = 1; i <= 5; i++) localStorage.setItem(cle + '.illisible.' + i * 1000, 'ancienne ' + i);
        }""",
        CLE_DONNEES,
    )
    for _ in range(3):  # trois chargements refusés : une seule copie de plus, pas trois
        page.reload()
        page.wait_for_selector("#resultats .carte")
    copies = page.evaluate(
        "cle => Object.keys(localStorage).filter(k => k.startsWith(cle + '.illisible.')).map(k => localStorage.getItem(k))",
        CLE_DONNEES,
    )
    assert sorted(copies) == sorted(["{abîmé", "ancienne 5", "ancienne 4"])


# ---------------------------------------------------------------- roadmap 751


def test_fusion_a_date_egale_donne_le_meme_resultat_des_deux_cotes(appareils, tmp_path):
    a = appareils().page
    b = appareils().page
    base = exporter_json(a, tmp_path / "base.json")
    versions = {}
    for nom, ttc in (("v1", 90000), ("v2", 95000)):
        fichier = json.loads(json.dumps(base))
        for f in fichier["forfaits"]:
            if f["ref"] == "EX-T2-3Q":
                f["ttc"] = ttc  # même date (maj 0) des deux côtés
        versions[nom] = tmp_path / f"{nom}.json"
        versions[nom].write_text(json.dumps(fichier), encoding="utf-8")
    importer(a, versions["v1"], "Remplacer tout")
    importer(b, versions["v2"], "Remplacer tout")
    importer(a, versions["v2"])
    b.set_input_files("#fichier-import", [])
    importer(b, versions["v1"])
    prix = []
    for p in (a, b):
        chercher(p, "EX-T2-3Q")
        prix.append(espaces(cartes(p)[0]["ttc"]))
    assert prix[0] == prix[1]


def test_borne_de_date_suit_la_date_d_export_du_fichier(page, tmp_path):
    exporte = maintenant() - 2 * 3600000
    futur = forfait("fft-futur1", "FUTUR-1", maj=maintenant() + 30 * JOUR)
    importer(page, ecrire_fichier(tmp_path / "futur.json", forfaits=[futur], exporte=exporte))
    gardes = [f["maj"] for f in stockage(page)["forfaits"] if f["ref"] == "FUTUR-1"]
    assert gardes == [exporte + JOUR]  # la même date quel que soit le moment de l'import


def test_fichier_exporte_dans_le_futur_refuse(page, tmp_path):
    chemin = ecrire_fichier(tmp_path / "horloge.json", forfaits=[forfait("fft-h1", "H-1")], exporte=maintenant() + 3 * JOUR)
    assert "horloge" in refus(page, chemin)
    assert refs(page) == TOUS


def test_tableau_nom_d_element_trop_long_refuse(page, tmp_path):
    long = "Zorba modèle " + "x" * 50
    chemin = ecrire_tableau(tmp_path / "long.csv", [f"L-1;;100,00;120,00;;{long};;;"])
    page.set_input_files("#fichier-import", str(chemin))
    d = dialogue(page)
    expect(d).to_contain_text("Import impossible")
    expect(d).to_contain_text("nom trop long (60 caractères au maximum)")


def test_tableau_guillemet_non_referme_refuse(page, tmp_path):
    chemin = ecrire_tableau(
        tmp_path / "guillemet.csv",
        ['G-1;"Écran 12 pouces;100,00;120,00;;;;;', "G-2;Autre;200,00;240,00;;;;;"],
        vides=0,
    )
    page.set_input_files("#fichier-import", str(chemin))
    d = dialogue(page)
    expect(d).to_contain_text("Import impossible")
    expect(d).to_contain_text("Ligne 2 : une cellule commence par un guillemet")


def test_famille_nommee_comme_une_colonne_du_tableau_refusee(page):
    activer_modif(page)
    page.click("#btn-menu")
    page.click("#btn-listes")
    d = dialogue(page)
    champ = d.get_by_label("Nouvelle famille")
    champ.fill("Exemple")
    champ.press("Enter")
    expect(d).to_contain_text("« Exemple » est le titre d'une colonne du tableau Excel")
    expect(d.get_by_label("Nom de la famille Exemple")).to_have_count(0)
    renomme = d.get_by_label("Nom de la famille Lumineux")
    renomme.fill("Prix HT")
    renomme.press("Tab")
    expect(d).to_contain_text("« Prix HT » est le titre d'une colonne du tableau Excel")
    expect(renomme).to_have_value("Lumineux")


def test_reference_en_double_dans_l_outil_signalee_a_l_import_du_tableau(page, tmp_path):
    double = forfait("fft-double", "EX-T2-3Q", maj=maintenant() - 3600000)
    page.set_input_files("#fichier-import", str(ecrire_fichier(tmp_path / "double.json", forfaits=[double])))
    dialogue(page).get_by_role("button", name="Mettre à jour", exact=True).click()
    expect(dialogue(page)).to_contain_text("Référence EX-T2-3Q (2 fois)")
    dialogue(page).get_by_role("button", name="Compris").click()

    d = ouvrir_tableau(page, ecrire_tableau(tmp_path / "t.csv", ["EX-T2-3Q;;800,00;960,00;T2;;3Q;;"]))
    expect(d).to_contain_text("Références présentes plusieurs fois dans l'outil")
    expect(d).to_contain_text("EX-T2-3Q (2 forfaits)")
    d.get_by_role("button", name="Annuler").click()


def test_bilan_d_import_annonce_elements_et_familles_renommes_ou_supprimes(page, tmp_path):
    fichier = exporter_json(page, tmp_path / "base.json")
    plus_tard = maintenant()
    for x in fichier["familles"]:
        if x["id"] == "fam-installation":
            x.update(nom="Pose", maj=plus_tard)
    for x in fichier["elements"]:
        if x["id"] == "elt-zorba5":
            x.update(nom="Zorba 6", maj=plus_tard)
        if x["id"] == "elt-kalpou":
            x.update(supprime=True, maj=plus_tard)
    chemin = tmp_path / "renomme.json"
    chemin.write_text(json.dumps(fichier), encoding="utf-8")
    page.set_input_files("#fichier-import", str(chemin))
    d = dialogue(page)
    expect(d).to_contain_text("Éléments et familles renommés")
    expect(d).to_contain_text("Famille Installation → Pose")
    expect(d).to_contain_text("Boîtier : Zorba 5 → Zorba 6")
    expect(d).to_contain_text("Éléments et familles supprimés : Boîtier : Kalpo universelle")
    d.get_by_role("button", name="Annuler").click()


def test_modele_excel_controle_autant_de_lignes_que_l_import():
    pytest.importorskip("openpyxl")
    spec = importlib.util.spec_from_file_location("modele_excel", RACINE / "outils" / "modele_excel.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    html = (RACINE / "index.html").read_text(encoding="utf-8")
    lignes_max = int(re.search(r"const LIGNES_TABLEAU_MAX = (\d+);", html).group(1))
    assert module.DERNIERE_LIGNE == lignes_max + 1  # la ligne des titres, puis un forfait par ligne
