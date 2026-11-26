"""Liste limitée : les premières rangées, puis « Afficher plus » (roadmap#1252).

Rendre une carte par forfait prenait 13 s à l'ouverture et 1 à 7 s par lettre avec 5 000 forfaits (outils/mesure_liste.py).
"""

import re

from conftest import CAPTURES, RACINE
from playwright.sync_api import expect
from test_forfaits import HAUT, dialogue, fiche, menu, ouvrir_filtre
from test_recherche_total import CLE_DONNEES, ajouter_donnees, autre_onglet

LIGNES = int(re.search(r"const LIGNES_LISTE = (\d+);", (RACINE / "index.html").read_text(encoding="utf-8")).group(1))
NB_LOTS = 250
TOTAL = NB_LOTS + 11  # plus les 11 exemples de départ
LE_MOINS_CHER = f"LOT-{NB_LOTS - 1:03d}"  # dernier dans l'ordre des références, premier par prix


def lots(page, tmp_path):
    """250 forfaits de plus, tous avec le boîtier Zorba 5 ; le dernier par référence est le moins cher."""
    assert LIGNES < TOTAL < 3 * LIGNES, "les tests supposent 2 à 3 « Afficher plus »"
    ajouter_donnees(
        page,
        tmp_path,
        forfaits=[
            {"id": f"fft-lot-{i:03d}", "ref": f"LOT-{i:03d}", "ht": 100 if i == NB_LOTS - 1 else 50000 + i * 100,
             "ttc": 120 if i == NB_LOTS - 1 else 60000 + i * 120, "elements": {"fam-boitier": "elt-zorba5"}}
            for i in range(NB_LOTS)
        ],
    )  # fmt: skip


def rangees(page):
    return page.locator("#resultats .carte")


def plus(page):
    return page.locator("#btn-afficher-plus")


def ref_en_focus(page):
    return page.evaluate("() => document.activeElement.closest('.carte')?.querySelector('.carte-ref').textContent")


def test_longue_liste_rend_les_premieres_rangees_puis_afficher_plus_au_clavier(page, tmp_path):
    lots(page, tmp_path)
    expect(rangees(page)).to_have_count(LIGNES)
    expect(page.locator("#compte")).to_have_text(f"{TOTAL} forfaits")  # le compteur dit tout ce qui est trouvé
    expect(page.locator(".plus-liste p")).to_have_text(f"{LIGNES} affichés sur {TOTAL}")
    expect(plus(page)).to_have_text(f"Afficher {LIGNES} de plus")
    # Au clavier : la première rangée ajoutée prend le focus, là où était le bouton.
    plus(page).focus()
    page.keyboard.press("Enter")
    expect(rangees(page)).to_have_count(2 * LIGNES)
    assert ref_en_focus(page) == page.locator("#resultats .carte-ref").nth(LIGNES).text_content()
    expect(plus(page)).to_have_text(f"Afficher {TOTAL - 2 * LIGNES} de plus")
    plus(page).click()
    expect(rangees(page)).to_have_count(TOTAL)
    assert ref_en_focus(page) == page.locator("#resultats .carte-ref").nth(2 * LIGNES).text_content()
    expect(plus(page)).to_have_count(0)  # tout est là
    expect(page.locator("#compte")).to_have_text(f"{TOTAL} forfaits")


def test_une_autre_recherche_repart_des_premieres_rangees_un_autre_rendu_les_garde(page, tmp_path):
    lots(page, tmp_path)
    plus(page).click()
    expect(rangees(page)).to_have_count(2 * LIGNES)
    # Même recherche redessinée (favori) : les rangées ajoutées restent.
    fiche(page, "LOT-150").get_by_role("button", name="Favori : LOT-150", exact=True).click()
    expect(page.locator("#resultats .carte-ref").first).to_have_text("LOT-150")
    expect(rangees(page)).to_have_count(2 * LIGNES)
    # Autre recherche, autre tri, recherche effacée : on repart des premières.
    page.fill("#recherche", "lot")
    expect(rangees(page)).to_have_count(LIGNES)
    expect(page.locator("#compte")).to_have_text(f"{NB_LOTS} forfaits sur {TOTAL}")
    plus(page).click()
    expect(rangees(page)).to_have_count(2 * LIGNES)
    page.fill("#recherche", "")
    expect(rangees(page)).to_have_count(LIGNES)
    plus(page).click()
    page.select_option("#tri", label="Prix croissant")
    expect(rangees(page)).to_have_count(LIGNES)


def test_filtres_et_tri_portent_sur_tous_les_forfaits_pas_sur_les_rangees_rendues(page, tmp_path):
    lots(page, tmp_path)
    zorba = ouvrir_filtre(page, "Boîtier").locator(".choix", has_text="Zorba 5")
    expect(zorba.locator(".nb")).to_have_text(str(NB_LOTS + 4))  # 4 exemples ont aussi Zorba 5
    zorba.click()
    expect(page.locator("#compte")).to_have_text(f"{NB_LOTS + 4} forfaits sur {TOTAL}")
    expect(rangees(page)).to_have_count(LIGNES)
    # Le moins cher est le dernier par référence, loin derrière les rangées rendues : le tri le met en tête.
    page.select_option("#tri", label="Prix croissant")
    expect(page.locator("#resultats .carte-ref").first).to_have_text(LE_MOINS_CHER)
    expect(rangees(page)).to_have_count(LIGNES)


def test_forfait_choisi_hors_des_rangees_rendues_garde_sa_fiche_et_revient_par_recents(page, tmp_path):
    page.set_viewport_size(HAUT)
    lots(page, tmp_path)
    plus(page).click()
    plus(page).click()
    fiche(page, LE_MOINS_CHER)  # consulté
    page.reload()
    page.wait_for_selector("#resultats .carte")
    expect(rangees(page)).to_have_count(LIGNES)
    expect(page.locator("#resultats .carte-ref", has_text=LE_MOINS_CHER)).to_have_count(0)  # pas rendu
    page.locator("#btn-recents").click()
    menu(page).locator(".recent", has_text=LE_MOINS_CHER).click()
    expect(page.locator("#fiche .fiche-ref")).to_have_text(LE_MOINS_CHER)
    expect(page.locator("#resultats .carte.choisie")).to_have_count(0)  # la liste ne bouge pas
    # La liste est redessinée (un autre onglet change un autre forfait) : il reste choisi, sa fiche aussi.
    autre_onglet(
        page,
        """cle => {
            const d = JSON.parse(localStorage.getItem(cle));
            Object.assign(d.forfaits.find((x) => x.ref === 'LOT-001'), { designation: 'Changé ailleurs', maj: Date.now() });
            localStorage.setItem(cle, JSON.stringify(d));
        }""",
        CLE_DONNEES,
    )
    expect(page.locator("#resultats .carte-designation", has_text="Changé ailleurs")).to_have_count(1)
    expect(page.locator("#fiche .fiche-ref")).to_have_text(LE_MOINS_CHER)
    expect(rangees(page)).to_have_count(LIGNES)


def test_afficher_plus_sur_telephone_et_en_grands_caracteres(navigateur, appareils, tmp_path):
    CAPTURES.mkdir(exist_ok=True)
    page = appareils(viewport={"width": 375, "height": 812}).page
    lots(page, tmp_path)
    plus(page).scroll_into_view_if_needed()
    page.wait_for_function("() => document.getAnimations().length === 0")  # rangées arrivées (cascade de l'ouverture)
    page.screenshot(path=str(CAPTURES / f"{navigateur.nom}-liste-afficher-plus-telephone.png"))
    plus(page).click()
    expect(rangees(page)).to_have_count(2 * LIGNES)
    # « Récents » sur téléphone : la fiche s'ouvre en feuille, même pour un forfait pas encore rendu.
    plus(page).click()
    fiche(page, LE_MOINS_CHER).get_by_role("button", name="Fermer").click()
    page.fill("#recherche", "lot")
    page.fill("#recherche", "")
    expect(page.locator("#resultats .carte-ref", has_text=LE_MOINS_CHER)).to_have_count(0)
    page.locator("#btn-recents").click()
    menu(page).locator(".recent", has_text=LE_MOINS_CHER).click()
    expect(page.locator("#dlg-fiche .fiche-ref")).to_have_text(LE_MOINS_CHER)
    page.locator("#dlg-fiche").get_by_role("button", name="Fermer").click()

    page.click("#btn-menu")
    dialogue(page).get_by_role("button", name="Grand", exact=True).click()
    page.keyboard.press("Escape")
    expect(page.locator("dialog[open]")).to_have_count(0)
    plus(page).scroll_into_view_if_needed()
    page.wait_for_function("() => document.getAnimations().length === 0")  # rangées arrivées (cascade de l'ouverture)
    cadre = plus(page).bounding_box()
    assert cadre["x"] >= 0 and cadre["x"] + cadre["width"] <= 375, cadre  # tient dans l'écran
    page.screenshot(path=str(CAPTURES / f"{navigateur.nom}-liste-afficher-plus-grand.png"))
    plus(page).click()
    expect(rangees(page)).to_have_count(2 * LIGNES)


def test_afficher_plus_sur_grand_ecran(navigateur, page, tmp_path):
    page.set_viewport_size(HAUT)
    lots(page, tmp_path)
    plus(page).scroll_into_view_if_needed()
    page.wait_for_function("() => document.getAnimations().length === 0")  # rangées arrivées (cascade de l'ouverture)
    CAPTURES.mkdir(exist_ok=True)
    page.screenshot(path=str(CAPTURES / f"{navigateur.nom}-liste-afficher-plus-pc.png"))
    expect(page.locator("#fiche .fiche-ref")).to_have_text(page.locator("#resultats .carte-ref").first.text_content())
