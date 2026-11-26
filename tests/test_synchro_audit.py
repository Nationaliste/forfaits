"""Mise à jour automatique : les constats de l'audit du 10/11/2026 (roadmap 750) et la taille des versions (roadmap 574).

Le vrai Worker tourne en local (voir conftest.py). Lancer :
    NAVIGATEURS=chromium python -m pytest tests/test_synchro_audit.py
"""

import base64
import json
import re
import time

from conftest import ATTENTE_SECOURS_TESTS, CODE_SECOURS, appel_cloud
from playwright.sync_api import expect
from test_forfaits import activer_modif, dialogue, exporter_json
from test_synchro import (
    A_JOUR,
    BRUIT_401,
    ajouter_forfait,
    attendre_envoi,
    attendre_forfait,
    attendre_sans_forfait,
    connecter_avec_lien,
    connecter_premier,
    creer_lien,
    ouvrir_maj,
    revenir_a_la_version_precedente,
    verifier_maintenant,
)
from test_synchro_fusion import CLE_DONNEES, VERSION_FORMAT, donnees, forfait, maintenant, poser_donnees

COUPURE = r"api/|Failed to|NetworkError|net::|load resource"


def initialiser(cloud, nom="Patron"):
    statut, rep = appel_cloud(cloud, "/api/initialiser", "POST", {"code_secours": CODE_SECOURS, "nom": nom})
    assert statut == 200, rep
    return rep


def ecrire_fichier(chemin, forfaits):
    contenu = {
        "format": "forfaits-comptoir",
        "version": VERSION_FORMAT,
        "exporteLe": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "familles": [],
        "elements": [],
        "forfaits": forfaits,
    }
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    return str(chemin)


def liste_des_appareils(page):
    ouvrir_maj(page).locator("#maj-appareils").click()
    liste = dialogue(page).locator("#maj-liste-appareils")
    expect(liste).to_contain_text("cet appareil", timeout=20000)
    return liste


# ---------------------------------------------------------------- U2 et I7 : le code de secours


def test_le_code_de_secours_se_bloque_apres_cinq_erreurs(cloud_vide):
    """Le frein est gardé dans le stockage et commun aux deux routes du code : porter un jeton n'y échappe pas.
    (Il vise la source qui se trompe, pas les autres : voir test_cloud_unitaire, les essais locaux n'en ont qu'une.)"""
    patron = initialiser(cloud_vide)
    for _ in range(4):
        statut, rep = appel_cloud(cloud_vide, "/api/initialiser", "POST", {"code_secours": "x" * 29})
        assert statut == 401 and rep["raison"] == "code de secours incorrect", rep
    # Avec un jeton responsable : compté pareil (« Tout effacer » demande aussi le code).
    statut, _ = appel_cloud(cloud_vide, "/api/tout", "DELETE", jeton=patron["jeton"], code_secours="y" * 29)
    assert statut == 401
    # Bloqué : même le bon code attend (une minute en vrai, raccourcie pour les essais).
    statut, rep = appel_cloud(cloud_vide, "/api/initialiser", "POST", {"code_secours": CODE_SECOURS})
    assert statut == 429 and rep["raison"] == "code de secours bloque", rep
    statut, rep = appel_cloud(cloud_vide, "/api/tout", "DELETE", jeton=patron["jeton"], code_secours=CODE_SECOURS)
    assert statut == 429, rep
    time.sleep(ATTENTE_SECOURS_TESTS / 1000 + 0.5)
    # Après l'attente, le bon code passe et remet le compteur à zéro.
    initialiser(cloud_vide)
    statut, rep = appel_cloud(cloud_vide, "/api/initialiser", "POST", {"code_secours": "x" * 29})
    assert statut == 401, rep


def test_l_outil_dit_combien_de_temps_le_code_est_bloque(cloud_vide, appareils_maj):
    """Sans message propre, le blocage s'affichait « Le cloud a répondu 429 » : on croirait le cloud en panne."""
    patron = appareils_maj(tolerer=r"429|load resource")
    connecter_premier(patron.page, cloud_vide)
    # La fenêtre est prête AVANT le blocage : l'attente des essais (1,5 s) ne laisse pas le temps de l'ouvrir après.
    ouvrir_maj(patron.page).locator("#maj-effacer").click()
    d = dialogue(patron.page)
    d.locator("#maj-code-effacer").fill("z" * 29)
    try:
        for _ in range(5):
            statut, _ = appel_cloud(cloud_vide, "/api/initialiser", "POST", {"code_secours": "x" * 29})
            assert statut == 401
        d.locator("#maj-confirmer-effacer").click()
        expect(d.locator(".msg-erreur")).to_contain_text("Trop de codes de secours faux : le cloud attend", timeout=20000)
    finally:
        # Les tests suivants repartent du bon code : attendre la fin du blocage, puis remettre le compteur à zéro.
        time.sleep(ATTENTE_SECOURS_TESTS / 1000 + 0.5)
        initialiser(cloud_vide)


def test_tout_effacer_garde_la_marque_des_appareils_retires(cloud_vide):
    """Un appareil retiré doit encore s'effacer après « Tout effacer » : sans sa marque, il gardait ses forfaits."""
    patron = initialiser(cloud_vide)
    _, inv = appel_cloud(cloud_vide, "/api/invitation", "POST", {"role": "consultation"}, patron["jeton"])
    _, perdu = appel_cloud(cloud_vide, "/api/appairage", "POST", {"code": inv["code"], "nom": "Téléphone perdu"})
    assert appel_cloud(cloud_vide, "/api/appareils/" + perdu["id"], "DELETE", jeton=patron["jeton"])[0] == 200
    assert appel_cloud(cloud_vide, "/api/tout", "DELETE", jeton=patron["jeton"], code_secours=CODE_SECOURS)[0] == 200
    statut, rep = appel_cloud(cloud_vide, "/api/donnees", jeton=perdu["jeton"])
    assert statut == 401 and rep["raison"] == "retire", rep


# ---------------------------------------------------------------- I12 et petits : appareils, liens, responsables fantômes


def test_les_liens_en_cours_se_listent_et_s_annulent(cloud_vide):
    patron = initialiser(cloud_vide, "PC du patron")
    _, inv = appel_cloud(
        cloud_vide, "/api/invitation", "POST", {"role": "responsable", "usages": 3, "nom": "Caisse"}, patron["jeton"]
    )
    statut, rep = appel_cloud(cloud_vide, "/api/invitations", jeton=patron["jeton"])
    assert statut == 200, rep
    (lien,) = rep["invitations"]
    assert (lien["role"], lien["usages"], lien["nom"], lien["par"]) == ("responsable", 3, "Caisse", "PC du patron")
    assert inv["code"] not in json.dumps(rep)  # la liste ne redonne pas le code
    assert appel_cloud(cloud_vide, "/api/invitations/" + lien["id"], "DELETE", jeton=patron["jeton"])[0] == 200
    assert appel_cloud(cloud_vide, "/api/appairage", "POST", {"code": inv["code"]})[0] == 401
    assert appel_cloud(cloud_vide, "/api/invitations", jeton=patron["jeton"])[1]["invitations"] == []


def test_annuler_un_lien_depuis_l_outil(cloud_vide, appareils_maj):
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    lien = creer_lien(patron.page, nom="Caisse")
    liste = liste_des_appareils(patron.page)
    # Deux appareils peuvent porter le même nom : la date d'ajout et un numéro les distinguent.
    expect(liste.locator(".menu-mode", has_text="cet appareil")).to_contain_text(re.compile(r"ajouté le .+ · n° \S{4}"))
    ligne = liste.locator(".menu-mode", has_text="Lien consultation pour « Caisse »")
    expect(ligne).to_contain_text("créé par PC du responsable")
    ligne.get_by_role("button", name="Annuler le lien").click()
    expect(patron.page.locator("#toast")).to_contain_text("Lien annulé")
    expect(liste).not_to_contain_text("Caisse")
    expect(liste).not_to_contain_text("null")  # plus aucun lien : replaceChildren écrivait « null » à la place du titre

    autre = appareils_maj(tolerer=BRUIT_401)
    ouvrir_maj(autre.page).locator("#btn-coller-lien").click()
    d = dialogue(autre.page)
    d.locator("#maj-lien").fill(lien)
    d.locator("#maj-connecter").click()
    expect(d).to_contain_text("déjà servi ou a expiré", timeout=20000)


def test_deconnecter_retire_aussi_l_appareil_du_cloud(cloud_vide, appareils_maj):
    """Sinon il restait responsable pour le cloud, et désarmait la garde du dernier responsable."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    second = appareils_maj()
    connecter_avec_lien(second.page, creer_lien(patron.page, role="Responsable"), "Portable")
    ouvrir_maj(second.page).locator("#maj-deconnecter").click()
    dialogue(second.page).get_by_role("button", name="Déconnecter", exact=True).click()
    expect(second.page.locator("dialog[open]")).to_have_count(0)
    liste = liste_des_appareils(patron.page)
    expect(liste).not_to_contain_text("Portable", timeout=20000)


def test_un_premier_appareil_qui_renonce_ne_reste_pas_inscrit(cloud_vide, appareils_maj):
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    intrus = appareils_maj()
    ouvrir_maj(intrus.page).locator("#btn-premier-appareil").click()
    d = dialogue(intrus.page)
    d.locator("#maj-adresse").fill(cloud_vide)
    d.locator("#maj-code").fill(CODE_SECOURS)
    d.locator("#maj-nom1").fill("Tablette")
    d.locator("#maj-initialiser").click()
    question = intrus.page.locator("dialog[open]", has_text="Le cloud contient déjà des forfaits")
    question.get_by_role("button", name="Annuler").click()
    expect(dialogue(intrus.page)).to_contain_text("Connexion annulée", timeout=20000)
    liste = liste_des_appareils(patron.page)
    expect(liste).not_to_contain_text("Tablette", timeout=20000)


# ---------------------------------------------------------------- I8 : import d'un fichier sur un appareil connecté


def test_un_import_sur_un_responsable_part_vers_l_equipe(cloud_vide, appareils_maj, tmp_path):
    patron = appareils_maj()
    poser_donnees(patron.page, forfaits=[forfait("fft-garde", "T1 GARDE"), forfait("fft-retire", "T1 RETIRE")])
    connecter_premier(patron.page, cloud_vide)
    second = appareils_maj()
    connecter_avec_lien(second.page, creer_lien(patron.page, role="Responsable"))
    attendre_forfait(second.page, "T1 RETIRE")

    # « Mettre à jour » : le forfait du fichier arrive chez l'autre responsable sans autre modification.
    fichier = ecrire_fichier(tmp_path / "ajout.json", [forfait("fft-zorba", "ZORBA FICHIER", maj=maintenant())])
    patron.page.set_input_files("#fichier-import", fichier)
    dialogue(patron.page).get_by_role("button", name="Mettre à jour", exact=True).click()
    attendre_envoi(patron.page)
    verifier_maintenant(second.page)
    attendre_forfait(second.page, "ZORBA FICHIER")

    # « Remplacer tout » : le fichier gagne aussi chez les autres (ce qu'il n'a pas disparaît partout).
    fichier = ecrire_fichier(tmp_path / "remplace.json", [forfait("fft-garde", "T1 GARDE")])
    patron.page.set_input_files("#fichier-import", [])
    patron.page.set_input_files("#fichier-import", fichier)
    d = dialogue(patron.page)
    expect(d).to_contain_text("tous ceux de l'équipe")
    d.get_by_role("button", name="Remplacer tout", exact=True).click()
    attendre_envoi(patron.page)
    verifier_maintenant(second.page)
    attendre_sans_forfait(second.page, "ZORBA FICHIER")
    attendre_sans_forfait(second.page, "T1 RETIRE")
    attendre_forfait(second.page, "T1 GARDE")


def test_un_appareil_de_consultation_refuse_l_import(cloud_vide, appareils_maj, tmp_path):
    """Ses forfaits sont remplacés par ceux de l'équipe à la mise à jour suivante : l'import ne servirait à rien."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    vendeur = appareils_maj()
    connecter_avec_lien(vendeur.page, creer_lien(patron.page))
    avant = donnees(vendeur.page)
    vendeur.page.set_input_files("#fichier-import", ecrire_fichier(tmp_path / "f.json", [forfait("fft-zorba", "ZORBA")]))
    d = dialogue(vendeur.page)
    expect(d).to_contain_text("Import impossible")
    expect(d).to_contain_text("reçoit les forfaits de l'équipe")
    assert donnees(vendeur.page) == avant


# ---------------------------------------------------------------- I9 et I10 : retour à une version


def test_un_retour_coupe_par_le_reseau_se_termine_a_la_mise_a_jour_suivante(cloud_vide, appareils_maj):
    """Le cloud a fait le retour mais la réponse s'est perdue : sans rattrapage, l'appareil renvoyait la fausse manœuvre."""
    patron = appareils_maj(tolerer=COUPURE)
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "BON-1")
    attendre_envoi(patron.page)
    ajouter_forfait(patron.page, "ERREUR-1")
    attendre_envoi(patron.page)
    second = appareils_maj()
    connecter_avec_lien(second.page, creer_lien(patron.page, role="Responsable"))
    attendre_forfait(second.page, "ERREUR-1")

    def couper(route):
        route.fetch()  # la demande arrive au cloud...
        route.abort()  # ...mais la réponse se perd

    patron.page.route("**/api/revenir", couper)
    ouvrir_maj(patron.page).locator("#maj-versions").click()
    liste = dialogue(patron.page).locator("#maj-liste-versions")
    expect(liste.locator("button[data-revenir]").first).to_be_visible(timeout=20000)
    liste.locator("button[data-revenir]").first.click()
    dialogue(patron.page).get_by_role("button", name="Revenir", exact=True).click()
    expect(dialogue(patron.page)).to_contain_text("Retour pas terminé", timeout=20000)
    dialogue(patron.page).get_by_role("button", name="Compris").click()
    patron.page.keyboard.press("Escape")
    expect(patron.page.locator("dialog[open]")).to_have_count(0)
    patron.page.unroute("**/api/revenir")

    verifier_maintenant(patron.page)
    attendre_sans_forfait(patron.page, "ERREUR-1")
    attendre_forfait(patron.page, "BON-1")
    verifier_maintenant(second.page)
    attendre_sans_forfait(second.page, "ERREUR-1")
    verifier_maintenant(patron.page)  # le second n'a rien renvoyé de la fausse manœuvre
    attendre_sans_forfait(patron.page, "ERREUR-1")


# La réponse de /api/revenir tarde, et une mise à jour part pendant ce temps (ici : retour du réseau).
RETARDER_LE_RETOUR = """() => {
    window.__messages = [];
    const toast = document.getElementById('toast');
    new MutationObserver(() => window.__messages.push(toast.textContent))
        .observe(toast, { childList: true, characterData: true, subtree: true });
    const vrai = window.fetch;
    window.fetch = async (adresse, options) => {
        if (String(adresse).includes('/api/revenir')) {
            window.dispatchEvent(new Event('online'));
            await new Promise((fin) => setTimeout(fin, 2500));
        }
        return vrai(adresse, options);
    };
}"""


def test_une_mise_a_jour_pendant_un_retour_ne_l_annonce_pas_rate(cloud_vide, appareils_maj):
    """La mise à jour lisait le cloud avant la fin du retour : elle oubliait le retour et disait « n'a pas abouti »."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "BON-1")
    attendre_envoi(patron.page)
    ajouter_forfait(patron.page, "ERREUR-1")
    attendre_envoi(patron.page)
    patron.page.evaluate(RETARDER_LE_RETOUR)
    revenir_a_la_version_precedente(patron.page)
    attendre_sans_forfait(patron.page, "ERREUR-1")
    verifier_maintenant(patron.page)
    attendre_sans_forfait(patron.page, "ERREUR-1")
    attendre_forfait(patron.page, "BON-1")
    messages = patron.page.evaluate("window.__messages")
    assert not any("pas abouti" in m for m in messages), messages


def test_un_retour_gagne_meme_face_a_une_horloge_en_avance(cloud_vide, appareils_maj):
    """Un appareil en avance de 4 min (toléré) date sa modification plus tard que « maintenant » chez celui qui revient."""
    patron = appareils_maj()
    poser_donnees(patron.page, forfaits=[forfait("fft-prix", "T1 PRIX", ttc=12000)])
    connecter_premier(patron.page, cloud_vide)
    second = appareils_maj()
    connecter_avec_lien(second.page, creer_lien(patron.page, role="Responsable"))
    attendre_forfait(second.page, "T1 PRIX")

    # Le second change le prix avec une date en avance, puis un ajout fait partir l'envoi.
    second.page.evaluate(
        """([cle, maj]) => {
            const d = JSON.parse(localStorage.getItem(cle));
            const f = d.forfaits.find((x) => x.id === 'fft-prix');
            f.ttc = 24000; f.ht = 20000; f.maj = maj;
            localStorage.setItem(cle, JSON.stringify(d));
            window.dispatchEvent(new StorageEvent('storage', { key: cle }));
        }""",
        [CLE_DONNEES, maintenant() + 4 * 60000],
    )
    activer_modif(second.page)
    ajouter_forfait(second.page, "T1 AUTRE")
    attendre_envoi(second.page)
    verifier_maintenant(patron.page)
    attendre_forfait(patron.page, "T1 AUTRE")

    revenir_a_la_version_precedente(patron.page)
    # Le retour s'envoie avec la réponse du cloud : « envoi en attente » peut ne jamais se voir.
    expect(patron.page.locator("#etat-donnees")).to_contain_text(A_JOUR, timeout=25000)
    verifier_maintenant(second.page)
    verifier_maintenant(patron.page)
    prix = {f["ref"]: f["ttc"] for f in donnees(second.page)["forfaits"] if not f.get("supprime")}
    assert prix.get("T1 PRIX") == 12000, prix
    prix = {f["ref"]: f["ttc"] for f in donnees(patron.page)["forfaits"] if not f.get("supprime")}
    assert prix.get("T1 PRIX") == 12000, prix


# ---------------------------------------------------------------- U2 écartée : le rappel d'export reste le filet

CLE_APPAREIL = ".".join(["forfaits", "appareil", "v1"])
JOUR_MS = 24 * 3600 * 1000


def reglage_appareil(page, **valeurs):
    """Change des réglages de l'appareil puis recharge (la page les relit au démarrage)."""
    page.evaluate(
        """([cle, valeurs]) => {
            const a = JSON.parse(localStorage.getItem(cle));
            localStorage.setItem(cle, JSON.stringify({ ...a, ...valeurs }));
        }""",
        [CLE_APPAREIL, valeurs],
    )
    page.reload()


def test_le_rappel_d_export_revient_chaque_semaine_chez_un_responsable_connecte(cloud_vide, appareils_maj, tmp_path):
    """Sans copie locale (choix de l'utilisateur, 26/11/2026), le dernier export sur OneDrive est le seul filet après un
    retrait de tous les appareils : or le rappel se taisait dès le premier envoi au cloud, pour toujours."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "T1 RAPPEL")
    attendre_envoi(patron.page)
    expect(patron.page.locator("#rappel")).to_be_hidden()  # connecté : pas à chaque modification

    # Jamais exporté : les 7 jours comptent depuis le passage à cette version.
    reglage_appareil(patron.page, departRappel=maintenant() - 6 * JOUR_MS)
    attendre_forfait(patron.page, "T1 RAPPEL")
    expect(patron.page.locator("#rappel")).to_be_hidden()
    reglage_appareil(patron.page, departRappel=maintenant() - 8 * JOUR_MS)
    expect(patron.page.locator("#rappel")).to_be_visible(timeout=20000)
    expect(patron.page.locator("#rappel-texte")).to_contain_text("1 modification pas encore exportée")

    # L'export le remet à zéro, et une modification juste après ne le rallume pas.
    exporter_json(patron.page, tmp_path / "export.json")
    expect(patron.page.locator("#rappel")).to_be_hidden()
    ajouter_forfait(patron.page, "T1 APRES")
    attendre_envoi(patron.page)
    expect(patron.page.locator("#rappel")).to_be_hidden()

    # Export de plus de 7 jours, avec une modification depuis : il revient.
    reglage_appareil(patron.page, dernierExport=maintenant() - 8 * JOUR_MS)
    expect(patron.page.locator("#rappel")).to_be_visible(timeout=20000)
    expect(patron.page.locator("#rappel-texte")).to_contain_text("1 modification pas encore exportée")


# ---------------------------------------------------------------- roadmap 574 : taille des versions


def test_la_liste_des_versions_donne_la_taille_de_chacune(cloud_vide):
    patron = initialiser(cloud_vide)
    tailles = []
    for i in range(3):
        brut = bytes([i]) * (48 + 300 * i)
        tailles.append(len(brut))
        blob = base64.b64encode(brut).decode()
        assert appel_cloud(cloud_vide, "/api/donnees", "PUT", {"version_precedente": i, "blob": blob}, patron["jeton"])[0] == 200
    statut, rep = appel_cloud(cloud_vide, "/api/versions", jeton=patron["jeton"])
    assert statut == 200, rep
    assert [(v["version"], v["taille"]) for v in rep["versions"]] == [(3, tailles[2]), (2, tailles[1]), (1, tailles[0])]
    assert all(v["par"] == "Patron" and v["date"] for v in rep["versions"])
