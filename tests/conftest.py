"""Préparation des tests : petit serveur web local + navigateurs (Chromium, Edge, Firefox)."""

import functools
import http.server
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
CONNECT_SRC = b"connect-src 'self' https://*.ts.net"


class _Serveur(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json"}
    connect_src = b""  # adresse ajoutée à la CSP de la page (tests de synchro avec un serveur local)

    def do_GET(self):
        if self.connect_src and self.path.split("?")[0] in ("/", "/index.html"):
            html = (RACINE / "index.html").read_bytes()
            assert CONNECT_SRC in html, "CSP de index.html changée : mettre à jour CONNECT_SRC"
            corps = html.replace(CONNECT_SRC, CONNECT_SRC + b" " + self.connect_src)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)
            return
        super().do_GET()

    def log_message(self, *_args):  # pas de bruit dans la sortie des tests
        pass


class _ServeurTcp(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def demarrer_serveur(connect_src=""):
    """Sert le dossier de l'outil sur http://127.0.0.1:<port libre>/ ; renvoie (adresse, serveur).

    connect_src : adresse que la page a le droit d'appeler en plus (serveur de synchro local).
    """
    gestionnaire = type("_ServeurPage", (_Serveur,), {"connect_src": connect_src.encode()}) if connect_src else _Serveur
    serveur = _ServeurTcp(("127.0.0.1", 0), functools.partial(gestionnaire, directory=str(RACINE)))
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


class Appareil:
    """Un appareil (navigateur avec ses propres données) qui ouvre l'outil."""

    def __init__(self, navigateur, url, tolerer=None, **options):
        """tolerer : motif des erreurs de console attendues (ex. serveur volontairement coupé)."""
        self.contexte = navigateur.new_context(locale="fr-FR", accept_downloads=True, service_workers="block", **options)
        self.erreurs = []
        self.page = self.contexte.new_page()
        self.page.on("pageerror", lambda e: self.erreurs.append(f"pageerror: {e}"))

        def console(m):
            if m.type == "error" and not (tolerer and tolerer.search(m.text)):
                self.erreurs.append(f"console: {m.text}")

        self.page.on("console", console)
        self.page.goto(url)
        self.page.wait_for_selector("#resultats .carte")

    def fermer(self):
        self.contexte.close()


@pytest.fixture
def appareils(navigateur, url_site):
    """Fabrique d'appareils ; vérifie à la fin qu'aucune erreur n'est apparue dans la console."""
    crees = []

    def creer(url=None, **options):
        a = Appareil(navigateur, url or url_site, **options)
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
