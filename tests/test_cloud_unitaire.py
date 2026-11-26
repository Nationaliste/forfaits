"""Le Durable Object seul, dans Node (tests/cloud_unitaire.mjs) : frein par source et historique d'avant.

Ces cas ne se préparent pas contre le Worker lancé par wrangler : il ne laisse pas choisir l'adresse de
l'appelant, et son historique est toujours écrit par la version du code en cours.
"""

import json
import shutil
import subprocess

import pytest
from conftest import RACINE


@pytest.fixture(scope="module")
def constats():
    if not shutil.which("node"):
        pytest.skip("node absent : les essais du Durable Object seul ne peuvent pas tourner")
    sortie = subprocess.run(
        ["node", str(RACINE / "tests" / "cloud_unitaire.mjs")], capture_output=True, text=True, timeout=60, check=False
    )
    assert sortie.returncode == 0, sortie.stderr
    return json.loads(sortie.stdout)


def test_une_adresse_ipv6_est_freinee_avec_tout_son_64(constats):
    """Chaque box reçoit au moins un /64 : changer d'adresse à l'intérieur ne doit pas remettre le seau à plein."""
    assert constats["ipv6_epuisee"] == 429
    assert constats["ipv6_meme_64"] == 429
    assert constats["ipv6_autre_64"] != 429


def test_remplir_la_memoire_du_frein_ne_libere_pas_une_source_epuisee(constats):
    """Au-delà de 200 sources, le frein vidait toute sa mémoire : 200 adresses suffisaient à repartir à plein."""
    assert constats["epuisee_avant"] == 429
    assert constats["epuisee_apres"] == 429


def test_les_versions_d_avant_la_taille_memorisee_restent_listees(constats):
    """roadmap 574 : la taille est notée à l'envoi ; une entrée d'avant (numéro seul) se lit encore dans son paquet."""
    assert constats["envoi"] == 200
    assert [(v["version"], v["taille"], v["par"]) for v in constats["versions"]] == [
        (3, 120, "Patron"),
        (2, 90, "Ancien"),
        (1, 60, "Ancien"),
    ]
    assert constats["hist"][:2] == [1, 2]
    assert constats["hist"][2]["v"] == 3 and constats["hist"][2]["taille"] == 120


def test_le_blocage_du_code_de_secours_ne_vise_que_la_source_qui_se_trompe(constats):
    """Compteur commun : 5 essais vides, sans jeton, puis un par attente, et plus personne ne pouvait récupérer."""
    assert constats["secours_meme_source"] == 429
    assert constats["secours_meme_64"] == 401  # première erreur de cette source-là
    assert constats["secours_ipv6_bloquee"] == 429  # tout son /64
    assert constats["secours_autre_source"] == 200
