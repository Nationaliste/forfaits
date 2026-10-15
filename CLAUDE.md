# Forfaits : règles et pièges du projet

- Dépôt PUBLIC (site GitHub Pages) : jamais de vrais forfaits, de vrais prix ni le nom de l'entreprise. Les exports (`forfaits-*.json`, `*.csv`) et `prive/` sont ignorés par git ; ne pas forcer leur ajout.
- Après toute modification du `<script>` de `index.html` : `python outils/csp.py`, sinon le navigateur bloque le script (page vide). `test_empreinte_de_securite_a_jour` le vérifie.
- Pas de `innerHTML` : tout passe par `h()` (texte inséré comme texte).
- Validations : `python -m pytest` (Chromium, Edge, Firefox ; `NAVIGATEURS=chromium` pour aller vite), `ruff check .`, `python -m vulture . --min-confidence 80`. Les captures d'écran des tests vont dans `captures/` : les regarder après un changement visuel.
- Format des données changé : incrémenter `VERSION_FORMAT` et continuer à lire les anciens fichiers (des exports circulent dans OneDrive).
- Ne jamais changer l'adresse du site (`nationaliste.github.io/forfaits`) : les données de chaque appareil sont liées à l'adresse, tout le monde devrait réimporter.
- Les suppressions sont des marques `supprime: true` (pas de retrait) : indispensable pour que la fusion propage les suppressions.
- `sw.js` sert la copie gardée puis la met à jour : une nouvelle version s'affiche à la 2e ouverture.
- Le dossier du projet est dans OneDrive : entre deux PC, passer par git (pull/push), pas par la synchro OneDrive du dossier `.git`.
