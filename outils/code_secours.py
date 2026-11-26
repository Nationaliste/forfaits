"""Tire un code de secours au hasard pour le cloud de mise à jour.

Le code de secours donne un accès responsable complet (il sert quand tous les appareils
responsables sont perdus) : il doit être impossible à deviner, donc tiré au hasard, jamais choisi.
29 caractères, dont 25 tirés parmi 31 (ni 0/O, ni 1/I/L) : environ 124 bits, à recopier sans
hésiter sur un téléphone.

    python outils/code_secours.py

Puis, dans le dossier cloud :  pnpm dlx wrangler@4.157.0 secret put CODE_SECOURS
et coller le code. Le garder hors du dépôt (gestionnaire de mots de passe, papier sous clé).
"""

import secrets

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
GROUPES = 5
TAILLE_GROUPE = 5


def code_secours() -> str:
    return "-".join("".join(secrets.choice(ALPHABET) for _ in range(TAILLE_GROUPE)) for _ in range(GROUPES))


if __name__ == "__main__":
    print(code_secours())
