# Packs : V1 vérifiée (09/11/2026)

## Ce que tu as demandé

Pouvoir assembler plusieurs forfaits, en quantités libres, dans un seul « pack » qui porte un nom et
affiche le détail et le prix total — depuis Excel ou depuis l'appli, et simplement, y compris au
doigt. Ton exemple : A à 100 €, B à 50 €, assemblés dans C qui vaut 150 € avec le détail visible.

## Ce que l'enquête a établi (vérifié dans le code, pas supposé)

| Fait | Où | Conséquence |
|---|---|---|
| Un forfait range ses éléments dans une table **famille → UN SEUL élément** | `index.html:882-885` | « A + B » ne peut PAS s'écrire avec `elements` : deux forfaits qui ont tous les deux un taximètre s'écraseraient. Et il n'y a aucune quantité. Il faut donc un champ nouveau. |
| Seuls les forfaits portent un prix (`ht`, `ttc`, en centimes) ; les éléments n'en ont aucun | `index.html:878` (élément), `index.html:890-896` (forfait) | Un pack assemble des **forfaits**. C'est ta réponse du 09/11. |
| **Le « Total » est déjà un assembleur de packs** | `ajouterAuTotal` `index.html:1700`, `ouvrirTotal` `1714`, `lireLigneTotal` `963` | Lignes `{id, nom, qte, ht, ttc}`, quantité par − et +, lignes libres (nom + prix tapés), somme HT et TTC qui se met à jour, 50 lignes, 99 par ligne. Déjà éprouvé au doigt, et tu t'en sers. **Il ne manque que trois choses : un nom, une place dans les données partagées, et la recherche.** |
| Le total est par appareil, jamais exporté, et ses prix sont figés à l'ajout | `appareil.total`, `TOTAL_MAX`/`QTE_MAX` `index.html:681-682` | Exactement ce qu'un pack ne doit PAS être : un pack doit se partager et rester juste dans six mois. |
| La fusion remplace un enregistrement entier d'après sa date `maj` | `fusionner` `index.html:1006-1017` | Un champ nouveau sur un forfait ne coûte rien à la synchro ni à l'import. |
| La recherche fabrique par forfait une liste de mots : référence, désignation, surnoms, noms et surnoms des éléments, noms des familles | `construireIndex` `index.html:1111-1119` | Un pack doit avoir sa propre liste, sinon il reste introuvable par « 3Q ». À faire : y verser les éléments de ses forfaits. |
| Deux forfaits identiques sont repérés par la combinaison de leurs éléments | `cleCombinaison` `index.html:1142` | Un pack n'a pas d'éléments à lui → clé vide → **tous les packs passeraient pour des doublons l'un de l'autre**. À corriger en même temps. |
| À l'import du tableau, **toute colonne inconnue devient une nouvelle famille** | `index.html:2454` | Une colonne « Contenu » non déclarée créerait une famille « Contenu » en silence. Elle doit entrer dans `COLONNES_TABLEAU`. |
| `Référence`, `Prix HT` et `Prix TTC` sont obligatoires, comme colonnes et sur chaque ligne | `index.html:2459` puis le contrôle par ligne | Une ligne de pack sans prix serait refusée. Le lecteur doit apprendre qu'un pack n'a pas de prix à saisir. |
| `VERSION_FORMAT` vaut 2, et un fichier d'une version plus récente est refusé en entier | `index.html:685` et `849` | Les packs, c'est la version 3. Un appareil qui n'a pas rechargé la page refusera le fichier, avec le message qui dit déjà quoi faire. |
| Tes 34 vraies références : 8 caractères au plus, **aucune** ne contient `+`, `;` ni `x` suivi d'un chiffre | statistique sur ton `Forfaits-a-remplir-v3`, sans lire un seul nom ni prix | La syntaxe `REF + REF ×2` est sûre pour ton tableau. 3 désignations sur 34 contiennent un `+`, mais la désignation n'est jamais découpée. |

## Le point qui change tout

**On ne construit pas un nouvel écran : on donne un nom au Total.**

Tu cherches, tu appuies sur « + Total » (ce que tu fais déjà), tu règles les quantités avec − et +,
puis un nouveau bouton **« Enregistrer comme pack »** demande le nom. C'est fini. Trois appuis de plus
que ce que tu fais aujourd'hui, sur un écran que tu connais, et aucune liste à cocher sur un téléphone.

Et dans l'autre sens : « Modifier » sur la carte d'un pack recharge son contenu **dans le Total**, où
tu le retouches et le réenregistres. Le Total sert donc d'éditeur, et il n'y a aucun deuxième endroit
à apprendre ni à tester. Prix à payer, dit tout de suite : ça remplace le total en cours, donc une
question avant (« ton total en cours sera remplacé »).

## Décisions

Tes réponses du 09/11 :

1. **Le prix d'un pack se calcule tout seul** depuis son contenu. Si le prix d'un de ses forfaits bouge
   dans trois mois, le pack suit. Aucun pack ne peut afficher un vieux prix au comptoir. Pas de remise
   en V1.
2. **Création en mode modification seulement** : un pack part dans le `.json` comme un forfait, donc
   c'est de la donnée partagée. Un vendeur peut toujours construire son total, il ne peut pas en faire
   un pack d'équipe.
3. **Un pack peut contenir un autre pack**, 3 niveaux au plus. La protection contre les boucles
   (A contient B qui contient A) est de toute façon obligatoire : sans elle, un fichier bricolé à la
   main figerait la page.
4. **Assemblage depuis le Total.**
5. **A et B sont des forfaits**, pas des éléments.

Ce que je tranche moi-même, parce que le code ou l'usage le dicte :

- **Un pack a une référence**, comme un forfait : elle est obligatoire et unique dans le modèle actuel,
  elle sert au bouton « Copier » et à l'aller-retour Excel. Elle est **proposée automatiquement**
  (`PACK-01`, `PACK-02`…) et modifiable. Le nom, lui, est la désignation : c'est elle qui s'affiche en
  titre de carte, comme pour un forfait.
- **Les lignes libres du Total** (pièce ou service dont tu tapes le nom et le prix) sont **gardées**
  dans le pack : tu t'en sers déjà pour une pose ou un divers. Leur prix reste figé — c'est le seul
  endroit où un pack peut vieillir, et le détail l'écrit (« prix saisi »).
- **Un badge `PACK`** sur la carte, à côté du nom. Les packs se mélangent aux forfaits dans les
  résultats : c'est tout l'intérêt (« une recherche plus rapide »), mais tu dois voir que c'est un
  assemblage.
- **Un pack s'ajoute au Total** comme un forfait : rien à faire, ça marche si son prix est à jour.

## Ce qu'on fait

### Le modèle de données

```js
// un forfait ordinaire : inchangé
{ id, ref, designation, ht, ttc, elements: { 'fam-taximetre': 'elt-t1demo' }, maj, surnoms? }

// un pack : le même enregistrement, plus un contenu
{ id, ref, designation, ht, ttc, contenu: [{ id, nom, qte, ht, ttc }], elements: {}, maj, surnoms? }
```

`contenu` reprend **exactement** la forme d'une ligne de Total (`lireLigneTotal`, `index.html:963`) :
aucune notion nouvelle à inventer, à valider ni à tester.

- Ligne **avec `id`** : le prix est relu sur ce forfait à l'affichage. Le `ht`/`ttc` enregistré ne sert
  que de secours si le forfait a disparu.
- Ligne **sans `id`** (pièce ou service) : son prix enregistré fait foi.
- `ht` et `ttc` du pack sont un **cache**, recalculé par une fonction `recalculerPacks()` appelée au
  chargement, après un import, après une fusion et après chaque modification. Tout le reste de l'appli
  (cartes, recherche, Total, export CSV) continue de lire `f.ht` sans rien savoir des packs.
- **`maj` ne change jamais à cause d'un recalcul** : sinon deux appareils se battraient sans fin à
  chaque fusion.
- Boucle ou profondeur > 3 : le prix vaut « à revoir » au lieu d'un montant, et la carte le dit.

Pourquoi pas une liste `packs` à part : la recherche, les cartes, les filtres, la fusion, l'export, les
surnoms, les favoris, les derniers consultés et le Total travaillent tous sur des forfaits. Une
deuxième liste, c'est une dizaine de chemins de code à écrire en double, et deux fois l'interface à
tenir au doigt. Un pack est un forfait avec un contenu : c'est tout.

### Lot 1 — les données et l'appli

- `valider` : lire et borner `contenu` (50 lignes, quantité 1 à 99, mêmes contrôles que `lireLigneTotal`),
  `VERSION_FORMAT` à 3, lecture des fichiers 1 et 2 inchangée.
- `recalculerPacks()` + protection des boucles (ensemble des identifiants déjà vus, profondeur 3).
- `construireIndex` : pour un pack, les mots de recherche = sa référence, sa désignation, ses surnoms,
  les noms de ses lignes, **et** les éléments et familles de ses forfaits (donc « 3Q » le trouve) ;
  ses éléments affichés = l'union de ceux de ses forfaits, donc les filtres de famille marchent sans
  une ligne de plus.
- `cleCombinaison` : pour un pack, la clé devient son contenu trié, pas ses éléments.
- `carte` : badge `PACK`, détail ligne par ligne (`2 × EX-T1-Z5-3Q … 246,90 € TTC`) puis le total ;
  un pack imbriqué apparaît en une ligne avec son nom et son total, sans dérouler ses propres lignes.
- Total : bouton « Enregistrer comme pack » (mode modification), et « Modifier » sur une carte de pack
  qui recharge le contenu dans le Total après confirmation.
- Suppression d'un forfait utilisé par des packs : le dire et compter (« il est dans 2 packs »), comme
  pour un élément utilisé. Supprimer quand même laisse le pack avec son prix de secours et la mention
  « à revoir ».
- « Supprimer les exemples » : un pack bâti sur des forfaits d'exemple suit la même règle que les
  forfaits d'exemple.

### Lot 2 — Excel, dans les deux sens

- Nouvelle colonne **`Contenu`**, déclarée dans `COLONNES_TABLEAU` (sans ça, elle deviendrait une
  famille). Syntaxe : `EX-T1-Z5-3Q + EX-LUM-POSE ×2`, séparateur `+`, quantité `×2` / `x2`, ou un
  retour à la ligne dans la cellule (Alt+Entrée) si tu préfères.
- Une ligne dont `Contenu` est rempli est un pack : **`Prix HT` et `Prix TTC` restent vides** (le
  lecteur ne les exige plus), et un prix tapé quand même est ignoré, en le signalant dans la fenêtre
  de confirmation.
- Référence inconnue dans un `Contenu` : signalée avec son texte exact, ligne par ligne.
- Référence qui contient un `+` : signalée (« renomme-la, ou assemble ce pack dans l'appli »). Aucune
  des tiennes n'est dans ce cas aujourd'hui.
- Export CSV : la même colonne, pour que l'aller-retour export → Excel → import ne perde rien.
- `outils/modele_excel.py` : la colonne dans le modèle. Les titres doivent rester d'accord entre
  l'export, `COLONNES_TABLEAU` et le modèle — les tests comparent déjà les trois.

### Lot 3 — tests et notes

- Tests nouveaux : enregistrer un pack depuis le Total ; son prix = la somme ; le changement du prix
  d'un forfait remonte dans le pack ; recherche par nom, par surnom et par élément d'un de ses
  forfaits ; filtre de famille ; détail de la carte ; pack dans un pack ; boucle dans un fichier
  bricolé qui ne fige pas la page ; forfait supprimé → pack « à revoir » ; import d'une ligne de pack ;
  aller-retour export/import ; fichier version 2 toujours lisible.
- `CLAUDE.md` du projet : la forme de `contenu`, le piège du cache de prix qui ne touche pas à `maj`,
  le piège de la colonne inconnue qui devient une famille.
- `.claude/plans/test-telephone.md` : deux points de plus, pour que tu l'essaies toi-même.

## Ce qu'on ne fait pas

- **Pas de remise** ni de prix imposé sur un pack (c'est ta réponse ; ça part en idée roadmap).
- **Pas de packs perso** par vendeur (idée roadmap si le besoin vient).
- **Pas de prix sur les éléments** : ce serait un autre projet, et tes 34 prix actuels seraient à revoir.
- Pas de ligne négative, donc pas de remise déguisée en ligne libre (les prix sont des entiers ≥ 0).
- Pas de liste `packs` séparée, pas de nouvel écran d'assemblage, pas de changement de l'adresse du
  site ni du circuit export/import `.json` au-delà du passage en version 3.

## Comment on saura que c'est fini

1. `python -m pytest` vert sur Chromium, Edge et Firefox, tests nouveaux compris.
2. `ruff check .`, `python -m vulture . --min-confidence 80`, `python outils/csp.py` et
   `test_empreinte_de_securite_a_jour` verts.
3. Les titres de colonnes d'accord entre l'export CSV, `COLONNES_TABLEAU` et `modele_excel.py`
   (tests existants).
4. Un pack bâti depuis le Total en 3 appuis sur un téléphone émulé, capture dans `captures/`.
5. Ton essai à toi : créer un pack sur ton Android, le retrouver en tapant son nom, vérifier le détail.
6. Une ligne de pack importée depuis ton tableau, avec le compte rendu de la fenêtre de confirmation.

## Risques

- **Deuxième conflit avec la PR #47 (synchro cloud), garanti** : les deux travaux réécrivent
  `index.html`. Je recommande de construire les packs sur `main` maintenant et de refaire la fusion de
  #47 ensuite — je l'ai faite aujourd'hui, c'est une quinzaine de minutes, et le piège est noté. Le
  contraire (attendre #47) bloquerait les packs sur ton `wrangler login`.
- **Version 3 du format** : le premier `.json` qui contient un pack est refusé par un appareil qui n'a
  pas rechargé la page. Le bandeau « Recharger » s'en occupe, mais il faut que tout le monde l'ait fait
  avant que tu envoies le premier fichier. À écrire dans la note de reprise.
- **Un prix de pack bouge quand un de ses forfaits bouge** : c'est voulu, mais un devis montré hier
  peut ne plus donner le même total aujourd'hui. À savoir au comptoir.
- **Les lignes libres gardent un prix figé** : le seul endroit où un pack vieillit. Le détail l'écrit.
- **Taille** : modèle, index, carte, Total, import, export, modèle Excel, tests — au-delà du seuil de
  mes règles. Deux PR : l'appli, puis Excel.
- **Le Total sert d'éditeur** : il remplace le total en cours. Question avant, et c'est tout.

## Zones grises qui restent

1. **Ton usage réel de la colonne `Contenu`** : je propose une cellule par pack (`A + B ×2`). Si tu
   préfères une ligne par composant dans le tableau, c'est un autre lecteur à écrire : dis-le avant le
   lot 2, ça ne coûte rien à ce moment-là.
2. **Combien de packs** tu auras, et si l'imbrication servira vraiment. Aucun coût à l'autoriser, donc
   rien ne bloque — mais si tu n'en fais jamais, c'est du code que personne n'exerce.
3. **Les références de packs** : `PACK-01` est ma proposition. Si ton métier a déjà une façon de les
   nommer, donne-la-moi, c'est une ligne à changer.
4. **Pas essayé sur un vrai téléphone**, comme d'habitude : émulation Playwright seulement.

## Autocritique

- **Je contredis ton mot « élément »**, et c'est le point où je pouvais me tromper le plus : dans
  l'outil, un élément n'a pas de prix. J'ai préféré te poser la question plutôt que de construire sur
  mon interprétation — si tu avais répondu « prix sur chaque élément », tout ce plan tombait.
- **Ma première idée était un nouvel écran d'assemblage** (liste de forfaits à cocher, quantité par
  ligne). C'est ce qu'on fait d'habitude, et c'était une erreur : long au doigt, un deuxième endroit à
  apprendre, et il aurait doublé un écran qui existe déjà et que tu utilises. Le Total faisait déjà
  90 % du travail ; je ne l'ai vu qu'en lisant `ouvrirTotal`.
- **J'ai failli garder les prix figés** « comme le Total », par cohérence. Mauvaise cohérence : un total
  est jeté dans la minute, un pack vit des mois. Figer un prix de pack, c'est fabriquer le défaut le
  plus coûteux au comptoir, et il ne se voit pas.
- **Ce que je n'avais pas vu seul** : la clé de doublon (`cleCombinaison`) qui aurait pris tous les
  packs pour des copies l'un de l'autre, et la colonne inconnue qui devient une famille en silence.
  Les deux ne se voient qu'en lisant le code, pas en réfléchissant au modèle.
- **Ce que je ne peux pas prouver ici** : ton téléphone, ta façon de remplir Excel, et si
  l'imbrication sert.

## Ce que TU fais

1. **Rien ce soir.** Le plan est écrit, les cinq questions sont tranchées.
2. Demain, un seul mot pour lancer le lot 1 (« go packs »). Je construis sur `main`, je refais la
   fusion de #47 après.
3. Quand le lot 1 est posé : créer un pack sur ton Android et me dire ce qui gêne. C'est comme ça
   qu'est née la rangée « Derniers consultés » — ton usage réel vaut mieux qu'un test de plus.
4. Avant le lot 2, dis-moi si tu veux `A + B ×2` dans une cellule (ma proposition) ou une ligne par
   composant dans le tableau.
5. Si tes packs ont déjà une façon de se nommer dans le métier, donne-la-moi.
