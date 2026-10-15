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


class _Serveur(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json"}

    def log_message(self, *_args):  # pas de bruit dans la sortie des tests
        pass


class _ServeurTcp(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def demarrer_serveur():
    """Sert le dossier de l'outil sur http://127.0.0.1:<port libre>/ ; renvoie (adresse, serveur)."""
    serveur = _ServeurTcp(("127.0.0.1", 0), functools.partial(_Serveur, directory=str(RACINE)))
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

    def __init__(self, navigateur, url, **options):
        self.contexte = navigateur.new_context(locale="fr-FR", accept_downloads=True, service_workers="block", **options)
        self.erreurs = []
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
