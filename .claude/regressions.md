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
- Où : `index.html`, les 20 règles `:hover` de la feuille.
- Bug : au doigt, l'effet de survol restait appliqué jusqu'au prochain appui ailleurs (mesuré sur Chromium, WebKit et Firefox : `transform` et `border-color` persistaient après l'appui).
- À garder : chaque règle de survol s'écrit `:where(html[data-geste=souris]) …:hover`, sur sa propre ligne et à sa place dans la feuille (`:where()` n'ajoute aucune spécificité). Le retour d'un appui vient de `:active` sous `:where(html[data-geste=doigt])`.
- Test : `test_la_rangee_des_familles_suit_le_doigt_et_pas_la_requete_media`.

## 2026-11-09 — « @media (pointer: coarse) » répond tactile sur un PC
- Où : `index.html`, tout ce qui dépend du geste (survol, repli des filtres, focus du champ de recherche).
- Bug : sur un PC Windows à dalle tactile avec une souris branchée, Firefox et Chrome répondent `pointer: coarse` et `hover: none`. Conséquences mesurées : le champ de recherche ne recevait pas le focus à l'ouverture, et une règle de survol sous `@media (hover: hover)` aurait disparu sur ce PC.
- À garder : `data-geste` sur `<html>`, posé par le `pointerType` de `pointerdown`/`pointermove` et au démarrage par `(any-pointer: fine)`. Jamais `@media (hover: …)` ni `(pointer: …)` pour décider du geste.
- Test : `test_la_rangee_des_familles_suit_le_doigt_et_pas_la_requete_media` (3e partie : après un mouvement de souris, `data-geste` repasse à `souris` ; la rangée, elle, reste repliée — c'est voulu, voir l'entrée suivante).

## 2026-11-09 — Appui avalé quand le contenu bouge entre le doigt qui touche et le doigt qui part
- Où : `index.html`, repli de la rangée des familles (`:where(html[data-recherche=doigt]) .zone-recherche:has(#recherche:not(:placeholder-shown)) .filtres`).
- Bug : replier la rangée sur le **focus** du champ la faisait revenir dès que le doigt touchait une carte ; le contenu redescendait de 116 px et plus aucune carte ne s'ouvrait (mesuré sur les 3 moteurs).
- À garder : le déclencheur est le TEXTE du champ, jamais son focus ni un événement de pointeur. Plus généralement : rien qui déplace le contenu ne doit réagir au focus ou au `touchstart`.
- Test : `test_la_rangee_des_familles_suit_le_doigt_et_pas_la_requete_media` (l'appui sur une carte reste pris).

## 2026-11-09 — Nouveau défaut d'un réglage d'appareil jamais appliqué aux appareils en service
- Où : `index.html`, `chargerAppareil` et `sauverAppareil` (réglage `recentsOuverts`).
- Bug : la rangée « Derniers consultés » devait devenir repliée par défaut. La lecture faisait `lu.recentsPlies !== false`, mais `sauverAppareil()` réécrit TOUT l'objet `appareil` : un appareil déjà en service avait déjà `recentsPlies: false` enregistré en clair, donc il gardait l'ancien défaut (vérifié en ouvrant l'ancienne version puis la nouvelle sur le même navigateur). Seul un appareil neuf voyait le changement.
- À garder : changer un défaut de `forfaits.appareil.v1` demande une NOUVELLE clé, jamais une lecture inversée. Ici `recentsPlies` est devenue `recentsOuverts` (sens inverse) et l'ancienne clé est ignorée.
- Test : `test_la_rangee_des_derniers_consultes_s_ouvre_et_se_referme` (il injecte l'ancienne forme enregistrée avant de recharger).
