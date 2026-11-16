# Product

## Platform

web

## Users

- Vendeurs au comptoir, sur PC (Edge, Chrome ou Firefox). La fenêtre de l'outil est tantôt en plein écran, tantôt sur une moitié d'écran à côté d'un autre logiciel.
- Techniciens, sur téléphone Android, souvent debout et d'une main. Ils cherchent un forfait par son nom ou par ses éléments, pas par sa référence.
- Des responsables qui ajoutent, modifient et suppriment (mode modification, par appareil). Tous les autres consultent.

## Product Purpose

Retrouver en quelques secondes un forfait (un assemblage d'éléments : taximètre, boîtier, imprimante, lumineux, pose) et donner son prix au client. Réussi quand le bon forfait et son prix TTC sont à l'écran sans défiler, et que la référence se copie ou que le forfait s'ajoute au total d'un seul geste.

## Positioning

Un seul fichier HTML, sans compte ni mot de passe, qui marche sans internet. Les données restent sur chaque appareil et se partagent par un fichier exporté.

## Operating Context

- Au comptoir, pendant qu'un client attend : l'outil sert des dizaines de fois par jour, pour la même poignée de gestes (chercher, lire le prix, copier la référence, additionner plusieurs forfaits).
- La référence sert aux vendeurs ; le nom et les éléments servent aux techniciens.
- Le TTC est le prix qu'on annonce au client ; le HT reste lisible à côté.

## Capabilities and Constraints

- Recherche par référence, nom, élément ou surnom ; filtres par famille d'éléments ; tri ; favoris ; derniers consultés ; total de plusieurs lignes ; surnoms perso et d'équipe ; import et export ; mode modification.
- Les réglages d'affichage (thème, taille du texte, ordre des filtres, tri) sont propres à chaque appareil et ne s'exportent jamais.
- Afficher est ouvert à tout le monde ; modifier les données partagées est réservé au mode modification.
- Dans un forfait, l'ordre de lecture est fixé : le nom, puis les éléments, puis le prix, la référence en dernier.
- Aucune ressource en ligne : polices déjà présentes sur l'appareil, aucun service externe.
- Les règles et pièges techniques sont dans `CLAUDE.md`.

## Brand Commitments

- Deux thèmes de couleur, sombre (noir dominant) et clair, avec le rouge en accent : les palettes de `:root` dans `index.html` ne changent pas. L'en-tête et les titres de fenêtre restent noirs dans les deux thèmes ; le champ de recherche reste blanc.
- Tutoiement, phrases courtes, mots du comptoir (forfait, élément, référence, surnom).

## Evidence on Hand

- Les données de départ sont des exemples aux noms et aux prix inventés. Aucun vrai forfait, vrai prix ni vrai nom de produit n'existe dans le dépôt, et aucun ne doit y être écrit.

## Product Principles

1. Le forfait cherché et son prix d'abord : tout ce qui n'est pas la liste cède la place.
2. Un geste pour ce qu'on fait cinquante fois par jour.
3. Le même outil du PC au téléphone : mêmes mots, mêmes gestes, même ordre de lecture.
4. Rien ne bouge sous le doigt.

## Accessibility & Inclusion

- Taille du texte réglable par appareil (normal, grand, très grand) ; zones d'appui d'au moins 44 px ; contrastes mesurés par les tests pour chaque thème.
