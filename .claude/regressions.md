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

## 2026-11-05 — Retour arrière annulé par un second appareil responsable
- Où : `index.html`, `pourRetourArriere` et le bouton « Revenir » de `ouvrirVersions`.
- Bug : `/api/revenir` remet l'ancien paquet comme une nouvelle version, mais avec ses `maj` d'origine, plus anciens que la fausse manœuvre. Un AUTRE appareil responsable ne fusionnait donc rien (`apporte(distant, donnees)` faux), concluait qu'il avait du plus récent (`apporte(donnees, distant)` vrai) et renvoyait la fausse manœuvre : le retour ne tenait que sur l'appareil qui l'avait demandé et sur les appareils de consultation, alors que la fenêtre promet « les forfaits de tous les appareils ».
- À garder : après `/api/revenir`, l'appareil relit la version, la passe par `pourRetourArriere` (réhorodatage au présent de ce que le retour change, marques `supprime: true` pour ce qui a été créé depuis, `maj 0` des exemples jamais touchés laissé tel quel) puis la RENVOIE (`aEnvoyer = true` + `synchroniser()`). Ne pas « simplifier » en remplaçant simplement les données locales.
- Test : `test_un_retour_arriere_tient_face_a_un_second_responsable`.

## 2026-11-05 — La clé de l'équipe restait dans la barre d'adresse quand le lien était refusé
- Où : `index.html`, `appairerDepuisAdresse`.
- Bug : le `history.replaceState` qui efface le `#` venait APRÈS `if (!lien) return`. Un lien refusé par `lireLien` (coupé en route par la messagerie, sous-domaine du compte pas encore renseigné, autre compte) laissait donc la clé de 43 caractères affichée dans la barre d'adresse, dans l'entrée d'historique du navigateur (donc dans l'autocomplétion et l'historique synchronisé) et sur toute capture d'écran — et sans aucun message, l'appareil restait simplement non connecté. Qui lit cet historique déchiffre tout le paquet gardé dans le cloud.
- À garder : on efface le `#` AVANT de lire le lien (dès que le fragment contient `maj=`), puis on dit pourquoi le lien n'a pas servi. Ne pas « simplifier » en remettant l'effacement après la validation du lien.
- Test : `test_un_lien_refuse_ne_laisse_pas_la_cle_dans_l_adresse`.

## 2026-11-05 — Retour arrière sans effet sur un exemple modifié depuis
- Où : `index.html`, `pourRetourArriere`.
- Bug : la règle « les exemples gardent leur maj 0 » ne regardait que la version CIBLE. Un forfait d'exemple modifié après cette version (donc `maj > 0` sur les autres appareils) revenait à `maj: 0` : la fusion le perdait face à l'autre appareil responsable, qui le jugeait plus récent et renvoyait la modification que le retour devait annuler. Le retour échouait exactement sur l'enregistrement visé, en silence.
- À garder : on réhorodate tout ce que le retour CHANGE, et on ne garde la date d'origine que si l'état actuel porte la même `maj` pour le même id (même écriture). Les exemples jamais touchés gardent ainsi leur maj 0, donc « Supprimer les exemples » continue de les balayer, sans sacrifier la fusion.
- Test : `test_un_retour_arriere_annule_aussi_la_modification_d_un_exemple`.

## 2026-11-05 — Un appareil retiré revenait par un lien qu'il avait émis
- Où : `cloud/src/index.js`, `POST /api/invitation` et `DELETE /api/appareils/<id>`.
- Bug : rien ne liait une invitation à son créateur, et retirer un appareil n'effaçait que `app:` et `jeton:`. Un lien d'appairage « responsable » émis avant le retrait (jusqu'à 20 usages pendant 24 h) restait valable : l'appareil retiré revenait avec un jeton neuf, un autre identifiant et un autre nom, sans que personne ne le voie passer dans la liste des appareils. C'est le scénario même que la fonction promet de régler (téléphone perdu).
- À garder : l'invitation porte `par: <id de l'appareil émetteur>`, et le retrait balaie `inv:` pour supprimer celles de la cible. Conséquence voulue : retirer son ancien téléphone invalide les liens encore en circulation émis depuis lui.
- Test : `test_retirer_un_appareil_annule_les_liens_qu_il_a_emis`.

## 2026-11-05 — Un inconnu pouvait fermer l'appairage à toute l'équipe
- Où : `cloud/src/index.js`, `freine` et le début de `fetch`.
- Bug : un seul seau à jetons, en mémoire du Durable Object, partagé par tous les appelants sans jeton valable. N'importe qui connaissant l'adresse du Worker le gardait vide (10 requêtes par minute suffisent) : l'appairage d'un nouvel appareil ET la récupération par code de secours renvoyaient 429 AVANT même la lecture de l'invitation. L'équipe se retrouvait dehors sans recours. Les porteurs de jeton, à l'inverse, n'étaient freinés par rien.
- À garder : un seau par source (`CF-Connecting-IP`), deux seaux par source — large pour tout appelant, appliqué avant la moindre lecture de stockage, et serré en plus pour les requêtes sans jeton valable. Sans en-tête de source (wrangler dev), tout le monde partage un seau : jamais plus permissif qu'avant. `DELETE /api/tout` vide les seaux.
- Test : pas de test (inonder le Worker en test coûterait des minutes pour prouver une limite de débit) ; la lecture du code et `test_le_cloud_refuse_l_ecriture_a_un_appareil_de_consultation` couvrent le chemin.
