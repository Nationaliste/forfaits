# Registre des régressions

## 2026-10-20 — « Remplacer tout » remettait d'anciens prix sans les annoncer
- Où : `index.html`, `bilanFusion` et la fenêtre « Importer ce fichier ? » (import .json).
- Bug : « Prix qui changent » ne comptait que les forfaits plus récents dans le fichier (ceux de « Mettre à jour »). Avec un fichier plus ancien, « Remplacer tout » remettait les anciens prix sans rien dire.
- À garder : `bilan.prixRemplacer` compare les prix sans regarder `maj`, et la fenêtre l'affiche quand il diffère de `bilan.prix`.
- Test : `test_remplacer_tout_annonce_les_anciens_prix`.
