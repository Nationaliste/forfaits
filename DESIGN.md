---
name: Forfaits
description: Trouver un forfait, lire sa ligne d'éléments jusqu'au prix, le copier ou l'ajouter au total
colors:
  rouge: "#e30613"
  rouge-fonce: "#b3040f"
  rouge-vif: "#ff4d5e"
  rouge-vif-clair: "#cc0511"
  noir: "#000000"
  blanc: "#ffffff"
  fond: "#000000"
  fond-clair: "#f1f1f1"
  surface: "#151515"
  surface-clair: "#ffffff"
  surface-2: "#232323"
  surface-2-clair: "#ebebeb"
  trait: "#333333"
  trait-clair: "#d6d6d6"
  trait-fort: "#747474"
  trait-fort-clair: "#858585"
  texte: "#f3f3f3"
  texte-clair: "#121212"
  texte-fort: "#ffffff"
  texte-fort-clair: "#000000"
  texte-doux: "#a3a3a3"
  texte-doux-clair: "#525252"
  inverse: "#ffffff"
  inverse-clair: "#121212"
  inverse-texte: "#121212"
  inverse-texte-clair: "#ffffff"
  encre: "#121212"
  vert: "#1f7a3a"
  ambre: "#f2b544"
  ambre-clair: "#8a5a00"
typography:
  display:
    fontFamily: "Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "42px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.3
rounded:
  petit: "8px"
  moyen: "12px"
  rangee: "14px"
  grand: "20px"
  feuille: "26px"
  rond: "999px"
components:
  bouton-principal:
    backgroundColor: "{colors.rouge}"
    textColor: "{colors.blanc}"
    rounded: "{rounded.rond}"
    height: "36px"
    padding: "0 16px"
  bouton-principal-hover:
    backgroundColor: "{colors.rouge-fonce}"
  bouton-second:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.texte}"
    rounded: "{rounded.rond}"
    height: "36px"
    padding: "0 16px"
  pastille-filtre:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.texte}"
    rounded: "{rounded.rond}"
    height: "36px"
    padding: "0 10px 0 14px"
  pastille-filtre-choisie:
    backgroundColor: "{colors.inverse}"
    textColor: "{colors.inverse-texte}"
  panneau:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.grand}"
  menu:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.grand}"
    padding: "6px"
  champ-recherche:
    backgroundColor: "{colors.blanc}"
    textColor: "{colors.encre}"
    rounded: "{rounded.rond}"
    height: "44px"
---

# Design System: Forfaits

## Overview

**Creative North Star: « La ligne »**

Un forfait est un trajet : des éléments qui s'enchaînent jusqu'à un prix. L'outil emprunte à la signalétique de transport d'aujourd'hui : dans la liste, chaque forfait montre sa ligne d'arrêts à l'horizontale ; dans la fiche, la ligne se déroule à la verticale, arrêt par arrêt, et le prix TTC est le terminus, en très grand.

C'est un outil de comptoir : on cherche, on lit, on copie une référence, on additionne. La densité prime (dix forfaits entiers dans une page de 1280×720), les formes sont rondes et calmes, et rien ne décore. Deux directions ont été montrées et refusées : le tarif de catalogue de pièces (rail de filtres à gauche, tableau à en-têtes de colonnes), jugé trop industriel.

**Key Characteristics:**
- Une liste douce sur un panneau arrondi, sans cadre ni carte par forfait.
- La ligne d'arrêts comme signature, à l'horizontale dans la liste, à la verticale dans la fiche.
- Tout ce qui se touche est une pilule ou un rond.
- Deux palettes (sombre par défaut, claire) qui disent la même chose.

## Colors

Noir, blanc et gris neutres, un seul rouge. Les valeurs du thème sombre sont la référence ; chaque variable a sa valeur claire (clés `-clair`), et l'en-tête comme les titres de fenêtre restent noirs dans les deux thèmes.

### Primary
- **Rouge d'accent** (`rouge`, `rouge-fonce` au survol) : fond de l'action principale et pastille du terminus. Texte blanc dessus.
- **Rouge lisible** (`rouge-vif`) : le prix TTC, partout où il s'écrit, et l'anneau de focus (3 px).

### Neutral
- **Fond** (`fond`) : la page et la barre des filtres.
- **Surface** (`surface`) : le panneau de la liste, la fiche, le total, les menus, les fenêtres.
- **Surface 2** (`surface-2`) : survols, boutons seconds, bandeaux.
- **Trait** (`trait`, `trait-fort`) : séparateur entre deux rangées, contour des pastilles ; le trait fort dessine la ligne entre deux arrêts.
- **Texte** (`texte`, `texte-fort`, `texte-doux`) : courant, noms et titres, mentions.
- **Inverse** (`inverse`, `inverse-texte`) : blanc sur sombre, noir sur clair.
- **Vert** (`vert`) : la confirmation « Copié », rien d'autre. **Ambre** (`ambre`) : l'étoile d'un favori et les avertissements.

### Named Rules
**La règle du rouge.** Le rouge ne sert qu'au prix TTC et à l'action principale d'un écran. Un état, un lien ou un décor rouge de plus, et le prix ne se trouve plus d'un coup d'œil.

**La règle de la pastille pleine.** Une pastille pleine en couleur inverse veut dire « choisi » : filtre posé, choix en cours dans un menu, réglage retenu, quantité déjà au total. Elle ne sert à rien d'autre.

**La règle des deux palettes.** Aucune couleur en dur : tout passe par une variable de `:root`, déclarée dans les deux palettes, et chaque association texte/fond est mesurée par les tests de contraste.

## Typography

**Display Font:** Segoe UI Variable Display (repli : Segoe UI, system-ui)
**Body Font:** Segoe UI Variable Text (repli : Segoe UI, system-ui)

**Character:** les caractères humanistes du système, gras et un peu serrés pour les noms et les prix, chiffres tabulaires partout où un montant s'aligne. Polices du système : l'outil marche sans internet et ne télécharge rien.

### Hierarchy
- **Display** (700, 42px, 1) : le prix TTC au terminus de la fiche. Un seul par écran.
- **Headline** (600, 20px, 1.25) : le nom du forfait dans la fiche ; 19px/700 pour le TTC d'une rangée.
- **Title** (600, 15px, 1.3) : le nom d'un forfait dans la liste ; 16px pour un arrêt de la fiche.
- **Body** (400, 15px, 1.4) : texte courant ; 13px/500 pour la ligne d'arrêts d'une rangée.
- **Label** (600, 13 à 14px) : pastilles, boutons, compteurs ; 12px en gris doux pour le nom d'une famille au-dessus de son arrêt.

### Named Rules
**La règle des chiffres.** Tout montant est en chiffres tabulaires et aligné à droite : dans la liste, les prix tombent toujours au même endroit.

## Layout

En-tête noir collant (64 px ; 60 px sous 600 px de large, 52 px en paysage bas) : la marque, la recherche blanche en pilule au centre, le menu. Dessous, une barre collante (56 px ; 60 px sur un écran qui se touche) : les pastilles de filtre, le nombre de forfaits, « Récents », le tri, puis l'ajout en mode modification.

La mise en page suit la largeur de la page (requêtes de conteneur), pas l'appareil :
- **1040 px et plus** : la liste à gauche, la fiche du forfait choisi et le total à droite. Cinq familles en pastilles. Si la page fait moins de 900 px de haut (portable, écran à 125 % ; seuil multiplié par la taille du texte), le total ne tient plus sous la fiche : il devient une barre rangée sous le panneau, qui ouvre sa feuille, et la fiche se serre (validé le 16/11/2026).
- **En dessous** : la liste seule ; la fiche monte du bas au premier appui, le total tient dans une barre en bas qui ouvre sa feuille.
- **Sous 600 px** : trois pastilles puis « Autres » (resserrées sous 375 px pour tenir sur une ligne à 360 px, validé le 19/11/2026) ; la rangée ne garde que le nom, la ligne d'arrêts, le TTC et le « + ».

Une rangée fait 50 px au moins (58 px sur la maquette, serrée le 16/11/2026 pour montrer un forfait de plus) : nom (trois lignes au plus), ligne d'arrêts dessous, puis TTC et HT, référence à copier, « + ». Les commandes font 36 px de haut à la souris et 44 px dès que l'écran se touche ; ce choix se fait une fois, à l'ouverture, jamais en cours de route.

La taille du texte se règle en trois crans (`zoom` sur la racine) : toute mesure en unités d'écran se divise par `var(--zoom)`.

## Elevation & Depth

Tout est à plat : les surfaces se détachent par leur ton (fond, surface, surface 2), sans filet de cadre ni ombre au repos.

### Shadow Vocabulary
- **Ombre portée forte** (`--ombre-forte`, `0 14px 40px` noir à 60 %, 25 % en clair) : seulement ce qui flotte au-dessus de la page (menus, fenêtres, feuilles, message de confirmation).

### Named Rules
**La règle du ton.** Une surface se sépare de sa voisine par un ton, jamais par un contour. Le seul trait de la liste est le séparateur d'un pixel entre deux rangées. Seuls gardent un contour d'un pixel : les pastilles de filtre et le tri (des commandes, pas des surfaces) et ce qui flotte au-dessus de la page.

## Shapes

Des ronds et des pilules. Toute commande est une pilule (`rond`) ou un cercle ; les panneaux, menus et fenêtres ont un grand rayon (20 px), les feuilles qui montent du bas 26 px, le survol d'une rangée et les choix d'un menu 14 px. Les arrêts de la ligne sont des anneaux ; le terminus est un disque rouge avec son halo.

## Components

### Buttons
- **Shape:** pilule (999px), 36 px de haut (44 px sur un écran tactile), texte 600.
- **Primary:** fond rouge, texte blanc ; un seul par écran ou par fenêtre.
- **Second:** fond `surface-2`, sans contour. **Nu:** transparent, texte doux. **Icône:** un rond de la hauteur d'une commande.
- **Hover / Focus:** le fond change en 150 ms ; à l'appui, `scale(.97)`. Le survol n'existe qu'à la souris (`html[data-geste=souris]`), jamais par une requête `hover` ou `pointer`. Focus : anneau `rouge-vif` de 3 px, décalé de 2 px.

### Chips
- **Style:** pastille de filtre sur `surface`, contour `trait`, chevron qui pivote quand son menu est ouvert.
- **State:** posée, elle devient pleine (couleur inverse) et affiche l'élément choisi ; le nom de la famille reste lu par les lecteurs d'écran.

### Cards / Containers
- **Corner Style:** 20 px pour le panneau de la liste, la fiche et le total.
- **Background:** `surface` sur `fond`.
- **Shadow Strategy:** aucune (voir Elevation & Depth).
- **Border:** aucun pour les panneaux de la page ; ce qui flotte (menus, fenêtres) garde un contour `trait` d'un pixel.
- **Internal Padding:** 16 px à gauche et à droite d'une rangée ; 18 px dans la fiche et le total (20 px en feuille).

### Inputs / Fields
- **Style:** la recherche est une pilule blanche de 44 px dans l'en-tête noir, dans les deux thèmes ; les champs des fenêtres sont sur `fond` avec un contour `trait-fort`, rayon 12 px, 46 px de haut.
- **Focus:** contour `rouge-vif` et halo rouge voilé de 3 px.
- **Error:** contour rouge (`aria-invalid`) et message sous le champ, dans la fenêtre.

### Navigation
- **Menus de la barre:** un menu s'ouvre sous sa pastille (rayon 20 px, ombre forte, entrée de 180 ms) ; chaque choix dit combien de forfaits il donne ; le choix en cours est une pastille pleine. Échap ou un appui ailleurs le referme et rend le focus.
- **Feuilles du bas:** fiche et total montent du bas (320 ms) sur les écrans étroits ; elles se ferment par leur bouton, Échap ou un appui à côté.

### La ligne (composant signature)
Dans une rangée : des anneaux de 9 px reliés par un trait fort de 2 px, le nom de chaque élément à droite de son anneau. Dans la fiche : la même ligne à la verticale, le nom de la famille en petit au-dessus de chaque arrêt, et le terminus en disque rouge qui porte le TTC en 42 px. Au changement de forfait, les arrêts entrent l'un après l'autre (45 ms d'écart).

### Mouvement
Courbe de sortie unique (`cubic-bezier(0.16, 1, 0.3, 1)`), 150 à 360 ms, toujours en réponse à un geste : entrée de la liste, changement de fiche, coche de « Copié », quantité qui arrive sur le « + », montants du total. Tout s'éteint sous `prefers-reduced-motion`.

## Do's and Don'ts

### Do:
- **Do** garder l'ordre nom, éléments, prix, dans la liste comme dans la fiche.
- **Do** écrire chaque survol sous `:where(html[data-geste=souris])` et chaque retour d'appui au doigt sous `:where(html[data-geste=doigt])`.
- **Do** décider la taille des commandes une fois, à l'ouverture (`html[data-tactile]`).
- **Do** garder le message d'une action dans la fenêtre où elle a eu lieu.

### Don't:
- **Don't** revenir au rail de filtres à gauche ni au tableau à en-têtes de colonnes : montrés et refusés.
- **Don't** entourer un forfait d'un cadre ni lui donner sa propre carte.
- **Don't** faire réagir au focus ou à un événement de pointeur quoi que ce soit qui déplace le contenu : l'appui du doigt est perdu.
- **Don't** utiliser `@media (hover: …)` ni `(pointer: …)` : un PC à écran tactile répond « tactile » même avec une souris.
- **Don't** charger une police ou une ressource en ligne : l'outil marche sans internet.
