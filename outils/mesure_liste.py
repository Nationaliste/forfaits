"""Mesure le temps d'ouverture et de frappe dans la recherche avec beaucoup de forfaits inventés.

Chromium sans fenêtre. Usage : python outils/mesure_liste.py [nombre de forfaits, 5000 par défaut]
Sert à choisir combien de rangées la liste rend d'abord (LIGNES_LISTE dans index.html).
"""

import pathlib
import statistics
import sys
import tempfile
import time

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "tests"))

from conftest import demarrer_serveur  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from test_forfaits import exporter_json  # noqa: E402

CLE_DONNEES = ".".join(["forfaits", "donnees", "v1"])
FRAPPES = ["z", "zo", "zor", "zorb", "zorba", "zorb", "zor", "zo", "z", "", "1", "11", "114", "1140", "", "t1", "t1 3q", ""]


def donnees_inventees(depart, nombre):
    """Les données de départ, complétées jusqu'à `nombre` forfaits aux éléments tirés des listes de départ."""
    familles = [f for f in depart["familles"] if not f.get("supprime")]
    deja = sum(not f.get("supprime") for f in depart["forfaits"])
    elements = [e for e in depart["elements"] if not e.get("supprime")]
    par_famille = {f["id"]: [e["id"] for e in elements if e["familleId"] == f["id"]] for f in familles}
    forfaits = []
    for i in range(nombre - deja):
        choix = {fid: ids[(i * (k + 3)) % len(ids)] for k, (fid, ids) in enumerate(par_famille.items()) if ids and (i + k) % 3}
        ht = 10_000 + (i * 137) % 900_000
        forfaits.append({
            "id": f"fft-mesure-{i:05d}", "ref": f"MES-{i:05d}", "designation": f"Forfait de mesure numéro {i} Kalpo",
            "elements": choix, "ht": ht, "ttc": round(ht * 1.2), "maj": 1_700_000_000_000,
        })  # fmt: skip
    return {**depart, "forfaits": depart["forfaits"] + forfaits}


def mesurer(nombre):
    url, serveur = demarrer_serveur()
    with sync_playwright() as p, tempfile.TemporaryDirectory() as dossier:
        navigateur = p.chromium.launch()
        contexte = navigateur.new_context(locale="fr-FR", accept_downloads=True, service_workers="block")
        contexte.add_init_script("Object.defineProperty(window, 'showSaveFilePicker', { value: undefined, writable: true })")
        page = contexte.new_page()
        page.goto(url)
        page.wait_for_selector("#resultats .carte")
        depart = exporter_json(page, pathlib.Path(dossier) / "depart.json")
        donnees = donnees_inventees(depart, nombre)
        page.evaluate("([cle, d]) => localStorage.setItem(cle, JSON.stringify(d))", [CLE_DONNEES, donnees])
        ouvertures = []
        for _ in range(3):
            debut = time.perf_counter()
            page.reload(wait_until="load")
            page.wait_for_selector("#resultats .carte")
            page.evaluate("() => new Promise((fin) => requestAnimationFrame(() => setTimeout(fin, 0)))")
            ouvertures.append(time.perf_counter() - debut)
        page.focus("#recherche")
        frappes = page.evaluate(
            """async (frappes) => {
                const champ = document.getElementById('recherche');
                const temps = [];
                for (const t of frappes) {
                    const debut = performance.now();
                    champ.value = t;
                    champ.dispatchEvent(new Event('input'));
                    await new Promise((fin) => requestAnimationFrame(() => setTimeout(fin, 0)));
                    temps.push(performance.now() - debut);
                }
                return temps;
            }""",
            FRAPPES,
        )
        rangees = page.locator("#resultats .carte").count()
        navigateur.close()
    serveur.shutdown()
    serveur.server_close()
    print(f"{nombre} forfaits, {rangees} rangées rendues (recherche vide)")
    print(f"ouverture : {', '.join(f'{t:.2f} s' for t in ouvertures)} (médiane {statistics.median(ouvertures):.2f} s)")
    print(f"frappe : médiane {statistics.median(frappes):.0f} ms, pire {max(frappes):.0f} ms")
    print("  " + ", ".join(f"«{t}» {ms:.0f}" for t, ms in zip(FRAPPES, frappes, strict=True)))


if __name__ == "__main__":
    mesurer(int(sys.argv[1]) if len(sys.argv) > 1 else 5000)
