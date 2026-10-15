"""Met à jour l'empreinte de sécurité (CSP) de index.html.

La page n'autorise que SON script, identifié par son empreinte sha256.
À relancer après chaque modification du script :  python outils/csp.py
"""

import base64
import hashlib
import pathlib
import re
import sys

PAGE = pathlib.Path(__file__).resolve().parent.parent / "index.html"
MOTIF_SCRIPT = re.compile(r"<script>(.*?)</script>", re.S)
MOTIF_EMPREINTE = re.compile(r"script-src 'sha256-[^']*'")


def empreinte(html: str) -> str:
    """Empreinte du script de la page, calculée comme le navigateur (fins de ligne en LF)."""
    scripts = MOTIF_SCRIPT.findall(html)
    if len(scripts) != 1:
        sys.exit(
            f"index.html doit contenir exactement un <script> (trouvé : {len(scripts)})"
        )
    contenu = scripts[0].replace("\r\n", "\n").replace("\r", "\n")
    return base64.b64encode(hashlib.sha256(contenu.encode("utf-8")).digest()).decode(
        "ascii"
    )


def main() -> None:
    html = PAGE.read_text(encoding="utf-8")
    nouveau = MOTIF_EMPREINTE.sub(
        f"script-src 'sha256-{empreinte(html)}'", html, count=1
    )
    if nouveau == html:
        print("Empreinte déjà à jour.")
        return
    PAGE.write_text(nouveau, encoding="utf-8", newline="")
    print("Empreinte mise à jour.")


if __name__ == "__main__":
    main()
