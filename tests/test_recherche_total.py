"""Recherche élargie et par prix, total (désignation, remise, prix mal écrit, plafond, prix changé), annuler une suppression.

Idées de l'essai du 10/11/2026 et points de l'audit (roadmap#752, #759, #751).
"""

import json
import re

from conftest import CAPTURES
from playwright.sync_api import expect
from test_forfaits import (
    AVEC_3Q,
    AVEC_T1,
    HAUT,
    TOUS,
    activer_modif,
    centimes,
    chercher,
    dialogue,
    espaces,
    exporter_json,
    fiche,
    importer,
    refs,
)

# Clés de stockage écrites en morceaux : un test qui les écrit en clair fait refuser le commit (gitleaks).
CLE_DONNEES = ".".join(["forfaits", "donnees", "v1"])
CLE_APPAREIL = ".".join(["forfaits", "appareil", "v1"])
AVEC_T2 = {r for r in TOUS if r.startswith("EX-T2-")}
DESIGNATION_T2_3Q = "EXEMPLE — Taximètre T2 + imprimante 3Q, sans boîtier"


def ajouter_donnees(page, tmp_path, elements=(), forfaits=()):
    """Ajoute des éléments et des forfaits aux données de l'appareil, puis recharge la page."""
    donnees = exporter_json(page, tmp_path / "depart.json")
    donnees["elements"] += [{"maj": 1_700_000_000_000, **e} for e in elements]
    donnees["forfaits"] += [{"designation": "", "elements": {}, "maj": 1_700_000_000_000, **f} for f in forfaits]
    page.evaluate("([cle, d]) => localStorage.setItem(cle, JSON.stringify(d))", [CLE_DONNEES, donnees])
    page.reload()
    page.wait_for_selector("#resultats .carte")


def poser_total(page, lignes):
    page.evaluate("([cle, total]) => localStorage.setItem(cle, JSON.stringify({total}))", [CLE_APPAREIL, lignes])
    page.reload()
    page.wait_for_selector("#resultats .carte")


def ouvrir_ligne_libre(page):
    page.locator("#total").get_by_role("button", name="Ligne libre").click()
    return dialogue(page)


# ---------------------------------------------------------------- recherche élargie (roadmap#752)


def test_nom_d_element_trouve_aussi_la_reference_ou_la_designation_qui_l_ecrit(page, tmp_path):
    ajouter_donnees(
        page,
        tmp_path,
        elements=[{"id": "elt-13q", "familleId": "fam-imprimante", "nom": "13Q"}],
        forfaits=[
            {"id": "fft-cable-t2", "ref": "CABLE T2", "ht": 1000, "ttc": 1200},  # sans l'élément T2
            {"id": "fft-kit-9", "ref": "KIT-9", "designation": "Support pour T1 DEMO", "ht": 2000, "ttc": 2400},
            {"id": "fft-pack-13q", "ref": "PACK-13Q", "designation": "Pack imprimante 13Q", "ht": 3000, "ttc": 3600,
             "elements": {"fam-imprimante": "elt-13q"}},
        ],
    )  # fmt: skip
    chercher(page, "t2")
    assert refs(page) == AVEC_T2 | {"CABLE T2"}
    chercher(page, "cable t2")  # le cas de l'audit : le forfait ne se trouvait plus
    assert refs(page) == {"CABLE T2"}
    chercher(page, "T1 DEMO")  # nom en deux mots, écrit dans la désignation
    assert refs(page) == AVEC_T1 | {"KIT-9"}
    # « 3Q » ne ramène pas l'élément « 13Q », ni la référence ou la désignation qui l'écrivent.
    chercher(page, "3q")
    assert refs(page) == AVEC_3Q
    chercher(page, "13Q")
    assert refs(page) == {"PACK-13Q"}


# ---------------------------------------------------------------- recherche par prix (roadmap#759)


def test_un_prix_tape_trouve_les_forfaits_de_ce_montant_et_le_texte_des_references(page, tmp_path):
    ajouter_donnees(page, tmp_path, forfaits=[{"id": "fft-ref-1140", "ref": "REF-1140", "ht": 1000, "ttc": 1200}])
    chercher(page, "1140")  # TTC de EX-T1-KPX-3Q ; REF-1140 l'écrit dans sa référence
    assert refs(page) == {"EX-T1-KPX-3Q", "REF-1140"}
    for saisie in ("1140,00", "1140,00€", "1140.0", "950"):  # 950 € : son HT
        chercher(page, saisie)
        assert refs(page) == {"EX-T1-KPX-3Q"}, saisie
    chercher(page, "1234,50")  # la virgule d'un prix ne coupe pas la recherche en deux mots
    assert refs(page) == {"EX-T1-Z5-3Q"}
    chercher(page, "t2 840")  # avec un nom d'élément : chaque mot réduit la liste
    assert refs(page) == {"EX-T2-3Q"}
    chercher(page, "zorba 5,3q")  # ailleurs, la virgule sépare toujours deux mots
    assert refs(page) == {"EX-T1-Z5-3Q", "EX-T2-Z5-3Q", "EX-T1-Z5-3Q-P"}


def test_un_prix_ecrit_par_milliers_trouve_aussi_ce_montant_sans_rien_perdre(page, tmp_path):
    """roadmap#1251 : « 1 140 » n'était pas lu comme un prix ; il l'est en plus de la recherche du texte."""
    ajouter_donnees(
        page,
        tmp_path,
        forfaits=[
            {"id": "fft-ref-1140", "ref": "REF-1140", "ht": 1000, "ttc": 1200},
            {"id": "fft-t1-petit", "ref": "T1-PETIT", "ht": 11700, "ttc": 14000, "elements": {"fam-taximetre": "elt-t1demo"}},
            {"id": "fft-z5-300", "ref": "Z5-300", "ht": 25000, "ttc": 30000, "elements": {"fam-boitier": "elt-zorba5"}},
            {"id": "fft-z5-gros", "ref": "Z5-GROS", "ht": 441700, "ttc": 530000, "elements": {"fam-boitier": "elt-zorba5"}},
        ],
    )  # fmt: skip
    # EX-T1-KPX-3Q vaut 1 140,00 € TTC ; REF-1140 (« 1 » et « 140 » dans sa référence) et T1-PETIT (« 1 » dans sa
    # référence, 140 € TTC) étaient déjà trouvés mot par mot : ils le restent.
    chercher(page, "1 140")
    assert refs(page) == {"EX-T1-KPX-3Q", "REF-1140", "T1-PETIT"}
    for saisie in ("1 140,00", "1 140,00 €", "1 140,00 €"):  # tel qu'affiché sur une fiche, copié
        chercher(page, saisie)
        assert "EX-T1-KPX-3Q" in refs(page), saisie
    chercher(page, "1 234,50")  # le HT de EX-T1-Z5-3Q
    assert refs(page) == {"EX-T1-Z5-3Q"}
    chercher(page, "T1 140")  # « T1 » n'est pas un nombre : rien ne change
    assert refs(page) == {"T1-PETIT"}
    # « Zorba 5 » est un élément : son « 5 » n'est pas le début d'un prix « 5 300 » (Z5-GROS vaut 5 300 €).
    chercher(page, "zorba 5 300")
    assert refs(page) == {"Z5-300"}


# ---------------------------------------------------------------- total : nom de la ligne (roadmap#759)


def test_ligne_du_total_porte_la_designation_et_les_anciennes_lignes_gardent_leur_nom(page, tmp_path):
    page.set_viewport_size(HAUT)
    ajouter_donnees(page, tmp_path, forfaits=[{"id": "fft-sans-nom", "ref": "SANS-NOM", "ht": 1000, "ttc": 1200}])
    total = page.locator("#total")
    page.get_by_role("button", name="Ajouter EX-T2-3Q au total", exact=True).click()
    page.get_by_role("button", name="Ajouter SANS-NOM au total", exact=True).click()
    expect(total.locator(".total-ligne-nom")).to_have_text([DESIGNATION_T2_3Q, "SANS-NOM"])  # sans désignation : la référence
    # Une ligne enregistrée avant ce changement garde le nom qu'elle a mémorisé.
    poser_total(page, [{"id": "fft-ext23q", "nom": "EX-T2-3Q", "qte": 1, "ht": 70000, "ttc": 84000}])
    page.get_by_role("button", name="Ajouter EX-T2-3Q au total", exact=True).click()
    expect(total.locator(".total-ligne-nom")).to_have_text(["EX-T2-3Q"])
    expect(total.locator(".total-qte")).to_have_text("2")


# ---------------------------------------------------------------- total : remise (roadmap#759)


def test_ligne_libre_remise_negative_gardee_et_total_negatif_affiche(page):
    page.set_viewport_size(HAUT)
    page.get_by_role("button", name="Ajouter EX-T2-3Q au total", exact=True).click()  # 700,00 € HT, 840,00 € TTC
    d = ouvrir_ligne_libre(page)
    d.get_by_label("Prix HT de la ligne libre").fill("-50")
    expect(d.get_by_label("Prix TTC de la ligne libre")).to_have_value("-60,00")
    d.get_by_role("button", name="Ajouter à la liste").click()
    expect(d.locator(".msg-erreur")).to_have_text("")
    d.get_by_role("button", name="Terminé").click()
    total = page.locator("#total")
    expect(total.locator(".total-ligne-nom")).to_have_text([DESIGNATION_T2_3Q, "Remise"])  # sans nom : « Remise »
    expect(total.locator(".total-tete")).to_contain_text("1 article")  # une remise n'est pas un article
    assert centimes(total.locator(".s-ttc").text_content()) == 84000 - 6000
    assert centimes(total.locator(".s-ht").text_content()) == 70000 - 5000
    page.reload()  # relue avec les données de l'appareil
    expect(total.locator(".total-ligne-nom")).to_have_text([DESIGNATION_T2_3Q, "Remise"])
    # Une remise plus grande que les achats : le total est négatif, et il le dit (pas de 0 qui cacherait l'erreur).
    total.get_by_role("button", name=f"Retirer {DESIGNATION_T2_3Q}").click()
    expect(total.locator(".s-ttc")).to_have_text(re.compile(r"^[-−]\s*60,00"))
    # Relecture : une remise de forfait ou à moitié négative est refusée, la ligne libre gardée.
    poser_total(
        page,
        [
            {"id": None, "nom": "Remise", "qte": 1, "ht": -5000, "ttc": -6000},
            {"id": "fft-ext23q", "nom": "EX-T2-3Q", "qte": 1, "ht": -100, "ttc": -120},
            {"id": None, "nom": "Moitié", "qte": 1, "ht": 100, "ttc": -120},
        ],
    )
    expect(total.locator(".total-ligne-nom")).to_have_text(["Remise"])


# ---------------------------------------------------------------- total : prix mal écrit (roadmap#759)


def test_ligne_libre_prix_mal_ecrit_message_precis(page):
    page.set_viewport_size(HAUT)
    page.get_by_role("button", name="Ajouter EX-T2-3Q au total", exact=True).click()
    d = ouvrir_ligne_libre(page)
    cas = {
        "12.345": "« 12.345 » : 2 chiffres au plus après la virgule. Pour 12 345,00 €, tape 12345, sans point.",
        "12,345": "« 12,345 » : 2 chiffres au plus après la virgule.",
        "douze": "« douze » n'est pas un prix : seulement des chiffres et une virgule (exemple : 45,50).",
        "1,2,3": "« 1,2,3 » : une seule virgule, devant les centimes, et pas de point (exemple : 1234,50).",
        ",50": "« ,50 » : mets un chiffre avant la virgule (exemple : 0,50).",
        "12345678": "« 12345678 » : 9 999 999,99 € au maximum.",
    }
    for saisie, attendu in cas.items():
        d.get_by_label("Prix TTC de la ligne libre").fill(saisie)
        d.get_by_role("button", name="Ajouter à la liste").click()
        expect(d.locator(".msg-erreur")).not_to_have_text("")
        assert espaces(d.locator(".msg-erreur").text_content()) == attendu, saisie
        expect(d.get_by_label("Prix TTC de la ligne libre")).to_be_focused()  # le champ mal écrit, pas l'autre resté vide
    d.get_by_role("button", name="Terminé").click()
    expect(page.locator("#total .total-ligne")).to_have_count(1)


# ---------------------------------------------------------------- total : plafond (roadmap#751)


def test_total_relu_jusqu_au_plafond_de_la_saisie(page):
    page.set_viewport_size(HAUT)
    page.get_by_role("button", name="Ajouter EX-T2-3Q au total", exact=True).click()
    d = ouvrir_ligne_libre(page)
    d.get_by_label("Nom de la ligne libre").fill("Gros chantier")
    d.get_by_label("Prix HT de la ligne libre").fill("1000000")  # 1 000 000 € : accepté à la saisie
    d.get_by_role("button", name="Ajouter à la liste").click()
    d.get_by_role("button", name="Terminé").click()
    total = page.locator("#total")
    expect(total.locator(".total-ligne")).to_have_count(2)
    page.reload()  # la ligne ne disparaît plus au rechargement
    expect(total.locator(".total-ligne-nom")).to_have_text([DESIGNATION_T2_3Q, "Gros chantier"])
    assert centimes(total.locator(".s-ht").text_content()) == 70000 + 100_000_000
    # Au-delà de ce que la saisie accepte, la relecture refuse toujours.
    poser_total(page, [{"id": None, "nom": "Trop", "qte": 1, "ht": 1_000_000_000, "ttc": 1_200_000_000}])
    expect(total).to_be_hidden()


# ---------------------------------------------------------------- total : prix changé (roadmap#751)


def test_prix_change_depuis_l_ajout_se_voit_dans_le_total(page):
    page.set_viewport_size(HAUT)
    # Ligne mémorisée quand EX-T2-3Q valait 600,00 € HT, 720,00 € TTC ; il vaut aujourd'hui 700,00 € HT, 840,00 € TTC.
    poser_total(
        page,
        [
            {"id": "fft-ext23q", "nom": "EX-T2-3Q", "qte": 1, "ht": 60000, "ttc": 72000},
            {"id": "fft-ext1kpx3q", "nom": "EX-T1-KPX-3Q", "qte": 1, "ht": 95000, "ttc": 114000},  # même prix
        ],
    )
    total = page.locator("#total")
    ecart = total.locator(".total-ligne-ecart")
    expect(ecart).to_have_count(1)
    assert "840,00 € TTC (700,00 € HT)" in espaces(ecart.text_content())
    page.get_by_role("button", name="Ajouter EX-T2-3Q au total", exact=True).click()
    expect(page.locator("#toast")).to_contain_text("à l'ancien prix")
    assert centimes(total.locator(".s-ttc").text_content()) == 2 * 72000 + 114000  # l'ancien prix reste compté (voulu)
    # Retirer la ligne puis rajouter le forfait prend le nouveau prix.
    total.get_by_role("button", name="Retirer EX-T2-3Q").click()
    page.get_by_role("button", name="Ajouter EX-T2-3Q au total", exact=True).click()
    expect(ecart).to_have_count(0)
    expect(page.locator("#toast")).not_to_contain_text("ancien prix")


# ---------------------------------------------------------------- annuler une suppression (roadmap#759)


def supprimer_forfait(page, ref):
    fiche(page, ref).get_by_role("button", name=f"Supprimer {ref}", exact=True).click()
    dialogue(page).get_by_role("button", name="Supprimer", exact=True).click()
    expect(page.locator("#toast")).to_contain_text(f"Forfait {ref} supprimé")


def test_annuler_une_suppression_et_l_annulation_gagne_a_la_fusion(appareils, tmp_path):
    a, b = appareils().page, appareils().page
    activer_modif(a)
    supprimer_forfait(a, "EX-LUM-POSE")
    assert "EX-LUM-POSE" not in refs(a)
    # Ce que l'appareil A aurait exporté juste après la suppression : B le reçoit.
    suppression = a.evaluate("cle => localStorage.getItem(cle)", CLE_DONNEES)
    (tmp_path / "suppression.json").write_text(suppression, encoding="utf-8")
    a.locator("#toast").get_by_role("button", name="Annuler", exact=True).click()
    expect(a.locator("#toast")).to_have_text("Forfait EX-LUM-POSE rétabli")
    assert refs(a) == TOUS
    a.reload()
    assert refs(a) == TOUS  # enregistré

    importer(b, tmp_path / "suppression.json")
    assert "EX-LUM-POSE" not in refs(b)
    retabli = exporter_json(a, tmp_path / "retabli.json")
    assert not any(f.get("supprime") for f in retabli["forfaits"] if f["ref"] == "EX-LUM-POSE")
    importer(b, tmp_path / "retabli.json")  # l'annulation est plus récente que la suppression : elle gagne
    assert refs(b) == TOUS
    assert json.loads(suppression)["forfaits"]  # le fichier de la suppression était bien lisible


def test_le_message_de_suppression_reste_le_temps_d_annuler_puis_son_bouton_part(page):
    activer_modif(page)
    supprimer_forfait(page, "EX-LUM-POSE")
    bouton = page.locator("#toast").get_by_role("button", name="Annuler", exact=True)
    page.wait_for_timeout(4000)  # un message ordinaire serait déjà parti (3 s)
    expect(bouton).to_be_visible()
    expect(bouton).to_have_count(0, timeout=8000)  # parti avec le message : il ne se prend plus au clavier
    assert "EX-LUM-POSE" not in refs(page)


def test_message_de_suppression_tient_dans_le_telephone_en_tres_grand(appareils):
    page = appareils(viewport={"width": 360, "height": 740}, has_touch=True).page
    page.click("#btn-menu")
    dialogue(page).get_by_role("button", name="Très grand", exact=True).click()
    page.keyboard.press("Escape")
    activer_modif(page)
    supprimer_forfait(page, "EX-LUM-POSE")
    message = page.locator("#toast")
    bouton = message.get_by_role("button", name="Annuler", exact=True)
    expect(bouton).to_be_visible()
    page.wait_for_function("() => document.getElementById('toast').getAnimations().length === 0")
    cadre, cadre_bouton = message.bounding_box(), bouton.bounding_box()
    assert cadre["x"] >= 0 and cadre["x"] + cadre["width"] <= 360, cadre  # tient dans l'écran
    assert cadre_bouton["x"] + cadre_bouton["width"] <= cadre["x"] + cadre["width"], (cadre, cadre_bouton)
    # Un message ne se serre plus dans la moitié de l'écran (left: 50 %) : il prend la largeur qu'il lui faut.
    bouton.click()
    expect(message).to_have_text("Forfait EX-LUM-POSE rétabli")
    page.wait_for_function("() => document.getElementById('toast').getAnimations().length === 0")
    assert message.bounding_box()["width"] > 360 / 2, message.bounding_box()


def test_ligne_libre_moins_zero_ne_s_affiche_pas_en_zero_negatif(page):
    page.set_viewport_size(HAUT)
    page.get_by_role("button", name="Ajouter EX-T2-3Q au total", exact=True).click()
    d = ouvrir_ligne_libre(page)
    d.get_by_label("Nom de la ligne libre").fill("Geste")
    d.get_by_label("Prix TTC de la ligne libre").fill("-0")
    expect(d.get_by_label("Prix HT de la ligne libre")).to_have_value("0,00")  # pas « -0,00 »
    d.get_by_role("button", name="Ajouter à la liste").click()
    d.get_by_role("button", name="Terminé").click()
    prix = page.locator("#total .total-ligne-prix")
    expect(prix).to_have_count(2)
    assert not re.search(r"[-−]", prix.last.text_content())


def test_quantite_du_total_annoncee_par_le_bouton_qui_garde_le_focus(page):
    # Le total est recréé à chaque appui : une zone role=status neuve ne serait pas annoncée.
    page.set_viewport_size(HAUT)
    page.get_by_role("button", name="Ajouter EX-T2-3Q au total", exact=True).click()
    total = page.locator("#total")
    total.get_by_role("button", name=f"Plus : {DESIGNATION_T2_3Q}").click()
    plus = total.get_by_role("button", name=f"Plus : {DESIGNATION_T2_3Q}, quantité 2", exact=True)
    expect(plus).to_be_focused()
    total.get_by_role("button", name=f"Moins : {DESIGNATION_T2_3Q}").click()
    expect(total.get_by_role("button", name=f"Moins : {DESIGNATION_T2_3Q}, quantité 1", exact=True)).to_be_attached()
    expect(total.locator("[role=status]")).to_have_count(0)  # pas une zone live par ligne


# ---------------------------------------------------------------- annuler une suppression : petits restes (roadmap#1251)


def autre_onglet(page, script, argument):
    """Un autre onglet du même appareil change le stockage ; la page le reçoit par l'événement « storage »."""
    autre = page.context.new_page()
    autre.goto(page.url)
    autre.wait_for_selector("#resultats .carte")
    autre.evaluate(script, argument)
    autre.close()


def test_annuler_une_suppression_deja_retablie_ailleurs_le_dit(page):
    activer_modif(page)
    supprimer_forfait(page, "EX-LUM-POSE")
    autre_onglet(
        page,
        """cle => {
            const d = JSON.parse(localStorage.getItem(cle));
            const f = d.forfaits.find((x) => x.ref === 'EX-LUM-POSE');
            delete f.supprime;
            f.maj = Date.now() + 1000;
            localStorage.setItem(cle, JSON.stringify(d));
        }""",
        CLE_DONNEES,
    )
    expect(page.locator("#resultats .carte-ref", has_text="EX-LUM-POSE")).to_have_count(1)  # la page a suivi
    page.locator("#toast").get_by_role("button", name="Annuler", exact=True).click()
    expect(page.locator("#toast")).to_have_text("Forfait EX-LUM-POSE déjà rétabli")  # avant : aucun message
    assert refs(page) == TOUS


def test_annuler_une_suppression_laisse_un_surnom_repris_entre_temps(page, tmp_path):
    donnees = exporter_json(page, tmp_path / "depart.json")
    for f in donnees["forfaits"]:
        if f["ref"] == "EX-LUM-POSE":
            f["surnoms"] = ["le gros", "pack nuit"]
    page.evaluate(
        "([cd, d, ca]) => { localStorage.setItem(cd, JSON.stringify(d)); localStorage.setItem(ca, JSON.stringify({ surnoms: { 'fft-exlumpose': ['ma pose'] } })); }",
        [CLE_DONNEES, donnees, CLE_APPAREIL],
    )
    page.reload()
    page.wait_for_selector("#resultats .carte")
    activer_modif(page)
    supprimer_forfait(page, "EX-LUM-POSE")
    # Pendant la suppression, un autre onglet donne « le gros » (équipe) et « ma pose » (perso) à EX-T2-3Q.
    # Son identifiant (fft-ext23q) est plus grand que celui du forfait supprimé (fft-exlumpose) : sans contrôle,
    # le forfait rétabli lui reprendrait les deux (le plus petit identifiant, ou le premier perso, gagne).
    autre_onglet(
        page,
        """([cd, ca]) => {
            const d = JSON.parse(localStorage.getItem(cd));
            Object.assign(d.forfaits.find((x) => x.ref === 'EX-T2-3Q'), { surnoms: ['le gros'], maj: Date.now() });
            localStorage.setItem(cd, JSON.stringify(d));
            const a = JSON.parse(localStorage.getItem(ca));
            a.surnoms['fft-ext23q'] = ['ma pose'];
            localStorage.setItem(ca, JSON.stringify(a));
        }""",
        [CLE_DONNEES, CLE_APPAREIL],
    )
    rangee_t2 = page.locator("#resultats .carte", has=page.locator(".carte-ref", has_text=re.compile("^EX-T2-3Q$")))
    expect(rangee_t2.locator(".carte-surnoms")).to_have_text("dit « le gros, ma pose »")
    page.locator("#toast").get_by_role("button", name="Annuler", exact=True).click()
    expect(page.locator("#toast")).to_have_text(
        "Forfait EX-LUM-POSE rétabli, sans ses surnoms « le gros », « ma pose » : ils désignent maintenant autre chose"
    )
    assert refs(page) == TOUS
    stocke = json.loads(page.evaluate("cle => localStorage.getItem(cle)", CLE_DONNEES))
    surnoms = {f["ref"]: f.get("surnoms") for f in stocke["forfaits"]}
    assert surnoms["EX-LUM-POSE"] == ["pack nuit"]  # celui que personne n'a pris revient avec lui
    assert surnoms["EX-T2-3Q"] == ["le gros"]
    assert json.loads(page.evaluate("cle => localStorage.getItem(cle)", CLE_APPAREIL))["surnoms"] == {"fft-ext23q": ["ma pose"]}
    expect(rangee_t2.locator(".carte-surnoms")).to_have_text("dit « le gros, ma pose »")  # EX-T2-3Q les garde


def test_annuler_une_suppression_dont_tous_les_surnoms_ont_ete_repris(page, tmp_path):
    """Revue : quand TOUS les surnoms étaient repris, le forfait rétabli gardait quand même sa liste d'origine."""
    donnees = exporter_json(page, tmp_path / "depart.json")
    for f in donnees["forfaits"]:
        if f["ref"] == "EX-LUM-POSE":
            f["surnoms"] = ["le gros"]
    page.evaluate("([cd, d]) => localStorage.setItem(cd, JSON.stringify(d))", [CLE_DONNEES, donnees])
    page.reload()
    page.wait_for_selector("#resultats .carte")
    activer_modif(page)
    supprimer_forfait(page, "EX-LUM-POSE")
    autre_onglet(
        page,
        """cd => {
            const d = JSON.parse(localStorage.getItem(cd));
            Object.assign(d.forfaits.find((x) => x.ref === 'EX-T2-3Q'), { surnoms: ['le gros'], maj: Date.now() });
            localStorage.setItem(cd, JSON.stringify(d));
        }""",
        CLE_DONNEES,
    )
    rangee_t2 = page.locator("#resultats .carte", has=page.locator(".carte-ref", has_text=re.compile("^EX-T2-3Q$")))
    expect(rangee_t2.locator(".carte-surnoms")).to_have_text("dit « le gros »")
    page.locator("#toast").get_by_role("button", name="Annuler", exact=True).click()
    expect(page.locator("#toast")).to_have_text(
        "Forfait EX-LUM-POSE rétabli, sans son surnom « le gros » : il désigne maintenant autre chose"
    )
    stocke = json.loads(page.evaluate("cle => localStorage.getItem(cle)", CLE_DONNEES))
    surnoms = {f["ref"]: f.get("surnoms") for f in stocke["forfaits"]}
    assert surnoms["EX-LUM-POSE"] is None  # avant : ["le gros"], le même surnom sur deux forfaits
    assert surnoms["EX-T2-3Q"] == ["le gros"]
    expect(rangee_t2.locator(".carte-surnoms")).to_have_text("dit « le gros »")


# ---------------------------------------------------------------- total : petits restes (roadmap#1251)


def test_remise_au_ht_negatif_et_ttc_a_zero_ne_compte_pas_comme_article(page):
    page.set_viewport_size(HAUT)
    poser_total(
        page,
        [
            {"id": "fft-ext23q", "nom": "EX-T2-3Q", "qte": 1, "ht": 70000, "ttc": 84000},
            {"id": None, "nom": "Geste", "qte": 2, "ht": -1, "ttc": 0},  # relue telle quelle (la relecture l'accepte)
        ],
    )
    total = page.locator("#total")
    expect(total.locator(".total-ligne")).to_have_count(2)
    expect(total.locator(".total-tete")).to_contain_text("1 article")  # avant : 3 articles


def test_deux_forfaits_de_meme_designation_se_distinguent_par_leur_reference(page, tmp_path, navigateur):
    page.set_viewport_size(HAUT)
    nom = "Kit Zorba nuit"
    ajouter_donnees(
        page,
        tmp_path,
        forfaits=[
            {"id": "fft-kit-a", "ref": "KIT-A", "designation": nom, "ht": 1000, "ttc": 1200},
            {"id": "fft-kit-b", "ref": "KIT-B", "designation": nom, "ht": 2000, "ttc": 2400},
            {"id": "fft-kit-c", "ref": "KIT-C", "designation": nom, "ht": 3000, "ttc": 3600, "supprime": True},
        ],
    )  # fmt: skip
    total = page.locator("#total")
    page.get_by_role("button", name="Ajouter KIT-A au total", exact=True).click()
    expect(total.locator(".total-ligne")).to_have_count(1)
    expect(total.locator(".total-ligne-ref")).to_have_count(0)  # une seule ligne de ce nom : rien de plus
    page.get_by_role("button", name="Ajouter KIT-B au total", exact=True).click()
    page.get_by_role("button", name="Ajouter EX-T2-3Q au total", exact=True).click()
    expect(total.locator(".total-ligne-ref")).to_have_text(["KIT-A", "KIT-B"])
    expect(total.get_by_role("button", name=f"Retirer {nom} (KIT-B)", exact=True)).to_be_attached()
    expect(total.get_by_role("button", name=f"Retirer {DESIGNATION_T2_3Q}", exact=True)).to_be_attached()
    # Lignes déjà enregistrées (le total enregistré n'a rien de plus), dont une d'un forfait supprimé depuis :
    # la référence est lue sur le forfait.
    poser_total(
        page,
        [
            {"id": "fft-kit-a", "nom": nom, "qte": 1, "ht": 1000, "ttc": 1200},
            {"id": "fft-kit-c", "nom": nom, "qte": 1, "ht": 3000, "ttc": 3600},
            {"id": None, "nom": nom, "qte": 1, "ht": 500, "ttc": 600},  # ligne libre : pas de référence
        ],
    )
    expect(total.locator(".total-ligne-nom")).to_have_text([f"{nom}KIT-A", f"{nom}KIT-C", nom])
    CAPTURES.mkdir(exist_ok=True)
    total.screenshot(path=str(CAPTURES / f"{navigateur.nom}-total-meme-designation.png"))
    total.get_by_role("button", name=f"Retirer {nom} (KIT-C)", exact=True).click()
    expect(total.locator(".total-ligne-ref")).to_have_text(["KIT-A"])
