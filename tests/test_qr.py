"""Le QR du lien d'appairage, comparé module par module à une bibliothèque de référence.

L'outil n'a aucune dépendance : son encodeur QR est écrit dans la page. Un QR faux ne se verrait
qu'au magasin, l'appareil photo refusant de lire. On compare donc chaque module de chaque matrice
à celle de `qrcode` (bibliothèque Python dérivée de l'implémentation de référence), pour les
8 masques, sur des liens qui couvrent les versions 1 à 10.

Deux choses que la comparaison a apprises, et qui expliquent la forme de ce fichier :
- `segno` ajoute un octet de remplissage de trop quand le flux de bits tombe pile sur un octet
  (`8 - longueur % 8` vaut 8 au lieu de 0, encoder.py `write_padding_bits`), ce qui arrive toujours
  en mode octets. Son QR reste lisible (le lecteur s'arrête au terminateur) mais ses modules ne
  sont pas ceux du standard : il ne sert ici que de deuxième avis sur le cas où il n'y a aucun
  remplissage (capacité remplie à l'octet près).
- Le masque retenu est une optimisation de lisibilité, pas une obligation : `segno` et `qrcode` ne
  choisissent pas toujours le même. On vérifie donc le choix de la page contre les 4 pénalités du
  standard réécrites ici, pas contre une bibliothèque.

Sauté si `qrcode` est absent (`pip install qrcode`), comme les tests du modèle Excel sans openpyxl.
"""

import pytest

qrcode = pytest.importorskip("qrcode", reason="qrcode absent : pip install qrcode")

# Des liens de longueurs variées : versions 1, 3, 6, 7, 8 et 10 (les versions 7 et plus portent en
# plus les 18 bits d'information de version, qui ont leur propre code correcteur).
LIENS = [
    "forfaits",
    "https://nationaliste.github.io/forfaits/",
    "Clé d'équipe, accents compris : éèàçù — " + "x" * 40,
    "http://127.0.0.1:60985/#maj=127.0.0.1:60922&inv=" + "k" * 22 + "&cle=" + "c" * 43,
    "https://nationaliste.github.io/forfaits/#maj=exemple.compte.workers.dev&inv=" + "q" * 22 + "&cle=" + "z" * 43,
    "x" * 213,  # la plus grande version acceptée (10), remplie au module près
]


def reference(texte, masque):
    """La matrice de `qrcode` : mêmes réglages que la page (mode octets, correction M)."""
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0, box_size=1)
    q.add_data(qrcode.util.QRData(texte.encode(), mode=qrcode.util.MODE_8BIT_BYTE))
    q.best_fit()
    q.makeImpl(False, masque)
    return [[1 if v else 0 for v in ligne] for ligne in q.modules]


def penalite(m):
    """Les 4 pénalités du standard (ISO/IEC 18004, 7.8.3), réécrites pour juger le choix du masque."""
    taille = len(m)
    total = 0
    # 1. Suites de 5 modules ou plus de la même couleur, en ligne et en colonne.
    for i in range(taille):
        for ligne in (m[i], [m[j][i] for j in range(taille)]):
            suite = 1
            for j in range(1, taille):
                suite = suite + 1 if ligne[j] == ligne[j - 1] else 1
                if suite == 5:
                    total += 3
                elif suite > 5:
                    total += 1
    # 2. Chaque carré de 2x2 d'une seule couleur.
    for l in range(taille - 1):  # noqa: E741
        for c in range(taille - 1):
            if m[l][c] == m[l][c + 1] == m[l + 1][c] == m[l + 1][c + 1]:
                total += 3
    # 3. Le motif 1:1:3:1:1 bordé de 4 modules clairs, qui imite une cible d'angle.
    for i in range(taille):
        for ligne in (m[i], [m[j][i] for j in range(taille)]):
            texte = "".join(str(v) for v in ligne)
            for motif in ("10111010000", "00001011101"):
                debut = texte.find(motif)
                while debut != -1:
                    total += 40
                    debut = texte.find(motif, debut + 1)
    # 4. Écart à 50 % de modules sombres.
    sombres = sum(sum(ligne) for ligne in m)
    total += abs(sombres * 100 / (taille * taille) - 50) // 5 * 10
    return total


def test_les_liens_couvrent_les_versions_1_a_10():
    """Sinon le test passerait sans jamais vérifier l'information de version (7 et plus)."""
    versions = sorted({(len(reference(lien, 0)) - 17) // 4 for lien in LIENS})
    assert versions == [1, 3, 6, 7, 8, 10]


def test_les_8_masques_de_la_page_sont_ceux_de_la_reference(appareils):
    page = appareils().page
    for lien in LIENS:
        for masque in range(8):
            obtenu = page.evaluate("([t, m]) => window.qrMatrice(t, m)", [lien, masque])
            assert obtenu == reference(lien, masque), f"masque {masque}, lien de {len(lien.encode())} octets"


def test_la_page_retient_le_masque_le_moins_penalise(appareils):
    page = appareils().page
    for lien in LIENS:
        essais = [page.evaluate("([t, m]) => window.qrMatrice(t, m)", [lien, m]) for m in range(8)]
        attendu = min(range(8), key=lambda m: (penalite(essais[m]), m))
        retenu = page.evaluate("(t) => window.qrMatrice(t)", lien)
        assert retenu == essais[attendu], f"lien de {len(lien.encode())} octets : masque {attendu} attendu"


def test_segno_donne_la_meme_matrice_quand_il_n_y_a_aucun_remplissage(appareils):
    """Deuxième avis, sur le seul cas où segno ne pose pas son octet de remplissage en trop."""
    segno = pytest.importorskip("segno", reason="segno absent : pip install segno")
    lien = "x" * 213
    page = appareils().page
    for masque in range(8):
        attendu = segno.make(lien, error="m", mode="byte", micro=False, boost_error=False, mask=masque)
        obtenu = page.evaluate("([t, m]) => window.qrMatrice(t, m)", [lien, masque])
        assert obtenu == [list(ligne) for ligne in attendu.matrix], f"masque {masque}"


def test_un_lien_trop_long_n_affiche_pas_de_qr(appareils):
    """Au-delà de la version 10, un QR demanderait une photo nette : on s'en tient au collage."""
    page = appareils().page
    assert page.evaluate("() => window.qrMatrice('x'.repeat(214))") is None


def test_le_dessin_est_noir_sur_blanc_avec_sa_marge(appareils):
    """Un QR inversé, ou collé au bord, ne se lit pas : les deux se voient dans les pixels."""
    page = appareils().page
    vu = page.evaluate("""() => {
        const toile = window.qrCanvas('forfaits', 6);
        const ctx = toile.getContext('2d');
        const px = (x, y) => Array.from(ctx.getImageData(x, y, 1, 1).data).slice(0, 3).join(',');
        return {
            cote: toile.width,
            marge: px(3, 3),            // dans la marge blanche (4 modules de 6 pixels)
            cible: px(26, 26),          // au cœur de la cible d'angle haut-gauche
            classe: toile.className,
        };
    }""")
    assert vu["cote"] == (21 + 8) * 6  # version 1 plus 4 modules de marge de chaque côté
    assert vu["marge"] == "255,255,255"
    assert vu["cible"] == "0,0,0"
    assert vu["classe"] == "qr"
