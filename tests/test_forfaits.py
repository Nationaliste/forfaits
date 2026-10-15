"""Tests de l'outil Forfaits : les cas demandés, puis les pièges repérés en route.

Lancer :  python -m pytest            (Chromium, Edge et Firefox)
          NAVIGATEURS=chromium python -m pytest   (plus rapide)
"""

import base64
import hashlib
import json
import re

import pytest
from conftest import CAPTURES, RACINE, demarrer_serveur
from PIL import Image
from playwright.sync_api import expect

# Références des forfaits d'exemple, par critère
TOUS = {
    "EX-M1-G7-3S",
    "EX-M1-G7-4S",
    "EX-M1-SPX-3S",
    "EX-M1-GTX-4S",
    "EX-F1-G7-3S",
    "EX-F1-SPX-4S",
    "EX-F1-GTX-3S",
    "EX-F1-SPU-4S",
    "EX-F1-3S",
    "EX-LUM-POSE",
    "EX-M1-G7-3S-P",
}
AVEC_3S = {"EX-M1-G7-3S", "EX-M1-SPX-3S", "EX-F1-G7-3S", "EX-F1-GTX-3S", "EX-F1-3S", "EX-M1-G7-3S-P"}
AVEC_M1 = {"EX-M1-G7-3S", "EX-M1-G7-4S", "EX-M1-SPX-3S", "EX-M1-GTX-4S", "EX-M1-G7-3S-P"}
AVEC_F1_ET_3S = {"EX-F1-G7-3S", "EX-F1-GTX-3S", "EX-F1-3S"}
AVEC_GAMMA7 = {"EX-M1-G7-3S", "EX-M1-G7-4S", "EX-F1-G7-3S", "EX-M1-G7-3S-P"}
AVEC_4S = {"EX-M1-G7-4S", "EX-M1-GTX-4S", "EX-F1-SPX-4S", "EX-F1-SPU-4S"}


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


def test_recherche_3S_ne_donne_que_des_forfaits_3S(page):
    chercher(page, "3S")
    assert refs(page) == AVEC_3S
    assert all(c["elements"].get("Imprimante") == "3S" for c in cartes(page))


def test_m1std_donne_les_memes_resultats_que_M1_STD(page):
    resultats = {}
    for saisie in ("M1 STD", "m1std", "M1-STD", "m1 std", "  M1   STD "):
        chercher(page, saisie)
        resultats[saisie] = refs(page)
    assert all(r == AVEC_M1 for r in resultats.values()), resultats


def test_3S_F1_ne_donne_que_les_forfaits_qui_ont_les_deux(page):
    chercher(page, "3S F1")
    assert refs(page) == AVEC_F1_ET_3S
    for c in cartes(page):
        assert c["elements"]["Imprimante"] == "3S" and c["elements"]["Taximètre"] == "F1"
    chercher(page, "f1 3s")  # l'ordre et la casse ne comptent pas
    assert refs(page) == AVEC_F1_ET_3S


def test_reference_complete_ou_morceau(page):
    chercher(page, "EX-F1-SPU-4S")
    assert refs(page) == {"EX-F1-SPU-4S"}
    chercher(page, "spu")
    assert refs(page) == {"EX-F1-SPU-4S"}
    chercher(page, "f1 spu")
    assert refs(page) == {"EX-F1-SPU-4S"}
    chercher(page, "EX-M1-G7-3S")  # la référence exacte passe avant EX-M1-G7-3S-P
    assert page.locator("#resultats .carte-ref").first.text_content() == "EX-M1-G7-3S"


def test_accents_majuscules_espaces_et_tirets_ignores(page):
    for saisie in ("Starplast universelle", "STARPLAST-UNIVERSELLE", "starplastuniverselle", "stârplast Universellé"):
        chercher(page, saisie)
        assert refs(page) == {"EX-F1-SPU-4S"}, saisie
    chercher(page, "boîtier gamma")
    avec_accent = refs(page)
    chercher(page, "BOITIER-GAMMA")
    assert refs(page) == avec_accent == AVEC_GAMMA7 | {"EX-M1-GTX-4S", "EX-F1-GTX-3S"}


def test_rien_trouve_puis_effacer(page):
    chercher(page, "zzzz")
    expect(page.locator("#compte")).to_have_text("Aucun forfait ne correspond")
    page.locator("#resultats").get_by_role("button", name="Effacer la recherche").click()
    assert refs(page) == TOUS
    expect(page.locator("#compte")).to_have_text("11 forfaits")


# ---------------------------------------------------------------- suggestions, étiquettes, boutons


def test_suggestions_gam_puis_etiquette(page):
    chercher(page, "gam")
    suggestions = page.locator("#suggestions .suggestion")
    expect(suggestions).to_have_count(2)
    noms = page.locator("#suggestions .suggestion-nom").all_text_contents()
    familles = page.locator("#suggestions .suggestion-famille").all_text_contents()
    assert noms == ["Gamma 7", "Gammatech X"]
    assert familles == ["Boîtier", "Boîtier"]

    page.locator("#suggestions .suggestion", has_text="Gamma 7").click()
    expect(page.locator("#etiquettes")).to_contain_text("Boîtier : Gamma 7")
    expect(page.locator("#recherche")).to_have_value("")
    assert refs(page) == AVEC_GAMMA7

    chercher(page, "3s")  # le mot tapé s'ajoute à l'étiquette
    assert refs(page) == AVEC_GAMMA7 & AVEC_3S

    page.locator("#etiquettes .etiquette").click()  # un clic retire l'étiquette
    expect(page.locator("#etiquettes")).to_be_hidden()
    assert refs(page) == AVEC_3S


def test_suggestion_au_clavier(page):
    page.click("#recherche")
    page.keyboard.type("starplast u")
    expect(page.locator("#suggestions .suggestion-nom")).to_have_text(["Starplast universelle"])
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator("#etiquettes")).to_contain_text("Boîtier : Starplast universelle")
    assert refs(page) == {"EX-F1-SPU-4S"}


def test_boutons_de_filtre(page):
    page.locator("#filtres .filtre", has_text="Imprimante").click()
    dialogue(page).get_by_role("button", name="4S", exact=True).click()
    assert refs(page) == AVEC_4S
    expect(page.locator("#filtres .filtre", has_text="Imprimante")).to_have_attribute("aria-pressed", "true")

    page.locator("#filtres .filtre", has_text="Imprimante").click()
    dialogue(page).get_by_role("button", name="Tous", exact=True).click()
    page.locator("#filtres .filtre", has_text="Boîtier").click()
    dialogue(page).get_by_role("button", name="Sans boîtier").click()
    assert refs(page) == {"EX-F1-3S", "EX-LUM-POSE"}
    expect(page.locator("#etiquettes")).to_contain_text("Boîtier : sans")


# ---------------------------------------------------------------- affichage et prix


def test_carte_complete_et_prix_au_format_francais(page):
    chercher(page, "EX-M1-G7-3S-P")
    (carte,) = cartes(page)
    assert espaces(carte["ht"]) == "1 150,00 €"
    assert espaces(carte["ttc"]) == "1 380,00 €"
    assert carte["elements"] == {"Taximètre": "M1 STD", "Boîtier": "Gamma 7", "Imprimante": "3S", "Installation": "Pose EXEMPLE"}
    chercher(page, "EX-M1-G7-3S")
    assert espaces(cartes(page)[0]["ttc"]) == "1 481,40 €"
    assert " " not in cartes(page)[0]["ttc"]  # espace visible avec toutes les polices
    assert espaces(cartes(page)[0]["ht"]) == "1 234,50 €"
    expect(page.locator(".badge-exemple").first).to_have_text("EXEMPLE")


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
    if navigateur.nom == "firefox":
        pytest.skip("Firefox ne laisse pas les tests lire le presse-papiers")
    a = appareils()
    a.contexte.grant_permissions(["clipboard-read", "clipboard-write"])
    chercher(a.page, "EX-F1-3S")
    a.page.get_by_role("button", name="Copier la référence").click()
    expect(a.page.locator("#toast")).to_contain_text("EX-F1-3S copiée")
    assert a.page.evaluate("navigator.clipboard.readText()") == "EX-F1-3S"


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
        {"Taximètre": "F1", "Boîtier": "Gammatech X", "Imprimante": "4S"},
        designation="Pack F1 complet",
    )
    expect(page.locator("#toast")).to_contain_text("TX-100 ajouté")
    chercher(page, "tx100")
    (carte,) = cartes(page)
    assert carte["ref"] == "TX-100" and carte["designation"] == "Pack F1 complet"
    assert espaces(carte["ttc"]) == "1 481,40 €"
    assert carte["elements"] == {"Taximètre": "F1", "Boîtier": "Gammatech X", "Imprimante": "4S"}

    modifier(page, "TX-100")
    remplir(page, ht="1 100,00", ttc="1 320,00", elements={"Boîtier": "Starplast universelle", "Imprimante": "3S"})
    (carte,) = cartes(page)
    assert espaces(carte["ht"]) == "1 100,00 €"
    assert carte["elements"] == {"Taximètre": "F1", "Boîtier": "Starplast universelle", "Imprimante": "3S"}
    chercher(page, "3S F1 starplast universelle")
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


def test_doublon_de_reference_bloque(page):
    activer_modif(page)
    for ref in ("EX-F1-3S", "ex-f1-3s"):
        ouvrir_ajout(page)
        remplir(page, ref, "100", "120")
        expect(dialogue(page).locator(".msg-erreur")).to_contain_text("existe déjà")
        dialogue(page).get_by_role("button", name="Annuler").click()
    assert len(refs(page)) == 11


def test_doublon_de_combinaison_averti(page):
    activer_modif(page)
    ouvrir_ajout(page)
    remplir(page, "NOUVEAU-1", "1 100", "1 320", {"Taximètre": "M1 STD", "Boîtier": "Gamma 7", "Imprimante": "4S"})
    avertissement = dialogue(page)
    expect(avertissement).to_contain_text("Même combinaison d'éléments que : EX-M1-G7-4S")
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
    page.locator("#filtres .filtre", has_text="Taximètre").click()  # les vrais éléments restent
    expect(dialogue(page).locator(".choix")).to_have_text(["Tous", "F1", "M1 STD", "Sans taximètre"])


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
    d.get_by_label("Nouvel élément pour Boîtier").fill("Gamma 8")
    d.get_by_label("Nouvel élément pour Boîtier").press("Enter")
    d.get_by_label("Nouvel élément pour Boîtier").fill("gamma-8")  # doublon refusé
    d.get_by_label("Nouvel élément pour Boîtier").press("Enter")
    expect(d.locator(".msg-erreur")).to_contain_text("existe déjà")
    d.get_by_label("Nom de l'élément Gamma 7").fill("Gamma 7 Plus")
    # Clic direct sur un autre bouton juste après le renommage : il ne doit pas être perdu.
    d.get_by_role("button", name="Supprimer 3S").click()  # utilisé : suppression refusée
    expect(dialogue(page)).to_contain_text("Suppression impossible")
    dialogue(page).get_by_role("button", name="Compris").click()
    dialogue(page).get_by_role("button", name="Terminé").click()

    expect(page.locator("#filtres .filtre", has_text="TPE")).to_be_visible()
    chercher(page, "gamma7plus")  # le renommage s'applique aux forfaits existants
    assert refs(page) == AVEC_GAMMA7
    chercher(page, "3S")
    assert refs(page) == AVEC_3S

    ouvrir_ajout(page)
    remplir(page, "TPE-1", "300", "360", {"TPE": "TPE X", "Boîtier": "Gamma 8"})
    chercher(page, "tpe x")
    assert refs(page) == {"TPE-1"}
    chercher(page, "gam")
    expect(page.locator("#suggestions .suggestion-nom")).to_have_text(["Gamma 7 Plus", "Gamma 8", "Gammatech X"])


# ---------------------------------------------------------------- sauvegarde et partage


def test_exporter_puis_importer_donne_les_memes_donnees(appareils, tmp_path):
    a = appareils().page
    activer_modif(a)
    ouvrir_ajout(a)
    remplir(
        a, "VRAI-1", "2 000", "2 400", {"Taximètre": "F1", "Imprimante": "4S"}, designation="Ligne 1\nLigne 2 ; « guillemets »"
    )
    modifier(a, "EX-F1-3S")
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

    modifier(a, "EX-F1-3S")
    remplir(a, ht="800", ttc="960")
    exporter_json(a, tmp_path / "a1.json")

    importer(b, tmp_path / "a1.json")
    chercher(b, "EX-F1-3S")
    assert espaces(cartes(b)[0]["ttc"]) == "960,00 €"
    chercher(b, "EX-LUM-POSE")
    b.get_by_role("button", name="Supprimer", exact=True).click()
    dialogue(b).get_by_role("button", name="Supprimer", exact=True).click()
    expect(b.locator("#resultats .carte")).to_have_count(0)
    ouvrir_ajout(b)
    remplir(b, "B-NOUVEAU", "100", "120")
    exporter_json(b, tmp_path / "b1.json")

    # Pendant ce temps, A modifie un autre forfait sans avoir importé le fichier de B.
    modifier(a, "EX-F1-G7-3S")
    remplir(a, designation="Modifié par A")
    importer(a, tmp_path / "b1.json")
    chercher(a, "")
    resultat = {c["ref"]: c for c in cartes(a)}
    assert "EX-LUM-POSE" not in resultat  # suppression de B propagée
    assert "B-NOUVEAU" in resultat  # ajout de B reçu
    assert resultat["EX-F1-G7-3S"]["designation"] == "Modifié par A"  # modif de A gardée
    assert espaces(resultat["EX-F1-3S"]["ttc"]) == "960,00 €"

    comptoir = appareils().page  # un collègue qui ne fait que consulter
    importer(comptoir, tmp_path / "b1.json")
    assert refs(comptoir) == (TOUS - {"EX-LUM-POSE"}) | {"B-NOUVEAU"}


def test_import_d_un_fichier_plus_ancien_garde_les_versions_recentes(appareils, tmp_path):
    a = appareils().page
    activer_modif(a)
    exporter_json(a, tmp_path / "ancien.json")
    modifier(a, "EX-F1-3S")
    remplir(a, ht="800", ttc="960")
    a.set_input_files("#fichier-import", str(tmp_path / "ancien.json"))
    expect(dialogue(a)).to_contain_text("plus ancien que tes données")
    dialogue(a).get_by_role("button", name="Mettre à jour").click()
    chercher(a, "EX-F1-3S")
    assert espaces(cartes(a)[0]["ttc"]) == "960,00 €"


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
    ligne = next(x for x in lignes if x.startswith("EX-M1-G7-3S;"))
    assert ";1234,50;1481,40;M1 STD;Gamma 7;3S;;;oui;" in ligne


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
    chercher(page, "3S")
    page.locator("#filtres .filtre", has_text="Taximètre").click()
    dialogue(page).get_by_role("button", name="F1", exact=True).click()
    assert refs(page) == AVEC_F1_ET_3S
    page.click("#btn-tout-effacer")  # efface le texte ET les filtres
    expect(page.locator("#recherche")).to_have_value("")
    expect(page.locator("#etiquettes")).to_be_hidden()
    assert refs(page) == TOUS


def test_exemple_modifie_devient_un_vrai_forfait(page):
    activer_modif(page)
    modifier(page, "EX-F1-3S")
    expect(dialogue(page).locator(".note-exemple")).to_contain_text("devient un vrai forfait")
    remplir(page, ref="VRAI-F1-3S", ht="500", ttc="600", designation="Vrai forfait")
    page.click("#btn-suppr-exemples")
    dialogue(page).get_by_role("button", name="Supprimer les exemples").click()
    expect(page.locator("#resultats .carte")).to_have_count(1)
    assert refs(page) == {"VRAI-F1-3S"}
    expect(page.locator(".badge-exemple")).to_have_count(0)


def test_date_absurde_dans_un_fichier_ne_bloque_rien(appareils, tmp_path):
    a = appareils().page
    fichier = exporter_json(a, tmp_path / "base.json")
    for f in fichier["forfaits"]:
        if f["ref"] == "EX-F1-3S":
            f["maj"] = 1e20
            f["ttc"] = 99999
    piege = tmp_path / "piege.json"
    piege.write_text(json.dumps(fichier), encoding="utf-8")
    importer(a, piege)
    chercher(a, "EX-F1-3S")
    assert espaces(cartes(a)[0]["ttc"]) == "999,99 €"
    expect(a.locator("#etat-donnees")).to_contain_text("Données du")
    # La date a été ramenée à demain au plus : une vraie modification plus tard l'emportera encore.
    a.reload()
    a.wait_for_selector("#resultats .carte")
    assert a.evaluate(
        "JSON.parse(localStorage.getItem('forfaits.donnees.v1')).forfaits.every(f => f.maj <= Date.now() + 86400000)"
    )


def test_meme_element_cree_par_deux_responsables_signale(appareils, tmp_path):
    a = appareils().page
    b = appareils().page
    for p in (a, b):
        activer_modif(p)
        p.click("#btn-menu")
        p.click("#btn-listes")
        champ = dialogue(p).get_by_label("Nouvel élément pour Boîtier")
        champ.fill("Gamma 8")
        champ.press("Enter")
        dialogue(p).get_by_role("button", name="Terminé").click()
    exporter_json(b, tmp_path / "b.json")
    a.set_input_files("#fichier-import", str(tmp_path / "b.json"))
    dialogue(a).get_by_role("button", name="Mettre à jour").click()
    expect(dialogue(a)).to_contain_text("Doublons à corriger")
    expect(dialogue(a)).to_contain_text("Boîtier : Gamma 8 (2 fois)")


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
        "#filtres .filtre, .carte-actions .btn, #btn-importer, #btn-menu", "els => els.map(e => e.getBoundingClientRect().height)"
    )
    assert min(hauteurs) >= 44, hauteurs

    page.click("#recherche")
    page.keyboard.type("gam")
    expect(page.locator("#suggestions")).to_be_visible()
    sans_defilement_horizontal()
    page.screenshot(path=f"{prefixe}-2-suggestions.png")
    page.locator("#suggestions .suggestion", has_text="Gamma 7").click()
    page.screenshot(path=f"{prefixe}-3-etiquette.png")

    activer_modif(page)
    ouvrir_ajout(page)
    sans_defilement_horizontal()
    boite = dialogue(page).bounding_box()
    assert boite["width"] <= largeur
    page.screenshot(path=f"{prefixe}-4-formulaire.png")


def test_marche_sans_internet(navigateur):
    if navigateur.nom == "firefox":
        pytest.skip("Le mode hors ligne est testé sur Chromium et Edge (même moteur que Chrome Android)")
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
        chercher(page, "3S")
        assert refs(page) == AVEC_3S
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
        chercher(page, "3S F1")
        assert refs(page) == AVEC_F1_ET_3S
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
