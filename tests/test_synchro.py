"""Tests de la mise à jour automatique : le vrai Worker et son Durable Object, lancés en local.

Rien n'est simulé côté cloud : `wrangler dev` exécute le même code que celui déployé. Ces tests
sont ignorés si pnpm (donc wrangler) est absent de la machine.

Lancer :  python -m pytest tests/test_synchro.py
          NAVIGATEURS=chromium python -m pytest tests/test_synchro.py   (plus rapide)
"""

import base64
import json
import re
import time
import urllib.error
import urllib.request

from conftest import CODE_SECOURS, appel_cloud
from playwright.sync_api import expect
from test_forfaits import activer_modif, chercher, dialogue, modifier, ouvrir_ajout, remplir

# L'en-tête affiche « · à jour 14:32 » quand tout est envoyé. Le motif évite « · mise à jour… »,
# qui s'affiche pendant l'échange et contient aussi « à jour ».
A_JOUR = re.compile(r"· à jour ")
# Un 401 attendu (lien déjà servi, appareil retiré, cloud effacé) : certains navigateurs l'écrivent
# dans la console. On tolère ce bruit-là, pas les vraies erreurs de script.
BRUIT_409 = r"409|Failed to load resource"
BRUIT_401 = r"401|Failed to load resource|load resource"


# ---------------------------------------------------------------- aides


def fermer(d):
    """La croix de l'en-tête : présente sur toutes les fenêtres, et sans ambiguïté de libellé."""
    d.locator(".dlg-tete .btn-icone").click()


def ouvrir_maj(page):
    """Menu → Mise à jour automatique."""
    page.click("#btn-menu")
    page.click("#btn-maj")
    return dialogue(page)


def connecter_premier(page, cloud, nom="Surface"):
    """Met la mise à jour en place depuis cet appareil, avec le code de secours (premier responsable)."""
    ouvrir_maj(page).locator("#btn-premier-appareil").click()
    d = dialogue(page)
    d.locator("#maj-adresse").fill(cloud)
    d.locator("#maj-code").fill(CODE_SECOURS)
    d.locator("#maj-nom1").fill(nom)
    d.locator("#maj-initialiser").click()
    expect(page.locator("#toast")).to_contain_text("Mise à jour en place", timeout=20000)
    expect(page.locator("dialog[open]")).to_have_count(0)


def creer_lien(page, role="Consultation", lot=False, nom=""):
    """Un responsable crée un lien d'appairage et le lit."""
    ouvrir_maj(page).locator("#maj-ajouter").click()
    d = dialogue(page)
    d.get_by_role("button", name=role, exact=True).click()
    if lot:
        d.get_by_role("button", name=re.compile("^Jusqu")).click()
    if nom:
        d.locator("#maj-nom-appareil").fill(nom)
    d.locator("#maj-creer-lien").click()
    expect(d.locator("#maj-lien-cree")).to_be_visible(timeout=20000)
    lien = d.locator("#maj-lien-cree").input_value()
    fermer(d)
    expect(page.locator("dialog[open]")).to_have_count(0)
    return lien


def connecter_avec_lien(page, lien, nom=""):
    ouvrir_maj(page).locator("#btn-coller-lien").click()
    d = dialogue(page)
    d.locator("#maj-lien").fill(lien)
    if nom:
        d.locator("#maj-nom").fill(nom)
    d.locator("#maj-connecter").click()
    expect(page.locator("#toast")).to_contain_text("Connecté", timeout=20000)
    expect(page.locator("dialog[open]")).to_have_count(0)


def verifier_maintenant(page, attendu="À jour"):
    d = ouvrir_maj(page)
    d.locator("#maj-maintenant").click()
    expect(d.locator("#maj-etat")).to_contain_text(attendu, timeout=20000)
    fermer(d)
    expect(page.locator("dialog[open]")).to_have_count(0)


def ajouter_forfait(page, ref, ht="100,00", ttc="120,00"):
    ouvrir_ajout(page)
    remplir(page, ref, ht, ttc)
    expect(page.locator("#toast")).to_contain_text(f"{ref} ajouté")


def attendre_envoi(page):
    """L'envoi part 2 s après la modification : l'en-tête passe de « envoi en attente » à « à jour »."""
    expect(page.locator("#etat-donnees")).to_contain_text("envoi en attente")
    expect(page.locator("#etat-donnees")).to_contain_text(A_JOUR, timeout=25000)


def carte(page, ref):
    return page.locator("#resultats .carte-ref", has_text=re.compile(f"^{re.escape(ref)}$"))


def attendre_forfait(page, ref):
    chercher(page, ref)
    expect(carte(page, ref)).to_have_count(1, timeout=20000)


def attendre_sans_forfait(page, ref):
    chercher(page, ref)
    expect(carte(page, ref)).to_have_count(0, timeout=20000)


def sonde(cloud):
    """Lit le cloud comme un responsable de plus : version et paquet chiffré, jamais la clé."""
    statut, rep = appel_cloud(cloud, "/api/initialiser", "POST", {"code_secours": CODE_SECOURS, "nom": "Sonde"})
    assert statut == 200, rep
    statut, etat = appel_cloud(cloud, "/api/donnees", jeton=rep["jeton"])
    assert statut == 200, etat
    return etat


# ---------------------------------------------------------------- le cloud seul (sans navigateur)


def test_le_cloud_refuse_une_origine_inconnue(cloud_vide):
    """La page du site est la seule à pouvoir parler au cloud (CORS)."""
    requete = urllib.request.Request(cloud_vide + "/api/donnees", headers={"Origin": "https://pirate.example"})
    try:
        urllib.request.urlopen(requete, timeout=20)
        raise AssertionError("le cloud a répondu à une origine inconnue")
    except urllib.error.HTTPError as err:
        assert err.code == 403


def test_le_cloud_refuse_une_version_perimee(cloud_vide):
    """Deux responsables qui envoient : le second est refusé plutôt que d'écraser le premier."""
    _, p = appel_cloud(cloud_vide, "/api/initialiser", "POST", {"code_secours": CODE_SECOURS})
    blob = base64.b64encode(b"x" * 48).decode()
    assert appel_cloud(cloud_vide, "/api/donnees", "PUT", {"version_precedente": 0, "blob": blob}, p["jeton"])[0] == 200
    statut, rep = appel_cloud(cloud_vide, "/api/donnees", "PUT", {"version_precedente": 0, "blob": blob}, p["jeton"])
    assert statut == 409 and rep["version"] == 1


def test_le_cloud_refuse_l_ecriture_a_un_appareil_de_consultation(cloud_vide):
    _, p = appel_cloud(cloud_vide, "/api/initialiser", "POST", {"code_secours": CODE_SECOURS})
    _, inv = appel_cloud(cloud_vide, "/api/invitation", "POST", {"role": "consultation"}, p["jeton"])
    _, vendeur = appel_cloud(cloud_vide, "/api/appairage", "POST", {"code": inv["code"]})
    blob = base64.b64encode(b"x" * 48).decode()
    statut, rep = appel_cloud(cloud_vide, "/api/donnees", "PUT", {"version_precedente": 0, "blob": blob}, vendeur["jeton"])
    assert statut == 401 and rep["raison"] == "lecture seule"


def test_le_cloud_garde_dix_versions_et_pas_plus(cloud_vide):
    _, p = appel_cloud(cloud_vide, "/api/initialiser", "POST", {"code_secours": CODE_SECOURS})
    for i in range(12):
        blob = base64.b64encode(bytes([i]) * 48).decode()
        statut, rep = appel_cloud(cloud_vide, "/api/donnees", "PUT", {"version_precedente": i, "blob": blob}, p["jeton"])
        assert statut == 200, rep
    _, hist = appel_cloud(cloud_vide, "/api/versions", jeton=p["jeton"])
    assert [v["version"] for v in hist["versions"]] == list(range(12, 2, -1))


def test_le_cloud_refuse_de_retirer_le_dernier_responsable(cloud_vide):
    """Sinon plus personne ne pourrait modifier les forfaits."""
    _, p = appel_cloud(cloud_vide, "/api/initialiser", "POST", {"code_secours": CODE_SECOURS})
    _, liste = appel_cloud(cloud_vide, "/api/appareils", jeton=p["jeton"])
    (moi,) = [a for a in liste["appareils"] if a["moi"]]
    assert appel_cloud(cloud_vide, "/api/appareils/" + moi["id"], "DELETE", jeton=p["jeton"])[0] == 409


# ---------------------------------------------------------------- l'appli et le cloud ensemble


def test_un_vendeur_recoit_les_forfaits_du_responsable(cloud_vide, appareils_maj):
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "MAJ-1")
    attendre_envoi(patron.page)

    vendeur = appareils_maj()
    connecter_avec_lien(vendeur.page, creer_lien(patron.page), "PC du comptoir")
    attendre_forfait(vendeur.page, "MAJ-1")

    # Puis un prix change chez le responsable : le vendeur le voit à la vérification suivante.
    chercher(patron.page, "MAJ-1")
    modifier(patron.page, "MAJ-1")
    remplir(patron.page, ht="200,00", ttc="240,00")
    attendre_envoi(patron.page)
    verifier_maintenant(vendeur.page)
    chercher(vendeur.page, "MAJ-1")
    expect(vendeur.page.locator("#resultats .carte")).to_contain_text("240,00")


def test_un_lien_pour_un_appareil_ne_sert_qu_une_fois(cloud_vide, appareils_maj):
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    lien = creer_lien(patron.page)
    connecter_avec_lien(appareils_maj().page, lien)

    autre = appareils_maj(tolerer=BRUIT_401)
    ouvrir_maj(autre.page).locator("#btn-coller-lien").click()
    d = dialogue(autre.page)
    d.locator("#maj-lien").fill(lien)
    d.locator("#maj-connecter").click()
    expect(d.locator(".msg-erreur")).to_contain_text("déjà servi", timeout=20000)


def test_un_lien_en_lot_equipe_plusieurs_appareils(cloud_vide, appareils_maj):
    """Avec 15 appareils et plus, c'est l'utilisateur qui les connecte : un lien doit pouvoir resservir."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "LOT-1")
    attendre_envoi(patron.page)
    lien = creer_lien(patron.page, lot=True)

    for nom in ("Comptoir 1", "Comptoir 2"):
        vendeur = appareils_maj()
        connecter_avec_lien(vendeur.page, lien, nom)
        attendre_forfait(vendeur.page, "LOT-1")

    # Chaque appareil garde malgré tout son propre accès : trois dans la liste, retirables un par un.
    ouvrir_maj(patron.page).locator("#maj-appareils").click()
    liste = dialogue(patron.page).locator("#maj-liste-appareils")
    expect(liste).to_contain_text("Comptoir 1", timeout=20000)
    expect(liste).to_contain_text("Comptoir 2")
    expect(liste.locator("button[data-retirer]")).to_have_count(3)


def test_un_appareil_de_consultation_ne_peut_pas_modifier(cloud_vide, appareils_maj):
    """La règle tient aux deux bouts : le cloud refuse l'écriture, et l'appli ne la propose pas."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    vendeur = appareils_maj()
    connecter_avec_lien(vendeur.page, creer_lien(patron.page))

    vendeur.page.click("#btn-menu")
    d = dialogue(vendeur.page)
    expect(d.locator("#menu-consultation")).to_contain_text("en consultation")
    expect(d.locator("#btn-mode-modif")).to_have_count(0)
    fermer(d)
    expect(vendeur.page.locator("#btn-ajouter")).to_be_hidden()


def test_les_forfaits_de_l_equipe_remplacent_ceux_d_un_appareil_de_consultation(cloud_vide, appareils_maj):
    """Un vendeur ne modifie rien : ses bricolages d'avant ne doivent pas survivre à l'appairage."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "EQUIPE-1")
    attendre_envoi(patron.page)

    vendeur = appareils_maj()
    activer_modif(vendeur.page)
    ajouter_forfait(vendeur.page, "BRICOLE-1")
    connecter_avec_lien(vendeur.page, creer_lien(patron.page))
    attendre_forfait(vendeur.page, "EQUIPE-1")
    attendre_sans_forfait(vendeur.page, "BRICOLE-1")


def test_deux_responsables_qui_envoient_en_meme_temps_ne_perdent_rien(cloud_vide, appareils_maj):
    """Le cloud refuse un envoi parti d'une version périmée : l'appli relit, fusionne et renvoie."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide, "Surface")
    second = appareils_maj(tolerer=BRUIT_409)  # le 409 refusé par le cloud est le cœur du test
    connecter_avec_lien(second.page, creer_lien(patron.page, role="Responsable"), "Portable")

    activer_modif(patron.page)
    ajouter_forfait(patron.page, "DEUX-A")
    attendre_envoi(patron.page)

    # On périme le PREMIER envoi du second appareil, pour que le cas arrive à chaque fois.
    perime = {"fait": False}

    def perimer(route):
        if route.request.method == "PUT" and not perime["fait"]:
            perime["fait"] = True
            corps = json.loads(route.request.post_data)
            corps["version_precedente"] = 0
            route.continue_(post_data=json.dumps(corps))
        else:
            route.continue_()

    second.page.route("**/api/donnees", perimer)
    activer_modif(second.page)
    ajouter_forfait(second.page, "DEUX-B")
    attendre_envoi(second.page)
    assert perime["fait"], "le cas de l'envoi périmé n'a pas été joué"

    attendre_forfait(second.page, "DEUX-A")
    attendre_forfait(second.page, "DEUX-B")
    verifier_maintenant(patron.page)
    attendre_forfait(patron.page, "DEUX-B")


def test_retirer_un_appareil_efface_ses_forfaits(cloud_vide, appareils_maj):
    """Seule réponse réaliste au téléphone perdu : l'appareil s'efface à sa prochaine ouverture en ligne."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "PERDU-1")
    attendre_envoi(patron.page)
    vendeur = appareils_maj(tolerer=BRUIT_401)
    connecter_avec_lien(vendeur.page, creer_lien(patron.page), "Téléphone perdu")
    attendre_forfait(vendeur.page, "PERDU-1")

    ouvrir_maj(patron.page).locator("#maj-appareils").click()
    liste = dialogue(patron.page).locator("#maj-liste-appareils")
    expect(liste).to_contain_text("Téléphone perdu", timeout=20000)
    liste.locator(".menu-mode", has_text="Téléphone perdu").get_by_role("button", name="Retirer", exact=True).click()
    dialogue(patron.page).get_by_role("button", name="Retirer", exact=True).click()
    expect(patron.page.locator("#toast")).to_contain_text("retiré")

    verifier_maintenant(vendeur.page, "a été retiré")
    expect(vendeur.page.locator("#bandeaux")).to_contain_text("effacés")
    chercher(vendeur.page, "")
    expect(vendeur.page.locator("#resultats .carte")).to_have_count(0)
    assert vendeur.page.evaluate("localStorage.getItem('forfaits.cloud.v1')") is None


def test_revenir_a_une_version_annule_une_fausse_manoeuvre(cloud_vide, appareils_maj):
    """Avec 15 appareils, une suppression de trop se propage partout : il faut pouvoir revenir."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "RETOUR-1")
    attendre_envoi(patron.page)

    chercher(patron.page, "RETOUR-1")
    patron.page.get_by_role("button", name="Supprimer", exact=True).click()
    dialogue(patron.page).get_by_role("button", name="Supprimer", exact=True).click()
    attendre_envoi(patron.page)
    attendre_sans_forfait(patron.page, "RETOUR-1")

    ouvrir_maj(patron.page).locator("#maj-versions").click()
    liste = dialogue(patron.page).locator("#maj-liste-versions")
    # 3 envois (mise en place, ajout, suppression) : l'actuel n'a pas de bouton.
    expect(liste.locator("button[data-revenir]")).to_have_count(2, timeout=20000)
    liste.locator("button[data-revenir]").first.click()  # la plus récente des précédentes
    dialogue(patron.page).get_by_role("button", name="Revenir", exact=True).click()
    expect(patron.page.locator("#toast")).to_contain_text("revenus à la version", timeout=20000)
    attendre_forfait(patron.page, "RETOUR-1")


def test_une_heure_fausse_empeche_l_envoi(cloud_vide, appareils_maj):
    """La fusion se fie aux dates de l'appareil : une horloge fausse écraserait les autres en silence."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    avant = sonde(cloud_vide)["version"]

    def decaler(route):
        # Sans « If-None-Match », le cloud renvoie tout (pas de 304) : plus simple à réécrire.
        entetes = {k: v for k, v in route.request.headers.items() if k != "if-none-match"}
        reponse = route.fetch(headers=entetes)
        sortie = dict(reponse.headers)
        sortie["x-heure"] = str(int(time.time() * 1000) - 3600000)  # cloud « en retard » d'une heure
        route.fulfill(response=reponse, headers=sortie)

    patron.page.route("**/api/**", decaler)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "HEURE-1")
    expect(patron.page.locator("#bandeaux")).to_contain_text("heure de cet appareil est fausse", timeout=25000)
    expect(patron.page.locator("#etat-donnees")).to_contain_text("heure fausse")
    assert sonde(cloud_vide)["version"] == avant, "l'envoi est parti malgré l'heure fausse"
    attendre_forfait(patron.page, "HEURE-1")  # rien n'est perdu sur l'appareil


def test_hors_ligne_puis_retour_du_reseau(cloud_vide, appareils_maj):
    patron = appareils_maj(tolerer=r"api/|Failed to|NetworkError|net::|load resource")
    connecter_premier(patron.page, cloud_vide)
    patron.page.route("**/api/**", lambda route: route.abort())
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "AVION-1")
    expect(patron.page.locator("#etat-donnees")).to_contain_text("hors ligne", timeout=25000)
    attendre_forfait(patron.page, "AVION-1")  # l'outil marche sans réseau

    patron.page.unroute("**/api/**")
    verifier_maintenant(patron.page)
    expect(patron.page.locator("#etat-donnees")).to_contain_text(A_JOUR)
    vendeur = appareils_maj()
    connecter_avec_lien(vendeur.page, creer_lien(patron.page))
    attendre_forfait(vendeur.page, "AVION-1")


def test_tout_effacer_du_cloud_laisse_les_forfaits_sur_les_appareils(cloud_vide, appareils_maj):
    """Bouton d'arrêt : si le patron dit non, le cloud est vidé et l'outil revient à l'import manuel."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "STOP-1")
    attendre_envoi(patron.page)
    vendeur = appareils_maj(tolerer=BRUIT_401)
    connecter_avec_lien(vendeur.page, creer_lien(patron.page))
    attendre_forfait(vendeur.page, "STOP-1")

    ouvrir_maj(patron.page).locator("#maj-effacer").click()
    d = dialogue(patron.page)
    d.locator("#maj-code-effacer").fill(CODE_SECOURS)
    d.locator("#maj-confirmer-effacer").click()
    expect(dialogue(patron.page)).to_contain_text("Il ne reste rien dans le cloud", timeout=20000)
    dialogue(patron.page).get_by_role("button", name="Compris", exact=True).click()

    attendre_forfait(patron.page, "STOP-1")  # les forfaits restent sur l'appareil
    verifier_maintenant(vendeur.page, "plus connecté")
    attendre_forfait(vendeur.page, "STOP-1")


def test_le_cloud_ne_voit_jamais_les_forfaits_en_clair(cloud_vide, appareils_maj):
    """Le point que le patron voudra vérifier : l'hébergeur ne peut pas lire les prix."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "ZORBA-SECRET-9", ht="1 234,50", ttc="1 481,40")
    attendre_envoi(patron.page)

    paquet = base64.b64decode(sonde(cloud_vide)["blob"])
    assert len(paquet) > 200
    for secret in (b"ZORBA", b"SECRET", b"123450", b"forfaits-comptoir"):
        assert secret not in paquet, f"{secret!r} lisible dans le paquet envoyé au cloud"


def test_un_lien_vers_un_autre_cloud_est_refuse(appareils_maj):
    """Hameçonnage : seul le cloud du compte de l'équipe est accepté (CSP + contrôle de l'adresse)."""
    vendeur = appareils_maj()
    ouvrir_maj(vendeur.page).locator("#btn-coller-lien").click()
    d = dialogue(vendeur.page)
    faux = "https://nationaliste.github.io/forfaits/#maj=pirate.autre-compte.workers.dev&inv=" + "a" * 22 + "&cle=" + "b" * 43
    d.locator("#maj-lien").fill(faux)
    d.locator("#maj-connecter").click()
    expect(d.locator(".msg-erreur")).to_contain_text("pas un lien de mise à jour valable")


def test_les_reglages_de_l_appareil_ne_partent_pas_dans_le_cloud(cloud_vide, appareils_maj):
    """Thème, taille du texte, favoris : par appareil, jamais exportés, donc jamais dans le cloud."""
    patron = appareils_maj()
    connecter_premier(patron.page, cloud_vide)
    patron.page.click("#btn-menu")
    d = dialogue(patron.page)
    d.get_by_role("button", name="Clair", exact=True).click()
    fermer(d)
    expect(patron.page.locator("dialog[open]")).to_have_count(0)
    activer_modif(patron.page)
    ajouter_forfait(patron.page, "REGLAGE-1")
    attendre_envoi(patron.page)

    vendeur = appareils_maj()
    connecter_avec_lien(vendeur.page, creer_lien(patron.page))
    attendre_forfait(vendeur.page, "REGLAGE-1")
    assert patron.page.evaluate("document.documentElement.dataset.theme") == "clair"
    assert vendeur.page.evaluate("document.documentElement.dataset.theme") == "sombre"
