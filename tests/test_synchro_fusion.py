"""Fusion venue du cloud : les mêmes garde-fous que l'import d'un fichier (audit du 10/11/2026, roadmap 750).

Le vrai Worker tourne en local (voir conftest.py). Lancer :
    NAVIGATEURS=chromium python -m pytest tests/test_synchro_fusion.py
"""

import json
import re
import time

from conftest import CODE_SECOURS, RACINE, appel_cloud
from playwright.sync_api import expect
from test_forfaits import activer_modif, dialogue
from test_synchro import (
    ajouter_forfait,
    attendre_envoi,
    attendre_forfait,
    attendre_sans_forfait,
    connecter_avec_lien,
    connecter_premier,
    creer_lien,
    fermer,
    ouvrir_maj,
    sonde,
    verifier_maintenant,
)

# Clés du stockage, écrites en morceaux (gitleaks les prend sinon pour des secrets).
CLE_DONNEES = ".".join(["forfaits", "donnees", "v1"])
CLE_CLOUD = ".".join(["forfaits", "cloud", "v1"])
VERSION_FORMAT = int(re.search(r"const VERSION_FORMAT = (\d+);", (RACINE / "index.html").read_text(encoding="utf-8")).group(1))


def maintenant():
    return int(time.time() * 1000)


def forfait(identifiant, ref, maj=None, **autres):
    return {
        "id": identifiant,
        "ref": ref,
        "designation": "",
        "ht": 10000,
        "ttc": 12000,
        "elements": {},
        "maj": maintenant() - 60000 if maj is None else maj,
        **autres,
    }


def familles(prefixe, n):
    return [
        {"id": f"fam-{prefixe}{i:03d}", "nom": f"Famille {prefixe.upper()}{i}", "ordre": i, "maj": maintenant() - 60000}
        for i in range(n)
    ]


def poser_donnees(page, familles=(), elements=(), forfaits=()):
    """Remplace les données de l'appareil (au lieu des exemples), puis recharge la page."""
    contenu = {
        "format": "forfaits-comptoir",
        "version": VERSION_FORMAT,
        "familles": list(familles),
        "elements": list(elements),
        "forfaits": list(forfaits),
    }
    page.evaluate("([c, v]) => localStorage.setItem(c, v)", [CLE_DONNEES, json.dumps(contenu)])
    page.reload()


def donnees(page):
    return page.evaluate("c => JSON.parse(localStorage.getItem(c))", CLE_DONNEES)


# Chiffre comme la page, avec la clé de l'équipe que garde cet appareil.
CHIFFRER = """async ([cleCloud, contenu]) => {
    const c = JSON.parse(localStorage.getItem(cleCloud));
    const octets = (t) => Uint8Array.from(atob(t.replace(/-/g, '+').replace(/_/g, '/')), (x) => x.charCodeAt(0));
    const cle = await crypto.subtle.importKey('raw', octets(c.cle), 'AES-GCM', false, ['encrypt']);
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const enc = new TextEncoder();
    const chiffre = new Uint8Array(await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv, additionalData: enc.encode('forfaits-comptoir') }, cle, enc.encode(JSON.stringify(contenu))));
    const tout = new Uint8Array(12 + chiffre.length);
    tout.set(iv);
    tout.set(chiffre, 12);
    let texte = '';
    for (const o of tout) texte += String.fromCharCode(o);
    return btoa(texte);
}"""


def envoyer_au_cloud(cloud, blob):
    """Un autre responsable envoie ce paquet chiffré ; renvoie la version du cloud qui en résulte."""
    statut, rep = appel_cloud(cloud, "/api/initialiser", "POST", {"code_secours": CODE_SECOURS, "nom": "Autre responsable"})
    assert statut == 200, rep
    statut, etat = appel_cloud(cloud, "/api/donnees", jeton=rep["jeton"])
    assert statut == 200, etat
    statut, envoi = appel_cloud(
        cloud, "/api/donnees", "PUT", {"version_precedente": etat["version"], "blob": blob}, jeton=rep["jeton"]
    )
    assert statut == 200, envoi
    return envoi["version"]


def test_une_union_trop_grosse_venue_du_cloud_est_refusee(cloud_vide, appareils_maj):
    """Chaque côté passe valider, pas leur union : enregistrée, elle rendait l'appareil illisible au chargement suivant."""
    patron = appareils_maj()
    poser_donnees(patron.page, familles=familles("a", 260))
    connecter_premier(patron.page, cloud_vide)
    version = sonde(cloud_vide)["version"]

    second = appareils_maj()
    poser_donnees(second.page, familles=familles("b", 260))
    avant = donnees(second.page)
    connecter_avec_lien(second.page, creer_lien(patron.page, role="Responsable"))
    d = ouvrir_maj(second.page)
    expect(d.locator("#maj-etat")).to_contain_text("Trop d'enregistrements")
    expect(d.locator("#maj-etat")).to_contain_text("rien n'a changé sur cet appareil")
    fermer(d)
    assert donnees(second.page) == avant
    assert sonde(cloud_vide)["version"] == version  # rien envoyé non plus


def test_un_forfait_qui_perd_son_element_par_le_cloud_est_signale(cloud_vide, appareils_maj):
    """Un responsable supprime un élément pendant qu'un autre crée un forfait avec : le dire, une fois."""
    boitier = {"id": "fam-boitier", "nom": "Boîtier", "ordre": 0, "maj": maintenant() - 60000}
    zorba8 = {"id": "elt-zorba8", "familleId": "fam-boitier", "nom": "Zorba 8", "maj": maintenant() - 60000}
    patron = appareils_maj()
    poser_donnees(patron.page, familles=[boitier], elements=[zorba8], forfaits=[forfait("fft-t1demo", "T1 DEMO")])
    connecter_premier(patron.page, cloud_vide)
    second = appareils_maj()
    connecter_avec_lien(second.page, creer_lien(patron.page, role="Responsable"))
    attendre_forfait(second.page, "T1 DEMO")

    activer_modif(patron.page)
    patron.page.click("#btn-menu")
    patron.page.click("#btn-listes")
    dialogue(patron.page).get_by_role("button", name="Supprimer Zorba 8", exact=True).click()
    dialogue(patron.page).get_by_role("button", name="Supprimer", exact=True).click()
    dialogue(patron.page).get_by_role("button", name="Terminé").click()
    attendre_envoi(patron.page)

    # Pendant ce temps, l'autre responsable a créé KALPO-9 avec Zorba 8 (écrit par un autre onglet de son appareil).
    second.page.evaluate(
        """([cle, kalpo]) => {
            const d = JSON.parse(localStorage.getItem(cle));
            d.forfaits.push(kalpo);
            localStorage.setItem(cle, JSON.stringify(d));
            window.dispatchEvent(new StorageEvent('storage', { key: cle }));
        }""",
        [CLE_DONNEES, forfait("fft-kalpo9", "KALPO-9", maj=maintenant(), elements={"fam-boitier": "elt-zorba8"})],
    )
    ouvrir_maj(second.page).locator("#maj-maintenant").click()
    a_corriger = second.page.locator("dialog[open]", has_text="Forfaits à corriger")
    expect(a_corriger).to_contain_text("Forfait KALPO-9 : Boîtier « Zorba 8 » supprimé", timeout=20000)
    a_corriger.get_by_role("button", name="Compris").click()
    fermer(dialogue(second.page))
    expect(second.page.locator("dialog[open]")).to_have_count(0)

    # La fusion suivante ne le redit pas : il est déjà signalé.
    ajouter_forfait(patron.page, "T2 DEMO")
    attendre_envoi(patron.page)
    verifier_maintenant(second.page)
    attendre_forfait(second.page, "T2 DEMO")
    expect(second.page.locator("dialog[open]")).to_have_count(0)


def test_les_exemples_retires_par_l_equipe_partent_aussi_par_le_cloud(cloud_vide, appareils_maj):
    """Même règle que l'import : des exemples d'une autre version de l'outil (autres identifiants) partent aussi."""
    patron = appareils_maj()
    activer_modif(patron.page)
    patron.page.click("#btn-suppr-exemples")
    dialogue(patron.page).get_by_role("button", name="Supprimer les exemples").click()
    expect(patron.page.locator("#toast")).to_contain_text("Exemples supprimés")
    connecter_premier(patron.page, cloud_vide)

    second = appareils_maj()
    poser_donnees(second.page, forfaits=[forfait("fft-exemple-ancien", "EXEMPLE ANCIEN", maj=0, exemple=True)])
    attendre_forfait(second.page, "EXEMPLE ANCIEN")
    connecter_avec_lien(second.page, creer_lien(patron.page, role="Responsable"))
    attendre_sans_forfait(second.page, "EXEMPLE ANCIEN")


def test_des_forfaits_sans_date_arrivent_sur_les_autres_appareils(cloud_vide, appareils_maj):
    """Un fichier d'avant les dates donne des forfaits à maj 0 : pris pour des exemples, ils n'arrivaient jamais."""
    patron = appareils_maj()
    poser_donnees(patron.page, forfaits=[forfait("fft-sans-date", "T1 SANS DATE", maj=0)])
    connecter_premier(patron.page, cloud_vide)

    vendeur = appareils_maj()
    connecter_avec_lien(vendeur.page, creer_lien(patron.page))
    attendre_forfait(vendeur.page, "T1 SANS DATE")
    second = appareils_maj()
    connecter_avec_lien(second.page, creer_lien(patron.page, role="Responsable"))
    attendre_forfait(second.page, "T1 SANS DATE")


def test_une_page_plus_ancienne_que_le_cloud_passe_en_lecture_seule(cloud_vide, appareils_maj):
    """Le cloud porte la version suivante du format (un appareil à jour l'a envoyée) : cette page ne l'écrase pas,
    n'efface rien, garde ses forfaits à l'écran et ne modifie plus rien jusqu'au rechargement."""
    patron = appareils_maj()
    poser_donnees(patron.page, forfaits=[forfait("fft-t1demo", "T1 DEMO")])
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    avant = donnees(patron.page)

    suivant = {
        "format": "forfaits-comptoir",
        "version": VERSION_FORMAT + 1,
        "familles": [],
        "elements": [],
        "forfaits": [forfait("fft-t1demo", "T1 DEMO"), forfait("fft-kalpo", "KALPO PACK")],
        "packs": [{"id": "pack-1", "nom": "Pack Kalpo"}],
    }
    version = envoyer_au_cloud(cloud_vide, patron.page.evaluate(CHIFFRER, [CLE_CLOUD, suivant]))

    ouvrir_maj(patron.page).locator("#maj-maintenant").click()
    expect(patron.page.locator("#bandeaux")).to_contain_text("version plus récente de l'outil", timeout=20000)
    expect(patron.page.locator("#btn-recharger-futur")).to_be_visible()
    expect(patron.page.locator("#etat-donnees")).to_have_text("Outil à mettre à jour")
    expect(patron.page.locator("dialog[open]")).to_have_count(0)
    attendre_forfait(patron.page, "T1 DEMO")  # ses forfaits restent lisibles

    # Ni modification, ni mise à jour : les deux écriraient les forfaits.
    patron.page.click("#btn-ajouter")
    expect(patron.page.locator("#toast")).to_contain_text("recharge la page")
    expect(patron.page.locator("dialog[open]")).to_have_count(0)
    patron.page.click("#btn-menu")
    patron.page.click("#btn-maj")
    expect(patron.page.locator("#toast")).to_contain_text("recharge la page")
    expect(patron.page.locator("dialog[open]")).to_have_count(0)
    patron.page.evaluate("window.dispatchEvent(new Event('online'))")  # la synchro repartirait

    statut, rep = appel_cloud(cloud_vide, "/api/initialiser", "POST", {"code_secours": CODE_SECOURS, "nom": "Sonde"})
    assert statut == 200, rep
    assert appel_cloud(cloud_vide, "/api/donnees", jeton=rep["jeton"])[1]["version"] == version
    assert donnees(patron.page) == avant

    # Exporter reste ouvert : les forfaits de l'appareil sont bons, seul le cloud est en avance — et après un retrait
    # de tous les appareils, le dernier export sur OneDrive est le seul filet (refusé, lui, si ce sont les données de
    # l'appareil qui sont en avance : test_donnees_d_une_version_plus_recente_ni_remplacees_ni_ecrasees).
    patron.page.evaluate("document.getElementById('toast').textContent = ''")  # le refus précédent y reste écrit
    patron.page.click("#btn-menu")
    dialogue(patron.page).get_by_role("button", name=re.compile("^Exporter")).click()
    expect(dialogue(patron.page)).to_contain_text("Exporter")
    expect(patron.page.locator("#toast")).not_to_contain_text("recharge la page")
