"""Tests de l'outil Forfaits : les cas demandés, puis les pièges repérés en route.

Lancer :  python -m pytest            (Chromium, Edge et Firefox)
          NAVIGATEURS=chromium python -m pytest   (plus rapide)
"""

import base64
import hashlib
import json
import re
from datetime import datetime

import pytest
from conftest import CAPTURES, RACINE, demarrer_serveur
from PIL import Image
from playwright.sync_api import expect

# Références des forfaits d'exemple, par critère
TOUS = {
    "EX-T1-Z5-3Q",
    "EX-T1-Z5-4Q",
    "EX-T1-KPX-3Q",
    "EX-T1-ZTX-4Q",
    "EX-T2-Z5-3Q",
    "EX-T2-KPX-4Q",
    "EX-T2-ZTX-3Q",
    "EX-T2-KPU-4Q",
    "EX-T2-3Q",
    "EX-LUM-POSE",
    "EX-T1-Z5-3Q-P",
}
AVEC_3Q = {"EX-T1-Z5-3Q", "EX-T1-KPX-3Q", "EX-T2-Z5-3Q", "EX-T2-ZTX-3Q", "EX-T2-3Q", "EX-T1-Z5-3Q-P"}
AVEC_T1 = {"EX-T1-Z5-3Q", "EX-T1-Z5-4Q", "EX-T1-KPX-3Q", "EX-T1-ZTX-4Q", "EX-T1-Z5-3Q-P"}
AVEC_T2_ET_3Q = {"EX-T2-Z5-3Q", "EX-T2-ZTX-3Q", "EX-T2-3Q"}
AVEC_ZORBA5 = {"EX-T1-Z5-3Q", "EX-T1-Z5-4Q", "EX-T2-Z5-3Q", "EX-T1-Z5-3Q-P"}
AVEC_4Q = {"EX-T1-Z5-4Q", "EX-T1-ZTX-4Q", "EX-T2-KPX-4Q", "EX-T2-KPU-4Q"}


# ---------------------------------------------------------------- aides


def espaces(texte):
    """Les prix français utilisent des espaces insécables : on les remplace par des espaces simples."""
    return texte.replace(" ", " ").replace(" ", " ")


def chercher(page, texte):
    page.fill("#recherche", texte)


def refs(page):
    return set(page.locator("#resultats .carte-ref").all_text_contents())


def cartes(page):
    """Ce qu'affiche chaque carte : référence, prix, désignation, éléments."""
    return page.eval_on_selector_all(
        "#resultats .carte",
        """cs => cs.map(c => ({
        ref: c.querySelector('.carte-ref').textContent,
        ht: c.querySelector('.prix-ht .prix-montant').textContent,
        ttc: c.querySelector('.prix-ttc .prix-montant').textContent,
        designation: c.querySelector('.carte-designation')?.textContent ?? '',
        elements: Object.fromEntries([...c.querySelectorAll('.carte-elements li')]
            .map(li => [li.querySelector('.el-famille').textContent, li.querySelector('.el-nom').textContent])),
    })).sort((a, b) => a.ref.localeCompare(b.ref))""",
    )


def dialogue(page):
    return page.locator("dialog[open]").last


def activer_modif(page):
    page.click("#btn-menu")
    page.click("#btn-mode-modif")
    dialogue(page).get_by_role("button", name="Activer").click()
    expect(page.locator("#barre-modif")).to_be_visible()


def ouvrir_ajout(page):
    page.click("#btn-ajouter")
    expect(dialogue(page)).to_contain_text("Ajouter un forfait")


def remplir(page, ref=None, ht=None, ttc=None, elements=None, designation=None):
    d = dialogue(page)
    for selecteur, valeur in (("#f-ref", ref), ("#f-des", designation), ("#f-ht", ht), ("#f-ttc", ttc)):
        if valeur is not None:
            d.locator(selecteur).fill(valeur)
    for famille, nom in (elements or {}).items():
        d.get_by_label(famille, exact=True).select_option(label=nom)
    d.locator("#f-enregistrer").click()


def modifier(page, ref):
    page.locator(".carte", has=page.locator(".carte-ref", has_text=re.compile(f"^{re.escape(ref)}$"))).get_by_role(
        "button", name="Modifier"
    ).click()


def exporter_json(page, chemin):
    page.click("#btn-menu")
    page.click("#btn-menu-exporter")
    with page.expect_download() as telechargement:
        page.click("#btn-export-json")
    telechargement.value.save_as(chemin)
    return json.loads(chemin.read_text(encoding="utf-8"))


def importer(page, chemin, choix="Mettre à jour"):
    page.set_input_files("#fichier-import", str(chemin))
    d = dialogue(page)
    expect(d).to_contain_text("Importer ce fichier")
    d.get_by_role("button", name=choix, exact=True).click()
    expect(page.locator("#toast")).to_have_text("Mise à jour terminée" if choix == "Mettre à jour" else "Données remplacées")
    expect(page.locator("dialog[open]")).to_have_count(0)


def contenu(fichier):
    """Données d'un export, sans la date d'export, triées pour comparer."""
    return {cle: sorted(fichier[cle], key=lambda x: x["id"]) for cle in ("familles", "elements", "forfaits")}


# ---------------------------------------------------------------- recherche (cas demandés)


def test_recherche_3Q_ne_donne_que_des_forfaits_3Q(page):
    chercher(page, "3Q")
    assert refs(page) == AVEC_3Q
    assert all(c["elements"].get("Imprimante") == "3Q" for c in cartes(page))


def test_t1demo_donne_les_memes_resultats_que_T1_DEMO(page):
    resultats = {}
    for saisie in ("T1 DEMO", "t1demo", "T1-DEMO", "t1 demo", "  T1   DEMO "):
        chercher(page, saisie)
        resultats[saisie] = refs(page)
    assert all(r == AVEC_T1 for r in resultats.values()), resultats


def test_3Q_T2_ne_donne_que_les_forfaits_qui_ont_les_deux(page):
    chercher(page, "3Q T2")
    assert refs(page) == AVEC_T2_ET_3Q
    for c in cartes(page):
        assert c["elements"]["Imprimante"] == "3Q" and c["elements"]["Taximètre"] == "T2"
    chercher(page, "t2 3q")  # l'ordre et la casse ne comptent pas
    assert refs(page) == AVEC_T2_ET_3Q


def test_reference_complete_ou_morceau(page):
    chercher(page, "EX-T2-KPU-4Q")
    assert refs(page) == {"EX-T2-KPU-4Q"}
    chercher(page, "kpu")
    assert refs(page) == {"EX-T2-KPU-4Q"}
    chercher(page, "t2 kpu")
    assert refs(page) == {"EX-T2-KPU-4Q"}
    chercher(page, "EX-T1-Z5-3Q")  # la référence exacte passe avant EX-T1-Z5-3Q-P
    assert page.locator("#resultats .carte-ref").first.text_content() == "EX-T1-Z5-3Q"


def test_accents_majuscules_espaces_et_tirets_ignores(page):
    for saisie in ("Kalpo universelle", "KALPO-UNIVERSELLE", "kalpouniverselle", "kâlpo Universellé"):
        chercher(page, saisie)
        assert refs(page) == {"EX-T2-KPU-4Q"}, saisie
    chercher(page, "boîtier zorba")
    avec_accent = refs(page)
    chercher(page, "BOITIER-ZORBA")
    assert refs(page) == avec_accent == AVEC_ZORBA5 | {"EX-T1-ZTX-4Q", "EX-T2-ZTX-3Q"}


def test_rien_trouve_puis_effacer(page):
    chercher(page, "zzzz")
    expect(page.locator("#compte")).to_have_text("Aucun forfait ne correspond")
    page.locator("#resultats").get_by_role("button", name="Effacer la recherche").click()
    assert refs(page) == TOUS
    expect(page.locator("#compte")).to_have_text("11 forfaits")


# ---------------------------------------------------------------- suggestions, étiquettes, boutons


def test_suggestions_zor_puis_etiquette(page):
    chercher(page, "zor")
    suggestions = page.locator("#suggestions .suggestion")
    expect(suggestions).to_have_count(2)
    noms = page.locator("#suggestions .suggestion-nom").all_text_contents()
    familles = page.locator("#suggestions .suggestion-famille").all_text_contents()
    assert noms == ["Zorba 5", "Zorbatech X"]
    assert familles == ["Boîtier", "Boîtier"]

    page.locator("#suggestions .suggestion", has_text="Zorba 5").click()
    expect(page.locator("#etiquettes")).to_contain_text("Boîtier : Zorba 5")
    expect(page.locator("#recherche")).to_have_value("")
    assert refs(page) == AVEC_ZORBA5

    chercher(page, "3q")  # le mot tapé s'ajoute à l'étiquette
    assert refs(page) == AVEC_ZORBA5 & AVEC_3Q

    page.locator("#etiquettes .etiquette").click()  # un clic retire l'étiquette
    expect(page.locator("#etiquettes")).to_be_hidden()
    assert refs(page) == AVEC_3Q


def test_suggestion_au_clavier(page):
    page.click("#recherche")
    page.keyboard.type("kalpo u")
    expect(page.locator("#suggestions .suggestion-nom")).to_have_text(["Kalpo universelle"])
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator("#etiquettes")).to_contain_text("Boîtier : Kalpo universelle")
    assert refs(page) == {"EX-T2-KPU-4Q"}


def test_boutons_de_filtre(page):
    page.locator("#filtres .filtre", has_text="Imprimante").click()
    dialogue(page).get_by_role("button", name="4Q", exact=True).click()
    assert refs(page) == AVEC_4Q
    expect(page.locator("#filtres .filtre", has_text="Imprimante")).to_have_attribute("aria-pressed", "true")

    page.locator("#filtres .filtre", has_text="Imprimante").click()
    dialogue(page).get_by_role("button", name="Tous", exact=True).click()
    page.locator("#filtres .filtre", has_text="Boîtier").click()
    dialogue(page).get_by_role("button", name="Sans boîtier").click()
    assert refs(page) == {"EX-T2-3Q", "EX-LUM-POSE"}
    expect(page.locator("#etiquettes")).to_contain_text("Boîtier : sans")


# ---------------------------------------------------------------- affichage et prix


def test_carte_complete_et_prix_au_format_francais(page):
    chercher(page, "EX-T1-Z5-3Q-P")
    (carte,) = cartes(page)
    assert espaces(carte["ht"]) == "1 150,00 €"
    assert espaces(carte["ttc"]) == "1 380,00 €"
    assert carte["elements"] == {"Taximètre": "T1 DEMO", "Boîtier": "Zorba 5", "Imprimante": "3Q", "Installation": "Pose EXEMPLE"}
    chercher(page, "EX-T1-Z5-3Q")
    assert espaces(cartes(page)[0]["ttc"]) == "1 481,40 €"
    assert " " not in cartes(page)[0]["ttc"]  # espace visible avec toutes les polices
    assert espaces(cartes(page)[0]["ht"]) == "1 234,50 €"
    expect(page.locator(".badge-exemple").first).to_have_text("EXEMPLE")


def test_trier_par_prix(page):
    def ttc_affiches():
        return [
            page.evaluate("s => window.Forfaits.lirePrix(s)", espaces(m))
            for m in page.locator("#resultats .prix-ttc .prix-montant").all_text_contents()
        ]

    def refs_affichees():
        return page.locator("#resultats .carte-ref").all_text_contents()

    assert refs_affichees() == sorted(TOUS)  # par défaut : ordre des références
    page.select_option("#tri", label="prix croissant")
    assert ttc_affiches() == sorted(ttc_affiches()) and len(ttc_affiches()) == len(TOUS)
    assert set(refs_affichees()) == TOUS
    page.select_option("#tri", label="prix décroissant")
    assert ttc_affiches() == sorted(ttc_affiches(), reverse=True)
    chercher(page, "3Q")  # le tri s'applique aussi aux résultats d'une recherche
    assert ttc_affiches() == sorted(ttc_affiches(), reverse=True) and set(refs_affichees()) == AVEC_3Q
    chercher(page, "EX-T2-3Q")  # une référence tapée en entier reste en tête
    assert refs_affichees()[0] == "EX-T2-3Q"
    page.select_option("#tri", label="par référence")
    chercher(page, "")
    assert refs_affichees() == sorted(TOUS)


def test_lecture_des_prix_saisis(page):
    cas = {
        "1 234,50": 123450,
        "1234,5": 123450,
        "1234.50": 123450,
        "1.234,50": 123450,
        "1234,50 €": 123450,
        "0": 0,
        "12": 1200,
        "abc": None,
        "12,345": None,
        "-5": None,
        "": None,
    }
    obtenu = {saisie: page.evaluate("s => window.Forfaits.lirePrix(s)", saisie) for saisie in cas}
    assert obtenu == cas


def test_copier_la_reference(navigateur, appareils):
    a = appareils()
    if navigateur.nom != "firefox":  # Firefox n'a pas cette permission (elle fait échouer le test) : il n'en a pas besoin
        a.contexte.grant_permissions(["clipboard-write"])
    a.page.clock.install(time=datetime(2026, 1, 1))
    a.page.clock.pause_at(
        datetime(2026, 1, 1, 0, 0, 1)
    )  # horloge figée : seules les avances voulues comptent, même si la machine est lente
    # Le presse-papiers contient d'abord autre chose : un reste d'un test précédent ne peut pas faire passer celui-ci.
    a.page.fill("#recherche", "pas-la-reference")
    a.page.keyboard.press("ControlOrMeta+A")
    a.page.keyboard.press("ControlOrMeta+C")
    chercher(a.page, "EX-T2-3Q")
    bouton = a.page.get_by_role("button", name="Copier la référence")
    bouton.click()
    expect(a.page.locator("#toast")).to_contain_text("EX-T2-3Q copiée")
    expect(bouton).to_have_text("Copié")
    # Un second clic relance la confirmation : le premier minuteur ne doit pas la couper.
    a.page.clock.run_for(1000)
    bouton.click()
    a.page.wait_for_timeout(300)  # temps réel : laisse la copie se terminer (l'horloge de la page est figée)
    a.page.clock.run_for(800)
    expect(bouton).to_have_text("Copié")
    a.page.clock.run_for(800)
    expect(bouton).to_have_text("Copier")
    # Ce qui a été copié : on le colle dans la recherche (les tests n'ont pas le droit de lire le presse-papiers sous Firefox).
    a.page.fill("#recherche", "")
    a.page.keyboard.press("ControlOrMeta+V")
    expect(a.page.locator("#recherche")).to_have_value("EX-T2-3Q")


# ---------------------------------------------------------------- saisie des forfaits


def test_ajouter_modifier_supprimer(page):
    expect(page.locator("#btn-ajouter")).to_be_hidden()  # sans le mode modification, pas de saisie
    activer_modif(page)

    ouvrir_ajout(page)
    remplir(
        page,
        "TX-100",
        "1 234,50",
        "1 481,40",
        {"Taximètre": "T2", "Boîtier": "Zorbatech X", "Imprimante": "4Q"},
        designation="Pack T2 complet",
    )
    expect(page.locator("#toast")).to_contain_text("TX-100 ajouté")
    chercher(page, "tx100")
    (carte,) = cartes(page)
    assert carte["ref"] == "TX-100" and carte["designation"] == "Pack T2 complet"
    assert espaces(carte["ttc"]) == "1 481,40 €"
    assert carte["elements"] == {"Taximètre": "T2", "Boîtier": "Zorbatech X", "Imprimante": "4Q"}

    modifier(page, "TX-100")
    remplir(page, ht="1 100,00", ttc="1 320,00", elements={"Boîtier": "Kalpo universelle", "Imprimante": "3Q"})
    (carte,) = cartes(page)
    assert espaces(carte["ht"]) == "1 100,00 €"
    assert carte["elements"] == {"Taximètre": "T2", "Boîtier": "Kalpo universelle", "Imprimante": "3Q"}
    chercher(page, "3Q T2 kalpo universelle")
    assert refs(page) == {"TX-100"}

    chercher(page, "TX-100")
    page.get_by_role("button", name="Supprimer", exact=True).click()
    expect(dialogue(page)).to_contain_text("Supprimer ce forfait ?")
    dialogue(page).get_by_role("button", name="Annuler").click()
    assert refs(page) == {"TX-100"}  # annuler ne supprime rien
    page.get_by_role("button", name="Supprimer", exact=True).click()
    dialogue(page).get_by_role("button", name="Supprimer", exact=True).click()
    expect(page.locator("#resultats .carte")).to_have_count(0)
    chercher(page, "")
    assert refs(page) == TOUS


def test_date_de_modification_sur_la_carte(page):
    expect(page.locator(".carte-maj")).to_have_count(0)  # exemples jamais touchés : pas de date
    activer_modif(page)
    modifier(page, "EX-T2-3Q")
    remplir(page, ht="800", ttc="960")
    chercher(page, "EX-T2-3Q")
    expect(page.locator(".carte-maj")).to_have_text(f"Modifié le {datetime.now():%d/%m/%Y}")


def test_doublon_de_reference_bloque(page):
    activer_modif(page)
    for ref in ("EX-T2-3Q", "ex-t2-3q"):
        ouvrir_ajout(page)
        remplir(page, ref, "100", "120")
        expect(dialogue(page).locator(".msg-erreur")).to_contain_text("existe déjà")
        dialogue(page).get_by_role("button", name="Annuler").click()
    assert len(refs(page)) == 11


def test_doublon_de_combinaison_averti(page):
    activer_modif(page)
    ouvrir_ajout(page)
    remplir(page, "NOUVEAU-1", "1 100", "1 320", {"Taximètre": "T1 DEMO", "Boîtier": "Zorba 5", "Imprimante": "4Q"})
    avertissement = dialogue(page)
    expect(avertissement).to_contain_text("Même combinaison d'éléments que : EX-T1-Z5-4Q")
    avertissement.get_by_role("button", name="Revenir").click()
    dialogue(page).locator("#f-enregistrer").click()
    dialogue(page).get_by_role("button", name="Enregistrer quand même").click()
    expect(page.locator("#compte")).to_have_text("12 forfaits")


def test_ttc_incoherent_averti(page):
    activer_modif(page)
    ouvrir_ajout(page)
    remplir(page, "ERREUR-TTC", "100,00", "150,00")
    expect(dialogue(page)).to_contain_text("ne correspond pas au HT + 20 %")
    dialogue(page).get_by_role("button", name="Revenir").click()
    dialogue(page).get_by_role("button", name="Calculer depuis le HT (+ 20 %)").click()
    expect(dialogue(page).locator("#f-ttc")).to_have_value("120,00")
    dialogue(page).locator("#f-enregistrer").click()
    expect(page.locator("#toast")).to_contain_text("ERREUR-TTC ajouté")


def test_texte_dangereux_affiche_tel_quel(page):
    activer_modif(page)
    ouvrir_ajout(page)
    piege = '<img src=x onerror="window.pirate=1">'
    remplir(page, piege, "100", "120", designation="<b>gras</b>")
    chercher(page, "img")
    (carte,) = cartes(page)
    assert carte["ref"] == piege and carte["designation"] == "<b>gras</b>"
    assert page.evaluate("window.pirate") is None
    assert page.locator("#resultats img").count() == 0


def test_donnees_gardees_apres_rechargement(page):
    activer_modif(page)
    ouvrir_ajout(page)
    remplir(page, "GARDE-1", "100", "120")
    page.reload()
    page.wait_for_selector("#resultats .carte")
    chercher(page, "garde1")
    assert refs(page) == {"GARDE-1"}
    expect(page.locator("#barre-modif")).to_be_visible()


def test_supprimer_les_exemples(page):
    activer_modif(page)
    page.click("#btn-suppr-exemples")
    dialogue(page).get_by_role("button", name="Supprimer les exemples").click()
    expect(page.locator("#resultats")).to_contain_text("Aucun forfait enregistré")
    page.locator("#filtres .filtre", has_text="Lumineux").click()  # l'élément d'exemple a disparu
    expect(dialogue(page).locator(".choix")).to_have_text(["Tous", "Sans lumineux"])
    dialogue(page).get_by_role("button", name="Tous").click()
    page.locator("#filtres .filtre", has_text="Taximètre").click()  # les éléments de départ, inutilisés, sont partis aussi
    expect(dialogue(page).locator(".choix")).to_have_text(["Tous", "Sans taximètre"])


def test_supprimer_les_exemples_retire_les_elements_de_depart_des_anciens_appareils(page, tmp_path):
    """Un appareil d'avant n'avait pas marqué ses éléments de départ comme exemples : jamais modifiés, ils partent aussi."""
    ancien = exporter_json(page, tmp_path / "ancien.json")
    for e in ancien["elements"]:
        e.pop("exemple", None)  # comme dans le stockage d'un appareil d'avant
    assert any(f.get("exemple") for f in ancien["forfaits"])  # les forfaits d'exemple, eux, étaient déjà marqués
    page.evaluate("(d) => localStorage.setItem('forfaits.donnees.v1', JSON.stringify(d))", ancien)
    page.reload()
    activer_modif(page)
    page.click("#btn-suppr-exemples")
    dialogue(page).get_by_role("button", name="Supprimer les exemples").click()
    expect(page.locator("#resultats")).to_contain_text("Aucun forfait enregistré")
    page.locator("#filtres .filtre", has_text="Taximètre").click()
    expect(dialogue(page).locator(".choix")).to_have_text(["Tous", "Sans taximètre"])
    dialogue(page).get_by_role("button", name="Tous").click()
    page.locator("#filtres .filtre", has_text="Boîtier").click()
    expect(dialogue(page).locator(".choix")).to_have_text(["Tous", "Sans boîtier"])


def test_supprimer_les_exemples_garde_les_elements_modifies(page, tmp_path):
    """Un élément de départ que l'utilisateur a retouché (maj > 0) est à lui : il reste."""
    ancien = exporter_json(page, tmp_path / "ancien.json")
    for e in ancien["elements"]:
        e.pop("exemple", None)
        if e["nom"] == "T2":
            e["nom"], e["maj"] = "T2 Plus", 1_700_000_000_000
    page.evaluate("(d) => localStorage.setItem('forfaits.donnees.v1', JSON.stringify(d))", ancien)
    page.reload()
    activer_modif(page)
    page.click("#btn-suppr-exemples")
    dialogue(page).get_by_role("button", name="Supprimer les exemples").click()
    page.locator("#filtres .filtre", has_text="Taximètre").click()
    expect(dialogue(page).locator(".choix")).to_have_text(["Tous", "T2 Plus", "Sans taximètre"])


def test_supprimer_les_exemples_garde_un_element_de_depart_renomme(page):
    """Renommer un élément de départ dans l'écran des listes le rend à l'utilisateur, même s'il garde sa marque d'exemple."""
    activer_modif(page)
    page.click("#btn-menu")
    page.click("#btn-listes")
    dialogue(page).get_by_label("Nom de l'élément T2").fill("T2 Plus")
    dialogue(page).get_by_role("button", name="Terminé").click()
    page.click("#btn-suppr-exemples")
    dialogue(page).get_by_role("button", name="Supprimer les exemples").click()
    expect(page.locator("#resultats")).to_contain_text("Aucun forfait enregistré")
    page.locator("#filtres .filtre", has_text="Taximètre").click()
    expect(dialogue(page).locator(".choix")).to_have_text(["Tous", "T2 Plus", "Sans taximètre"])


# ---------------------------------------------------------------- listes modifiables sans code


def test_listes_ajouter_renommer_et_proteger(page):
    activer_modif(page)
    page.click("#btn-menu")
    page.click("#btn-listes")
    d = dialogue(page)
    d.locator("#nouvelle-famille").fill("TPE")
    d.locator("#nouvelle-famille").press("Enter")
    d.get_by_label("Nouvel élément pour TPE").fill("TPE X")
    d.get_by_label("Nouvel élément pour TPE").press("Enter")
    d.get_by_label("Nouvel élément pour Boîtier").fill("Zorba 8")
    d.get_by_label("Nouvel élément pour Boîtier").press("Enter")
    d.get_by_label("Nouvel élément pour Boîtier").fill("zorba-8")  # doublon refusé
    d.get_by_label("Nouvel élément pour Boîtier").press("Enter")
    expect(d.locator(".msg-erreur")).to_contain_text("existe déjà")
    d.get_by_label("Nom de l'élément Zorba 5").fill("Zorba 5 Plus")
    # Clic direct sur un autre bouton juste après le renommage : il ne doit pas être perdu.
    d.get_by_role("button", name="Supprimer 3Q").click()  # utilisé : suppression refusée
    expect(dialogue(page)).to_contain_text("Suppression impossible")
    dialogue(page).get_by_role("button", name="Compris").click()
    dialogue(page).get_by_role("button", name="Terminé").click()

    expect(page.locator("#filtres .filtre", has_text="TPE")).to_be_visible()
    chercher(page, "zorba5plus")  # le renommage s'applique aux forfaits existants
    assert refs(page) == AVEC_ZORBA5
    chercher(page, "3Q")
    assert refs(page) == AVEC_3Q

    ouvrir_ajout(page)
    remplir(page, "TPE-1", "300", "360", {"TPE": "TPE X", "Boîtier": "Zorba 8"})
    chercher(page, "tpe x")
    assert refs(page) == {"TPE-1"}
    chercher(page, "zor")
    expect(page.locator("#suggestions .suggestion-nom")).to_have_text(["Zorba 5 Plus", "Zorba 8", "Zorbatech X"])


# ---------------------------------------------------------------- sauvegarde et partage


def test_exporter_puis_importer_donne_les_memes_donnees(appareils, tmp_path):
    a = appareils().page
    activer_modif(a)
    ouvrir_ajout(a)
    remplir(
        a, "VRAI-1", "2 000", "2 400", {"Taximètre": "T2", "Imprimante": "4Q"}, designation="Ligne 1\nLigne 2 ; « guillemets »"
    )
    modifier(a, "EX-T2-3Q")
    remplir(a, ht="800", ttc="960")
    chercher(a, "EX-LUM-POSE")
    a.get_by_role("button", name="Supprimer", exact=True).click()
    dialogue(a).get_by_role("button", name="Supprimer", exact=True).click()
    expect(a.locator("#resultats .carte")).to_have_count(0)
    chercher(a, "")
    fichier = exporter_json(a, tmp_path / "a.json")
    attendu = cartes(a)

    for choix in ("Mettre à jour", "Remplacer tout"):
        b = appareils().page
        importer(b, tmp_path / "a.json", choix)
        assert cartes(b) == attendu, choix
        reexport = exporter_json(b, tmp_path / f"b-{choix}.json")
        assert contenu(reexport) == contenu(fichier), choix


def test_fusion_entre_deux_responsables_et_un_comptoir(appareils, tmp_path):
    a = appareils().page
    b = appareils().page
    activer_modif(a)
    activer_modif(b)

    modifier(a, "EX-T2-3Q")
    remplir(a, ht="800", ttc="960")
    exporter_json(a, tmp_path / "a1.json")

    importer(b, tmp_path / "a1.json")
    chercher(b, "EX-T2-3Q")
    assert espaces(cartes(b)[0]["ttc"]) == "960,00 €"
    chercher(b, "EX-LUM-POSE")
    b.get_by_role("button", name="Supprimer", exact=True).click()
    dialogue(b).get_by_role("button", name="Supprimer", exact=True).click()
    expect(b.locator("#resultats .carte")).to_have_count(0)
    ouvrir_ajout(b)
    remplir(b, "B-NOUVEAU", "100", "120")
    exporter_json(b, tmp_path / "b1.json")

    # Pendant ce temps, A modifie un autre forfait sans avoir importé le fichier de B.
    modifier(a, "EX-T2-Z5-3Q")
    remplir(a, designation="Modifié par A")
    importer(a, tmp_path / "b1.json")
    chercher(a, "")
    resultat = {c["ref"]: c for c in cartes(a)}
    assert "EX-LUM-POSE" not in resultat  # suppression de B propagée
    assert "B-NOUVEAU" in resultat  # ajout de B reçu
    assert resultat["EX-T2-Z5-3Q"]["designation"] == "Modifié par A"  # modif de A gardée
    assert espaces(resultat["EX-T2-3Q"]["ttc"]) == "960,00 €"

    comptoir = appareils().page  # un collègue qui ne fait que consulter
    importer(comptoir, tmp_path / "b1.json")
    assert refs(comptoir) == (TOUS - {"EX-LUM-POSE"}) | {"B-NOUVEAU"}


def test_import_annonce_les_prix_qui_changent(appareils, tmp_path):
    a = appareils().page
    activer_modif(a)
    modifier(a, "EX-T2-3Q")
    remplir(a, ht="800", ttc="960")
    modifier(a, "EX-T2-Z5-3Q")
    remplir(a, designation="Seule la désignation change")
    exporter_json(a, tmp_path / "a.json")

    b = appareils().page
    b.set_input_files("#fichier-import", str(tmp_path / "a.json"))
    d = dialogue(b)
    expect(d).to_contain_text("2 modifiés")
    texte = espaces(d.inner_text())
    assert "Prix qui changent : EX-T2-3Q : 700,00 € → 800,00 € HT, 840,00 € → 960,00 € TTC" in texte
    assert "EX-T2-Z5-3Q :" not in texte  # modifié, mais pas son prix
    d.get_by_role("button", name="Annuler").click()


def test_import_d_un_fichier_plus_ancien_garde_les_versions_recentes(appareils, tmp_path):
    a = appareils().page
    activer_modif(a)
    exporter_json(a, tmp_path / "ancien.json")
    modifier(a, "EX-T2-3Q")
    remplir(a, ht="800", ttc="960")
    a.set_input_files("#fichier-import", str(tmp_path / "ancien.json"))
    expect(dialogue(a)).to_contain_text("plus ancien que tes données")
    dialogue(a).get_by_role("button", name="Mettre à jour").click()
    chercher(a, "EX-T2-3Q")
    assert espaces(cartes(a)[0]["ttc"]) == "960,00 €"


def test_remplacer_tout_annonce_les_anciens_prix(appareils, tmp_path):
    """Un fichier plus ancien : « Mettre à jour » ne change aucun prix, « Remplacer tout » remet l'ancien, et le dit avant."""
    a = appareils().page
    activer_modif(a)
    exporter_json(a, tmp_path / "ancien.json")
    modifier(a, "EX-T2-3Q")
    remplir(a, ht="800", ttc="960")
    a.set_input_files("#fichier-import", str(tmp_path / "ancien.json"))
    texte = espaces(dialogue(a).inner_text())
    assert "Prix qui changent : " not in texte
    assert "Prix qui changent avec « Remplacer tout » : EX-T2-3Q : 800,00 € → 700,00 € HT, 960,00 € → 840,00 € TTC" in texte
    dialogue(a).get_by_role("button", name="Annuler").click()


def test_export_csv_lisible_dans_excel(page, tmp_path):
    page.click("#btn-menu")
    page.click("#btn-menu-exporter")
    with page.expect_download() as telechargement:
        page.click("#btn-export-csv")
    chemin = tmp_path / "f.csv"
    telechargement.value.save_as(chemin)
    brut = chemin.read_bytes()
    assert brut.startswith(b"\xef\xbb\xbf")  # accents corrects dans Excel
    lignes = brut.decode("utf-8-sig").split("\r\n")
    assert (
        lignes[0]
        == "Référence;Désignation;Prix HT;Prix TTC;Taximètre;Boîtier;Imprimante;Lumineux;Installation;Exemple;Modifié le"
    )
    assert len(lignes) == 12
    ligne = next(x for x in lignes if x.startswith("EX-T1-Z5-3Q;"))
    assert ";1234,50;1481,40;T1 DEMO;Zorba 5;3Q;;;oui;" in ligne


# ---------------------------------------------------------------- tableau Excel (.csv)

EN_TETE_TABLEAU = "Référence;Désignation;Prix HT;Prix TTC;Taximètre;Boîtier;Imprimante;Lumineux;Installation"


def ecrire_tableau(chemin, lignes, encodage="utf-8-sig", en_tete=EN_TETE_TABLEAU, vides=5):
    """Écrit un tableau comme Excel : « ; », prix à virgule, fins de ligne Windows, lignes vides à la fin."""
    texte = "\r\n".join([en_tete, *lignes, *[";;;;;;;;"] * vides]) + "\r\n"
    chemin.write_bytes(texte.encode(encodage))
    return chemin


def ouvrir_tableau(page, chemin):
    page.set_input_files(
        "#fichier-import", []
    )  # le bouton « Importer » vide le champ : sans cela, un même fichier ne se rouvre pas
    page.set_input_files("#fichier-import", str(chemin))
    d = dialogue(page)
    expect(d).to_contain_text("Importer ce tableau")
    return d


@pytest.mark.parametrize("encodage", ["utf-8-sig", "cp1252"])  # « CSV UTF-8 » d'Excel, puis l'ancien « CSV »
def test_importer_un_tableau_excel_et_supprimer_les_exemples(appareils, tmp_path, encodage):
    page = appareils().page
    chemin = ecrire_tableau(
        tmp_path / "tableau.csv",
        [
            "T-1;Taximètre T1 DEMO + Zorba 5;1234,50;1481,40;T1 DEMO;Zorba 5;3Q;;",
            't-2;"Ligne 1\nLigne 2 « guillemets » et ""doubles""";1000,00;1200,00;T2;;4Q;;',
            "001;Référence qui ressemble à un nombre;99,90;119,88;;Zorba 9;;;",
            "T-4;- désignation qui commence par un tiret;100,00;130,00;T2;;;;",
        ],
        encodage,
    )
    d = ouvrir_tableau(page, chemin)
    expect(d).to_contain_text("4 forfaits")
    expect(d).to_contain_text("4 nouveaux, 0 modifié, 0 inchangé")
    expect(d).to_contain_text("Boîtier : Zorba 9")  # élément inconnu : annoncé avant d'être créé
    expect(d).to_contain_text("TTC à vérifier")  # TTC qui ne correspond pas au HT + 20 %
    expect(d).to_contain_text("T-4 : 130,00")
    d.get_by_role("button", name="Importer et supprimer les exemples", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    assert refs(page) == {"T-1", "t-2", "001", "T-4"}
    carte = {c["ref"]: c for c in cartes(page)}
    assert espaces(carte["T-1"]["ht"]) == "1 234,50 €"
    assert espaces(carte["T-1"]["ttc"]) == "1 481,40 €"
    assert carte["T-1"]["elements"] == {"Taximètre": "T1 DEMO", "Boîtier": "Zorba 5", "Imprimante": "3Q"}
    assert carte["t-2"]["designation"] == 'Ligne 1\nLigne 2 « guillemets » et "doubles"'
    assert carte["001"]["elements"] == {"Boîtier": "Zorba 9"}
    assert carte["T-4"]["designation"] == "- désignation qui commence par un tiret"

    fichier = exporter_json(page, tmp_path / "apres.json")
    assert [e["familleId"] for e in fichier["elements"] if e["nom"] == "Zorba 9"] == ["fam-boitier"]  # créé une seule fois
    assert not [f for f in fichier["forfaits"] if f.get("exemple") and not f.get("supprime")]
    gardes = {e["nom"] for e in fichier["elements"] if not e.get("supprime")}
    assert {"T1 DEMO", "T2", "Zorba 5", "3Q", "4Q", "Zorba 9"} <= gardes  # ceux que les 4 forfaits utilisent
    assert not gardes & {
        "Kalpo X",
        "Zorbatech X",
        "Kalpo universelle",
        "Lumineux EXEMPLE",
        "Pose EXEMPLE",
    }  # les autres partent


def test_tableau_refuse_avec_les_numeros_de_ligne(page, tmp_path):
    chemin = ecrire_tableau(
        tmp_path / "faux.csv",
        [
            "A-1;ok;100,00;120,00;;;;;",
            ";sans référence;100,00;120,00;;;;;",
            "A-3;prix illisible;12 abc;120,00;;;;;",
            "A-4;ttc manquant;100,00;;;;;;",
            "a-1;doublon;100,00;120,00;;;;;",
        ],
    )
    page.set_input_files("#fichier-import", str(chemin))
    d = dialogue(page)
    expect(d).to_contain_text("Import impossible")
    texte = d.text_content()
    assert "Ligne 3 : la référence est vide." in texte
    assert "Ligne 4 (A-3) : prix HT illisible « 12 abc »" in texte
    assert "Ligne 5 (A-4) : prix TTC manquant" in texte
    assert "Ligne 6 (a-1) : cette référence est déjà à la ligne 2" in texte
    d.get_by_role("button", name="Compris").click()
    assert refs(page) == TOUS  # rien n'a bougé : même la ligne « A-1 », correcte, n'est pas importée


def noms_familles(page, chemin):
    """Familles actives de l'appareil, dans l'ordre (lues dans un export)."""
    return [f["nom"] for f in exporter_json(page, chemin)["familles"] if not f.get("supprime")]


def test_tableau_sans_les_titres_obligatoires_refuse(page, tmp_path):
    chemin = ecrire_tableau(tmp_path / "titres.csv", [], en_tete="Code;Prix", vides=0)
    page.set_input_files("#fichier-import", str(chemin))
    d = dialogue(page)
    expect(d).to_contain_text("Import impossible")
    assert "Colonne « Référence » introuvable" in d.text_content()
    d.get_by_role("button", name="Compris").click()
    assert refs(page) == TOUS
    assert "Code" not in noms_familles(
        page, tmp_path / "apres.json"
    )  # des titres inconnus + un titre obligatoire manquant : pas de familles créées


def test_tableau_une_colonne_nouvelle_cree_la_famille(page, tmp_path):
    """Une colonne inconnue est une nouvelle famille : annoncée avant, créée une seule fois, reconnue ensuite."""
    chemin = ecrire_tableau(
        tmp_path / "dash.csv",
        ["DC-1;Dash cam avant;100,00;120,00;;;;;;Dash X1", "DC-2;Dash cam avant et arrière;150,00;180,00;;;;;;Dash X2"],
        en_tete=f"{EN_TETE_TABLEAU};Dash cam",
    )
    d = ouvrir_tableau(page, chemin)
    expect(d).to_contain_text("Familles (colonnes) qui n'existent pas encore")
    expect(d).to_contain_text("Dash cam")
    d.get_by_role("button", name="Annuler").click()
    familles_de_depart = ["Taximètre", "Boîtier", "Imprimante", "Lumineux", "Installation"]
    assert noms_familles(page, tmp_path / "annule.json") == familles_de_depart  # annuler ne crée rien

    d = ouvrir_tableau(page, chemin)
    d.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    par_ref = {c["ref"]: c for c in cartes(page)}
    assert par_ref["DC-1"]["elements"] == {"Dash cam": "Dash X1"}
    assert par_ref["DC-2"]["elements"] == {"Dash cam": "Dash X2"}
    assert noms_familles(page, tmp_path / "apres.json") == [*familles_de_depart, "Dash cam"]  # à la suite des autres

    # Le même tableau une seconde fois : la famille et ses éléments sont reconnus, rien n'est créé de nouveau.
    d = ouvrir_tableau(page, chemin)
    expect(d).to_contain_text("0 nouveau, 0 modifié, 2 inchangés")
    expect(d).not_to_contain_text("n'existent pas encore")
    d.get_by_role("button", name="Annuler").click()


def test_tableau_trop_de_colonnes_nouvelles_ou_nom_trop_long_refuse(page, tmp_path):
    cas = {
        "trop.csv": (";".join(f"Colonne {i}" for i in range(11)), "10 nouvelles familles au maximum"),
        "long.csv": ("x" * 61, "nom de famille trop long"),
    }
    for nom, (colonnes, attendu) in cas.items():
        chemin = ecrire_tableau(tmp_path / nom, [], en_tete=f"{EN_TETE_TABLEAU};{colonnes}", vides=0)
        page.set_input_files("#fichier-import", str(chemin))
        d = dialogue(page)
        expect(d).to_contain_text("Import impossible")
        assert attendu in d.text_content(), nom
        d.get_by_role("button", name="Compris").click()
    assert refs(page) == TOUS


def test_tableau_exporte_par_l_outil_se_reimporte_sans_changement(page, tmp_path):
    page.click("#btn-menu")
    page.click("#btn-menu-exporter")
    with page.expect_download() as telechargement:
        page.click("#btn-export-csv")
    chemin = tmp_path / "export.csv"
    telechargement.value.save_as(chemin)
    d = ouvrir_tableau(page, chemin)
    expect(d).to_contain_text("11 forfaits")
    expect(d).to_contain_text("0 nouveau, 0 modifié, 11 inchangés")
    expect(d.get_by_role("button", name="Importer et supprimer les exemples")).to_have_count(0)  # ce sont des exemples
    d.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    assert refs(page) == TOUS


def test_tableau_met_a_jour_un_forfait_sans_le_dupliquer(page, tmp_path):
    chemin = ecrire_tableau(tmp_path / "maj.csv", ["ex-t2-3q;Nouvelle désignation;800,00;960,00;T2;;;;"])
    d = ouvrir_tableau(page, chemin)
    expect(d).to_contain_text("0 nouveau, 1 modifié, 0 inchangé")
    assert "Prix qui changent : ex-t2-3q : 700,00 € → 800,00 € HT, 840,00 € → 960,00 € TTC" in espaces(d.inner_text())
    d.get_by_role("button", name="Importer", exact=True).click()  # sans supprimer les exemples
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    assert refs(page) == (TOUS - {"EX-T2-3Q"}) | {"ex-t2-3q"}  # même forfait, pas un doublon
    (carte,) = [c for c in cartes(page) if c["ref"] == "ex-t2-3q"]
    assert espaces(carte["ttc"]) == "960,00 €"
    assert carte["designation"] == "Nouvelle désignation"
    assert carte["elements"] == {"Taximètre": "T2"}  # cellule vide : l'imprimante 3Q est retirée

    d = ouvrir_tableau(page, chemin)  # même tableau une seconde fois : rien à changer
    expect(d).to_contain_text("0 nouveau, 0 modifié, 1 inchangé")
    d.get_by_role("button", name="Annuler").click()


def test_tableau_sans_colonne_designation_ne_l_efface_pas(page, tmp_path):
    """Un tableau réduit à « Référence ; Prix HT ; Prix TTC » ne met à jour que les prix."""
    chemin = ecrire_tableau(tmp_path / "prix.csv", ["EX-T2-3Q;800,00;960,00"], en_tete="Référence;Prix HT;Prix TTC", vides=0)
    d = ouvrir_tableau(page, chemin)
    expect(d).to_contain_text("0 nouveau, 1 modifié, 0 inchangé")
    d.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    (carte,) = [c for c in cartes(page) if c["ref"] == "EX-T2-3Q"]
    assert espaces(carte["ttc"]) == "960,00 €"
    assert carte["designation"].startswith("EXEMPLE")  # désignation d'origine gardée
    assert carte["elements"] == {"Taximètre": "T2", "Imprimante": "3Q"}  # familles absentes du tableau : intactes
    stock = page.evaluate("JSON.parse(localStorage.getItem('forfaits.donnees.v1'))")
    assert next(f for f in stock["forfaits"] if f["ref"] == "EX-T2-3Q")["exemple"] is True  # le repère « exemple » aussi


def test_tableau_la_barre_oblique_veut_dire_pas_de_donnees(page, tmp_path):
    """Dans les tableaux remplis à la main, « / » = pas de données : jamais un élément nommé « / »."""
    chemin = ecrire_tableau(
        tmp_path / "barre.csv",
        ["EX-T2-3Q;/;800,00;960,00;T2;/;/;/;/", "NV-1;Forfait neuf;100,00;120,00;/;/;/;/;/"],
    )
    d = ouvrir_tableau(page, chemin)
    expect(d).to_contain_text("1 nouveau, 1 modifié, 0 inchangé")
    expect(d).not_to_contain_text("n'existent pas encore")  # aucun élément « / » à créer
    d.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    par_ref = {c["ref"]: c for c in cartes(page)}
    assert par_ref["EX-T2-3Q"]["elements"] == {"Taximètre": "T2"}  # « / » comme une case vide : l'imprimante 3Q est retirée
    assert par_ref["EX-T2-3Q"]["designation"] == ""
    assert par_ref["NV-1"]["elements"] == {}
    assert (
        page.evaluate("JSON.parse(localStorage.getItem('forfaits.donnees.v1')).elements.filter(e => e.nom === '/').length") == 0
    )


def test_tableau_dans_l_ordre_du_modele_et_forfait_sans_aucun_element(page, tmp_path):
    """Le modèle Excel met Boîtier et Installation à droite : l'import lit les colonnes par leur titre, pas par leur place.
    Un forfait sans taximètre (dash cam…) n'a que sa référence, sa désignation et ses prix."""
    chemin = ecrire_tableau(
        tmp_path / "ordre-du-modele.csv",
        ["MO-1;Taximètre avec boîtier;1000,00;1200,00;T2;4Q;/;Zorba 5;/", "MO-DASH;Dash cam seule;150,00;180,00;/;/;/;/;/"],
        en_tete="Référence;Désignation;Prix HT;Prix TTC;Taximètre;Imprimante;Lumineux;Boîtier;Installation",
    )
    d = ouvrir_tableau(page, chemin)
    expect(d).to_contain_text("2 nouveaux, 0 modifié, 0 inchangé")
    expect(d).not_to_contain_text("n'existent pas encore")  # Zorba 5 est reconnu dans la famille Boîtier
    d.get_by_role("button", name="Importer", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Tableau importé")
    par_ref = {c["ref"]: c for c in cartes(page)}
    assert par_ref["MO-1"]["elements"] == {"Taximètre": "T2", "Imprimante": "4Q", "Boîtier": "Zorba 5"}
    assert par_ref["MO-DASH"]["elements"] == {}
    page.fill("#recherche", "dash cam")
    assert refs(page) == {"MO-DASH"}  # un forfait sans élément se retrouve par sa désignation


def test_import_d_un_mauvais_fichier_refuse(page, tmp_path):
    cas = {
        "texte.json": "bonjour",
        "autre.json": json.dumps({"format": "autre chose"}),
        "futur.json": json.dumps({"format": "forfaits-comptoir", "version": 99, "familles": [], "elements": [], "forfaits": []}),
        "abime.json": json.dumps(
            {
                "format": "forfaits-comptoir",
                "version": 1,
                "familles": [],
                "elements": [],
                "forfaits": [{"id": "fft-x", "ref": "", "ht": 1, "ttc": 1, "elements": {}, "maj": 1}],
            }
        ),
    }
    messages = {}
    for nom, texte in cas.items():
        chemin = tmp_path / nom
        chemin.write_text(texte, encoding="utf-8")
        page.set_input_files("#fichier-import", str(chemin))
        d = dialogue(page)
        expect(d).to_contain_text("Import impossible")
        messages[nom] = d.locator(".dlg-message").text_content()
        d.get_by_role("button", name="Compris").click()
    assert "pas un fichier de forfaits" in messages["texte.json"]
    assert "version plus récente" in messages["futur.json"]
    assert "abîmé" in messages["abime.json"]
    assert refs(page) == TOUS  # rien n'a bougé


def test_rappel_d_exporter(page, tmp_path):
    activer_modif(page)
    expect(page.locator("#rappel")).to_be_hidden()
    ouvrir_ajout(page)
    remplir(page, "R-1", "100", "120")
    expect(page.locator("#rappel")).to_contain_text("1 modification pas encore exportée")
    page.click("#btn-rappel-exporter")  # le bouton du rappel ouvre l'export
    expect(dialogue(page)).to_contain_text("Fichier de sauvegarde (.json)")
    dialogue(page).get_by_role("button", name="Fermer").click()
    exporter_json(page, tmp_path / "r.json")
    expect(page.locator("#rappel")).to_be_hidden()


def test_export_dans_le_dossier_choisi(page):
    """Edge et Chrome sur PC : le fichier va dans le dossier choisi (OneDrive), sans passer par Téléchargements."""
    page.evaluate("""() => {
        window.showSaveFilePicker = async (options) => {
            window.choix = options;
            if (window.annuler) throw new DOMException('annulé', 'AbortError');
            return { createWritable: async () => ({ write: async (c) => { window.ecrit = c; }, close: async () => {} }) };
        };
    }""")
    activer_modif(page)
    ouvrir_ajout(page)
    remplir(page, "D-1", "100", "120")
    expect(page.locator("#rappel")).to_be_visible()
    telechargements = []
    page.on("download", lambda t: telechargements.append(t))

    page.evaluate("window.annuler = true")
    page.click("#btn-menu")
    page.click("#btn-menu-exporter")
    page.click("#btn-export-json")
    expect(page.locator("dialog[open]")).to_have_count(0)
    page.wait_for_function("window.choix")
    expect(page.locator("#rappel")).to_be_visible()  # annulé : rien n'est exporté

    page.evaluate("window.annuler = false")
    page.click("#btn-rappel-exporter")
    page.click("#btn-export-json")
    expect(page.locator("#toast")).to_have_text("Fichier de sauvegarde enregistré")
    expect(page.locator("#rappel")).to_be_hidden()
    choix = page.evaluate("window.choix")
    assert choix["id"] == "forfaits" and re.fullmatch(r"forfaits-\d{4}-\d\d-\d\d-\d\dh\d\d\.json", choix["suggestedName"])
    fichier = json.loads(page.evaluate("window.ecrit"))
    assert "D-1" in {f["ref"] for f in fichier["forfaits"]}
    assert telechargements == []


def test_rappel_d_importer_apres_une_semaine(appareils, tmp_path):
    a = appareils().page
    activer_modif(a)
    a.click("#btn-suppr-exemples")
    dialogue(a).get_by_role("button", name="Supprimer les exemples").click()
    ouvrir_ajout(a)
    remplir(a, "S-1", "100", "120")
    exporter_json(a, tmp_path / "s.json")

    comptoir = appareils().page
    comptoir.clock.install()  # le test avance l'horloge de la page
    comptoir.reload()
    importer(comptoir, tmp_path / "s.json", "Remplacer tout")
    bandeaux = comptoir.locator("#bandeaux")
    debut = comptoir.evaluate("Date.now()") / 1000

    def revenir_sur_l_appli_apres(jours):  # appli Android reprise depuis l'arrière-plan
        comptoir.clock.set_system_time(debut + jours * 86400)
        comptoir.evaluate("document.dispatchEvent(new Event('visibilitychange'))")

    revenir_sur_l_appli_apres(6)
    expect(bandeaux).not_to_contain_text("Dernier import")
    revenir_sur_l_appli_apres(7)
    expect(bandeaux).to_contain_text("Dernier import il y a 7 jours")

    with comptoir.expect_file_chooser() as choix:  # le bouton du bandeau ouvre le choix du fichier
        bandeaux.get_by_role("button", name="Importer").click()
    choix.value.set_files(str(tmp_path / "s.json"))
    dialogue(comptoir).get_by_role("button", name="Mettre à jour", exact=True).click()
    expect(comptoir.locator("#toast")).to_have_text("Mise à jour terminée")
    expect(bandeaux).not_to_contain_text("Dernier import")

    comptoir.clock.fast_forward(7 * 86400000)  # onglet resté ouvert une semaine : le contrôle horaire le voit
    expect(bandeaux).to_contain_text("Dernier import il y a 7 jours")


def test_boutons_vider_et_tout_effacer(page):
    chercher(page, "zzz")
    page.click("#btn-vider")
    expect(page.locator("#recherche")).to_have_value("")
    assert refs(page) == TOUS
    chercher(page, "3Q")
    page.locator("#filtres .filtre", has_text="Taximètre").click()
    dialogue(page).get_by_role("button", name="T2", exact=True).click()
    assert refs(page) == AVEC_T2_ET_3Q
    page.click("#btn-tout-effacer")  # efface le texte ET les filtres
    expect(page.locator("#recherche")).to_have_value("")
    expect(page.locator("#etiquettes")).to_be_hidden()
    assert refs(page) == TOUS


def test_exemple_modifie_devient_un_vrai_forfait(page):
    activer_modif(page)
    modifier(page, "EX-T2-3Q")
    expect(dialogue(page).locator(".note-exemple")).to_contain_text("devient un vrai forfait")
    remplir(page, ref="VRAI-T2-3Q", ht="500", ttc="600", designation="Vrai forfait")
    page.click("#btn-suppr-exemples")
    dialogue(page).get_by_role("button", name="Supprimer les exemples").click()
    expect(page.locator("#resultats .carte")).to_have_count(1)
    assert refs(page) == {"VRAI-T2-3Q"}
    expect(page.locator(".badge-exemple")).to_have_count(0)


def test_date_absurde_dans_un_fichier_ne_bloque_rien(appareils, tmp_path):
    a = appareils().page
    fichier = exporter_json(a, tmp_path / "base.json")
    for f in fichier["forfaits"]:
        if f["ref"] == "EX-T2-3Q":
            f["maj"] = 1e20
            f["ttc"] = 99999
    piege = tmp_path / "piege.json"
    piege.write_text(json.dumps(fichier), encoding="utf-8")
    importer(a, piege)
    chercher(a, "EX-T2-3Q")
    assert espaces(cartes(a)[0]["ttc"]) == "999,99 €"
    expect(a.locator("#etat-donnees")).to_contain_text("Données du")
    # La date a été ramenée à demain au plus : une vraie modification plus tard l'emportera encore.
    a.reload()
    a.wait_for_selector("#resultats .carte")
    assert a.evaluate(
        "JSON.parse(localStorage.getItem('forfaits.donnees.v1')).forfaits.every(f => f.maj <= Date.now() + 86400000)"
    )


def test_horloge_en_avance_une_correction_l_emporte_quand_meme(appareils, tmp_path):
    """Un fichier daté de quelques heures dans le futur (appareil à l'horloge en avance) ne doit pas
    faire perdre les corrections faites ensuite, ni à la main ni par le tableau."""
    a = appareils().page
    fichier = exporter_json(a, tmp_path / "base.json")
    for f in fichier["forfaits"]:
        if f["ref"] == "EX-T2-3Q":
            f["maj"] = int(datetime.now().timestamp() * 1000) + 12 * 3600 * 1000
            f["ht"], f["ttc"] = 100000, 120000
    avance = tmp_path / "avance.json"
    avance.write_text(json.dumps(fichier), encoding="utf-8")
    importer(a, avance)

    activer_modif(a)
    modifier(a, "EX-T2-3Q")
    remplir(a, ht="800", ttc="960")
    a.set_input_files("#fichier-import", [])
    importer(a, avance)  # le fichier « du futur » revient : la correction reste
    chercher(a, "EX-T2-3Q")
    assert espaces(cartes(a)[0]["ttc"]) == "960,00 €"

    d = ouvrir_tableau(a, ecrire_tableau(tmp_path / "t.csv", ["EX-T2-3Q;Corrigé;850,00;1020,00;T2;;3Q;;"]))
    expect(d).to_contain_text("0 nouveau, 1 modifié, 0 inchangé")
    d.get_by_role("button", name="Importer", exact=True).click()
    expect(a.locator("#toast")).to_have_text("Tableau importé")
    a.set_input_files("#fichier-import", [])
    importer(a, avance)
    chercher(a, "EX-T2-3Q")
    assert espaces(cartes(a)[0]["ttc"]) == "1 020,00 €"


def test_fenetre_lisible_sur_grand_ecran(page):
    """Safari écrasait le corps des fenêtres à sa seule marge au-delà de 600 px de large."""
    page.set_viewport_size({"width": 1280, "height": 720})
    activer_modif(page)
    ouvrir_ajout(page)
    corps = dialogue(page).locator(".dlg-corps")
    assert corps.evaluate("c => c.clientHeight") >= min(300, corps.evaluate("c => c.scrollHeight"))


def test_export_iphone_par_le_menu_partager(appareils):
    """iPhone : le téléchargement peut ne rien enregistrer, l'export passe par le menu Partager."""
    iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
    page = appareils(user_agent=iphone).page
    page.evaluate("""() => {
        navigator.canShare = (d) => !!d.files;
        navigator.share = async (d) => {
            if (window.annuler) throw new DOMException('annulé', 'AbortError');
            window.partage = { nom: d.files[0].name, texte: await d.files[0].text() };
        };
    }""")
    activer_modif(page)
    ouvrir_ajout(page)
    remplir(page, "I-1", "100", "120")
    telechargements = []
    page.on("download", lambda t: telechargements.append(t))

    page.evaluate("window.annuler = true")
    page.click("#btn-rappel-exporter")
    page.click("#btn-export-json")
    expect(page.locator("dialog[open]")).to_have_count(0)
    expect(page.locator("#rappel")).to_be_visible()  # annulé : le rappel reste

    page.evaluate("window.annuler = false")
    page.click("#btn-rappel-exporter")
    page.click("#btn-export-json")
    expect(page.locator("#toast")).to_have_text("Fichier de sauvegarde enregistré")
    expect(page.locator("#rappel")).to_be_hidden()
    partage = page.evaluate("window.partage")
    assert re.fullmatch(r"forfaits-\d{4}-\d\d-\d\d-\d\dh\d\d\.json", partage["nom"])
    assert "I-1" in {f["ref"] for f in json.loads(partage["texte"])["forfaits"]}
    assert telechargements == []


def test_meme_element_cree_par_deux_responsables_signale(appareils, tmp_path):
    a = appareils().page
    b = appareils().page
    for p in (a, b):
        activer_modif(p)
        p.click("#btn-menu")
        p.click("#btn-listes")
        champ = dialogue(p).get_by_label("Nouvel élément pour Boîtier")
        champ.fill("Zorba 8")
        champ.press("Enter")
        dialogue(p).get_by_role("button", name="Terminé").click()
    exporter_json(b, tmp_path / "b.json")
    a.set_input_files("#fichier-import", str(tmp_path / "b.json"))
    dialogue(a).get_by_role("button", name="Mettre à jour").click()
    expect(dialogue(a)).to_contain_text("Doublons à corriger")
    expect(dialogue(a)).to_contain_text("Boîtier : Zorba 8 (2 fois)")


# ---------------------------------------------------------------- téléphone, hors ligne, fichier local


@pytest.mark.parametrize("largeur,hauteur,nom", [(375, 812, "telephone"), (1280, 800, "pc")])
def test_affichage_telephone_et_pc(navigateur, appareils, largeur, hauteur, nom):
    options = {"viewport": {"width": largeur, "height": hauteur}, "reduced_motion": "reduce"}
    if largeur < 600 and navigateur.nom != "firefox":
        options |= {"is_mobile": True, "has_touch": True, "device_scale_factor": 2}
    page = appareils(**options).page
    CAPTURES.mkdir(exist_ok=True)
    prefixe = CAPTURES / f"{navigateur.nom}-{nom}"

    def sans_defilement_horizontal():
        assert page.evaluate("document.documentElement.scrollWidth") <= largeur

    sans_defilement_horizontal()
    page.screenshot(path=f"{prefixe}-1-accueil.png")
    # Gros boutons faciles à toucher
    hauteurs = page.eval_on_selector_all(
        "#filtres .filtre, .btn-copier, #btn-importer, #btn-menu", "els => els.map(e => e.getBoundingClientRect().height)"
    )
    assert min(hauteurs) >= 44, hauteurs

    page.click("#recherche")
    page.keyboard.type("zor")
    expect(page.locator("#suggestions")).to_be_visible()
    sans_defilement_horizontal()
    page.screenshot(path=f"{prefixe}-2-suggestions.png")
    page.locator("#suggestions .suggestion", has_text="Zorba 5").click()
    page.screenshot(path=f"{prefixe}-3-etiquette.png")

    activer_modif(page)
    ouvrir_ajout(page)
    sans_defilement_horizontal()
    boite = dialogue(page).bounding_box()
    assert boite["width"] <= largeur
    page.screenshot(path=f"{prefixe}-4-formulaire.png")


# ---------------------------------------------------------------- thème clair et sombre


def choisir_theme(page, nom):
    """Ouvre le Menu, touche le thème voulu (la fenêtre reste ouverte), puis la ferme."""
    page.click("#btn-menu")
    dialogue(page).get_by_role("button", name=nom, exact=True).click()
    expect(dialogue(page).get_by_role("button", name=nom, exact=True)).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("Escape")


def fond(page, selecteur):
    return page.eval_on_selector(selecteur, "e => getComputedStyle(e).backgroundColor")


def test_theme_sombre_par_defaut_puis_clair_garde_apres_rechargement(page):
    html = page.locator("html")
    # Playwright simule un appareil clair : sans choix, l'outil reste noir et rouge.
    expect(html).to_have_attribute("data-theme", "sombre")
    assert fond(page, "body") == "rgb(0, 0, 0)"

    choisir_theme(page, "Clair")
    expect(html).to_have_attribute("data-theme", "clair")
    assert fond(page, "body") == "rgb(241, 241, 241)"
    assert fond(page, ".entete") == "rgb(0, 0, 0)"  # l'en-tête reste noir : c'est l'enseigne

    page.reload()
    expect(html).to_have_attribute("data-theme", "clair")
    page.click("#btn-menu")
    expect(dialogue(page).get_by_role("button", name="Clair", exact=True)).to_have_attribute("aria-pressed", "true")
    expect(dialogue(page).get_by_role("button", name="Sombre", exact=True)).to_have_attribute("aria-pressed", "false")
    page.keyboard.press("Escape")

    choisir_theme(page, "Sombre")
    expect(html).to_have_attribute("data-theme", "sombre")


def test_theme_auto_suit_le_reglage_de_l_appareil(appareils):
    page = appareils(color_scheme="dark").page
    html = page.locator("html")
    choisir_theme(page, "Auto")
    expect(html).to_have_attribute("data-theme", "sombre")
    page.emulate_media(color_scheme="light")  # l'utilisateur change le réglage de son téléphone
    expect(html).to_have_attribute("data-theme", "clair")
    page.reload()
    expect(html).to_have_attribute("data-theme", "clair")
    page.emulate_media(color_scheme="dark")
    expect(html).to_have_attribute("data-theme", "sombre")


def test_theme_inconnu_dans_les_reglages_revient_au_sombre(page):
    page.evaluate("localStorage.setItem('forfaits.appareil.v1', JSON.stringify({ theme: 'violet' }))")
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "sombre")


def _luminance(couleur):
    canaux = [int(couleur[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canaux)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(a, b):
    clair, sombre = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (clair + 0.05) / (sombre + 0.05)


# (couleur, fond, minimum) : seulement les associations réellement affichées.
# 4,5 = texte lisible (WCAG AA) ; 3 = bordure ou icône visible.
PAIRES_PAGE = [
    ("--texte", "--fond", 4.5), ("--texte", "--surface", 4.5), ("--texte-fort", "--surface", 4.5),
    ("--texte-doux", "--fond", 4.5), ("--texte-doux", "--surface", 4.5), ("--texte-doux", "--surface-2", 4.5),
    ("--texte-pale", "--fond", 4.5),  # texte d'exemple dans les champs
    ("--rouge-vif", "--fond", 4.5), ("--rouge-vif", "--surface", 4.5), ("--rouge-vif", "--surface-2", 4.5),
    ("--ambre", "--surface-2", 4.5), ("--ambre", "--surface", 4.5),
    ("--inverse-texte", "--inverse", 4.5),
    ("--blanc", "--rouge", 4.5), ("--blanc", "--vert", 4.5),
    ("--trait-fort", "--fond", 3),
]  # fmt: skip
PAIRES_BANDEAU_NOIR = [("--blanc", "--noir", 4.5), ("--texte-doux", "--noir", 4.5), ("--trait-fort", "--noir", 3)]


@pytest.mark.parametrize("theme", ["sombre", "clair"])
def test_contraste_des_couleurs_des_deux_themes(page, theme):
    if theme == "clair":
        choisir_theme(page, "Clair")
    expect(page.locator("html")).to_have_attribute("data-theme", theme)
    lire = "([sel, noms]) => noms.map(n => getComputedStyle(document.querySelector(sel)).getPropertyValue(n).trim())"
    for selecteur, paires in (("html", PAIRES_PAGE), (".entete", PAIRES_BANDEAU_NOIR)):
        for premier, second, minimum in paires:
            a, b = page.evaluate(lire, [selecteur, [premier, second]])
            assert _contraste(a, b) >= minimum, f"{theme} {selecteur} : {premier} {a} sur {second} {b} = {_contraste(a, b):.2f}"


@pytest.mark.parametrize("largeur,hauteur,nom", [(375, 812, "telephone"), (1280, 800, "pc")])
def test_affichage_clair_telephone_et_pc(navigateur, appareils, largeur, hauteur, nom):
    options = {"viewport": {"width": largeur, "height": hauteur}, "reduced_motion": "reduce"}
    if largeur < 600 and navigateur.nom != "firefox":
        options |= {"is_mobile": True, "has_touch": True, "device_scale_factor": 2}
    page = appareils(**options).page
    CAPTURES.mkdir(exist_ok=True)
    prefixe = CAPTURES / f"{navigateur.nom}-{nom}-clair"
    page.click("#btn-menu")
    dialogue(page).get_by_role("button", name="Clair", exact=True).click()
    page.screenshot(path=f"{prefixe}-1-menu.png")
    page.keyboard.press("Escape")
    chercher(page, "3Q")
    page.locator("#filtres .filtre", has_text="Taximètre").click()
    page.screenshot(path=f"{prefixe}-2-filtre.png")
    page.keyboard.press("Escape")
    page.locator("#recherche").fill("")
    page.click("#recherche")
    page.keyboard.type("zor")
    expect(page.locator("#suggestions")).to_be_visible()
    page.screenshot(path=f"{prefixe}-3-suggestions.png")
    page.locator("#suggestions .suggestion", has_text="Zorba 5").click()
    activer_modif(page)
    ouvrir_ajout(page)
    assert page.evaluate("document.documentElement.scrollWidth") <= largeur
    page.screenshot(path=f"{prefixe}-4-formulaire.png")


def test_marche_sans_internet(navigateur):
    url, serveur = demarrer_serveur()  # serveur à part : on le coupe pour de vrai
    contexte = navigateur.new_context(service_workers="allow")
    try:
        page = contexte.new_page()
        page.goto(url)
        page.wait_for_selector("#resultats .carte")
        page.evaluate("navigator.serviceWorker.ready.then(() => true)")
        page.wait_for_function("navigator.serviceWorker.controller !== null")
        serveur.shutdown()
        serveur.server_close()
        contexte.set_offline(True)
        page.reload()
        page.wait_for_selector("#resultats .carte")
        chercher(page, "3Q")
        assert refs(page) == AVEC_3Q
    finally:
        contexte.close()


def test_marche_en_ouvrant_le_fichier_directement(navigateur):
    contexte = navigateur.new_context()
    try:
        page = contexte.new_page()
        erreurs = []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.on("console", lambda m: erreurs.append(m.text) if m.type == "error" else None)
        page.goto((RACINE / "index.html").as_uri())
        page.wait_for_selector("#resultats .carte")
        chercher(page, "3Q T2")
        assert refs(page) == AVEC_T2_ET_3Q
        # Seul refus toléré : le navigateur ne lit pas le manifeste (icône d'appli) depuis un fichier local.
        assert all("manifest" in e.lower() for e in erreurs), erreurs
    finally:
        contexte.close()


# ---------------------------------------------------------------- vérifications sans navigateur


def test_empreinte_de_securite_a_jour():
    html = (RACINE / "index.html").read_text(encoding="utf-8")
    (script,) = re.findall(r"<script>(.*?)</script>", html, re.S)
    empreinte = base64.b64encode(hashlib.sha256(script.replace("\r\n", "\n").encode()).digest()).decode()
    assert f"script-src 'sha256-{empreinte}'" in html, "Lance : python outils/csp.py"


def test_icones_et_manifeste():
    manifeste = json.loads((RACINE / "manifest.webmanifest").read_text(encoding="utf-8"))
    for icone in manifeste["icons"]:
        largeur, hauteur = (int(x) for x in icone["sizes"].split("x"))
        with Image.open(RACINE / icone["src"]) as img:
            assert img.size == (largeur, hauteur)
    sw = (RACINE / "sw.js").read_text(encoding="utf-8")
    for icone in manifeste["icons"]:
        assert icone["src"] in sw, f"{icone['src']} absent du cache hors ligne"


def test_aucune_vraie_donnee_dans_le_depot():
    """Le dépôt est public : les exports (vrais prix) sont exclus de git."""
    regles = (RACINE / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert {"forfaits-*.json", "*.csv", "prive/"} <= set(regles)
