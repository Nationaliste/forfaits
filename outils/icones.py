"""Dessine les icônes de l'outil (loupe rouge et damier sur fond noir).

À relancer seulement pour changer le dessin :  python outils/icones.py
"""

import pathlib

from PIL import Image, ImageDraw

RACINE = pathlib.Path(__file__).resolve().parent.parent
NOIR = (0, 0, 0)
ROUGE = (227, 6, 19)  # = --rouge de index.html (#e30613)
BLANC = (255, 255, 255)
GRAND = 1024  # dessin en grand, puis réduit : bords plus nets


def dessiner(marge: float) -> Image.Image:
    """Dessine l'icône ; `marge` = part laissée libre au bord (zone de sécurité Android)."""
    img = Image.new("RGB", (GRAND, GRAND), NOIR)
    d = ImageDraw.Draw(img)
    utile = GRAND * (1 - 2 * marge)
    x0 = y0 = GRAND * marge

    # Bande en damier rouge et noir en bas
    case = utile / 8
    haut_damier = y0 + utile - 2 * case
    for ligne in range(2):
        for col in range(8):
            if (ligne + col) % 2 == 0:
                gauche = x0 + col * case
                dessus = haut_damier + ligne * case
                d.rectangle([gauche, dessus, gauche + case, dessus + case], fill=ROUGE)

    # Loupe : verre rouge cerclé de blanc + manche blanc
    cx, cy = x0 + utile * 0.43, y0 + utile * 0.36
    rayon = utile * 0.26
    epaisseur = utile * 0.075
    manche_fin = (x0 + utile * 0.80, y0 + utile * 0.70)
    d.line(
        [(cx + rayon * 0.6, cy + rayon * 0.6), manche_fin],
        fill=BLANC,
        width=round(epaisseur * 1.5),
    )
    d.ellipse([cx - rayon, cy - rayon, cx + rayon, cy + rayon], fill=BLANC)
    interieur = rayon - epaisseur
    d.ellipse(
        [cx - interieur, cy - interieur, cx + interieur, cy + interieur], fill=ROUGE
    )
    return img


def main() -> None:
    normale = dessiner(marge=0.06)
    for taille in (192, 512):
        normale.resize((taille, taille), Image.LANCZOS).save(
            RACINE / f"icon-{taille}.png", optimize=True
        )
    # Version « maskable » : Android peut la découper en rond, le dessin reste dans le centre.
    dessiner(marge=0.16).resize((512, 512), Image.LANCZOS).save(
        RACINE / "icon-maskable-512.png", optimize=True
    )
    print("Icônes écrites.")


if __name__ == "__main__":
    main()
