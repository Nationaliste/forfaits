# Écran principal (recherche et liste des forfaits)

Portée : toute l'appli (ordi et téléphone), écran principal d'abord ; les fenêtres suivent le même monde. Mode : Operate.

- Public et tâche : voir `PRODUCT.md`. Réponses du 13/11/2026 : on voit trop peu de forfaits, ça fait bricolé, trop d'appuis pour agir ; seul l'ordre nom, éléments, prix est intouchable (avec les palettes) ; la fenêtre du PC est tantôt pleine, tantôt sur une moitié d'écran.
- Palettes épinglées par l'utilisateur : sombre et claire actuelles, inchangées.
- Moment à retenir : le forfait dessiné comme une ligne, ses éléments en arrêts, son prix TTC au terminus.
- Directions déjà montrées et refusées : le tarif de catalogue de pièces (tirage 1, 5, 7 du 13/11, « trop industriel », puis sa version adoucie). Ne pas y revenir : ni rail de filtres à gauche, ni tableau à en-têtes de colonnes.
- Décidé le 26/11/2026 : pas de police embarquée, l'outil garde les polices du système (il marche sans internet et ne télécharge rien).

## Direction contract

THESIS: un forfait est un trajet : des éléments qui s'enchaînent jusqu'à un prix. L'outil refuse le mur de cartes à boutons comme le tableau d'administration à colonnes : une liste douce où chaque forfait montre sa ligne, et une fiche qui la déroule.

OWN-WORLD: la signalétique de transport d'aujourd'hui. Palettes actuelles inchangées ; formes rondes partout (pastilles, champs et boutons en pilule, panneaux aux grands rayons) ; caractères humanistes du système, gras et serrés pour les noms et les prix, chiffres tabulaires ; une pastille pleine en couleur inverse dit « choisi » (filtre posé, quantité au total) ; le rouge ne sert qu'au prix TTC et à l'action principale ; aucun filet de cadre, les surfaces se détachent par leur ton.

STORY: je tape deux mots, la liste se resserre ; le premier forfait ouvre sa fiche, où ses éléments descendent arrêt par arrêt jusqu'au prix en grand ; un clic copie la référence, un clic l'ajoute au total.

FIRST VIEWPORT: bandeau noir (marque, recherche blanche en pilule au centre, menu). Dessous, une rangée de pastilles de filtres par famille, le nombre de forfaits et le tri. Grand écran : à gauche la liste sur un panneau arrondi (nom, ligne d'arrêts, TTC et HT, référence à copier, « + »), à droite la fiche du forfait choisi (nom, ligne verticale des éléments avec leur famille, TTC au terminus en très grand, référence, « Ajouter au total ») puis le total. Demi-écran et téléphone : la liste seule, la fiche monte du bas au premier appui, le total reste en barre basse. Dix lignes au moins visibles sur un écran d'ordi, six sur un téléphone.

FORM: la signalétique de transport d'aujourd'hui, n° 7 de la liste ; tirage 7, 3, 4 (seconde liste, après le refus du tarif de catalogue). Appli bancaire (n° 3) : compétitive, elle tient la clarté (une ligne, un montant) mais ne dit rien du métier ; elle reste l'alternative entière. Relance de l'écran des départs (n° 4, écarté) : chaque rangée se lit d'un seul regard, les prix tombent toujours au même endroit.

FINISH: relecture de fin faite le 16/11/2026, `disposition: fix` (4 points), `DESIGN.md` écrit. Suites données :
- Dix lignes sur un écran d'ordi : rangées serrées de 58 à 50 px sur choix de l'utilisateur (10 entières à 1280×720, 11 à 1366×768 ; dans Edge sur un portable 1366×768, page de ~640 px de haut : 9).
- Police sur Android (`system-ui`, donc pas Segoe) : celle du téléphone, acceptée le 26/11/2026 (roadmap#1030) ; aucune capture d'un vrai téléphone n'a encore été jugée.
- Filtre posé : la pastille pleine affiche l'élément seul, comme la maquette validée (la famille reste lue par les lecteurs d'écran) ; l'utilisateur garde aussi le retrait par « Tous » (pas de croix).
- Pastille « Exemple » au-dessus du nom dans la fiche : gardée (marque de donnée déjà présente dans l'ancien outil et sur la maquette validée ; absente des vrais forfaits) ; le relecteur la tient pour un surtitre à retirer.
- Page d'ordi peu haute (moins de 900 px, multiplié par la taille du texte) : le total sortait de l'écran sous la fiche (trouvé par la relecture du code). Maquette montrée et validée le 16/11/2026 : le total devient une barre rangée sous le panneau, qui ouvre sa feuille ; la fiche se serre.
- Écarts acceptés avec la maquette : choix « Tous » et « Sans … » dans les menus, icône des surnoms dans la fiche, référence et HT sur chaque ligne du total, commandes de 44 px sur un écran qui se touche, ligne « Données du … » sous la marque, contour d'un pixel sur les pastilles et sur ce qui flotte (OWN-WORLD disait « aucun filet de cadre » : il vaut pour les panneaux de la page).
