# Session 03 (16/10/2026) : saisie des forfaits par Excel, sécurité d'accès

## État
- `main` : V1 en ligne, PR #1 à #21 fusionnées. `feat/serveur` reste en pause (voir `session-02-brief.md`).
- Saisie par tableau : `python outils/modele_excel.py` fabrique le modèle dans `prive/` (ignoré par git) ; Menu → « Importer (sauvegarde ou tableau Excel) » lit un « CSV UTF-8 ».
  - Les colonnes sont lues par leur titre (ordre libre) ; « / » ou case vide = pas de données ; un forfait peut n'avoir aucun élément (dash cam…).
  - Colonne inconnue = nouvelle famille (10 au maximum) ; élément inconnu = créé ; tout est annoncé dans la fenêtre avant validation, rien n'est créé si on annule.
  - Une référence qui existe déjà est mise à jour (même identifiant), jamais dupliquée. Tout ou rien, avec les numéros de ligne en cas d'erreur.
- Fichiers de l'utilisateur dans `prive/` : `Forfaits-a-remplir.xlsx` est son fichier de travail (ancien agencement, 4 lignes saisies au 16/10 11:43) ; `Forfaits-a-remplir-v3.xlsx` est le nouveau modèle vierge (Boîtier et Installation à droite, listes qui avertissent au lieu de bloquer).
- Essai à blanc de ses 4 lignes sur le site publié, dans un navigateur jetable : 4 nouveaux, aucun avertissement, aucune erreur. Le CSV prêt à importer est `prive/forfaits-a-importer.csv`. Pas encore importé sur un appareil de l'utilisateur (son navigateur de tous les jours n'est pas connu).
- Sécurité : la page publique ne contient aucun prix, donc rien à protéger de ce côté. Ce qui est à protéger : le navigateur de chaque appareil et le `.json` sur OneDrive (droits OneDrive de l'entreprise). Un lien secret ne peut pas fermer un site statique public. La vraie réponse est l'appairage d'appareil par lien ou QR à usage unique, qui demande le serveur : [roadmap#265](https://github.com/Nationaliste/roadmap/issues/265). La page `prive/serveur-pour-le-patron.md` le présente.

## Reste à faire
- L'utilisateur : importer le tableau sur UN seul appareil (« Importer et supprimer les exemples »), exporter le `.json` dans OneDrive ; les autres appareils importent ce `.json`.
- « Supprime les anciens éléments de test » : l'utilisateur a répondu « tu peux tout virer » (16/10). Fait : tous les éléments de départ sont marqués exemples dans `donneesInitiales()` ; « Supprimer les exemples » (et « Importer et supprimer les exemples ») les retire avec les forfaits d'exemple, sauf ceux qu'un vrai forfait utilise ou que l'utilisateur a renommés (maj > 0) ; sur un appareil d'avant, les éléments de départ jamais modifiés (maj 0) partent aussi. Les listes du modèle Excel sont vides. Un appareil qui a déjà supprimé ses exemples garde ses éléments de départ : les retirer avec le ✕ de l'écran des éléments.
- Décider l'adresse avec le patron AVANT de saisir les vrais forfaits : les données de chaque appareil sont liées à l'adresse (un export `.json` permet de tout reprendre si elle change).
- Décision du patron sur le serveur ; fermer à la main roadmap#258 (V2 Microsoft 365, plus prévue).
- `feat/serveur` a besoin des PR #10, #12, #13, #15 et #17 avant sa propre PR.

## Pièges
- Ne JAMAIS écraser `prive/Forfaits-a-remplir.xlsx` : c'est la saisie de l'utilisateur. Pour passer au nouveau modèle, recopier ses lignes par titre de colonne (un copier-coller de cellules de famille décalerait les colonnes).
- Importer le même tableau sur deux appareils crée des identifiants différents, donc des doublons de référence ; les familles nouvelles seraient aussi créées en double. Un seul appareil importe, les autres prennent le `.json`.
- Toute colonne en trop dans le tableau (un prix d'achat par exemple) devient une famille : lire la liste annoncée dans la fenêtre de confirmation avant de valider.
- Deux titres presque identiques (« Dash cam » et « Dash-cam ») : la seconde colonne est ignorée sans message.
- Dépôt public : jamais de vraies références, de vrais prix ni le nom de l'entreprise dans une note, un test ou une PR.
- Non essayé sur le PC du boulot.
