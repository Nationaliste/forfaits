"""Packs (roadmap 713, lot 1) : un forfait qui assemble d'autres forfaits, enregistré depuis le total.

Lancer :  NAVIGATEURS=chromium python -m pytest tests/test_packs.py
"""

import base64
import hashlib
import json
import re
import time

from conftest import CAPTURES, RACINE
from playwright.sync_api import expect
from test_forfaits import (
    AVEC_3Q,
    HAUT,
    STOCKAGE,
    _page_en_lecture_seule,
    activer_modif,
    chercher,
    dialogue,
    ecrire_tableau,
    espaces,
    exporter_json,
    fiche,
    filtrer,
    importer,
    modifier,
    ouvrir_tableau,
    refs,
    supprimer,
)
from test_fusion_import import CLE_DONNEES, ecrire_fichier, forfait, stockage

# Prix des forfaits d'exemple (inventés), en centimes.
T1_Z5_3Q = (123450, 148140)
T2_3Q = (70000, 84000)
LUM_POSE = (45000, 54000)


# ---------------------------------------------------------------- aides


def depart(page, tmp_path):
    """Les données de départ de l'outil (les exemples), telles qu'il les exporte."""
    return exporter_json(page, tmp_path / "depart.json")


def id_de(donnees, ref):
    return next(f["id"] for f in donnees["forfaits"] if f["ref"] == ref)


def ligne(donnees, ref, qte=1):
    f = next(f for f in donnees["forfaits"] if f["ref"] == ref)
    return {"id": f["id"], "nom": f["designation"] or f["ref"], "qte": qte, "ht": f["ht"], "ttc": f["ttc"]}


def libre(nom, ht, ttc, qte=1):
    return {"id": None, "nom": nom, "qte": qte, "ht": ht, "ttc": ttc}


def pack(identifiant, ref, contenu, designation="", maj=1, **autres):
    return {
        "id": identifiant,
        "ref": ref,
        "designation": designation,
        "ht": 0,
        "ttc": 0,
        "elements": {},
        "contenu": contenu,
        "maj": maj,
        **autres,
    }


def poser(page, donnees):
    """Écrit ces données dans le stockage de l'appareil (format 3) et recharge la page."""
    page.evaluate(
        "([cle, d]) => localStorage.setItem(cle, JSON.stringify({ format: 'forfaits-comptoir', version: 3, ...d }))",
        [CLE_DONNEES, {k: donnees[k] for k in ("familles", "elements", "forfaits")}],
    )
    page.reload()
    page.wait_for_selector("#resultats .carte")


def rangee(page, ref):
    return page.locator("#resultats .carte", has=page.locator(".carte-ref", has_text=re.compile(f"^{re.escape(ref)}$")))


def prix_rangee(page, ref):
    r = rangee(page, ref)
    return espaces(r.locator(".prix-ttc .prix-montant").text_content()), espaces(
        r.locator(".prix-ht .prix-montant").text_content()
    )


def du_stockage(page, ref):
    return next(f for f in stockage(page)["forfaits"] if f["ref"] == ref and not f.get("supprime"))


def ajouter(page, ref, fois=1):
    for _ in range(fois):
        page.get_by_role("button", name=f"Ajouter {ref} au total", exact=True).click()


def enregistrer_pack(page, nom, ref=None):
    """« Enregistrer comme pack » dans le total visible (sous la fiche, ou feuille du bas), puis la fenêtre du nom."""
    if page.locator("#total").is_visible():
        total = page.locator("#total")
    else:
        page.locator("#barre-total").click()
        total = page.locator("#dlg-total")
    total.locator(".btn-pack").click()
    d = dialogue(page)
    expect(d).to_contain_text("Enregistrer")
    d.locator("#p-nom").fill(nom)
    if ref is not None:
        d.locator("#p-ref").fill(ref)
    d.locator("#p-enregistrer").click()


# ---------------------------------------------------------------- enregistrer depuis le total


def test_enregistrer_un_pack_depuis_le_total(page, tmp_path):
    page.set_viewport_size(HAUT)
    # Hors du mode modification, le total n'en fait pas un pack (donnée d'équipe).
    ajouter(page, "EX-T1-Z5-3Q", 2)
    ajouter(page, "EX-LUM-POSE")
    expect(page.locator("#total .btn-pack")).to_have_count(0)
    expect(page.locator("#total")).not_to_contain_text("null")  # rien d'absent ne s'écrit en toutes lettres
    activer_modif(page)
    page.locator("#total .btn-pack").click()
    d = dialogue(page)
    expect(d.locator("#p-ref")).to_have_value("PACK-01")  # proposée, modifiable
    d.locator("#p-enregistrer").click()
    expect(d.locator(".msg-erreur")).to_have_text("Donne un nom au pack.")
    d.locator("#p-nom").fill("Pack nuit Zorba")
    d.locator("#p-enregistrer").click()
    expect(page.locator("#toast")).to_contain_text("Pack PACK-01 enregistré")

    # Son prix = la somme de ses lignes.
    ht = 2 * T1_Z5_3Q[0] + LUM_POSE[0]
    ttc = 2 * T1_Z5_3Q[1] + LUM_POSE[1]
    assert prix_rangee(page, "PACK-01") == ("3 502,80 €", "2 919,00 €")
    expect(rangee(page, "PACK-01").locator(".badge-pack")).to_have_text("Pack")
    expect(rangee(page, "PACK-01").locator(".carte-designation")).to_contain_text("Pack nuit Zorba")
    p = du_stockage(page, "PACK-01")
    assert (p["ht"], p["ttc"]) == (ht, ttc)
    assert [(lg["qte"], lg["ht"], lg["ttc"]) for lg in p["contenu"]] == [(2, *T1_Z5_3Q), (1, *LUM_POSE)]
    assert p["elements"] == {}

    # La fiche montre le détail, ligne par ligne, et le total au terminus.
    f = page.locator("#fiche")  # le pack enregistré est choisi
    expect(f.locator(".fiche-nom")).to_have_text("Pack nuit Zorba")
    lignes = f.locator(".ligne-pack")
    expect(lignes).to_have_count(2)
    assert espaces(lignes.nth(0).text_content()).startswith("2 × · EX-T1-Z5-3Q")
    expect(lignes.nth(0).locator(".ligne-pack-prix")).to_have_text(re.compile(r"2\s962,80\s€\s?TTC"))
    expect(f.locator(".ttc-grand")).to_contain_text(re.compile(r"3\s502,80"))

    # Le .json part en version 3, avec le contenu.
    fichier = exporter_json(page, tmp_path / "export.json")
    assert fichier["version"] == 3
    assert next(x for x in fichier["forfaits"] if x["ref"] == "PACK-01")["contenu"] == p["contenu"]

    # Deuxième pack : la référence suivante est proposée ; même contenu = avertissement, comme une même combinaison.
    page.locator("#total .btn-pack").click()
    expect(dialogue(page).locator("#p-ref")).to_have_value("PACK-02")
    dialogue(page).locator("#p-nom").fill("Copie")
    dialogue(page).locator("#p-enregistrer").click()
    expect(dialogue(page)).to_contain_text("Même contenu que : PACK-01")
    dialogue(page).get_by_role("button", name="Revenir").click()
    dialogue(page).get_by_role("button", name="Annuler").click()
    assert "PACK-02" not in refs(page)


def test_total_avec_une_remise_ne_devient_pas_un_pack(page):
    page.set_viewport_size(HAUT)
    activer_modif(page)
    ajouter(page, "EX-T2-3Q")
    page.locator("#total").get_by_role("button", name="Ligne libre").click()
    d = dialogue(page)
    d.get_by_label("Nom de la ligne libre").fill("Remise fidélité")
    d.get_by_label("Prix TTC de la ligne libre").fill("-50")
    d.get_by_role("button", name="Ajouter à la liste").click()
    d.get_by_role("button", name="Terminé").click()
    page.locator("#total .btn-pack").click()
    expect(dialogue(page)).to_contain_text("Un pack ne peut pas contenir de remise : retire « Remise fidélité »")
    dialogue(page).get_by_role("button", name="Compris").click()
    assert not any(f.get("contenu") for f in (stockage(page) or {"forfaits": []})["forfaits"])


def test_le_prix_d_un_forfait_remonte_dans_le_pack_sans_toucher_a_sa_date(page, tmp_path):
    d = depart(page, tmp_path)
    d["forfaits"].append(
        pack("pck-nuit", "PK-NUIT", [ligne(d, "EX-T2-3Q"), ligne(d, "EX-LUM-POSE", 2)], "Pack nuit complet", maj=1000)
    )
    poser(page, d)
    assert prix_rangee(page, "PK-NUIT") == ("1 920,00 €", "1 600,00 €")  # 840 + 2 × 540
    activer_modif(page)
    modifier(page, "EX-LUM-POSE")
    dialogue(page).locator("#f-ht").fill("500")
    dialogue(page).locator("#f-ttc").fill("600")
    dialogue(page).locator("#f-enregistrer").click()
    expect(page.locator("#toast")).to_contain_text("Forfait EX-LUM-POSE modifié")
    assert prix_rangee(page, "PK-NUIT") == ("2 040,00 €", "1 700,00 €")
    p = du_stockage(page, "PK-NUIT")
    assert p["maj"] == 1000  # le recalcul n'est pas une modification du pack
    assert [lg["ttc"] for lg in p["contenu"]] == [84000, 54000]  # prix notés : le secours, inchangé


# ---------------------------------------------------------------- recherche et filtres


def test_recherche_et_filtres_trouvent_un_pack(page, tmp_path):
    d = depart(page, tmp_path)
    d["forfaits"].append(
        pack("pck-nuit", "PK-NUIT", [ligne(d, "EX-T2-3Q"), ligne(d, "EX-LUM-POSE")], "Pack nuit complet", surnoms=["veilleuse"])
    )
    poser(page, d)
    chercher(page, "nuit")  # un mot de son nom
    assert refs(page) == {"PK-NUIT"}
    chercher(page, "veilleuse")  # son surnom d'équipe
    assert refs(page) == {"PK-NUIT"}
    chercher(page, "3Q")  # un élément d'un de ses forfaits
    assert refs(page) == AVEC_3Q | {"PK-NUIT"}
    chercher(page, "4Q")
    assert "PK-NUIT" not in refs(page)
    chercher(page, "EX-LUM-POSE")  # la référence d'une de ses lignes
    assert refs(page) == {"EX-LUM-POSE", "PK-NUIT"}
    chercher(page, "")
    # Ses éléments affichés : ceux de ses forfaits, plusieurs familles.
    noms = rangee(page, "PK-NUIT").locator(".el-nom").all_text_contents()
    assert noms == ["T2", "Lumineux EXEMPLE", "3Q", "Pose EXEMPLE"] or set(noms) == {
        "T2",
        "Lumineux EXEMPLE",
        "3Q",
        "Pose EXEMPLE",
    }
    # Filtre de famille : par l'élément d'un de ses forfaits, et « Sans … ».
    filtrer(page, "Lumineux", "Lumineux EXEMPLE")
    assert refs(page) == {"EX-LUM-POSE", "PK-NUIT"}
    filtrer(page, "Lumineux", "Tous")
    filtrer(page, "Lumineux", "Sans lumineux")
    assert "PK-NUIT" not in refs(page)


def test_pack_avec_deux_elements_d_une_meme_famille(page, tmp_path):
    """T1 DEMO et T2 sont deux taximètres : le pack se trouve par l'un comme par l'autre."""
    d = depart(page, tmp_path)
    d["forfaits"].append(pack("pck-deux", "PK-DEUX", [ligne(d, "EX-T1-Z5-3Q"), ligne(d, "EX-T2-3Q")], "Deux taxis"))
    poser(page, d)
    for element in ("T1 DEMO", "T2"):
        filtrer(page, "Taximètre", element)
        assert "PK-DEUX" in refs(page), element
    filtrer(page, "Taximètre", "Tous")
    chercher(page, "T1 DEMO")
    assert "PK-DEUX" in refs(page)


# ---------------------------------------------------------------- fiche, imbrication, boucles


def test_fiche_d_un_pack_avec_pack_imbrique_et_ligne_libre(page, tmp_path):
    page.set_viewport_size(HAUT)
    d = depart(page, tmp_path)
    d["forfaits"] += [
        pack("pck-petit", "PK-PETIT", [ligne(d, "EX-T2-3Q"), ligne(d, "EX-LUM-POSE")], "Petit pack"),
        pack(
            "pck-grand",
            "PK-GRAND",
            [
                {"id": "pck-petit", "nom": "Petit pack", "qte": 2, "ht": 0, "ttc": 0},
                ligne(d, "EX-T1-Z5-3Q"),
                libre("Câble rallonge", 1000, 1200, 3),
            ],
            "Grand pack",
        ),
    ]
    poser(page, d)
    # Pack dans un pack : 2 × (840 + 540) + 1 481,40 + 3 × 12 = 4 277,40 TTC.
    assert prix_rangee(page, "PK-PETIT") == ("1 380,00 €", "1 150,00 €")
    assert prix_rangee(page, "PK-GRAND") == ("4 277,40 €", "3 564,50 €")
    f = fiche(page, "PK-GRAND")
    lignes = f.locator(".ligne-pack")
    expect(lignes).to_have_count(3)  # le pack imbriqué tient en une ligne
    expect(lignes.nth(0)).to_contain_text("2 × · Pack")
    expect(lignes.nth(0).locator(".el")).to_have_text("Petit pack")
    expect(lignes.nth(0).locator(".ligne-pack-prix")).to_contain_text(re.compile(r"2\s760,00"))
    expect(lignes.nth(2)).to_contain_text("3 × · Prix saisi")
    expect(lignes.nth(2).locator(".el")).to_have_text("Câble rallonge")
    expect(f.locator(".prix-revoir-fiche")).to_have_count(0)


def test_boucle_ou_trop_de_niveaux_dans_un_fichier_bricole_ne_fige_pas_la_page(page, tmp_path):
    d = depart(page, tmp_path)
    a = ligne(d, "EX-T2-3Q")
    d["forfaits"] += [
        # A contient B qui contient A.
        pack("pck-a", "PK-A", [a, {"id": "pck-b", "nom": "B", "qte": 1, "ht": 100, "ttc": 120}], "Boucle A"),
        pack("pck-b", "PK-B", [{"id": "pck-a", "nom": "A", "qte": 1, "ht": 200, "ttc": 240}], "Boucle B"),
        # Un pack qui se contient lui-même.
        pack("pck-moi", "PK-MOI", [{"id": "pck-moi", "nom": "Moi", "qte": 2, "ht": 50, "ttc": 60}], "Lui-même"),
        # Quatre niveaux : un de trop.
        pack("pck-n1", "PK-N1", [a], "Niveau 1"),
        pack("pck-n2", "PK-N2", [{"id": "pck-n1", "nom": "N1", "qte": 1, "ht": 0, "ttc": 0}], "Niveau 2"),
        pack("pck-n3", "PK-N3", [{"id": "pck-n2", "nom": "N2", "qte": 1, "ht": 0, "ttc": 0}], "Niveau 3"),
        pack("pck-n4", "PK-N4", [{"id": "pck-n3", "nom": "N3", "qte": 1, "ht": 0, "ttc": 0}], "Niveau 4"),
    ]
    # Des centaines de packs qui se contiennent l'un l'autre, chacun de 50 lignes : borné, la page répond.
    for i in range(300):
        d["forfaits"].append(
            pack(
                f"pck-x{i}",
                f"PK-X{i}",
                [{"id": f"pck-x{(i + j) % 300}", "nom": "X", "qte": 99, "ht": 1, "ttc": 1} for j in range(50)],
            )
        )
    poser(page, d)
    for ref in ("PK-A", "PK-B", "PK-MOI", "PK-N4", "PK-X0"):
        expect(rangee(page, ref).locator(".prix-revoir")).to_have_text("Prix à revoir")
    for ref in ("PK-N1", "PK-N2", "PK-N3"):
        expect(rangee(page, ref).locator(".prix-revoir")).to_have_count(0)
    assert prix_rangee(page, "PK-N3") == ("840,00 €", "700,00 €")
    # Le montant reste lisible (borné à ce qu'un forfait peut valoir), et le fichier exporté se relit.
    fichier = exporter_json(page, tmp_path / "boucles.json")
    assert all(0 <= f["ttc"] <= 999999999 for f in fichier["forfaits"])
    page.reload()
    page.wait_for_selector("#resultats .carte")
    expect(rangee(page, "PK-A").locator(".prix-revoir")).to_have_count(1)


def test_forfait_supprime_laisse_le_pack_a_revoir(page, tmp_path):
    d = depart(page, tmp_path)
    d["forfaits"] += [
        pack("pck-nuit", "PK-NUIT", [ligne(d, "EX-T2-3Q"), ligne(d, "EX-LUM-POSE")], "Pack nuit"),
        pack("pck-jour", "PK-JOUR", [ligne(d, "EX-LUM-POSE", 2)], "Pack jour"),
    ]
    poser(page, d)
    activer_modif(page)
    supprimer(page, "EX-LUM-POSE")
    expect(dialogue(page)).to_contain_text("Il est dans 2 packs (PK-NUIT, PK-JOUR)")
    dialogue(page).get_by_role("button", name="Supprimer").click()
    expect(page.locator("#toast")).to_contain_text("Forfait EX-LUM-POSE supprimé")
    # Le prix de secours (noté sur la ligne) reste, avec la mention.
    assert prix_rangee(page, "PK-NUIT") == ("1 380,00 €", "1 150,00 €")
    expect(rangee(page, "PK-NUIT").locator(".prix-revoir")).to_have_text("Prix à revoir")
    f = fiche(page, "PK-NUIT")
    expect(f.locator(".ligne-pack").nth(1)).to_contain_text("Supprimé : prix à revoir")
    expect(f.locator(".prix-revoir-fiche")).to_be_visible()
    # « Annuler » le fait revenir : le pack n'est plus à revoir.
    page.locator("#toast").get_by_role("button", name="Annuler").click()
    expect(rangee(page, "PK-NUIT").locator(".prix-revoir")).to_have_count(0)


def test_supprimer_les_exemples_retire_les_packs_d_exemples(page, tmp_path):
    d = depart(page, tmp_path)
    d["forfaits"] += [
        pack("pck-ex", "PK-EX", [ligne(d, "EX-T2-3Q"), ligne(d, "EX-LUM-POSE")], "Que des exemples"),
        pack("pck-ex2", "PK-EX2", [{"id": "pck-ex", "nom": "PK-EX", "qte": 1, "ht": 0, "ttc": 0}], "Pack d'un pack d'exemples"),
        pack("pck-mien", "PK-MIEN", [ligne(d, "EX-T2-3Q"), libre("Pose maison", 5000, 6000)], "Avec une ligne à moi"),
    ]
    poser(page, d)
    activer_modif(page)
    page.click("#btn-suppr-exemples")
    expect(dialogue(page)).to_contain_text("Les 13 forfaits marqués EXEMPLE")
    dialogue(page).get_by_role("button", name="Supprimer les exemples").click()
    expect(page.locator("#toast")).to_have_text("Exemples supprimés")
    assert refs(page) == {"PK-MIEN"}
    expect(rangee(page, "PK-MIEN").locator(".prix-revoir")).to_have_text("Prix à revoir")


# ---------------------------------------------------------------- modifier un pack dans le total


def test_modifier_un_pack_le_recharge_dans_le_total(page, tmp_path):
    page.set_viewport_size(HAUT)
    d = depart(page, tmp_path)
    d["forfaits"].append(pack("pck-nuit", "PK-NUIT", [ligne(d, "EX-T2-3Q"), ligne(d, "EX-LUM-POSE")], "Pack nuit", maj=1000))
    poser(page, d)
    activer_modif(page)
    ajouter(page, "EX-T1-Z5-3Q")  # un total en cours : il sera remplacé, après une question
    modifier(page, "PK-NUIT")
    expect(dialogue(page)).to_contain_text("Ton total en cours sera remplacé")
    dialogue(page).get_by_role("button", name="Remplacer le total").click()
    total = page.locator("#total")
    expect(total.locator(".total-pack")).to_have_text("Modification du pack PK-NUIT")
    expect(total).not_to_contain_text("null")
    expect(total.locator(".total-ligne")).to_have_count(2)
    total.get_by_role("button", name=re.compile("^Plus : EXEMPLE — Lumineux")).click()
    expect(total.locator(".btn-pack")).to_have_text("Enregistrer le pack PK-NUIT")
    total.locator(".btn-pack").click()
    d2 = dialogue(page)
    expect(d2.locator("#p-ref")).to_have_value("PK-NUIT")
    expect(d2.locator("#p-nom")).to_have_value("Pack nuit")
    d2.locator("#p-enregistrer").click()
    expect(page.locator("#toast")).to_contain_text("Pack PK-NUIT modifié")
    assert prix_rangee(page, "PK-NUIT") == ("1 920,00 €", "1 600,00 €")
    p = du_stockage(page, "PK-NUIT")
    assert p["id"] == "pck-nuit" and p["maj"] > 1000
    assert [lg["qte"] for lg in p["contenu"]] == [1, 2]
    assert len([f for f in stockage(page)["forfaits"] if f.get("contenu")]) == 1
    # Le total reste ; un nouvel enregistrement ferait un autre pack.
    expect(total.locator(".total-pack")).to_have_count(0)
    expect(total.locator(".btn-pack")).to_have_text("Enregistrer comme pack")


# ---------------------------------------------------------------- fichiers, tableau, fusion


def test_ligne_du_tableau_qui_porte_la_reference_d_un_pack_ne_le_modifie_pas(page, tmp_path):
    d = depart(page, tmp_path)
    d["forfaits"].append(pack("pck-nuit", "PK-NUIT", [ligne(d, "EX-T2-3Q")], "Pack nuit", maj=1000))
    poser(page, d)
    avant = du_stockage(page, "PK-NUIT")
    activer_modif(page)
    chemin = ecrire_tableau(tmp_path / "t.csv", ["PK-NUIT;Pack nuit;100,00;120,00;T2;;;;", "NV-1;Nouveau;10,00;12,00;T2;;;;"])
    ouvrir_tableau(page, chemin)
    d2 = dialogue(page)
    expect(d2).to_contain_text(
        "Packs laissés tels quels (le tableau ne modifie pas encore un pack : fais-le dans l'outil) : PK-NUIT"
    )
    expect(d2).to_contain_text("1 nouveau, 0 modifié")
    d2.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    apres = du_stockage(page, "PK-NUIT")
    sans_cache = lambda f: {k: v for k, v in f.items() if k not in ("ht", "ttc")}  # noqa: E731 (le cache posé à 0 est recalculé)
    assert sans_cache(apres) == sans_cache(avant)
    assert (apres["ht"], apres["ttc"]) == T2_3Q
    assert "NV-1" in refs(page)


def test_meme_pack_qui_ne_differe_que_par_le_cache_n_est_pas_modifie(page, tmp_path):
    """Le cache de prix entre dans canonique : à date égale, il ne doit pas faire un « modifié » ni un « prix qui change »."""
    d = depart(page, tmp_path)
    d["forfaits"].append(pack("pck-nuit", "PK-NUIT", [ligne(d, "EX-T2-3Q"), ligne(d, "EX-LUM-POSE")], "Pack nuit", maj=1000))
    poser(page, d)
    fichier = exporter_json(page, tmp_path / "export.json")
    p = next(f for f in fichier["forfaits"] if f["ref"] == "PK-NUIT")
    p["ht"], p["ttc"] = 999999, 999999  # l'autre appareil a un vieux cache (prix d'un forfait pas encore reçu)
    chemin = tmp_path / "autre.json"
    chemin.write_text(json.dumps(fichier), encoding="utf-8")
    page.set_input_files("#fichier-import", str(chemin))
    d2 = dialogue(page)
    expect(d2).to_contain_text("0 nouveau, 0 modifié, 0 supprimé")
    expect(d2).not_to_contain_text("Prix qui changent")
    d2.get_by_role("button", name="Mettre à jour", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Mise à jour terminée")
    assert prix_rangee(page, "PK-NUIT") == ("1 380,00 €", "1 150,00 €")


def test_fichier_version_2_toujours_lisible_et_pack_abime_refuse(page, tmp_path):
    chemin = ecrire_fichier(tmp_path / "v2.json", forfaits=[forfait("fft-v2", "V2-1", 10000, 12000, maj=5)])
    importer(page, chemin)
    assert "V2-1" in refs(page)
    # Un pack de version 3 au contenu abîmé (ligne négative) : le fichier est refusé, rien ne change.
    abime = json.loads(chemin.read_text(encoding="utf-8"))
    abime["version"] = 3
    abime["forfaits"].append(pack("pck-abime", "PK-ABIME", [libre("Remise", -100, -120)]))
    (tmp_path / "abime.json").write_text(json.dumps(abime), encoding="utf-8")
    page.set_input_files("#fichier-import", str(tmp_path / "abime.json"))
    expect(dialogue(page)).to_contain_text("Fichier abîmé : pack « PK-ABIME » invalide.")
    dialogue(page).get_by_role("button", name="Compris").click()
    assert "PK-ABIME" not in refs(page)


def test_pack_cree_depuis_le_total_respecte_le_plafond_de_forfaits(page, tmp_path):
    """Un pack est un forfait : à FORFAITS_MAX forfaits, « Enregistrer comme pack » refuse comme « Ajouter »."""
    page.set_viewport_size(HAUT)
    plafond = int(re.search(r"const FORFAITS_MAX = (\d+);", (RACINE / "index.html").read_text(encoding="utf-8")).group(1))
    d = depart(page, tmp_path)
    actifs = sum(not f.get("supprime") for f in d["forfaits"])
    d["forfaits"] += [forfait(f"fft-plein-{i}", f"PLEIN-{i}") for i in range(plafond - actifs)]
    poser(page, d)
    activer_modif(page)
    chercher(page, "EX-T2-3Q")
    ajouter(page, "EX-T2-3Q")
    page.locator("#total .btn-pack").click()
    dlg = dialogue(page)
    dlg.locator("#p-nom").fill("Pack de trop")
    dlg.locator("#p-enregistrer").click()
    expect(dlg.locator(".msg-erreur")).to_contain_text("forfaits au maximum")
    dlg.get_by_role("button", name="Annuler").click()
    assert sum(not f.get("supprime") for f in stockage(page)["forfaits"]) == plafond
    assert not any(f.get("contenu") for f in stockage(page)["forfaits"])


def page_de_la_version_d_avant():
    """index.html tel qu'une page restée au format précédent : même code, VERSION_FORMAT - 1, empreinte CSP refaite."""
    html = (RACINE / "index.html").read_text(encoding="utf-8")
    trouve = re.findall(r"const VERSION_FORMAT = (\d+);", html)
    assert len(trouve) == 1
    n = int(trouve[0])
    ancien = html.replace(f"const VERSION_FORMAT = {n};", f"const VERSION_FORMAT = {n - 1};")
    script = re.search(r"<script>(.*?)</script>", ancien, re.S).group(1).replace("\r\n", "\n")
    empreinte = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    return re.sub(r"script-src 'sha256-[^']*'", f"script-src 'sha256-{empreinte}'", ancien, count=1)


def test_page_restee_au_format_2_refuse_proprement_un_pack(page, tmp_path):
    """Un onglet resté ouvert sur l'ancienne page reçoit un fichier ou des données au format 3 : il refuse, n'écrit rien."""
    d = depart(page, tmp_path)
    d["forfaits"].append(pack("pck-nuit", "PK-NUIT", [ligne(d, "EX-T2-3Q")], "Pack nuit", maj=1000))
    poser(page, d)
    fichier = tmp_path / "format3.json"
    assert exporter_json(page, fichier)["version"] == 3
    donnees_3 = page.evaluate(STOCKAGE)

    ancienne = page_de_la_version_d_avant()
    page.route(re.compile(r"/(index\.html)?(\?.*)?$"), lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8", body=ancienne))
    # 1. L'appareil a encore ses données au format 2 : le fichier au format 3 est refusé, en le disant.
    page.evaluate("cle => localStorage.removeItem(cle)", CLE_DONNEES)
    page.reload()
    page.wait_for_selector("#resultats .carte")
    assert "const VERSION_FORMAT = 2;" in page.content()
    avant = page.evaluate(STOCKAGE)
    page.set_input_files("#fichier-import", str(fichier))
    expect(dialogue(page)).to_contain_text("Import impossible")
    expect(dialogue(page)).to_contain_text("recharge la page")
    dialogue(page).get_by_role("button", name="Compris").click()
    assert page.evaluate(STOCKAGE) == avant
    assert "PK-NUIT" not in refs(page)

    # 2. Un autre onglet, déjà à jour, a écrit les données au format 3 : l'ancienne page passe en lecture seule.
    page.evaluate("([cle, v]) => localStorage.setItem(cle, v)", [CLE_DONNEES, donnees_3])
    page.reload()
    _page_en_lecture_seule(page)
    page.set_input_files("#fichier-import", str(fichier))
    expect(page.locator("#toast")).to_contain_text("recharge la page")
    assert page.evaluate(STOCKAGE) == donnees_3


# ---------------------------------------------------------------- captures


def test_captures_des_packs(appareils, tmp_path):
    """Rangée avec la marque, fiche du pack, total avec « Enregistrer comme pack » : grand écran et téléphone, deux thèmes."""
    dossier = CAPTURES / "packs"
    dossier.mkdir(parents=True, exist_ok=True)
    for theme in ("sombre", "clair"):
        for nom, options in (
            ("grand", {"viewport": HAUT}),
            ("telephone", {"viewport": {"width": 375, "height": 812}, "has_touch": True, "is_mobile": True}),
        ):
            a = appareils(**options)
            page = a.page
            d = depart(page, tmp_path)
            d["forfaits"].append(
                pack(
                    "pck-nuit",
                    "PK-NUIT",
                    [ligne(d, "EX-T1-Z5-3Q", 2), ligne(d, "EX-LUM-POSE"), libre("Câble rallonge", 1000, 1200, 3)],
                    "Pack nuit Zorba",
                    maj=int(time.time() * 1000),
                )
            )
            poser(page, d)
            page.evaluate(
                "t => { const c = 'forfaits.' + 'appareil.v1'; const a = JSON.parse(localStorage.getItem(c) || '{}'); a.theme = t; localStorage.setItem(c, JSON.stringify(a)); }",
                theme,
            )
            page.reload()
            page.wait_for_selector("#resultats .carte")
            activer_modif(page)
            chercher(page, "nuit")
            if nom == "grand":
                ajouter(page, "PK-NUIT")
                fiche(page, "PK-NUIT")
                page.mouse.move(0, 0)
                page.screenshot(path=dossier / f"pack-{nom}-{theme}.png")
            else:
                page.screenshot(path=dossier / f"pack-{nom}-rangee-{theme}.png")
                f = fiche(page, "PK-NUIT")
                expect(f).to_have_attribute("id", "dlg-fiche")
                page.wait_for_timeout(400)
                page.screenshot(path=dossier / f"pack-{nom}-fiche-{theme}.png")
                f.get_by_role("button", name="Ajouter au total").click()
                f.get_by_role("button", name="Fermer").click()
                page.locator("#barre-total").click()
                expect(page.locator("#dlg-total .btn-pack")).to_be_visible()
                page.wait_for_timeout(400)
                page.screenshot(path=dossier / f"pack-{nom}-total-{theme}.png")
