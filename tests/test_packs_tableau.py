"""Packs (roadmap 713, lot 2) : un pack s'écrit, se relit et se modifie par le tableau, une case « Contenu » par pack.

Lancer :  NAVIGATEURS=chromium python -m pytest tests/test_packs_tableau.py
"""

import importlib.util
import re

import pytest
from conftest import CAPTURES, RACINE
from playwright.sync_api import expect
from test_forfaits import HAUT, dialogue, ecrire_tableau, espaces, ouvrir_tableau, refs
from test_fusion_import import ecrire_fichier, forfait, stockage
from test_packs import LUM_POSE, T1_Z5_3Q, T2_3Q, depart, du_stockage, id_de, ligne, libre, pack, poser

EN_TETE = "Référence;Désignation;Prix HT;Prix TTC;Surnoms;Taximètre;Contenu"


def tableau(tmp_path, lignes, en_tete=EN_TETE, nom="t.csv"):
    return ecrire_tableau(tmp_path / nom, lignes, en_tete=en_tete, vides=0)


def importer_tableau(page, chemin, attendu=None):
    d = ouvrir_tableau(page, chemin)
    if attendu:
        expect(d).to_contain_text(attendu)
    d.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")


def refus_tableau(page, chemin):
    """Le tableau est refusé : renvoie la liste des problèmes de la fenêtre."""
    page.set_input_files("#fichier-import", [])
    page.set_input_files("#fichier-import", str(chemin))
    d = dialogue(page)
    expect(d).to_contain_text("Import impossible")
    problemes = [espaces(x) for x in d.locator("li").all_text_contents()]
    d.get_by_role("button", name="Compris").click()
    return problemes


def exporter_csv(page, chemin):
    page.click("#btn-menu")
    page.click("#btn-menu-exporter")
    with page.expect_download() as telechargement:
        page.click("#btn-export-csv")
    telechargement.value.save_as(chemin)
    return chemin


def colonne(chemin, ref, titre):
    """Case d'une ligne de l'export CSV (aucune case de ces tests ne contient « ; » ni guillemet)."""
    lignes = chemin.read_bytes().decode("utf-8-sig").split("\r\n")
    titres = lignes[0].split(";")
    rangee = next(x for x in lignes[1:] if x.split(";")[0] == ref).split(";")
    return rangee[titres.index(titre)]


def sans_cache(donnees):
    """Les forfaits du stockage, sans le prix des packs : un cache qui n'y est écrit qu'au premier enregistrement."""
    return [{k: v for k, v in f.items() if not (f.get("contenu") and k in ("ht", "ttc"))} for f in donnees["forfaits"]]


# ---------------------------------------------------------------- créer et lire


def test_tableau_cree_un_pack_avec_un_forfait_plus_bas_et_une_ligne_libre(page, tmp_path):
    chemin = tableau(
        tmp_path,
        [
            # Le pack cite NV-1, créé plus bas dans le même tableau ; retour à la ligne = séparateur ; « x3 » comme « ×3 ».
            'PK-A;Pack A;;;le pack a;;"EX-T2-3Q ×2 + NV-1\nEX-LUM-POSE x3 + [Câble + fiche : 10,00 HT / 12,00 TTC] ×2"',
            "NV-1;Nouveau;10,00;12,00;;T2;",
            "NV-2;Pas un pack;20,00;24,00;;;/",  # « / » dans Contenu : pas de données, donc un forfait ordinaire
        ],
    )
    d = ouvrir_tableau(page, chemin)
    expect(d).to_contain_text("3 forfaits, dont 1 pack.")
    expect(d).to_contain_text("3 nouveaux, 0 modifié, 0 inchangé")
    assert 2 * T2_3Q[1] + 1200 + 3 * LUM_POSE[1] + 2 * 1200 == 333600
    assert "Packs créés ou modifiés (vérifie leur contenu) : PK-A : 4 lignes, 3 336,00 € TTC" in espaces(d.inner_text())
    expect(d).not_to_contain_text("Ignoré sur les packs")
    d.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")

    d = stockage(page)
    p = du_stockage(page, "PK-A")
    ids = {f["ref"]: f["id"] for f in d["forfaits"]}
    noms = {f["ref"]: f["designation"] for f in d["forfaits"]}
    assert [(x["id"], x["nom"], x["qte"]) for x in p["contenu"]] == [
        (ids["EX-T2-3Q"], noms["EX-T2-3Q"], 2),
        (ids["NV-1"], "Nouveau", 1),
        (ids["EX-LUM-POSE"], noms["EX-LUM-POSE"], 3),
        (None, "Câble + fiche", 2),
    ]
    assert p["contenu"][3] == {"id": None, "nom": "Câble + fiche", "qte": 2, "ht": 1000, "ttc": 1200}
    assert p["elements"] == {}
    assert p["designation"] == "Pack A" and p["surnoms"] == ["le pack a"]
    ht = 2 * T2_3Q[0] + 1000 + 3 * LUM_POSE[0] + 2 * 1000
    ttc = 2 * T2_3Q[1] + 1200 + 3 * LUM_POSE[1] + 2 * 1200
    assert (p["ht"], p["ttc"]) == (ht, ttc)
    assert "contenu" not in du_stockage(page, "NV-2")
    assert {"PK-A", "NV-1", "NV-2"} <= refs(page)


def test_noms_des_lignes_du_pack_cree_par_le_tableau(page, tmp_path):
    """Une ligne de forfait porte la désignation du forfait (sa référence s'il n'en a pas), comme dans le total."""
    importer_tableau(page, tableau(tmp_path, ["NV-1;;10,00;12,00;;;", "PK-A;;;;;;EX-T2-3Q + NV-1"]))
    t2 = du_stockage(page, "EX-T2-3Q")["designation"]
    assert [x["nom"] for x in du_stockage(page, "PK-A")["contenu"]] == [t2, "NV-1"]


def test_prix_et_elements_tapes_sur_un_pack_ignores_et_annonces(page, tmp_path):
    chemin = tableau(tmp_path, ["PK-A;;100,00;120,00;;T2;EX-T2-3Q"])
    d = ouvrir_tableau(page, chemin)
    texte = espaces(d.inner_text())
    assert "Ignoré sur les packs (un pack prend le prix et les éléments de ses forfaits)" in texte
    assert "PK-A : Taximètre « T2 »" in texte
    assert "PK-A : 100,00 HT et 120,00 TTC tapés (calculé : 700,00 € HT, 840,00 € TTC)" in texte
    d.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    p = du_stockage(page, "PK-A")
    assert (p["ht"], p["ttc"]) == T2_3Q and p["elements"] == {}


def test_pack_dans_un_pack_et_boucle_annoncee(page, tmp_path):
    importer_tableau(
        page,
        tableau(tmp_path, ["PK-B;;;;;;PK-A ×2 + EX-T2-3Q", "PK-A;;;;;;EX-LUM-POSE"]),
        "2 nouveaux",
    )
    assert (du_stockage(page, "PK-B")["ht"], du_stockage(page, "PK-B")["ttc"]) == (
        2 * LUM_POSE[0] + T2_3Q[0],
        2 * LUM_POSE[1] + T2_3Q[1],
    )
    # Le prix de secours de la ligne PK-A est celui du pack calculé, pas 0.
    ligne_a = du_stockage(page, "PK-B")["contenu"][0]
    assert (ligne_a["ht"], ligne_a["ttc"]) == LUM_POSE

    # A contient B qui contient A : accepté (recalculerPacks borne le calcul), annoncé avant l'import.
    d = ouvrir_tableau(page, tableau(tmp_path, ["PK-A;;;;;;PK-B"], nom="boucle.csv"))
    expect(d).to_contain_text("Packs au prix à revoir (ils se contiennent l'un l'autre, ou sur plus de 3 niveaux) : PK-A")
    d.get_by_role("button", name="Annuler").click()


# ---------------------------------------------------------------- erreurs, ligne par ligne


def test_erreurs_de_la_case_contenu_dites_ligne_par_ligne(page, tmp_path):
    d = depart(page, tmp_path)
    d["forfaits"].append(forfait("fft-plus", "ZB+1"))
    poser(page, d)
    cinquante_et_une = " + ".join(["EX-T2-3Q"] * 51)
    problemes = refus_tableau(
        page,
        tableau(
            tmp_path,
            [
                "PK-1;;;;;;EX-T2-3Q + INCONNUE ×2",
                "PK-2;;;;;;EX-T2-3Q + ZB+1",
                "PK-3;;;;;;EX-T2-3Q ×deux",
                "PK-4;;;;;;EX-T2-3Q ×0",
                "PK-5;;;;;;EX-T2-3Q x100",
                f"PK-6;;;;;;{cinquante_et_une}",
                "PK-7;;;;;;EX-T2-3Q + PK-7",
                "PK-8;;;;;;[Pose : 45 euros]",
            ],
        ),
    )
    assert problemes == [
        "Ligne 2 (PK-1) : Contenu, référence inconnue « INCONNUE ».",
        "Ligne 3 (PK-2) : Contenu, la référence « ZB+1 » contient un « + » : renomme-la, ou assemble ce pack dans l'appli.",
        "Ligne 4 (PK-3) : Contenu, quantité illisible « EX-T2-3Q ×deux » (exemple : REF ×2).",
        "Ligne 5 (PK-4) : Contenu, quantité 0 pour « EX-T2-3Q ×0 » : de 1 à 99.",
        "Ligne 6 (PK-5) : Contenu, quantité 100 pour « EX-T2-3Q x100 » : de 1 à 99.",
        "Ligne 7 (PK-6) : Contenu, 51 lignes, 50 au maximum.",
        "Ligne 8 (PK-7) : Contenu, un pack ne peut pas se contenir lui-même (« PK-7 »).",
        "Ligne 9 (PK-8) : Contenu, ligne libre illisible « [Pose : 45 euros] » : écris-la [Nom : 45,00 HT / 54,00 TTC].",
    ]
    assert not {"PK-1", "PK-7"} & refs(page)  # rien n'a changé


def test_reference_qui_contient_un_x_se_lit_avec_sa_quantite(page, tmp_path):
    d = depart(page, tmp_path)
    d["forfaits"].append(forfait("fft-x2", "T1-X2"))
    poser(page, d)
    importer_tableau(page, tableau(tmp_path, ["PK-A;;;;;;T1-X2 + T1-X2 x3"]))
    assert [x["qte"] for x in du_stockage(page, "PK-A")["contenu"]] == [1, 3]


def test_case_contenu_piegee_refusee_sans_figer_l_onglet(page, tmp_path):
    """Des milliers d'espaces dans une ligne libre ou de « x » à la suite figeaient l'onglet : l'import est refusé tout
    de suite (la fenêtre doit s'ouvrir dans le délai de expect)."""
    problemes = refus_tableau(
        page,
        tableau(tmp_path, ["PK-1;;;;;;[a:" + " " * 5000 + "]", "PK-2;;;;;;" + "x" * 100000, "PK-3;;;;;;+ +"]),
    )
    assert len(problemes) == 3
    assert problemes[0].startswith("Ligne 2 (PK-1) : Contenu, ligne trop longue « [a:")
    assert problemes[1].startswith("Ligne 3 (PK-2) : Contenu, ligne trop longue « xxx")
    assert all(p.endswith("» (200 caractères au maximum).") for p in problemes[:2])
    assert problemes[2] == "Ligne 4 (PK-3) : Contenu, aucun forfait (exemple : REF-A + REF-B ×2)."


def test_reference_avec_un_plus_ne_bloque_que_la_lecture_fausse(page, tmp_path):
    d = depart(page, tmp_path)
    d["forfaits"] += [forfait("fft-a", "A1"), forfait("fft-b", "B1"), forfait("fft-ab", "A1+B1"), forfait("fft-p", "EX-T2-3Q+")]
    d["forfaits"].append(pack("pck-ab", "PK-AB", [ligne(d, "A1+B1")]))
    poser(page, d)
    # « EX-T2-3Q + … » ressemble à la référence « EX-T2-3Q+ », et « A1 + B1 » se lit A1 puis B1 dans un pack neuf : la
    # case dit bien ce qu'elle veut dire, rien n'est bloqué.
    importer_tableau(page, tableau(tmp_path, ["PK-1;;;;;;EX-T2-3Q + EX-LUM-POSE ×2", "PK-2;;;;;;A1 + B1"]))
    assert [x["id"] for x in du_stockage(page, "PK-1")["contenu"]] == [id_de(d, "EX-T2-3Q"), id_de(d, "EX-LUM-POSE")]
    assert [x["id"] for x in du_stockage(page, "PK-2")["contenu"]] == ["fft-a", "fft-b"]
    # Le pack qui contient « A1+B1 » le perdrait (relu A1 puis B1) : refusé.
    problemes = refus_tableau(page, tableau(tmp_path, ["PK-AB;;;;;;A1 + B1"], nom="ab.csv"))
    assert problemes == [
        "Ligne 2 (PK-AB) : Contenu, la référence « A1+B1 » contient un « + » : renomme-la, ou assemble ce pack dans l'appli."
    ]


def test_ligne_libre_au_crochet_jamais_ferme_se_relit(page, tmp_path):
    """Un nom « Pose [b » écrit par l'export ne colle pas la ligne suivante à la sienne."""
    d = depart(page, tmp_path)
    d["forfaits"].append(pack("pck-c", "PK-C", [libre("Pose [b", 4500, 5400), ligne(d, "EX-T2-3Q")], maj=1000))
    poser(page, d)
    case = colonne(exporter_csv(page, tmp_path / "export.csv"), "PK-C", "Contenu")
    assert case == "[Pose [b : 45,00 HT / 54,00 TTC] + EX-T2-3Q"
    d2 = ouvrir_tableau(page, tableau(tmp_path, [f"PK-C;;;;;;{case}"]))
    expect(d2).to_contain_text("0 nouveau, 0 modifié, 1 inchangé")
    d2.get_by_role("button", name="Annuler").click()


def test_pack_present_deux_fois_dans_l_outil_annonce(page, tmp_path):
    """Deux packs de même référence (fusion de deux appareils) : un seul est mis à jour, la fenêtre le dit."""
    d = depart(page, tmp_path)
    d["forfaits"] += [pack("pck-1", "PK-D", [ligne(d, "EX-T2-3Q")]), pack("pck-2", "PK-D", [ligne(d, "EX-LUM-POSE")])]
    poser(page, d)
    d2 = ouvrir_tableau(page, tableau(tmp_path, ["PK-D;;;;;;EX-T1-Z5-3Q"]))
    expect(d2).to_contain_text("PK-D (2 forfaits)")
    d2.get_by_role("button", name="Annuler").click()


# ---------------------------------------------------------------- mettre à jour un pack existant


def test_tableau_met_a_jour_un_pack_sans_le_dupliquer(page, tmp_path):
    d = depart(page, tmp_path)
    d["forfaits"].append(pack("pck-nuit", "PK-NUIT", [ligne(d, "EX-T2-3Q"), libre("Pose", 4500, 5400)], "Pack nuit", maj=1000))
    poser(page, d)
    # Ligne libre réécrite telle quelle, même désignation : le pack n'est pas modifié.
    pareil = tableau(tmp_path, ["PK-NUIT;Pack nuit;;;;;EX-T2-3Q + [Pose : 45,00 HT / 54,00 TTC]"], nom="pareil.csv")
    d2 = ouvrir_tableau(page, pareil)
    expect(d2).to_contain_text("0 nouveau, 0 modifié, 1 inchangé")
    d2.get_by_role("button", name="Annuler").click()

    importer_tableau(page, tableau(tmp_path, ["pk-nuit;Pack nuit;;;;;EX-T2-3Q ×2 + EX-T1-Z5-3Q"]), "0 nouveau, 1 modifié")
    p = du_stockage(page, "pk-nuit")
    assert p["id"] == "pck-nuit" and p["maj"] > 1000  # même pack, date neuve
    assert [(x["id"] is None, x["qte"]) for x in p["contenu"]] == [(False, 2), (False, 1)]  # la ligne libre est retirée
    assert (p["ht"], p["ttc"]) == (2 * T2_3Q[0] + T1_Z5_3Q[0], 2 * T2_3Q[1] + T1_Z5_3Q[1])
    assert sum(1 for f in stockage(page)["forfaits"] if f["id"] == "pck-nuit") == 1


def test_ligne_d_un_pack_sans_contenu_refusee_et_forfait_ordinaire_jamais_change_en_pack(page, tmp_path):
    d = depart(page, tmp_path)
    d["forfaits"].append(pack("pck-nuit", "PK-NUIT", [ligne(d, "EX-T2-3Q")], "Pack nuit", maj=1000))
    poser(page, d)
    avant = stockage(page)
    problemes = refus_tableau(
        page,
        tableau(
            tmp_path,
            [
                "PK-NUIT;Pack nuit;800,00;960,00;;T2;",  # case vide : jamais un forfait ordinaire en silence
                "EX-T1-Z5-3Q;;;;;;EX-T2-3Q",  # forfait ordinaire : jamais un pack (il perdrait ses éléments)
                "pk-nuit2;;;;;;/",
            ],
        ),
    )
    assert problemes[:2] == [
        "Ligne 2 (PK-NUIT) : c'est un pack et sa case Contenu est vide : écris ses forfaits (exemple : REF-A + REF-B ×2), ou retire la ligne du tableau.",
        "Ligne 3 (EX-T1-Z5-3Q) : cette référence est un forfait ordinaire, pas un pack : vide sa case Contenu, ou donne une autre référence au pack.",
    ]
    assert sans_cache(stockage(page)) == sans_cache(avant)


def test_ligne_d_un_pack_dans_un_tableau_sans_colonne_contenu_le_garde(page, tmp_path):
    """Ancien modèle, sans la colonne : une colonne absente ne touche à rien, le pack reste un pack."""
    d = depart(page, tmp_path)
    d["forfaits"].append(pack("pck-nuit", "PK-NUIT", [ligne(d, "EX-T2-3Q")], "Pack nuit", maj=1000))
    poser(page, d)
    avant = du_stockage(page, "PK-NUIT")
    chemin = ecrire_tableau(
        tmp_path / "ancien.csv",
        ["PK-NUIT;Pack de nuit;100,00;120,00;T2;;;;", "NV-1;Nouveau;10,00;12,00;T2;;;;"],
    )
    d2 = ouvrir_tableau(page, chemin)
    texte = espaces(d2.inner_text())
    assert "1 nouveau, 1 modifié, 0 inchangé" in texte
    assert "PK-NUIT : Taximètre « T2 »" in texte
    assert "PK-NUIT : 100,00 HT et 120,00 TTC tapés (calculé : 700,00 € HT, 840,00 € TTC)" in texte
    d2.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    apres = du_stockage(page, "PK-NUIT")
    assert apres["designation"] == "Pack de nuit"
    assert apres["id"] == avant["id"] and apres["contenu"] == avant["contenu"] and apres["elements"] == {}
    assert (apres["ht"], apres["ttc"]) == T2_3Q


# ---------------------------------------------------------------- export, aller-retour


def packs_complets(d):
    """Pack avec un pack imbriqué, une ligne libre et un forfait supprimé (« à revoir »)."""
    d["forfaits"].append(forfait("fft-vieux", "VIEUX-1", 5000, 6000, maj=1000))
    d["forfaits"].append(
        pack(
            "pck-nuit",
            "PK-NUIT",
            [ligne(d, "EX-T1-Z5-3Q", 2), libre("Câble + fiche [noir]", 1000, 1200, 3), ligne(d, "VIEUX-1")],
            "Pack nuit Zorba",
            maj=1000,
            surnoms=["la nuit"],
        )
    )
    d["forfaits"].append(pack("pck-grand", "PK-GRAND", [ligne(d, "PK-NUIT"), ligne(d, "EX-LUM-POSE", 4)], maj=1000))
    for f in d["forfaits"]:
        if f["id"] == "fft-vieux":
            f.update(supprime=True, maj=2000)
    return d


def test_export_csv_ecrit_le_contenu_et_se_reimporte_sans_changement(page, tmp_path):
    poser(page, packs_complets(depart(page, tmp_path)))
    avant = stockage(page)
    chemin = exporter_csv(page, tmp_path / "export.csv")
    assert colonne(chemin, "PK-NUIT", "Contenu") == "EX-T1-Z5-3Q ×2 + [Câble + fiche [noir] : 10,00 HT / 12,00 TTC] ×3 + VIEUX-1"
    assert colonne(chemin, "PK-GRAND", "Contenu") == "PK-NUIT + EX-LUM-POSE ×4"
    assert colonne(chemin, "EX-T2-3Q", "Contenu") == ""
    # Le prix calculé, à lire (ignoré à la réimportation) : 2 × T1, 3 câbles, et le prix de secours du forfait supprimé.
    assert (
        colonne(chemin, "PK-NUIT", "Prix TTC")
        == "3058,80"
        == f"{(2 * T1_Z5_3Q[1] + 3 * 1200 + 6000) / 100:.2f}".replace(".", ",")
    )
    assert colonne(chemin, "PK-NUIT", "Taximètre") == ""

    d = ouvrir_tableau(page, chemin)
    texte = espaces(d.inner_text())
    assert "0 nouveau, 0 modifié, 13 inchangés" in texte
    assert "Ignoré sur les packs" not in texte
    d.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    assert sans_cache(stockage(page)) == sans_cache(avant)


def lisible(p, donnees):
    """Un pack sans ses identifiants (un autre appareil en donne d'autres) : référence des forfaits, lignes libres en entier."""
    refs_par_id = {f["id"]: f["ref"] for f in donnees["forfaits"]}
    lignes = [(refs_par_id[x["id"]], x["qte"]) if x["id"] else (x["nom"], x["qte"], x["ht"], x["ttc"]) for x in p["contenu"]]
    return lignes, p["designation"], p.get("surnoms")


def test_export_csv_sur_un_appareil_neuf_recree_les_packs_avec_leurs_lignes_libres(page, tmp_path):
    """L'aller-retour ne perd aucune ligne libre, même là où le pack n'existe pas encore."""
    d = packs_complets(depart(page, tmp_path))
    d["forfaits"][-2]["contenu"].pop()  # sans le forfait supprimé : il n'existe que sur le premier appareil
    poser(page, d)
    attendu = {ref: lisible(du_stockage(page, ref), stockage(page)) for ref in ("PK-NUIT", "PK-GRAND")}
    chemin = exporter_csv(page, tmp_path / "export.csv")
    poser(page, {**d, "forfaits": [f for f in d["forfaits"] if not f["ref"].startswith("PK-")]})  # l'autre appareil
    importer_tableau(page, chemin, "2 nouveaux, 0 modifié")
    for ref, avant in attendu.items():
        assert lisible(du_stockage(page, ref), stockage(page)) == avant
    nuit = (2 * T1_Z5_3Q[0] + 3 * 1000, 2 * T1_Z5_3Q[1] + 3 * 1200)
    assert (du_stockage(page, "PK-NUIT")["ht"], du_stockage(page, "PK-NUIT")["ttc"]) == nuit
    grand = du_stockage(page, "PK-GRAND")
    assert (grand["ht"], grand["ttc"]) == (nuit[0] + 4 * LUM_POSE[0], nuit[1] + 4 * LUM_POSE[1])
    libre_lue = du_stockage(page, "PK-NUIT")["contenu"][1]
    assert libre_lue == {"id": None, "nom": "Câble + fiche [noir]", "qte": 3, "ht": 1000, "ttc": 1200}


# ---------------------------------------------------------------- plafonds, modèle Excel


def test_pack_cree_par_le_tableau_respecte_le_plafond_de_forfaits(page, tmp_path):
    # 11 forfaits de départ + 4 989 = 5 000 : le pack du tableau serait le 5 001e.
    pleins = [forfait(f"fft-n{i:05d}", f"N-{i}") for i in range(4989)]
    page.set_input_files("#fichier-import", str(ecrire_fichier(tmp_path / "plein.json", forfaits=pleins)))
    dialogue(page).get_by_role("button", name="Mettre à jour", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Mise à jour terminée")
    d = ouvrir_tableau(page, tableau(tmp_path, ["PK-A;;;;;;N-1 + N-2"]))
    d.get_by_role("button", name="Importer", exact=True).click()
    d = dialogue(page)
    expect(d).to_contain_text("Import impossible")
    expect(d).to_contain_text(re.compile(r"Trop d'enregistrements.*5\s000 au maximum"))
    d.get_by_role("button", name="Compris").click()
    assert "PK-A" not in {f["ref"] for f in stockage(page)["forfaits"]}


def test_contenu_est_une_colonne_du_tableau_dans_l_outil_et_le_modele(tmp_path):
    """Sans cette déclaration, la colonne « Contenu » deviendrait une famille à l'import."""
    html = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "['contenu', 'contenu']" in html
    assert "'Contenu', 'Exemple', 'Modifié le'" in html  # export CSV
    openpyxl = pytest.importorskip("openpyxl")
    spec = importlib.util.spec_from_file_location("modele_excel", RACINE / "outils" / "modele_excel.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    chemin = tmp_path / "modele.xlsx"
    module.fabriquer().save(chemin)
    feuille = openpyxl.load_workbook(chemin)["Forfaits"]
    titres = [c.value for c in feuille[1]]
    assert titres[-1] == "Contenu"
    # Un pack n'a pas de prix à saisir : ses cases de prix vides ne sont pas rouges.
    regles = [r.formula[0] for plage in feuille.conditional_formatting for r in plage.rules]
    lettre = openpyxl.utils.get_column_letter(len(titres))
    assert sum(f'${lettre}2=""' in r for r in regles) == 2


# ---------------------------------------------------------------- capture


def test_capture_de_la_confirmation_d_un_import_qui_cree_un_pack(appareils, tmp_path):
    dossier = CAPTURES / "packs"
    dossier.mkdir(parents=True, exist_ok=True)
    page = appareils(viewport=HAUT).page
    chemin = tableau(
        tmp_path,
        [
            "PK-NUIT;Pack nuit Zorba;100,00;120,00;la nuit;T2;EX-T1-Z5-3Q ×2 + EX-LUM-POSE + [Pose : 45,00 HT / 54,00 TTC]",
            "NV-1;Nouveau forfait;10,00;12,00;;T2;",
        ],
    )
    d = ouvrir_tableau(page, chemin)
    expect(d).to_contain_text("2 nouveaux")
    expect(d).to_contain_text("Ignoré sur les packs")
    page.wait_for_timeout(300)
    page.screenshot(path=dossier / "import-tableau-pack.png")
    d.get_by_role("button", name="Annuler").click()
