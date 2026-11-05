# Connecter les appareils à la mise à jour automatique

Une page par type d'appareil. À suivre dans l'ordre : d'abord le premier appareil responsable, puis
les autres.

Vocabulaire : **responsable** = peut modifier les forfaits. **Consultation** = ne peut que les lire
(le mode modification disparaît de son menu). Choisis « consultation » pour tous les vendeurs.

---

## 0. Le tout premier appareil (une seule fois, sur l'appareil du responsable)

Il n'y a pas encore de lien : l'adresse et le code de secours se tapent à la main.

1. Ouvre l'outil → **Menu** → **Mise à jour automatique** → **Premier appareil**.
2. **Adresse** : `<nom-du-worker>.<compte>.workers.dev` (sans `https://`).
3. **Code de secours** : celui choisi au déploiement.
4. **Nom de cet appareil** : par exemple « Surface du responsable ».
5. **Connecter**. Le menu affiche alors « Mise à jour automatique (connectée) ».

À ce moment-là, le cloud est vide. **Importe ton tableau maintenant, sur cet appareil seulement**
(bouton **Importer** en haut de la page, ou Menu → « Importer (sauvegarde ou tableau Excel) »). Il part tout seul vers le cloud 2 secondes plus tard.

> Ne jamais importer le même tableau sur deux appareils : chacun créerait ses propres identifiants
> et tu te retrouverais avec des doublons de références.

---

## 1. Créer un lien pour les autres

Sur l'appareil responsable : **Menu** → **Mise à jour automatique** → **Ajouter un appareil**.

| Choix | Quand |
|---|---|
| **1 appareil** (lien valable 10 minutes) | tu envoies le lien à quelqu'un à distance |
| **Jusqu'à 20** (lien valable 24 h) | tu équipes l'équipe en une séance, appareil après appareil |

Donne un nom (« PC du comptoir », « Téléphone comptoir 2 ») pour t'y retrouver dans la liste, choisis
le rôle, puis **Créer le lien**. Tu obtiens le lien, les boutons **Copier** / **Partager**, et un
**QR code**.

Chaque appareil reçoit malgré tout son propre accès : un lien de lot ne les rend pas solidaires, tu
peux en retirer un seul plus tard.

---

## 2. PC du comptoir (Chrome, Edge, Firefox)

1. Ouvre `nationaliste.github.io/forfaits`.
2. Scanne le QR avec ton téléphone pour récupérer le lien, ou colle-le dans la barre d'adresse du PC.
3. L'outil affiche « Connecté : les mises à jour arrivent toutes seules ».

Si le lien ne s'ouvre pas tout seul : **Menu** → **Mise à jour automatique** → **Coller un lien**.

> Un PC qui nettoie les données des sites à chaque fermeture (profil invité, nettoyage nocturne)
> perdra son accès **et sa copie des forfaits** : il rouvrira comme un appareil neuf. Il suffit de
> le reconnecter avec un lien de lot. Ça se verra au premier essai : teste ce PC avant la démo.

---

## 3. Android (Chrome)

1. Ouvre `nationaliste.github.io/forfaits`.
2. Menu de Chrome (⋮) → **Ajouter à l'écran d'accueil**. Ferme Chrome, ouvre l'outil par l'icône.
3. Scanne le QR affiché par le responsable, **ou** copie le lien et : **Menu** → **Mise à jour
   automatique** → **Coller un lien**.

Le scan marche sur Android : l'appareil photo ouvre l'outil installé.

---

## 4. iPhone (le seul cas qui demande de l'attention)

Deux pièges de Safari, les deux contournés par la même chose : **l'outil doit être ajouté à l'écran
d'accueil, et l'appairage doit se faire DANS l'appli installée.**

1. Ouvre `nationaliste.github.io/forfaits` dans **Safari** (pas Chrome iOS).
2. Bouton Partager → **Sur l'écran d'accueil** → Ajouter. Ferme Safari.
3. Ouvre l'outil **par son icône** sur l'écran d'accueil.
4. Copie le lien donné par le responsable (depuis un message, un mail, le presse-papiers).
5. Dans l'appli : **Menu** → **Mise à jour automatique** → **Coller un lien** → coller → **Connecter**.

**Ne scanne pas le QR sur iPhone** : l'appareil photo ouvre Safari, pas l'appli installée, et la
connexion se ferait dans le mauvais stockage (Safari et l'appli installée ont deux stockages
séparés). L'appli te le rappelle sous le QR.

**Ne connecte pas l'outil depuis Safari** : sans ajout à l'écran d'accueil, Safari efface les données
des sites après 7 jours sans visite, et il faudrait tout refaire.

À vérifier une fois, sur un vrai iPhone, avant la démo :
- l'ajout à l'écran d'accueil fonctionne ;
- le collage du lien dans l'appli installée connecte bien l'appareil ;
- les forfaits sont toujours là **2 jours plus tard**, sans avoir rouvert entre-temps.

Si l'un des trois casse : les iPhone restent à l'import manuel (`.json`), le reste de l'équipe
fonctionne normalement.

---

## 5. Vérifier que ça marche (2 minutes, à faire une fois tout branché)

1. Sur l'appareil responsable, change un prix.
2. Compte jusqu'à 10 sur un téléphone : le nouveau prix doit être là. Sinon, tire la page vers le bas
   ou ferme/rouvre l'appli (la vérification se fait aussi au retour sur l'appli).
3. Mets un téléphone en **mode avion** : l'outil doit continuer à afficher les forfaits, sans aucune
   fenêtre d'erreur, avec « hors ligne » dans le menu. Réseau revenu, la synchro repart seule.

---

## 6. Retirer un appareil (téléphone perdu, départ)

Sur l'appareil responsable : **Menu** → **Mise à jour automatique** → **Appareils connectés** →
**Retirer** sur la ligne concernée.

Effet : il ne reçoit plus rien, et à sa prochaine ouverture **avec du réseau** il efface ses
forfaits. S'il n'est jamais rallumé, les forfaits déjà reçus y restent — comme un fichier envoyé par
mail. Les autres appareils ne bougent pas.

---

## 7. Annuler une erreur

Sur l'appareil responsable : **Menu** → **Mise à jour automatique** → **Revenir à une version** →
choisis la version. Les 10 dernières sont gardées, et la correction repart sur tous les appareils.

---

## 8. Tout arrêter

Sur l'appareil responsable : **Menu** → **Mise à jour automatique** → **Tout effacer du cloud**,
puis le code de secours.

Chaque appareil garde sa copie et revient à l'import manuel. Pense à exporter un `.json` de
sauvegarde avant, depuis l'appareil responsable.
