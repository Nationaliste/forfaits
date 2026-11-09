# Base de référence sécurité

Ce fichier ne porte que des **comptes**. Le détail des constats reste hors du dépôt, et les restes
sont suivis en privé : dans un dépôt public, une liste de failles serait une carte pour un attaquant.

| | |
|---|---|
| Date de la passe | 2026-11-09 |
| Commit | ed6dd1e |
| Lignes analysées | 5708 |
| Portée | tout le dépôt suivi par git, et tout l'historique des commits |

## Constats par gravité

| gravité | identité et historique | failles du code et dépendances |
|---|---|---|
| CRITICAL | 0 | 0 |
| HIGH | 2 | 0 |
| MEDIUM | 3 | 1 |
| LOW | 1 | 3 |

Outils : `scan-anonymat.mjs --complet` (1 constat `info`), `trivy fs`, `outils/csp.py`, et la lecture
complète du dépôt par deux relecteurs. Chaque constat a été recontrôlé par lecture avant d'être
retenu. Ce qui n'a pas été corrigé ici est suivi en privé.
