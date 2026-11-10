# Surnoms : V1 (proposition du 29/10/2026)

## But
Retrouver un appareil ou un forfait par le nom que les techniciens lui donnent, en plus de la recherche actuelle (référence, désignation, noms d'appareils, familles), qui ne change pas.

## Deux sortes de surnoms

| | Équipe | Perso |
|---|---|---|
| Qui | responsables | tout le monde (responsables compris) |
| Appareil | appli : mode modification → Listes des éléments, champ « Surnoms » de chaque appareil | appli : Menu → Mes surnoms |
| Forfait | Excel : nouvelle colonne « Surnoms » (séparés par des virgules) ; appli : champ « Surnoms » du formulaire (mode modification) | appli : petit bouton « + Surnom » en bas de la carte |
| Partagé | oui : dans le .json exporté, puis importé par les autres postes | non : reste sur ce poste (et dans l'appli installée sur ce PC) |
| Perdu si | jamais (OneDrive) | navigateur vidé, autre poste, icône iPhone (données à part) |

Sur un poste, la recherche utilise les deux (ils s'additionnent).

## Règles
1. **Un surnom désigne une seule chose.** On refuse un surnom déjà pris (nom ou surnom d'un autre appareil, surnom d'un autre forfait), toutes familles confondues, en le disant : « « la petite » est déjà le surnom de 3Q ».
2. Une fois les espaces, majuscules et accents ignorés : au moins 2 caractères, au plus 40 caractères, et 10 surnoms au plus par appareil ou par forfait.
3. Un surnom perso identique à un surnom d'équipe de la même chose : le doublon disparaît. Si l'équipe prend ensuite ce surnom pour **autre chose**, l'équipe gagne. Le surnom perso est alors marqué « en conflit » dans Mes surnoms et ignoré par la recherche (plus d'ambiguïté).
4. Excel, comme pour la désignation : si la colonne est présente, la case **remplace** les surnoms d'équipe du forfait. Une case vide ou « / » les efface. Pas de colonne : rien ne change. Un surnom refusé (règle 1) est annoncé dans la fenêtre de confirmation et ignoré, la ligne est importée quand même.
5. Fusion entre postes : les surnoms d'équipe sont un champ de l'appareil ou du forfait, et la version la plus récente gagne (même règle que le prix).

## Recherche
- Taper le surnom entier d'un appareil (« la petite ») filtre comme son vrai nom (« 3Q »).
- Taper le début d'un surnom propose l'appareil dans les suggestions, sous la forme « 3Q — « la petite » ». Le technicien apprend ainsi le vrai nom.
- Un surnom de forfait se cherche comme la désignation (morceaux de mots acceptés).
- La carte affiche une petite ligne : « Aussi appelé : le gros pack, pack nuit ».

## Ce qui change ailleurs
- Format des données : `VERSION_FORMAT` passe à 2 (`surnoms` sur les appareils et les forfaits). Les anciens fichiers restent lus. Un poste pas encore à jour refuse un fichier v2 avec « recharge la page » : la mise à jour arrive à la 2e ouverture.
- Modèle Excel (`outils/modele_excel.py`), export CSV et `COLONNES_TABLEAU` : colonne « Surnoms », les trois ensemble.
- Aide : une ligne.

## Autocritique (zones grises traitées)
- *Un 3e bouton sur la carte écraserait la référence sur téléphone* : « + Surnom » va en bas de la carte, en petit texte, pas en haut.
- *Surnom de forfait égal au nom d'un appareil* : la recherche le prendrait pour l'appareil et ne trouverait pas le forfait. Refusé par la règle 1.
- *Deux responsables modifient les surnoms d'un même forfait en même temps* : le plus récent gagne, l'autre est perdu, comme pour un prix. C'est rare, et c'est la même règle que tout le reste.
- *Perso non sauvegardé* : c'est voulu (tu l'as choisi). À dire dans l'aide : « tes surnoms restent sur ce poste ». Avec le futur serveur (roadmap #260), ils pourront être centralisés.
- *Surnom très court (« a »)* : minimum 2 caractères.
- *Version minimale possible* : appareils seulement. Écartée, parce que tu veux aussi les forfaits.

## Fini quand
Tests : refus des doublons (appareil, forfait, perso contre équipe), recherche par surnom entier et par début, import Excel avec la colonne (remplace, efface, annonce les refus), export et réimport .json v2, lecture d'un fichier v1, perso gardé au rechargement et absent de l'export, capture sur téléphone.
