"""Préparation des tests : petit serveur web local + navigateurs (Chromium, Edge, Firefox)."""

import functools
import http.server
import io
import json
import os
import pathlib
import re
import shutil
import socket
import socketserver
import subprocess
import threading
import urllib.error
import urllib.request

import pytest
from playwright.sync_api import sync_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent
CAPTURES = RACINE / "captures"
# NAVIGATEURS=chromium pour aller plus vite pendant le développement
NAVIGATEURS = os.environ.get("NAVIGATEURS", "chromium,msedge,firefox").split(",")
# La page n'a le droit d'appeler que le cloud de l'équipe (CSP). Pour les tests, le cloud tourne en
# local : la page est servie avec cette adresse ajoutée à sa CSP (un en-tête ne pourrait que la
# resserrer, pas l'élargir).
CONNECT_SRC = b"connect-src 'self' https://*.a-remplir.workers.dev"
WRANGLER = "wrangler@4.157.0"
CODE_SECOURS = "code-de-secours-des-tests"


class _Serveur(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json"}
    connect_src = b""  # adresse ajoutée à la CSP de la page (tests de mise à jour avec un cloud local)

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


def demarrer_serveur(marque=None, connect_src=""):
    """Sert le dossier de l'outil sur http://127.0.0.1:<port libre>/ ; renvoie (adresse, serveur).

    `marque` ({"version": "v1"}, que le test change en cours de route) : la page part avec une balise
    `<meta name="marque">` qui porte cette version, comme si une nouvelle version venait d'être mise en ligne.
    connect_src : adresse que la page a le droit d'appeler en plus (le cloud local).
    """
    gestionnaire = _Serveur
    if connect_src:
        gestionnaire = type("_ServeurPage", (_Serveur,), {"connect_src": connect_src.encode()})
    serveur = _ServeurTcp(("127.0.0.1", 0), functools.partial(gestionnaire, directory=str(RACINE)))
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

    def __init__(self, navigateur, url, compact=False, tolerer=None, **options):
        """tolerer : motif des erreurs de console attendues (ex. cloud volontairement coupé)."""
        self.contexte = navigateur.new_context(locale="fr-FR", accept_downloads=True, service_workers="block", **options)
        if not compact:
            self.contexte.add_init_script(CARTES_ENTIERES)
        self.erreurs = []
        self.tolerer = re.compile(tolerer) if tolerer else None
        # Le choix du dossier d'export (Edge, Chrome) ouvrirait une fenêtre : les tests prennent le téléchargement,
        # et test_export_dans_le_dossier_choisi remplace ce choix par un faux.
        self.contexte.add_init_script(
            "Object.defineProperty(window, 'showSaveFilePicker', { value: undefined, writable: true, configurable: true })"
        )
        self.page = self.contexte.new_page()
        self.page.on("pageerror", lambda e: self._noter(f"pageerror: {e}"))
        self.page.on("console", lambda m: self._noter(f"console: {m.text}") if m.type == "error" else None)
        self.page.goto(url)
        self.page.wait_for_selector("#resultats .carte")

    def _noter(self, texte):
        if not (self.tolerer and self.tolerer.search(texte)):
            self.erreurs.append(texte)

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


# --------------------------------------------------------- mise à jour automatique


def _port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def appel_cloud(adresse, chemin, methode="GET", corps=None, jeton=None, code_secours=None):
    """Appelle le cloud comme le ferait la page (l'origine est contrôlée par le Worker)."""
    entetes = {"Origin": "http://127.0.0.1:1"}
    if jeton:
        entetes["Authorization"] = "Bearer " + jeton
    if corps is not None:
        entetes["Content-Type"] = "application/json"
    if code_secours:
        entetes["X-Code-Secours"] = code_secours
    donnees = json.dumps(corps).encode() if corps is not None else None
    requete = urllib.request.Request(adresse + chemin, data=donnees, headers=entetes, method=methode)
    try:
        with urllib.request.urlopen(requete, timeout=20) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}")


@pytest.fixture(scope="session")
def cloud():
    """Le vrai Worker et son Durable Object, lancés en local par wrangler (ni compte ni réseau)."""
    if not shutil.which("pnpm"):
        pytest.skip("pnpm absent : le cloud ne peut pas être lancé")
    port = _port_libre()
    adresse = f"http://127.0.0.1:{port}"
    commande = (
        f"pnpm dlx {WRANGLER} dev --port {port} --inspector-port {_port_libre()} "
        f"--var DEV:1 --var CODE_SECOURS:{CODE_SECOURS}"
    )
    journal = (RACINE / "captures" / "wrangler-tests.log").open("w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        commande, shell=True, cwd=str(RACINE / "cloud"), stdout=journal, stderr=subprocess.STDOUT,
        env={**os.environ, "CI": "1"},
    )
    try:
        for _ in range(120):  # jusqu'à 2 min : le premier pnpm dlx télécharge wrangler
            if proc.poll() is not None:
                journal.close()
                pytest.skip("wrangler n'a pas démarré (voir captures/wrangler-tests.log)")
            try:
                appel_cloud(adresse, "/api/donnees")
                break
            except OSError:
                threading.Event().wait(1)
        else:
            pytest.skip("wrangler n'a pas répondu (voir captures/wrangler-tests.log)")
        yield adresse
    finally:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
        else:
            proc.terminate()
        proc.wait(timeout=30)
        journal.close()


@pytest.fixture
def cloud_vide(cloud):
    """Un cloud sans rien : chaque test repart du même état."""
    statut, rep = appel_cloud(cloud, "/api/initialiser", "POST", {"code_secours": CODE_SECOURS}, code_secours=CODE_SECOURS)
    assert statut == 200, rep
    appel_cloud(cloud, "/api/tout", "DELETE", jeton=rep["jeton"], code_secours=CODE_SECOURS)
    return cloud


@pytest.fixture(scope="session")
def url_site_cloud(cloud):
    """La page, servie avec le droit d'appeler le cloud local."""
    url, serveur = demarrer_serveur(connect_src=cloud)
    yield url
    serveur.shutdown()
    serveur.server_close()


@pytest.fixture
def appareils_maj(navigateur, url_site_cloud):
    """Comme « appareils », mais sur la page autorisée à joindre le cloud."""
    crees = []

    def creer(**options):
        a = Appareil(navigateur, url_site_cloud, **options)
        crees.append(a)
        return a

    yield creer
    erreurs = [e for a in crees for e in a.erreurs]
    for a in crees:
        a.fermer()
    assert not erreurs, erreurs
