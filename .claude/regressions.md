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
- À garder : sur iPhone/iPad, `navigator.share` avec le fichier ; annulé = rappel gardé.
- Test : `test_export_iphone_par_le_menu_partager`.
