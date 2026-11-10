"""Préparation des tests : petit serveur web local + navigateurs (Chromium, Edge, Firefox)."""

import functools
import http.server
import io
import os
import pathlib
import socketserver
import threading

import pytest
from playwright.sync_api import sync_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent
CAPTURES = RACINE / "captures"
# NAVIGATEURS=chromium pour aller plus vite pendant le développement
NAVIGATEURS = os.environ.get("NAVIGATEURS", "chromium,msedge,firefox").split(",")


class _Serveur(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json"}

    def log_message(self, *_args):  # pas de bruit dans la sortie des tests
        pass

    def send_head(self):
        if self.server.page_lente and self.path.split("?")[0] == "/sw.js":
            # Le service worker du dépôt, qui répond à une demande de page avec un peu de retard (voir _ServeurTcp).
            sw = (RACINE / "sw.js").read_text(encoding="utf-8")
            assert sw.count(REPONSE_SW) == 1, "sw.js changé : mettre à jour REPONSE_SW"
            corps = sw.replace(REPONSE_SW, ATTENTE_SW + REPONSE_SW).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            return io.BytesIO(corps)
        marque = self.server.marque
        if marque is None or not self.path.split("?")[0].endswith(("/", "/index.html")):
            return super().send_head()
        # La page part avec sa version écrite dedans : un test peut ainsi dire laquelle le service worker a servie.
        balise = f'<head><meta name="marque" content="{marque["version"]}">'.encode()
        corps = (RACINE / "index.html").read_bytes().replace(b"<head>", balise, 1)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        return io.BytesIO(corps)

    def end_headers(self):
        # Sans cela, Firefox recharge la page hors ligne depuis son cache HTTP : le test du service worker ne prouverait rien.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class _ServeurTcp(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True
    marque = None
    # True (posé par le test juste après demarrer_serveur) : la page demandée arrive 150 ms plus tard, donc à coup sûr
    # après que le service worker a rangé la nouvelle copie. Sur un vrai appareil c'est une affaire de millisecondes.
    page_lente = False


# Le retard se place APRÈS la lecture de la copie gardée : la page reçoit bien l'ancienne copie, mais en retard.
REPONSE_SW = "    if (gardee) return gardee;\n"
ATTENTE_SW = "    if (gardee && requete.mode === 'navigate') await new Promise((fin) => setTimeout(fin, 150));\n"


def demarrer_serveur(marque=None):
    """Sert le dossier de l'outil sur http://127.0.0.1:<port libre>/ ; renvoie (adresse, serveur).

    `marque` ({"version": "v1"}, que le test change en cours de route) : la page part avec une balise
    `<meta name="marque">` qui porte cette version, comme si une nouvelle version venait d'être mise en ligne.
    """
    serveur = _ServeurTcp(("127.0.0.1", 0), functools.partial(_Serveur, directory=str(RACINE)))
    serveur.marque = marque
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{serveur.server_address[1]}/", serveur


@pytest.fixture(scope="session")
def url_site():
    url, serveur = demarrer_serveur()
    yield url
    serveur.shutdown()
    serveur.server_close()


@pytest.fixture(scope="session")
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session", params=NAVIGATEURS)
def navigateur(request, pw):
    nom = request.param
    try:
        b = pw.chromium.launch(channel="msedge") if nom == "msedge" else getattr(pw, nom).launch()
    except Exception as exc:  # navigateur absent de la machine
        pytest.skip(f"{nom} indisponible : {exc}")
    b.nom = nom
    yield b
    b.close()


# Les cartes sont repliées par défaut (réglage de l'appareil). La plupart des tests lisent et
# cliquent dans le détail des cartes : ils demandent « cartes entières » avant le chargement.
CARTES_ENTIERES = """try {
  const cle = ['forfaits', 'appareil', 'v1'].join('.');
  const regl = JSON.parse(localStorage.getItem(cle) || '{}');
  regl.compact = false;
  localStorage.setItem(cle, JSON.stringify(regl));
} catch {}"""


class Appareil:
    """Un appareil (navigateur avec ses propres données) qui ouvre l'outil."""

    def __init__(self, navigateur, url, compact=False, **options):
        self.contexte = navigateur.new_context(locale="fr-FR", accept_downloads=True, service_workers="block", **options)
        if not compact:
            self.contexte.add_init_script(CARTES_ENTIERES)
        self.erreurs = []
        # Le choix du dossier d'export (Edge, Chrome) ouvrirait une fenêtre : les tests prennent le téléchargement,
        # et test_export_dans_le_dossier_choisi remplace ce choix par un faux.
        self.contexte.add_init_script(
            "Object.defineProperty(window, 'showSaveFilePicker', { value: undefined, writable: true, configurable: true })"
        )
        self.page = self.contexte.new_page()
        self.page.on("pageerror", lambda e: self.erreurs.append(f"pageerror: {e}"))
        self.page.on("console", lambda m: self.erreurs.append(f"console: {m.text}") if m.type == "error" else None)
        self.page.goto(url)
        self.page.wait_for_selector("#resultats .carte")

    def fermer(self):
        self.contexte.close()


@pytest.fixture
def appareils(navigateur, url_site):
    """Fabrique d'appareils ; vérifie à la fin qu'aucune erreur n'est apparue dans la console."""
    crees = []

    def creer(**options):
        a = Appareil(navigateur, url_site, **options)
        crees.append(a)
        return a

    yield creer
    erreurs = [e for a in crees for e in a.erreurs]
    for a in crees:
        a.fermer()
    assert not erreurs, erreurs


@pytest.fixture
def page(appareils):
    return appareils().page
