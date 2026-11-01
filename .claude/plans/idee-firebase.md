# Idée : synchro par Firebase au lieu du serveur de #260

Écrit le 01/11/2026 depuis la session bexley-dressing (PC maison), à la demande de l'utilisateur, pour sa reprise au bureau. Idée seulement : rien n'est décidé ni codé dans forfaits. Roadmap : [#539](https://github.com/Nationaliste/roadmap/issues/539), liée à [#260](https://github.com/Nationaliste/roadmap/issues/260) (serveur en pause) et [#265](https://github.com/Nationaliste/roadmap/issues/265) (appairage).

## Pourquoi en parler
- #260 attend l'avis du patron : serveur Rust sur la Surface, Tailscale payant (~8 $/mois), installation en admin.
- Firebase (Google), offre gratuite Spark : pas de serveur à faire tourner, pas de Tailscale, HTTPS public. Un site statique comme GitHub Pages peut l'appeler en REST (`fetch`), sans SDK.
- Déjà fait et testé dans le dépôt privé `Nationaliste/bexley-dressing` (v2.3.0 et v2.4.0, novembre 2026) : synchro PC ↔ téléphone, connexion réelle réussie le 01/11. Le code se lit depuis le PC du bureau avec `gh` (même compte).

## Ce qui a marché dans bexley-dressing (à relire avant de concevoir)
- Plan et avancement : `.claude/plans/synchro-plan.md` (choix, autocritique, pièges).
- Code, dans `bexley-dressing/src/sync/` :
  - `firebaseRest.ts` : connexion, jeton, Firestore en REST ;
  - `synchro.ts` : fusion, derrière une interface `Cloud` testée avec un faux cloud en mémoire ;
  - `journal.ts` : dates et empreintes de chaque élément ;
  - `engine.ts` : déclencheurs (ouverture, ~5 s après un changement, retour sur l'appli, toutes les 5 min) ;
  - `hotes.ts` : les 3 hôtes Google.
- Règles : `bexley-dressing/firestore.rules`. Tests contre la copie locale : `src/sync/firestore.emulateur.test.ts`, `scripts/emulateurs.mjs`, `scripts/fauxAuth.mjs`.
- Pas de SDK Firebase. Seulement 3 API REST : `identitytoolkit` (connexion, « mot de passe oublié »), `securetoken` (renouvellement du jeton), `firestore`. La CSP `connect-src` ajoute exactement ces 3 hôtes.
- Un document par élément, `users/{uid}/items/{store~clé}`, avec ces champs :
  - `v` : la valeur, en JSON dans un texte ;
  - `u` : la date de modification ;
  - `del` : la suppression marquée ;
  - `f` : le format ;
  - `s` : l'heure du serveur.

  La plus récente gagne, élément par élément. Les suppressions restent dans le cloud, comme les marques `supprime: true` de forfaits : même logique de fusion que l'import `.json`.
- Lecture des seuls changements : `runQuery` sur `s > dernière lecture − 60 s`. L'heure est celle du serveur, pas celle de l'appareil.
- Écriture conditionnelle (`currentDocument.updateTime`) : si l'autre appareil a écrit entre-temps, relire puis renvoyer.
- Limites Firestore :
  - 1 Mio par document ;
  - 10 Mio et 500 écritures par envoi : envoyer par lots (bexley : 400 écritures et 2 Mio au plus par lot).
- Tests :
  - copie locale de Firestore (`cloud-firestore-emulator` en .jar, Java 21, sans installer `firebase-tools`, trop de paquets) ;
  - faux serveur de connexion ;
  - les jetons non signés sont acceptés par la copie locale, et les règles y sont chargées par son API.
- Console Firebase, faite par l'utilisateur en ~15 min :
  - emplacement **eur3** (Europe), définitif ;
  - Authentication en « E-mail/Mot de passe » ;
  - **création de compte coupée** : sinon n'importe qui peut s'inscrire avec la clé publique de l'appli ;
  - clé web limitée aux 3 API ;
  - règles collées depuis le fichier.
- La clé web n'est pas un secret (un `gitleaks:allow` sur sa ligne). Ce qui protège les données : les règles et les comptes.
- CORS : vérifié depuis `file://` (exe) et `https://localhost` (Android). Depuis GitHub Pages : pas vérifié, à faire en premier.

## Ce qui change pour forfaits (à trancher)
- **Avis du patron d'abord** : les forfaits et leurs prix seraient hébergés chez Google (en Europe). Même question que pour #260.
- **Plusieurs personnes partagent les mêmes données** : les règles de bexley (« chacun ses données ») ne conviennent pas. Piste : création de compte coupée, comptes créés à la main dans la console, une collection d'équipe lisible et modifiable par ces seuls comptes (liste des uid dans les règles, ou une collection « membres »). Retirer un appareil = désactiver son compte.
- **Dépôt public** : la configuration Firebase (clé web, identifiant du projet) serait visible dans `index.html`. C'est normal pour Firebase, à condition d'avoir des règles strictes et la création de compte coupée. En plus pour forfaits : limiter la clé aux requêtes venant de `nationaliste.github.io` (restriction par site, pas possible pour l'exe de bexley).
- **Chiffrement** : garder celui de `feat/serveur`, fait par l'appli, ferait que Google ne stocke que du chiffré. C'est à décider avec le patron.
- **Sans mot de passe (#265)** : Firebase Auth propose une connexion par lien envoyé par e-mail. Pas essayé dans bexley, à vérifier.
- **Quotas gratuits** (de mémoire, à revérifier dans la doc) : 1 Gio de stockage, environ 50 000 lectures et 20 000 écritures par jour. Large pour quelques centaines de forfaits.
- **Site hors ligne** (`sw.js`) : la synchro doit rester facultative. Hors ligne, rien ne bloque, elle repart au retour du réseau (comme dans bexley).

## Prochaine étape proposée
1. Avec l'utilisateur : Firebase remplace-t-il le serveur de #260 ? Puis l'avis du patron.
2. Si oui : gate, questions avant plan, puis un essai jetable avec les données EXEMPLE seulement :
   - CORS depuis GitHub Pages ;
   - règles d'équipe contre la copie locale de Firestore.
