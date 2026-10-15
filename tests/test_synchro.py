"""Synchronisation avec le vrai serveur Rust (serveur/) : envoi, réception, conflits, coupure, refus.

Le serveur est compilé une fois (cargo), puis lancé sur 127.0.0.1 pour chaque test.
Sans Rust installé, ces tests sont sautés.
"""

import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import time
import urllib.request

import pytest
from conftest import CAPTURES, RACINE, demarrer_serveur
from playwright.sync_api import expect
from test_forfaits import activer_modif, cartes, chercher, dialogue, espaces, modifier, ouvrir_ajout, refs, remplir

EQUIPE = "EXEMPLE mot de passe equipe"
RESPONSABLE = "EXEMPLE code responsable"
# Erreurs que le navigateur affiche de lui-même quand le serveur refuse (401, 409) ou ne répond pas.
ATTENDUES = re.compile(r"Failed to load resource|ERR_CONNECTION_REFUSED|status of (401|409)|NetworkError|Cross-Origin Request")


@pytest.fixture(scope="session")
def exe_serveur():
    cargo = shutil.which("cargo") or str(pathlib.Path.home() / ".cargo" / "bin" / "cargo.exe")
    if not pathlib.Path(cargo).exists() and not shutil.which("cargo"):
        pytest.skip("Rust (cargo) n'est pas installé")
    # Compilation hors de OneDrive : des milliers de fichiers temporaires à ne pas synchroniser.
    cible = pathlib.Path(
        os.environ.get("CARGO_TARGET_DIR") or pathlib.Path(os.environ.get("LOCALAPPDATA", RACINE)) / "forfaits-cargo-target"
    )
    env = {**os.environ, "CARGO_TARGET_DIR": str(cible)}
    subprocess.run(
        [cargo, "build", "--release", "--quiet", "--manifest-path", str(RACINE / "serveur" / "Cargo.toml")], env=env, check=True
    )
    return cible / "release" / ("forfaits-serveur.exe" if os.name == "nt" else "forfaits-serveur")


def port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServeurForfaits:
    def __init__(self, exe, dossier, origine, port):
        self.exe, self.dossier, self.port = exe, dossier, port
        self.url = f"http://127.0.0.1:{self.port}"
        self.configurer(EQUIPE, RESPONSABLE, origine)
        self.processus = None
        self.demarrer()

    def configurer(self, equipe, responsable, origine=None):
        options = ["--port", str(self.port)] + (["--origine", origine] if origine else [])
        saisie = f"{equipe}\n{equipe}\n{responsable}\n{responsable}\n"
        commande = [self.exe, "configurer", "--stdin", "--dossier", str(self.dossier), *options]
        subprocess.run(commande, input=saisie, text=True, check=True, capture_output=True)

    def demarrer(self):
        self.processus = subprocess.Popen(
            [self.exe, "--dossier", str(self.dossier)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        limite = time.monotonic() + 10
        while True:
            try:
                urllib.request.urlopen(self.url + "/api/sel", timeout=1).close()
                return
            except OSError:
                if time.monotonic() > limite:
                    raise
                time.sleep(0.1)

    def arreter(self):
        self.processus.terminate()
        self.processus.wait(10)

    def version(self):
        """Version enregistrée sur le disque du serveur (0 = rien reçu)."""
        chemin = self.dossier / "donnees.json"
        return json.loads(chemin.read_text(encoding="utf-8"))["version"] if chemin.exists() else 0

    def attendre_version(self, attendue, delai=20, page=None):
        """page : à donner si elle a des interceptions (page.route), qui ne tournent que pendant un appel à Playwright."""
        limite = time.monotonic() + delai
        while self.version() < attendue:
            assert time.monotonic() < limite, f"le serveur est resté en version {self.version()} (attendu {attendue})"
            page.wait_for_timeout(100) if page else time.sleep(0.1)


@pytest.fixture
def serveur(exe_serveur, tmp_path):
    """Serveur de synchro + site de test dont la page a le droit de l'appeler (la vraie page n'autorise que *.ts.net)."""
    port = port_libre()
    url_page, site = demarrer_serveur(connect_src=f"http://127.0.0.1:{port}")
    s = ServeurForfaits(exe_serveur, tmp_path / "serveur", url_page.rstrip("/"), port)
    s.url_page = url_page
    yield s
    if s.processus.poll() is None:
        s.arreter()
    site.shutdown()
    site.server_close()


@pytest.fixture
def appareil(appareils, serveur):
    return lambda **options: appareils(url=serveur.url_page, tolerer=ATTENDUES, **options).page


def ouvrir_connexion(page):
    page.click("#btn-menu")
    page.click("#btn-serveur")
    expect(dialogue(page)).to_contain_text("Serveur de mise à jour")


def connecter(page, serveur, code=None, equipe=EQUIPE):
    ouvrir_connexion(page)
    d = dialogue(page)
    d.locator("#s-adresse").fill(serveur.url)
    d.locator("#s-equipe").fill(equipe)
    if code:
        d.locator("#s-code").fill(code)
    d.locator("#s-connecter").click()
    expect(page.locator("#toast")).to_contain_text("Connecté", timeout=30000)
    expect(page.locator("dialog[open]")).to_have_count(0)


def synchroniser(page):
    ouvrir_connexion(page)
    dialogue(page).locator("#s-synchro").click()
    expect(dialogue(page).locator("#s-etat")).to_contain_text("À jour", timeout=20000)
    dialogue(page).get_by_role("button", name="Fermer").click()


def ajouter(page, ref, ht="1 000,00", ttc="1 200,00"):
    ouvrir_ajout(page)
    remplir(page, ref, ht, ttc)  # sans éléments : pas d'avertissement « même combinaison »
    expect(page.locator("#toast")).to_contain_text(f"{ref} ajouté")


def test_responsable_envoie_et_comptoir_recoit(appareil, serveur, navigateur):
    a = appareil()
    connecter(a, serveur, code=RESPONSABLE)
    expect(a.locator("#btn-importer")).to_be_hidden()  # plus besoin d'importer à la main
    assert serveur.version() == 0, "des données d'exemple jamais touchées ne sont pas envoyées"

    activer_modif(a)
    ajouter(a, "TX-100")
    serveur.attendre_version(1)  # envoyé tout seul
    expect(a.locator("#etat-synchro")).to_contain_text("à jour")
    expect(a.locator("#rappel")).to_be_hidden()  # pas de rappel d'export : le serveur a les modifications

    b = appareil()
    connecter(b, serveur)  # comptoir : mot de passe d'équipe seulement
    CAPTURES.mkdir(exist_ok=True)
    b.screenshot(path=CAPTURES / f"{navigateur.nom}-serveur-1-connecte.png")
    chercher(b, "TX-100")
    assert refs(b) == {"TX-100"}

    # Modification puis suppression : elles arrivent au comptoir.
    chercher(a, "TX-100")
    modifier(a, "TX-100")
    remplir(a, ht="900,00", ttc="1 080,00")
    serveur.attendre_version(2)
    synchroniser(b)
    assert espaces(cartes(b)[0]["ttc"]) == "1 080,00 €"

    a.get_by_role("button", name="Supprimer", exact=True).click()
    dialogue(a).get_by_role("button", name="Supprimer", exact=True).click()
    serveur.attendre_version(3)
    synchroniser(b)
    expect(b.locator("#resultats .carte")).to_have_count(0)

    # Le comptoir ne peut pas envoyer, même en mode modification : ses changements restent chez lui.
    activer_modif(b)
    ajouter(b, "TX-COMPTOIR")
    synchroniser(b)
    assert serveur.version() == 3

    # Sur le disque du serveur : rien de lisible (ni références, ni prix, ni mots de passe).
    for fichier in [*serveur.dossier.rglob("*.json"), serveur.dossier / "serveur.log"]:
        texte = fichier.read_text(encoding="utf-8")
        for indice in ("TX-100", "EX-M1", "Gamma", "Taxim", "108000", EQUIPE, RESPONSABLE):
            assert indice not in texte, f"{fichier.name} contient « {indice} »"


def test_mauvais_mot_de_passe_mauvais_code_mauvaise_adresse(appareil, serveur, navigateur):
    page = appareil(viewport={"width": 375, "height": 812}, reduced_motion="reduce")  # téléphone
    ouvrir_connexion(page)
    d = dialogue(page)

    def essayer(adresse, equipe, code, message):
        d.locator("#s-adresse").fill(adresse)
        d.locator("#s-equipe").fill(equipe)
        d.locator("#s-code").fill(code)
        d.locator("#s-connecter").click()
        expect(d.locator(".msg-erreur")).to_contain_text(message, timeout=30000)
        expect(d.locator("#s-connecter")).to_be_enabled()

    essayer("http://exemple.com", EQUIPE, "", "Adresse invalide")
    serveur.arreter()  # PC du serveur éteint
    essayer(serveur.url, EQUIPE, "", "Serveur injoignable")
    serveur.demarrer()
    essayer(serveur.url, "EXEMPLE faux mot de passe", "", "Mot de passe d'équipe incorrect")
    essayer(serveur.url, EQUIPE, "EXEMPLE faux code responsable", "Code responsable incorrect")
    page.screenshot(path=CAPTURES / f"{navigateur.nom}-serveur-2-erreur-telephone.png")
    assert dialogue(page).bounding_box()["width"] <= 375
    d.get_by_role("button", name="Annuler").click()
    expect(page.locator("#btn-importer")).to_be_visible()  # toujours pas connecté


def test_deux_responsables_en_meme_temps_fusionnes(appareil, serveur):
    a, c = appareil(), appareil()
    connecter(a, serveur, code=RESPONSABLE)
    connecter(c, serveur, code=RESPONSABLE)
    activer_modif(a)
    activer_modif(c)

    # C n'a pas encore vu l'envoi de A : on lui fait croire une fois que rien n'a changé (304),
    # pour que son envoi arrive avec une version périmée → refus 409 → il récupère, fusionne, renvoie.
    origine = c.evaluate("location.origin")
    vu = []

    def perime(route):
        if route.request.method == "GET" and not vu:
            vu.append(True)
            route.fulfill(
                status=304,
                headers={"ETag": '"0"', "Access-Control-Allow-Origin": origine, "Access-Control-Expose-Headers": "etag"},
            )
        else:
            route.continue_()

    ajouter(a, "TX-A")
    serveur.attendre_version(1)
    c.route(f"{serveur.url}/api/donnees", perime)
    ajouter(c, "TX-C")
    serveur.attendre_version(2, page=c)
    assert vu, "l'envoi de C n'est pas passé par le cas périmé"

    for page in (a, c):
        synchroniser(page)
        chercher(page, "TX-")
        assert {r for r in refs(page) if r.startswith("TX-")} == {"TX-A", "TX-C"}


def test_serveur_coupe_puis_relance(appareil, serveur):
    a = appareil()
    connecter(a, serveur, code=RESPONSABLE)
    activer_modif(a)
    serveur.arreter()
    ajouter(a, "TX-200")
    expect(a.locator("#etat-synchro")).to_contain_text("envoi en attente")
    a.wait_for_timeout(3000)  # l'envoi automatique échoue : rien n'est perdu
    expect(a.locator("#etat-synchro")).to_contain_text("envoi en attente")

    serveur.demarrer()
    synchroniser(a)
    assert serveur.version() == 1
    expect(a.locator("#etat-synchro")).to_contain_text("à jour")

    b = appareil()
    connecter(b, serveur)
    chercher(b, "TX-200")
    assert refs(b) == {"TX-200"}


def test_mot_de_passe_change_signale(appareil, serveur):
    page = appareil()
    connecter(page, serveur)
    # Serveur en marche : refus (il garderait les anciens mots de passe en mémoire).
    with pytest.raises(subprocess.CalledProcessError) as refus:
        serveur.configurer("EXEMPLE nouveau mot de passe", "EXEMPLE nouveau code responsable")
    assert "le serveur tourne encore" in refus.value.stderr
    serveur.arreter()
    serveur.configurer("EXEMPLE nouveau mot de passe", "EXEMPLE nouveau code responsable")
    serveur.demarrer()
    ouvrir_connexion(page)
    dialogue(page).locator("#s-synchro").click()
    expect(dialogue(page).locator("#s-etat")).to_contain_text("refuse le mot de passe", timeout=20000)
    dialogue(page).get_by_role("button", name="Fermer").click()
    expect(page.locator("#bandeaux")).to_contain_text("refuse le mot de passe")
    expect(page.locator("#etat-synchro")).to_contain_text("accès refusé")

    # Se reconnecter avec le nouveau mot de passe remet tout en ordre.
    ouvrir_connexion(page)
    dialogue(page).locator("#s-deconnecter").click()
    dialogue(page).get_by_role("button", name="Se déconnecter").click()
    expect(page.locator("#btn-importer")).to_be_visible()
    connecter(page, serveur, equipe="EXEMPLE nouveau mot de passe")
    expect(page.locator("#bandeaux")).not_to_contain_text("refuse")
