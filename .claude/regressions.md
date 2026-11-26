# Registre des régressions

## 2026-10-20 — « Remplacer tout » remettait d'anciens prix sans les annoncer
- Où : `index.html`, `bilanFusion` et la fenêtre « Importer ce fichier ? » (import .json).
- Bug : « Prix qui changent » ne comptait que les forfaits plus récents dans le fichier (ceux de « Mettre à jour »). Avec un fichier plus ancien, « Remplacer tout » remettait les anciens prix sans rien dire.
- À garder : `bilan.prixRemplacer` compare les prix sans regarder `maj`, et la fenêtre l'affiche quand il diffère de `bilan.prix`.
- Test : `test_remplacer_tout_annonce_les_anciens_prix`.

## 2026-10-28 — Safari : corps des fenêtres écrasé au-delà de 600 px de large
- Où : `index.html`, CSS `.dlg-corps` et `.dlg-form` (le formulaire entre la fenêtre et son corps).
- Bug : `flex: 1` (base 0) dans une fenêtre sans hauteur fixée : WebKit ramenait le corps à sa marge (32 px), contenu invisible.
- À garder : `.dlg-corps` et `.dlg-form` en `flex: 1 1 auto; min-height: 0;` (jamais `flex: 1`, base 0 écrasée par Safari).
- Test : `test_fenetre_lisible_sur_grand_ecran` (lancer avec `NAVIGATEURS=webkit`).

## 2026-10-28 — Safari : clic perdu juste après un renommage dans « Listes des éléments »
- Où : `index.html`, `ouvrirListes`, message `msg-erreur msg-reserve`.
- Bug : effacer le message d'erreur au renommage faisait remonter la liste pendant le clic ; WebKit perdait le clic.
- À garder : la classe `msg-reserve` (place gardée pour le message).
- Test : `test_listes_ajouter_renommer_et_proteger` (sous WebKit).

## 2026-10-28 — Horloge en avance : une correction perdait la fusion
- Où : `index.html`, `remplacer` et l'import du tableau (`maj` du forfait).
- Bug : un enregistrement daté dans le futur (moins de 24 h) gardait la priorité sur une correction faite ensuite.
- À garder : une modification prend `max(maintenant, ancienne maj + 1)`.
- Test : `test_horloge_en_avance_une_correction_l_emporte_quand_meme`.

## 2026-10-28 — iPhone : export compté réussi sans fichier
- Où : `index.html`, `exporterJson`.
- Bug : sur iPhone, le téléchargement peut ne rien enregistrer, mais le rappel d'export était remis à zéro.
- À garder : sur iPhone/iPad, `navigator.share` avec le fichier ; annulé ou partage refusé (repli sur le téléchargement) = rappel gardé.
- Test : `test_export_iphone_par_le_menu_partager`.

## 2026-10-28 — Exemples d'une autre version jamais retirés par le fichier de l'équipe
- Où : `index.html`, `importerFichier` (choix « Mettre à jour »).
- Bug : les exemples ont changé d'identifiants (renommage) ; la fusion propage les suppressions par identifiant, donc un appareil neuf qui importait le fichier de l'équipe gardait ses exemples.
- À garder : après la fusion, un fichier qui a des exemples supprimés et aucun exemple actif lance `marquerExemplesSupprimes(true)` (éléments marqués exemple seulement : un élément d’un fichier sans date a aussi maj 0).
- Test : `test_fichier_sans_exemples_retire_ceux_d_une_autre_version`.

## 2026-11-09 — Survol resté allumé après un appui du doigt
- Où : `index.html`, toutes les règles `:hover` de la feuille.
- Bug : au doigt, l'effet de survol restait appliqué jusqu'au prochain appui ailleurs (mesuré sur Chromium, WebKit et Firefox : `transform` et `border-color` persistaient après l'appui).
- À garder : chaque règle de survol s'écrit `:where(html[data-geste=souris]) …:hover`, sur sa propre ligne et à sa place dans la feuille (`:where()` n'ajoute aucune spécificité). Le retour d'un appui vient de `:active` sous `:where(html[data-geste=doigt])`.
- Test : `test_la_rangee_des_familles_suit_le_doigt_et_pas_la_requete_media`.

## 2026-11-09 — « @media (pointer: coarse) » répond tactile sur un PC
- Où : `index.html`, tout ce qui dépend du geste (survol, repli des filtres, focus du champ de recherche).
- Bug : sur un PC Windows à dalle tactile avec une souris branchée, Firefox et Chrome répondent `pointer: coarse` et `hover: none`. Conséquences mesurées : le champ de recherche ne recevait pas le focus à l'ouverture, et une règle de survol sous `@media (hover: hover)` aurait disparu sur ce PC.
- À garder : `data-geste` sur `<html>`, posé par le `pointerType` de `pointerdown`/`pointermove` et au démarrage par `(any-pointer: fine)`. Jamais `@media (hover: …)` ni `(pointer: …)` pour décider du geste.
- Test : `test_la_rangee_des_familles_suit_le_doigt_et_pas_la_requete_media` (3e partie : après un mouvement de souris, `data-geste` repasse à `souris` ; la rangée, elle, reste repliée — c'est voulu, voir l'entrée suivante).

## 2026-11-09 — Appui avalé quand le contenu bouge entre le doigt qui touche et le doigt qui part
- Où : `index.html`, repli des pastilles de filtre sans filtre posé (`:where(html[data-recherche=doigt]) .page:has(#recherche:not(:placeholder-shown)) .filtre:not(.actif)`).
- Bug : replier la rangée sur le **focus** du champ la faisait revenir dès que le doigt touchait une carte ; le contenu redescendait de 116 px et plus aucune carte ne s'ouvrait (mesuré sur les 3 moteurs).
- À garder : le déclencheur est le TEXTE du champ, jamais son focus ni un événement de pointeur. Plus généralement : rien qui déplace le contenu ne doit réagir au focus ou au `touchstart`.
- Test : `test_la_rangee_des_familles_suit_le_doigt_et_pas_la_requete_media` (l'appui sur une carte reste pris).

## 2026-11-09 — Nouveau défaut d'un réglage d'appareil jamais appliqué aux appareils en service
- Où : `index.html`, `chargerAppareil` et `sauverAppareil` (réglage `recentsOuverts`).
- Bug : la rangée « Derniers consultés » devait devenir repliée par défaut. La lecture faisait `lu.recentsPlies !== false`, mais `sauverAppareil()` réécrit TOUT l'objet `appareil` : un appareil déjà en service avait déjà `recentsPlies: false` enregistré en clair, donc il gardait l'ancien défaut (vérifié en ouvrant l'ancienne version puis la nouvelle sur le même navigateur). Seul un appareil neuf voyait le changement.
- À garder : changer un défaut de `forfaits.appareil.v1` demande une NOUVELLE clé, jamais une lecture inversée. Ici `recentsPlies` est devenue `recentsOuverts` (sens inverse) et l'ancienne clé est ignorée.
- Test : `test_recents_quatre_au_plus_le_dernier_en_tete_et_anciens_reglages_ignores` (depuis la refonte du 16/11/2026 les récents sont un menu et ces réglages sont ignorés : le test injecte les anciennes formes enregistrées et vérifie qu'elles ne cassent rien).

## 2026-11-10 — Appareil figé sur une vieille page après une visite à une adresse à paramètres
- Où : `sw.js`, `ranger` et la réponse de l'écouteur `fetch`.
- Bug : la copie était rangée sous l'adresse complète (`cache.put(requete)`) mais relue avec `ignoreSearch`. Après une seule visite à « /?x=1 », cette copie passait devant celle de « / » (la plus ancienne gagne) et plus rien ne la rafraîchissait : l'appareil restait sur la page de ce jour-là, et « Recharger » la redonnait (rejoué sur Chromium, Edge et Firefox).
- À garder : une copie se range ET se relit sous `cle(requete)` (adresse sans paramètres ni ancre), dans `CACHE` seulement — jamais `ignoreSearch`, jamais `caches.match` global. Pour débloquer des appareils déjà touchés, le nom de `CACHE` change (`forfaits-v2`) : l'activation jette l'ancienne copie.
- Test : `test_adresse_a_parametres_ne_fige_pas_la_page` et `test_ancienne_copie_jetee_quand_son_nom_change`.

## 2026-11-10 — Bandeau « nouvelle version » absent quand la page vient d'être demandée
- Où : `sw.js`, `ranger`.
- Bug : `ranger` prévenait les onglets de `clients.matchAll()` dès la copie fraîche rangée. L'onglet qui venait de demander la page n'y était pas encore (liste vide, ou seulement la page qu'il remplace) : il affichait l'ancienne copie sans bandeau, et la nouveauté n'arrivait qu'à l'ouverture suivante. Mesuré sur Edge entre 1 fois sur 10 et 1 fois sur 5 (3 sur 30, 5 sur 25), et à chaque fois dès que la page arrive 150 ms plus tard : sur Chromium, Edge et Firefox par le test, sur WebKit par une mesure à la main.
- À garder : `ranger` reçoit `ev.resultingClientId` et, si cet onglet n'était pas dans la liste, le redemande par `clients.get()` toutes les 100 ms (3 s au plus) avant de lui écrire. La boucle est nécessaire : Firefox répond « rien » sans attendre que l'onglet existe.
- Test : `test_nouvelle_version_proposee_a_la_page_qui_vient_d_etre_demandee` (le serveur de test sert `sw.js` avec un retard posé après la lecture de la copie gardée, `page_lente`).

## 2026-11-10 — Données d'une version plus récente prises pour des données abîmées, puis écrasées
- Où : `index.html`, `charger`, `sauver` et l'écouteur `storage`.
- Bug : `valider` refuse une `version` supérieure à `VERSION_FORMAT`, et `charger` prenait tout refus pour des données abîmées : copie de côté, exemples à l'écran, puis le premier enregistrement réécrivait la clé avec les exemples. Il suffit d'une page en retard sur les données de l'appareil : deux onglets dont un à jour, un onglet endormi, un site revenu à une ancienne page.
- À garder : `charger` reconnaît ce cas AVANT tout le reste (`estFutur`, `donneesFutures`) : ni copie de côté, ni exemples, rien d'affiché, un bandeau « Recharger ». `sauver()` relit le stockage juste avant d'écrire et renvoie `false` sans rien écrire : chaque appel s'écrit `if (!sauver()) return;`. Import, export, formulaire et listes commencent par `if (lectureSeule()) return;` (un export fait là serait vide, et effacerait tout une fois importé ailleurs en « Remplacer »).
- Test : `test_donnees_d_une_version_plus_recente_ni_remplacees_ni_ecrasees`, `test_enregistrement_refuse_quand_une_version_plus_recente_est_passee_entre_temps` et `test_onglet_ouvert_prevenu_par_l_onglet_passe_a_une_version_plus_recente`.

## 2026-11-10 — Référence en double : deux messages l'un sous l'autre
- Où : `index.html`, `ouvrirFormulaire` (`verifierRef`, `msgRef` et `msgErreur`).
- Bug : à l'enregistrement d'une référence déjà prise, le refus (`msgErreur`) venait se poser sous le champ, juste sous le contrôle en direct (`msgRef`) qui disait déjà la même chose.
- À garder : un seul message sous la référence. Au refus, `msgRef` est vidé ; dès que la référence est retapée, c'est `msgErreur` qui est vidé et le contrôle en direct reprend la main. Les deux textes viennent de `dejaPrise()`.
- Test : `test_doublon_de_reference_bloque`.

## 2026-11-10 — Listes des éléments : un surnom refusé vidait la saisie, et le message restait
- Où : `index.html`, `ouvrirListes` (`signaler`, `changer`).
- Bug : un seul surnom refusé parmi plusieurs remettait tout le champ à l'ancienne valeur (les surnoms valables étaient à retaper), et le message d'erreur restait affiché après l'action suivante, alors qu'il ne parlait plus de rien.
- À garder : la saisie refusée reste dans son champ, marqué `aria-invalid` (bordure rouge) ; rien n'est enregistré. `changer()` appelle `signaler('')` : au changement suivant qui réussit, le champ reprend ce qui est enregistré et le message s'en va. Les boutons « Supprimer » n'effacent pas le message eux-mêmes (un refus jamais vu disparaîtrait au clic).
- Test : `test_surnoms_refuses_dans_les_listes_restent_a_corriger` et `test_plus_de_trois_surnoms_d_avant_la_limite_ne_bloquent_rien`.

## 2026-11-10 — Tri perdu à chaque rechargement
- Où : `index.html`, `chargerAppareil`, `rendreResultats` et l'écouteur de `#tri`.
- Bug : le tri n'existait que dans la liste `#tri` de la page : rechargée, elle revenait à « par référence ».
- À garder : le tri est un réglage de l'appareil (`tri` dans `forfaits.appareil.v1`, jamais exporté). `rendreResultats` lit `appareil.tri` et y aligne la liste ; une valeur inconnue revient à `ref`.
- Test : `test_trier_par_prix` et `test_tri_inconnu_dans_les_reglages_revient_aux_references`.

## 2026-11-10 — Téléphone d'un responsable : le rappel d'export et le total couvraient tous les forfaits
- Où : `index.html`, CSS `.rappel`, `.barre` et `#btn-ajouter` sous 600 px de large (conteneur `page`) ; `rendreRappel` ; `--bas-total`.
- Bug : en 375x812, mode modification, une modification à exporter et un total en cours : le rappel prenait 128 px (texte sur deux lignes, bouton dessous) au-dessus des 70 px du total, et « + Ajouter un forfait » passait sous le compteur (58 px de plus). Il restait 7 px du premier forfait à l'écran (mesuré).
- À garder : sous 600 px le rappel tient sur une ligne (`flex-wrap: nowrap`, la consigne `.rappel-suite` cachée, elle est redite par la fenêtre d'export) et le bouton d'ajout reste sur la ligne du compteur, réduit à « + ». Son texte long (`.long`) est caché, et son `aria-label` « Ajouter un forfait » reste le nom lu par les lecteurs d'écran. Le rappel se pose au-dessus de la barre du total d'après sa hauteur MESURÉE (`--bas-total`, ResizeObserver sur `#barre-total`), jamais d'après une hauteur écrite en dur.
- Test : `test_telephone_du_responsable_rappel_et_total_laissent_voir_un_forfait`.

## 2026-11-16 — Commandes qui grossissaient au contact du doigt
- Où : `index.html`, `--h` (hauteur des commandes) et `html[data-tactile]`.
- Bug : pendant la refonte, `--h` passait de 36 à 44 px d'après `data-geste`. Au premier contact du doigt sur un PC tactile, toutes les commandes grossissaient, le contenu descendait et l'appui était perdu (même famille que « Appui avalé »).
- À garder : `--h` ne dépend jamais de `data-geste`. Il vaut 44 px si l'écran se touche (`data-tactile`, posé UNE fois au démarrage par `(any-pointer: coarse)`), sous 600 px et dans une feuille du bas ; 36 px sinon.
- Test : `test_taille_des_commandes_ne_change_pas_au_contact_du_doigt` (l'attendu sans émulation se calcule d'après `(any-pointer: coarse)` : Firefox lit la vraie dalle tactile du PC).

## 2026-11-16 — Très grands caractères : le rappel chevauchait le total, et le TTC sortait de la barre
- Où : `index.html`, `#rappel`, `#barre-total` (`.barre-total`, `.barre-total-montants`), `--bas-total`.
- Bug : en « Très grand » sur téléphone, la barre du total est plus haute que prévu : le rappel d'export, posé à une hauteur écrite en dur, passait dessus ; et le montant TTC dépassait le bord droit de la barre.
- À garder : `--bas-total` vient de la hauteur mesurée de la barre ; la barre et ses montants sont en `flex-wrap: wrap` (les montants passent sous « Total · N articles » au lieu de sortir).
- Test : `test_telephone_du_responsable_rappel_et_total_laissent_voir_un_forfait` (partie « Très grand » : `dans_la_barre`).

## 2026-11-16 — Refonte : le HT de chaque ligne du total avait disparu
- Où : `index.html`, `totalContenu` (`.total-ligne-prix small`).
- Bug : la refonte de l'interface n'affichait plus que le TTC de chaque ligne du total ; le HT par ligne (les clients sont des professionnels) n'était plus que dans la somme. Trouvé en comparant les textes de l'ancienne page et de la nouvelle.
- À garder : chaque ligne du total montre son TTC et, dessous, son HT.
- Test : `test_total_additionne_forfaits_quantites_et_lignes_libres`.

## 2026-11-16 — Téléphone tourné d'un responsable : rappel et total empilés cachaient la liste
- Où : `index.html`, bloc `@media (orientation: landscape) and (max-height: 540px)` (`.rappel`, `.barre-total`, `--bas-rappel`).
- Bug : en 812x375, mode modification, une modification à exporter et un total en cours : les deux barres empilées prenaient 128 px des 375 de l'écran, il restait 41 px du premier forfait (mesuré).
- À garder : en paysage bas, rappel et total sont côte à côte (une moitié d'écran chacun) et la barre des filtres tient sur une ligne (« + » seul, sans icône de pastille) ; sans total, le rappel reste au milieu.
- Test : `test_telephone_tourne_du_responsable_rappel_et_total_cote_a_cote`.

## 2026-11-16 — Page d'ordi peu haute : le total sortait de l'écran sous la fiche
- Où : `index.html`, `totalSousFiche`, `rendreTotal`, `calerBas`, CSS `--total` sur `.panneau`, `.barre-total.colonne`, `.panneau[data-total="barre"]`.
- Bug : sur un portable (page de 1366x640 dans Edge) ou un écran à 125 %, la fiche d'un forfait à 4 éléments prend 481 px des 504 du panneau : la somme du total était hors de l'écran, il fallait faire défiler le panneau (mesuré ; jusqu'à 1536x730).
- À garder : sous 900 px de haut (seuil multiplié par la taille du texte), le total est la barre `#barre-total.colonne`, rangée sous le panneau, qui ouvre `#dlg-total` ; le panneau lui laisse la place (`--bas-colonne`) et la fiche se serre. Le seuil est dans la feuille de style seulement (`--total`), le script le lit.
- Test : `test_fenetre_retrecie_la_fiche_et_le_total_changent_de_place` et `test_affichage_telephone_et_pc` (cas « pc », 1280x800).

## 2026-11-16 — Total redessiné : ses lignes repartaient en haut
- Où : `index.html`, `rendreTotal` (`poser`).
- Bug : chaque ajout ou changement de quantité reconstruit le total ; la zone des lignes revenait en haut et la ligne qui venait d'arriver restait sous le bord.
- À garder : `poser` rend son défilement à `.total-lignes` et amène la ligne ajoutée dans la zone, par `scrollTop` (jamais `scrollIntoView`, qui ferait aussi défiler la page sous la souris).
- Test : `test_total_du_panneau_garde_son_defilement_et_montre_la_ligne_ajoutee`.

## 2026-11-16 — Fiche fermée après un favori : le clavier retombait en haut de la page
- Où : `index.html`, écouteur `close` de `#dlg-fiche`.
- Bug : sur petit écran, un favori redessine la liste sous la feuille ; le bouton qui l'avait ouverte n'existe plus. À l'événement `close`, le focus est encore sur un bouton de la feuille fermée (pas sur `body`), donc le retour au forfait ne se faisait pas (Chromium et Firefox).
- À garder : le focus revient à la rangée du forfait choisi s'il est sur `body` OU encore dans la feuille.
- Test : `test_fiche_fermee_apres_un_favori_le_clavier_revient_au_forfait`.

## 2026-11-16 — Refonte : plus de retour d'appui au doigt sur une rangée ni sur une suggestion
- Où : `index.html`, règle `:where(html[data-geste=doigt]) :is(…):active`.
- Bug : la refonte avait retiré `.carte-ouvrir` et `.suggestion` de la liste ; au doigt le survol est éteint, donc rien ne montrait que l'appui était pris.
- À garder : tout ce qui s'appuie et n'est pas un `.btn` est dans cette liste (rangée, suggestion, pastille, « + », copie, choix de menu, `.btn-doux`, `.btn-lien`).
- Test : `test_retour_d_appui_au_doigt_sur_les_rangees_et_les_suggestions`.

## 2026-11-16 — Écran tactile : la page défilait de 4 px pour rien
- Où : `index.html`, `--barre` sous `html[data-tactile]`.
- Bug : avec des commandes de 44 px la barre des filtres fait 60 px, mais `--barre` disait 56 : la liste dépassait l'écran de 4 px et le panneau collait 4 px trop haut (mesuré sur Firefox, qui lit la dalle tactile du PC).
- À garder : `--barre` vaut 60 px quand `data-tactile` est posé.
- Test : `test_total_du_panneau_garde_son_defilement_et_montre_la_ligne_ajoutee` (`scrollY` reste à 0 ; Firefox lit la vraie dalle).

## 2026-11-19 — Téléphone de 360 px : « Autres » seul sur une 2e ligne de filtres
- Où : `index.html`, `@container page (max-width: 374px)` (`.filtres`, `.filtre`).
- Bug : à 360 px de large (courant sur Android) il manquait quelques pixels pour les trois pastilles et « Autres » ; « Autres » passait seul sur une 2e ligne et prenait la place d'un forfait (50 px). Reste de la refonte (roadmap#1032).
- À garder : sous 375 px, pastilles resserrées (marges de 6 px, écart de 4 px, texte inchangé). À 320 px la 2e ligne reste, choix de l'utilisateur.
- Test : `test_telephone_etroit_garde_les_filtres_sur_une_ligne`.

## 2026-11-26 — Recherche : un nom d'élément cachait les références et désignations qui l'écrivent
- Où : `index.html`, `analyserRecherche`, `correspond`, `construireIndex` (`motsRefDes`).
- Bug : un mot égal au nom ou au surnom d'un élément devenait un filtre exact sur l'élément ; un forfait dont la référence ou la désignation contenait ce mot, sans avoir l'élément, disparaissait (roadmap#752).
- À garder : l'élément OU le mot entier dans la référence ou la désignation (`suiteDeMots` : « 3Q » ne ramène pas « 13Q »), jamais par le nom d'un autre élément.
- Test : `test_nom_d_element_trouve_aussi_la_reference_ou_la_designation_qui_l_ecrit`.

## 2026-11-26 — Total jeté à la relecture au-dessus d'un plafond plus bas que la saisie
- Où : `index.html`, `lireLigneTotal`.
- Bug : la relecture refusait un prix que la saisie et `valider` acceptaient ; au rechargement, la ligne (et le total) disparaissait (roadmap#751).
- À garder : un seul plafond, `PRIX_MAX`, pour la saisie, la relecture et `valider`.
- Test : `test_total_relu_jusqu_au_plafond_de_la_saisie`.

## 2026-11-26 — « + » au total : l'ancien prix gardé sans le dire
- Où : `index.html`, `ajouterAuTotal`, `totalContenu`, `prixChange`.
- Bug : un forfait dont le prix a changé depuis l'ajout restait à l'ancien prix dans le total, sans que rien ne le montre (roadmap#751).
- À garder : l'ancien prix reste (voulu), mais la ligne l'écrit en ambre avec le prix du moment, et le message du « + » le dit.
- Test : `test_prix_change_depuis_l_ajout_se_voit_dans_le_total`.

## 2026-11-26 — Message avec « Annuler » serré dans la moitié de l'écran
- Où : `index.html`, `.toast` (`width: max-content`).
- Bug : le message, posé à `left: 50 %`, prenait la largeur qui restait à droite ; au téléphone il passait sur trois lignes.
- À garder : `.toast { width: max-content; }` (la largeur maximale le garde dans l'écran).
- Test : `test_message_de_suppression_tient_dans_le_telephone_en_tres_grand`.
