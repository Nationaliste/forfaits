# Ergonomie tactile : V1 vérifiée (09/11/2026)

Demande : « un truc me gêne, audite en tant que simple utilisateur ; rapide et simple, tactile
simple, pas que pensée souris ». Tout ce qui suit est **mesuré**, dans un navigateur sans fenêtre
(Playwright headless), sur un écran de téléphone 375 × 812 avec un doigt (`has_touch`), et sur les
3 moteurs (Chromium, WebKit = iPhone, Firefox). Scripts jetables : voir « Comment je l'ai mesuré ».

---

## 1. Ce que l'enquête a trouvé

### La vitesse n'est pas le problème

| Mesure | Résultat |
|---|---|
| Une frappe dans la recherche (filtre + rendu complet) | **0,6 à 1,4 ms** |
| Premier affichage de la page | 188 ms |
| Page prête | 298 ms |
| Erreurs de console | aucune |

L'outil n'est pas lent. **Ce qui est lent, c'est de trouver le forfait à l'écran**, parce qu'il n'y
en a presque pas d'affiché.

### La place : 551 px sur 812 avant le premier forfait

Téléphone 375 × 812, données réelles (pas de bandeau EXEMPLE), au repos :

| Bloc | Hauteur |
|---|---|
| En-tête (titre, Importer, ☰) | 72 px |
| Damier | 12 px |
| Champ de recherche | 58 px |
| **Rangée de filtres** (4 boutons sur 2 rangées) | **104 px** |
| **Barre « 11 forfaits · Trier · Cartes entières »** (3 lignes) | **88 px** |
| **Rangée « Derniers consultés »** (dépliée par défaut) | **136 px** |
| Premier forfait commence à | **551 px (68 % de l'écran)** |
| **Forfaits entiers visibles** | **2** |

- Sans la rangée « Derniers consultés » : 401 px, 4 forfaits.
- Pendant que tu tapes (il reste ~450 px visibles au-dessus du clavier) : **0 forfait entier**.
  Les suggestions recouvrent les filtres, et ce qu'on voit en dessous, c'est le menu « Trier ».
- Téléphone tourné (812 × 375) : **0 forfait entier** avec la rangée « Derniers consultés ».
- Petit téléphone (360 × 740) : 3 forfaits. En taille de texte « Grand » : 3 forfaits.

Capture : `captures/audit-1-accueil-telephone.png`, `captures/audit-3-recherche-zone-clavier.png`.

### Les noms coupés

Carte repliée (le réglage par défaut) : le nom n'a que **171 px** sur les 341 px de la carte — le
bloc prix prend les 170 autres. Mesuré : **36 caractères passent, 40 sont coupés** (je n'ai pas
mesuré entre les deux). Le badge EXEMPLE n'y change rien : la largeur vient du prix.

Ton fichier de saisie (mesuré sur le `.csv` de ton dossier, longueurs seulement, aucun contenu) :
la désignation médiane fait une trentaine de caractères, **la plus longue une soixantaine**, et
**près d'un tiers dépassent 40 caractères**. Donc **au moins un tiers de
tes forfaits s'affichent avec un nom coupé**, alors que c'est au nom que les techniciens les
reconnaissent.

En « Cartes entières », le nom a 315 px et 3 lignes : rien n'est coupé, mais on voit encore moins
de forfaits. Aujourd'hui tu choisis entre voir les noms et voir les forfaits.

### Ce qui est pensé souris (tu ne l'as pas retenu comme gênant, je le corrige quand même : c'est ta demande)

- **Le survol reste collé après un appui.** Vérifié sur les 3 moteurs : après avoir touché une
  carte, son fond passe de transparent à `rgb(35,35,35)` et **y reste** jusqu'au prochain appui
  ailleurs. Un bouton touché reste soulevé d'1 px. Il y a **20 règles `:hover` et aucune n'est
  protégée** par `@media (hover: hover)`.
- **La croix ✕ de la recherche rappelle le clavier** : elle refait `focus()` sans condition, alors
  qu'ailleurs le code teste bien `pointer: fine` avant de donner le focus (ligne 3911).
- **3 infobulles `title`** (Favori, + Total, Mise à jour) : invisibles au doigt. Les deux premières
  ont un `aria-label`, donc rien n'est perdu pour un lecteur d'écran, mais l'explication n'arrive
  jamais sur téléphone.

### Les cibles au doigt (presque bon)

21 cibles mesurées à l'accueil, 25 carte dépliée. Une seule règle de taille n'est pas tenue :

| Élément | Mesuré | Attendu |
|---|---|---|
| Bouton « Cartes entières » | 36 px de haut | 44 |
| Bouton favori ☆ | 43 px de large | 44 |
| Écart menu « Trier » ↔ « Cartes entières » | 4 px | 8 |
| Écart entre ☆, « + Total » et « Copier » | 6 px | 8 |

Le reste (filtres, cartes, boutons de fenêtre, champs) est à 48 px, et la page ne défile jamais en
largeur. Le gros du travail tactile a donc déjà été fait : ce qui reste, c'est la place.

---

## 2. Ce qu'on fait

Tout est dans `index.html` (CSS + quelques lignes de script). **Aucun changement de format de
données**, aucun nouveau fichier, aucune dépendance.

1. **« Derniers consultés » repliée par défaut** (`recentsPlies`). Un appui la déplie, l'appareil
   s'en souvient. *Piège à ne pas rater* : la lecture des réglages fait `lu.recentsPlies === true` ;
   elle doit devenir `!== false`, sinon les appareils déjà en service gardent l'ancien défaut.
   → **+96 px**.
2. **Barre de résultats sur une seule ligne** : « Cartes entières / Liste compacte » rejoint le Menu,
   à côté d'Apparence et Taille du texte (c'est un réglage d'affichage, pas une commande de
   recherche). Il reste le compte et « Trier ». → **+44 px**.
3. **Rangée de filtres repliée tant que le champ de recherche a le focus.** Les suggestions la
   recouvrent déjà pendant la frappe : rien n'est perdu à l'écran. Elle revient dès qu'on sort du
   champ (Entrée range le clavier). Les étiquettes des filtres posés, elles, restent visibles.
   → **+104 px, exactement quand l'écran est le plus petit**.
4. **Nom complet sur la carte repliée** : 3 lignes au lieu de 2, et bloc prix resserré pour rendre
   ~30 px au nom. Une carte ne grandit que si son nom est long (80 px → ~101 px) ; les autres ne
   bougent pas. Le TTC reste rouge et gros.
5. **Plus de survol collé au doigt** : les 20 règles `:hover` passent sous `@media (hover: hover)`.
   À la souris, rien ne change ; au doigt, plus rien ne reste allumé. L'appui (`:active`) est gardé.
6. **Cibles et écarts** : « Cartes entières » et ☆ à 44 px, écarts portés à 8 px.
7. **La croix ✕ ne rappelle plus le clavier** sur un écran tactile (même test `pointer: fine`
   qu'ailleurs dans le code).

### Ce que ça doit donner (à vérifier après, pas promis avant)

| | Aujourd'hui | Visé |
|---|---|---|
| Forfaits entiers, au repos, 375 × 812 | 2 | **5** |
| Forfaits entiers pendant la frappe (~450 px) | 0 | **2** |
| Désignations coupées | près d'un tiers | **0** |
| Cibles sous 44 px | 2 | 0 |
| Survol collé après un appui | oui | non |

---

## 3. Ce qu'on ne fait pas

- **On ne touche pas aux données** : ni format, ni `VERSION_FORMAT`, ni export/import, ni cloud.
- **On ne supprime rien** : le tri et « Cartes entières » changent de place, ils ne disparaissent pas.
- **On ne touche pas à la fenêtre de filtre** (plein écran 812 px pour 4 choix de 56 px). C'est
  lourd, mais c'est un vrai changement d'interface : après la démo, pas avant.
- **On ne refait pas les lots 2 et 3** du rapport du 30/10 (circuit import/export, garde-fou à la
  fermeture du formulaire). Ils restent valables, ils ne touchent pas à ce qui te gêne.
- **On ne retire pas le bouton « Importer » de l'en-tête** même s'il est aussi dans le Menu : il ne
  coûte aucune hauteur (c'est le titre qui fixe celle de l'en-tête).
- Pas de README, pas de nouvelle dépendance, pas de nouveau réglage à comprendre.

---

## 4. Comment on saura que c'est fini

1. `python -m pytest` vert sur Chromium, Edge et Firefox, puis `NAVIGATEURS=webkit` vert.
2. `ruff check .`, `python -m vulture . --min-confidence 80`, `python outils/csp.py` lancé et
   `test_empreinte_de_securite_a_jour` vert.
3. Le script de mesure relancé affiche : **≥ 5 forfaits entiers** au repos en 375 × 812,
   **≥ 2** dans la bande de 450 px, **aucune cible sous 44 px**, **aucun écart sous 8 px**,
   **aucun survol collé** sur les 3 moteurs.
4. Un texte de 62 caractères n'est plus coupé sur une carte repliée (le test de mesure le vérifie).
5. Les captures téléphone refaites **et regardées**, portrait et paysage.
6. `/review-local` passé, puis PR.

---

## 5. Risques

- **Le repli des filtres pendant la frappe fait sauter la page de 104 px** quand tu touches le
  champ. C'est le seul point qui peut déplaire à l'usage. Il tient en une règle isolée : si ça te
  gêne, on l'enlève sans rien casser d'autre.
- **Tests à adapter** : au moins le test qui clique `#btn-compact` (il devra passer par le Menu), et
  deux tests téléphone à relire (hauteurs des filtres, suggestions). Je les compte avant de coder ;
  si ça dépasse quelques lignes, je le dis au lieu de les réécrire en masse.
- **Conflit avec la PR #47** (synchro cloud, non fusionnée) : les deux modifient le `<script>`, donc
  l'empreinte de sécurité en tête de `index.html`. Conflit garanti sur **cette ligne-là seulement**,
  réglé en relançant `python outils/csp.py` après la fusion. Je pars de `main` exprès, pour que
  cette amélioration puisse être publiée **sans attendre** ton `wrangler login`.
- **Taille de texte « Grand »** : la barre de résultats peut repasser sur 2 lignes. Elle se replie
  proprement, ce n'est pas une casse.
- **Rien n'est irréversible** : CSS et mise en page, aucune donnée touchée.

---

## 6. Zones grises qui restent

1. **Aucun vrai téléphone.** Tout est émulé en 375 × 812 et 812 × 375. La hauteur réelle du clavier
   de ton Android n'est pas mesurée : j'ai pris une bande visible de 450 px. C'est toi qui tranches,
   en regardant l'écran d'accueil après coup.
2. **Tes vraies données ne sont pas chargées dans l'outil.** J'ai mesuré la mise en page avec les
   exemples inventés, et seulement les **longueurs** de ton fichier (aucun nom, aucun prix lu ni
   recopié). Si tes désignations s'allongent, la carte repliée s'allonge avec.
3. **Ce qui te gêne vraiment.** Tu as confirmé « on voit 2 forfaits » et « les noms sont coupés ».
   Si après coup la gêne reste, c'est qu'elle est ailleurs, et on repartira de ton ressenti plutôt
   que de mes mesures.
4. **Le poids de la fenêtre de filtre** (2 appuis + un plein écran pour poser un filtre) : signalé,
   pas traité. À décider après la démo.

---

## 7. Ce que TU fais

1. Dire « go ». Le reste se fait tout seul, y compris les tests et la PR.
2. Après : ouvrir l'outil sur ton Android, regarder l'écran d'accueil, et me dire si ça va mieux —
   c'est la seule mesure que je ne peux pas prendre à ta place.
3. Rien d'autre. Le `wrangler login` de la synchro reste de ton côté, mais il n'a rien à voir avec
   ça et ne bloque pas cette amélioration.

---

## 8. Autocritique

- **J'ai failli te sortir un chiffre faux.** Ma première mesure donnait « 65 % de l'écran avant le
  premier forfait », mais elle comptait le bandeau « forfaits EXEMPLE », qui disparaîtra avec tes
  vraies données. J'ai refait la mesure sans lui avant d'écrire quoi que ce soit : 49 % sans la
  rangée « Derniers consultés », 68 % avec. Le problème reste, le chiffre n'est pas le même.
- **J'ai aussi failli accuser le badge EXEMPLE** pour les noms coupés. Mesure faite badge retiré :
  la largeur du nom ne bouge pas d'un pixel, c'est le bloc prix qui prend la place.
- **J'ai failli ne rien trouver.** Le code est déjà très tactile : 48 px partout, pas de focus
  automatique sur téléphone, 16 px minimum sur les menus déroulants pour que l'iPhone ne zoome pas,
  un mode paysage dédié. C'est en mesurant la place laissée aux forfaits — et pas en relisant le CSS
  — que le vrai défaut est sorti. C'est la leçon de la PR #46, appliquée à l'endroit.
- **Ce que j'avais raté au rapport du 30/10** : il listait 25 constats de libellés et de circuits,
  et pas une seule fois « on ne voit que 2 forfaits ». Il lisait le code, il ne regardait pas
  l'écran.
- **Là où je peux me tromper** : le repli des filtres pendant la frappe. C'est le seul changement
  qui modifie un geste plutôt qu'un pixel, et je le propose sur un raisonnement (« les suggestions
  les recouvrent déjà ») que seule la vraie utilisation confirmera.

---

## Comment je l'ai mesuré

Scripts jetables du jour (dossier temporaire de la session, non versionnés) :
`mesure-tactile.py` (cibles, écarts, survol, vitesse), `mesure-place.py` (hauteurs des blocs dans
7 états), `mesure-noms.py` et `mesure-noms2.py` (troncature caractère par caractère),
`mesure-survol.py` (3 moteurs), `stats-donnees.py` (longueurs du fichier réel, statistiques seules).
À refaire après coup pour le point 3 de « Comment on saura que c'est fini ».

---

## 9. Ce qui a changé à la construction (mesuré, pas supposé)

Quatre points du plan étaient faux. Les corrections viennent de mesures faites sur Chromium, WebKit
(moteur des iPhone) et Firefox, en 375 × 812 avec un écran tactile — et, pour le quatrième, sur ce
PC Windows, à dalle tactile *et* souris.

### a. Le repli des filtres sur le *focus* avalait l'appui suivant

Le plan disait : « rangée de filtres repliée tant que le champ de recherche a le focus ». Mesuré :
quand le doigt touche une carte, le champ perd le focus **au contact**, la rangée revient, le contenu
redescend de 116 px, et au moment où le doigt se lève il n'est plus sur la carte visée. Résultat :
**aucune carte ne s'ouvre**, sur les trois moteurs (témoin sans la règle : la bonne carte s'ouvre).

Corrigé : le repli est déclenché par le **texte** du champ, pas par son focus
(`@media (pointer: coarse) { .zone-recherche:has(#recherche:not(:placeholder-shown)) .filtres { display: none } }`).
Un appui sur une carte ne change pas le texte, donc rien ne bouge sous le doigt — revérifié : la
bonne carte s'ouvre sur les trois moteurs. La croix ✕ fait revenir la rangée, mais elle est
*au-dessus* d'elle : rien ne se déplace sous le doigt non plus.

**Ce que ça coûte** : au doigt, on ne peut plus poser un filtre de famille pendant qu'une recherche
est tapée (il faut effacer la recherche). Les filtres déjà posés restent visibles et retirables. À la
souris, rien ne change.

### b. La barre de résultats ne tenait pas sur une ligne, même sans « Cartes entières »

Mesuré : « Trier » prend 190 px à lui seul, le compte 124 px, la largeur disponible est 343 px.
Retirer « Cartes entières » ne suffisait pas — il restait « Effacer la recherche » (103 px).

Corrigé : « Effacer la recherche » devient « Tout effacer » et **ne sort que si un filtre est posé**.
Avec une recherche seule, la croix ✕ du champ fait déjà exactement la même chose, à 2 cm du texte.
La barre tient alors sur une ligne (48 px au lieu de 88).

### c. Le nom entier coûtait deux forfaits à l'écran

Le plan disait « 3 lignes + bloc prix resserré ». Mesuré : à 171 px de large, 3 lignes ne suffisent
pas pour 62 caractères, et 4 lignes font passer les cartes de 61 à 103 px — on voyait **moins** de
forfaits qu'avant.

Corrigé : la mention « TTC » passe **sous** le montant au lieu d'être à côté. Elle prenait 30 px sur
la largeur du nom, et elle ne coûte aucune hauteur (le montant fait déjà la hauteur de la ligne). Le
nom passe à 201 px, 3 lignes suffisent pour 62 caractères, et la carte reste à 61 px (82 px pour un
nom long). Le TTC garde son rouge et sa taille, et la mention reste lisible — je l'avais d'abord
supprimée, ce qui ne disait plus que le prix affiché était le TTC.

### d. « Écran tactile » n'existe pas : la requête média répondait tactile sur un PC

Le plan reposait sur `@media (hover: none)` et `@media (pointer: coarse)` pour dire « on est au
doigt ». **Mesuré** (Windows, PC à dalle tactile, souris branchée) : Firefox répond
`pointer: coarse` et `hover: none`, Chrome aussi quand il tourne avec son interface. Autrement dit,
livré tel quel, le plan aurait **supprimé le survol** et **replié les filtres en tapant** sur un PC
à écran tactile — l'inverse du but. Et il n'aurait rien fait pour le vrai problème de ces appareils
(le survol qui reste allumé après un appui du doigt), puisqu'une requête média décrit le *matériel*,
jamais le *geste en cours*.

Corrigé : on suit le **dernier geste**. `data-geste` vaut `souris` ou `doigt` sur `<html>`, posé par
le `pointerType` des événements `pointerdown` / `pointermove` et, au démarrage, par
`(any-pointer: fine)` (aucun pointeur fin = téléphone). Les règles de survol s'écrivent
`:where(html[data-geste=souris]) …:hover` : `:where()` n'ajoute aucune spécificité, donc aucune
égalité entre règles ne change — c'était le risque de ce changement.

Résultat mesuré sur les trois moteurs : au doigt, pas de survol et les filtres se replient ; à la
souris, le survol marche et les filtres restent ; sur un appareil hybride, la souris qui **bouge**
suffit à tout ramener, sans attendre un clic. Deux endroits du code qui demandaient `pointer: fine`
suivent maintenant le geste, dont un défaut qui existait déjà avant ce travail : sur un PC à dalle
tactile, le champ de recherche ne recevait pas le focus à l'ouverture.

### Résultat mesuré (375 × 812, données sans exemples, un navigateur neuf par mesure)

| | main | après |
|---|---|---|
| Haut de la 1re carte, au repos | 401 px | **361 px** |
| Forfaits entiers, au repos | 5 | **5** (avec les noms entiers) |
| Haut de la 1re carte, clavier ouvert | 401 px | **245 px** |
| Forfaits entiers, clavier ouvert (450 px visibles) | **0** | **2** |
| Désignation de 62 caractères | coupée dès 45 | **entière** |
| Cibles sous 44 px | 2 (+2 dans « Derniers consultés ») | **0** |
| Survol resté allumé après un appui | oui, sur les 3 moteurs | **non, sur les 3 moteurs** |

### e. Deux défauts trouvés par la relecture, après la mesure

La relecture locale a trouvé deux choses que mes propres mesures avaient manquées. Les deux sont
corrigées, et chacune a maintenant son test.

**Le nouveau défaut « rangée repliée » n'atteignait aucun appareil déjà en service.** La fonction qui
enregistre les réglages réécrit **tout** l'objet, donc un téléphone qui s'était servi de l'outil avait
déjà l'ancien défaut écrit en clair dans son navigateur. Changer la lecture ne changeait rien pour
lui : seul un appareil neuf aurait vu la rangée repliée. Vérifié en ouvrant la version d'avant, puis
la nouvelle, sur le même navigateur. Corrigé par une **nouvelle clé** (`recentsOuverts`), l'ancienne
étant ignorée. Re-vérifié de la même façon : la rangée est bien repliée après la mise à jour.

**Sur un appareil hybride, l'appui du doigt était perdu.** Si le repli des filtres suit le geste, le
geste bascule **au contact** du doigt : la rangée disparaissait pendant l'appui, le contenu montait de
116 px, et la carte visée ne s'ouvrait pas (reproduit 3 fois sur 3, Chromium et WebKit). C'est
exactement le défaut du point a, revenu par une autre porte. Corrigé : le repli se décide au moment où
le champ passe de vide à rempli, puis ne bouge plus. Plus rien ne se déplace entre le doigt qui touche
et le doigt qui part.

### Ce que je n'ai pas pu prouver

- **Aucun vrai téléphone** : tout est émulé. La hauteur réelle du clavier peut différer des 450 px
  retenus (c'est une hypothèse, pas une mesure).
- **Appareil hybride** (PC à dalle tactile) : traité au point d. Ce qui reste : une fois la
  recherche tapée au doigt, la rangée des familles ne revient pas si tu bouges la souris — il
  faut effacer la recherche. C'est volontaire : si elle suivait le geste, l'appui du doigt
  suivant la replierait **au contact** et serait perdu (mesuré, puis corrigé — voir le point e).
- **Tes vraies données** ne sont pas chargées dans l'outil : les longueurs viennent de ton tableau,
  les textes affichés sont ceux, inventés, des exemples.
