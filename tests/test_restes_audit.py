"""Petits restes de l'audit du 10/11/2026 (roadmap#751) : un test par correction."""

import importlib.util
import re
import shutil
import subprocess
import urllib.error
import urllib.request

import pytest
from conftest import FICHIERS_DU_SITE, RACINE
from playwright.sync_api import expect
from test_forfaits import activer_modif, dialogue


def _statut(url):
    try:
        with urllib.request.urlopen(url) as reponse:
            return reponse.status
    except urllib.error.HTTPError as erreur:
        return erreur.code


# ---------------------------------------------------------------- serveur de test


def test_serveur_de_test_ne_sert_que_les_fichiers_du_site(url_site):
    """Le dossier du projet contient prive/ (les vrais forfaits), .git, les tests : rien de cela ne doit sortir."""
    for chemin in ("", "index.html", "sw.js", "manifest.webmanifest", "icon-192.png"):
        assert _statut(url_site + chemin) == 200, chemin
    for chemin in (
        "CLAUDE.md",
        "tests/conftest.py",
        ".git/config",
        "prive/forfaits.json",
        "pyproject.toml",
        "outils/csp.py",
        "sw.js/../CLAUDE.md",
    ):
        assert _statut(url_site + chemin) == 404, chemin


def test_les_fichiers_servis_aux_tests_sont_ceux_que_le_service_worker_garde():
    """Sinon un fichier du site absent de la liste du serveur ferait échouer l'installation du service worker."""
    sw = (RACINE / "sw.js").read_text(encoding="utf-8")
    gardes = re.search(r"const FICHIERS = \[(.*?)\];", sw, re.S).group(1)
    for adresse in re.findall(r"'\./([^']*)'", gardes):
        assert "/" + adresse in FICHIERS_DU_SITE, adresse
    assert "/sw.js" in FICHIERS_DU_SITE


# ---------------------------------------------------------------- outils/csp.py


def _csp():
    spec = importlib.util.spec_from_file_location("csp_outil", RACINE / "outils" / "csp.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _page(tmp_path, csp, balise):
    page = tmp_path / "index.html"
    page.write_text(f"<html><head>{balise}</head><body><script>let x = 1;</script></body></html>", encoding="utf-8", newline="")
    csp.PAGE = page
    return page


def test_csp_refuse_une_page_sans_empreinte_au_lieu_de_dire_a_jour(tmp_path, capsys):
    csp = _csp()
    page = _page(tmp_path, csp, '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'">')
    avant = page.read_bytes()
    with pytest.raises(SystemExit) as sortie:
        csp.main()
    assert "Aucune empreinte" in str(sortie.value)
    assert "à jour" not in capsys.readouterr().out
    assert page.read_bytes() == avant


def test_csp_met_a_jour_puis_reconnait_une_page_a_jour(tmp_path, capsys):
    csp = _csp()
    page = _page(tmp_path, csp, "<meta content=\"script-src 'sha256-ancienne'\">")
    csp.main()
    assert f"script-src 'sha256-{csp.empreinte(page.read_text(encoding='utf-8'))}'" in page.read_text(encoding="utf-8")
    assert "mise à jour" in capsys.readouterr().out
    csp.main()
    assert "déjà à jour" in capsys.readouterr().out


# ---------------------------------------------------------------- .gitignore


@pytest.mark.skipif(shutil.which("git") is None, reason="git absent")
@pytest.mark.parametrize(
    "chemin",
    ["cloud/wrangler.toml", "cloud/wrangler.jsonc", "cloud/.dev.vars", "cloud/.dev.vars.staging", "cloud/.wrangler/state"],
)
def test_gitignore_couvre_la_config_privee_du_cloud(chemin):
    """Le nom réel du Worker ne doit jamais partir dans ce dépôt public, quelle que soit la forme de la config."""
    ignore = subprocess.run(["git", "check-ignore", "-q", chemin], cwd=RACINE, check=False)
    assert ignore.returncode == 0, f"{chemin} n'est pas ignoré par git"


# ---------------------------------------------------------------- interface


def test_famille_renommee_libere_son_ancien_nom_et_prend_le_nouveau(page):
    """La liste des familles était prise à l'ouverture de la fenêtre : un renommage ne la mettait pas à jour."""
    activer_modif(page)
    page.click("#btn-menu")
    page.click("#btn-listes")
    d = dialogue(page)
    famille = d.get_by_label("Nom de la famille Lumineux")  # le renommage ne redessine pas : l'étiquette reste l'ancienne
    famille.fill("Coffret")
    famille.press("Tab")
    d.locator("#nouvelle-famille").fill("Coffret")
    d.locator("#nouvelle-famille").press("Enter")
    expect(d.locator(".msg-erreur")).to_contain_text("« Coffret » existe déjà")
    d.locator("#nouvelle-famille").fill("Lumineux")
    d.locator("#nouvelle-famille").press("Enter")
    expect(d.get_by_label("Nom de la famille Lumineux", exact=True)).to_have_count(1)
    assert "existe déjà" not in (d.locator(".msg-erreur").text_content() or "")


def test_le_grossissement_du_texte_arrive_jusqu_a_l_entete_et_aux_titres_de_fenetre(page):
    """`--zoom` redéclaré sur .entete et .dlg-tete y redonnait 1 : tout ce qui s'y divise par var(--zoom) débordait."""
    page.evaluate("document.documentElement.dataset.texte = 'tres-grand'")
    zoom = "getComputedStyle(document.querySelector(%r)).getPropertyValue('--zoom').trim()"
    assert page.evaluate(zoom % ".entete") == "1.3"
    page.click("#btn-menu")
    assert page.evaluate(zoom % "dialog[open] .dlg-tete") == "1.3"


def test_fenetre_fermee_rend_le_focus_au_bouton_qui_l_avait_ouverte(page):
    """Garde-fou : les trois moteurs rendent le focus seuls (mesuré, y compris NAVIGATEURS=webkit) ; la page ne doit rien faire qui l'empêche."""
    # Au clavier : un clic de souris ne donne pas le focus au bouton dans Safari, il n'y aurait rien à rendre.
    page.focus("#btn-menu")
    page.keyboard.press("Enter")
    dialogue(page).get_by_role("button", name="Fermer").click()
    expect(page.locator("#btn-menu")).to_be_focused()
    activer_modif(page)
    page.focus("#btn-ajouter")
    page.keyboard.press("Enter")
    dialogue(page).get_by_role("button", name="Fermer").click()
    expect(page.locator("#btn-ajouter")).to_be_focused()
