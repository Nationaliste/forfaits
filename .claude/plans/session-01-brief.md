# Session 01 (15/10/2026) : passation

## État
- V1 en ligne : https://nationaliste.github.io/forfaits/ (PR #1 fusionnée). Tests verts (Chromium, Edge, Firefox), site public vérifié (recherche, hors ligne, aucune erreur console).
- Choix validés avec l'utilisateur : plusieurs magasins, PC sans droits admin + téléphones Android ; 1 ou 2 responsables modifient (« mode modification » par appareil) ; partage par fichier `.json` rangé dans le OneDrive de l'entreprise (Exporter → OneDrive → Importer, fusion « la plus récente gagne ») ; HT et TTC saisis tous les deux ; doublon de référence bloqué, même combinaison = avertissement.
- Adresse gardée avec le nom du compte (refus d'une organisation au nom neutre). Ne plus la changer : les données de chaque appareil y sont liées.
- Synchro : l'utilisateur ne veut ni passer par le service informatique (V2 Microsoft 365 abandonnée) ni de serveur. Besoin réel : une mise à jour par semaine, faite à la main (export par le responsable, import sur chaque appareil). Le bandeau « Dernier import il y a N jours » s'affiche après 7 jours.

## Reste à faire
- L'utilisateur : tester sur son Android (Chrome → « Ajouter à l'écran d'accueil »), supprimer les exemples, saisir les vrais forfaits, exporter dans le dossier OneDrive partagé.

## Pièges
- Toute autre page publiée sur nationaliste.github.io partagerait l'origine et pourrait lire les données (localStorage) : ne pas publier d'autre site Pages sur ce compte sans y penser.
- Non vérifié sur un vrai téléphone (émulation Chromium seulement), ni l'import depuis OneDrive sur Android.
- Une session parallèle avait commencé un serveur de synchro (Rust + Tailscale Funnel, branche `feat/serveur`, worktree `.claude/worktrees/serveur`) : abandonné par l'utilisateur, ne pas le fusionner.
