# Essayer l'outil sur un vrai téléphone

Tout a été vérifié en émulation seulement. Voici quoi faire, dans l'ordre, et ce qu'il faut voir.
Compte 10 minutes. Si quelque chose ne colle pas, note le numéro du point et dis-le-moi.

## 1. Ouvrir le site

Sur le téléphone, dans Chrome (Android) ou Safari (iPhone) :

    nationaliste.github.io/forfaits

Attendu : la page noire et rouge, titre FORFAITS, un bandeau qui dit que les forfaits marqués
EXEMPLE sont faux.

## 2. L'installer comme une appli (facultatif mais conseillé)

- **Android** : menu ⋮ → « Ajouter à l'écran d'accueil » (ou « Installer l'application »).
- **iPhone** : bouton Partager → « Sur l'écran d'accueil ».

Attendu : une icône sur l'écran d'accueil, qui ouvre l'outil en plein écran, sans barre d'adresse.
L'outil marche ensuite **sans réseau** : coupe les données et rouvre-le pour le vérifier.

## 3. Mettre tes vraies données

Deux façons :

- Tu as déjà un `.json` exporté : mets-le dans OneDrive, ouvre-le depuis le téléphone, puis dans
  l'outil **Importer** → choisis le fichier.
- Sinon, reste sur les exemples pour cette séance : ça suffit pour juger l'affichage.

⚠️ Rappel : si tu dois **remplir** depuis le tableau Excel, fais-le sur **un seul** appareil, puis
envoie le `.json` aux autres. Le même tableau importé deux fois donne des doublons.

## 4. Les filtres (le point corrigé aujourd'hui)

Sous la recherche : trois boutons de famille, puis **Autres**. (Avec les exemples ce sera
Taximètre, Lumineux, Imprimante ; avec ton vrai fichier, tes familles à toi.)

Attendu : **tous les boutons sont visibles**, sur une ou deux lignes, sans rien faire glisser.
Avant aujourd'hui, « Autres » était hors de l'écran.

- Appuie sur le premier → une liste plein écran s'ouvre, choisis un modèle.
- Attendu : une étiquette « Famille : modèle ✕ » apparaît au-dessus, et la liste des forfaits se
  réduit. L'appui sur la croix retire le filtre.
- Appuie sur **Autres** → les familles qui ne sont pas en bouton (Boîtier, Installation…).
- Pour les ranger dans ton ordre : **Menu ☰ → Ordre des filtres**. Les 3 premières deviennent des
  boutons, le reste va dans « Autres ». C'est propre à ce téléphone.
- **Nouveau, et voulu** : dès que tu tapes une recherche au doigt, cette rangée **disparaît** —
  clavier ouvert, elle mangeait les deux seules cartes visibles. Elle revient quand tu effaces la
  recherche (la croix ✕ du champ). Les filtres déjà posés, eux, restent visibles et retirables.
  Conséquence à connaître : au doigt, on ne peut pas poser un filtre pendant qu'une recherche est
  tapée. Dis-moi si ça te gêne à l'usage.

## 5. Les cartes repliées

Attendu : au départ, chaque carte montre seulement le **nom** et le **prix TTC** en rouge.

- Appuie sur une carte → elle s'ouvre : éléments, prix HT, référence.
- Pour tout ouvrir d'office : **Menu ☰ → Cartes → Entières** (le bouton était à côté de
  « Trier » ; il faisait passer la barre de résultats sur deux lignes). Ce choix reste sur ce
  téléphone.
- Vérifie que le doigt touche sans peine : les boutons font au moins 44 px.

## 6. Chercher

- Tape `zor` → des suggestions apparaissent pendant la frappe.
- Tape un mot avec une faute, au moins 4 lettres (par exemple `taximetr` mal écrit) → un bouton doit
  proposer la correction, et seulement si elle donne vraiment des forfaits.
- Vide la recherche → le titre **Derniers consultés** apparaît, **replié** : la place va aux
  forfaits. (Il a changé depuis ton premier essai : avant, la rangée était ouverte d'office.)
- Appuie sur le titre → la rangée s'ouvre et montre les forfaits que tu viens de regarder
  (4 au maximum) ; le chevron se retourne. Réappuie pour la replier. Ce choix reste sur ce
  téléphone, même après avoir fermé l'outil.

## 7. Le Total

- Sur une carte, **+ Total**, deux ou trois fois, sur des forfaits différents.
- Attendu : une barre en bas de l'écran avec la somme. Appuie dessus → le panneau s'ouvre, tu peux
  changer les quantités et ajouter une ligne libre.
- Vérifie que la barre ne cache pas le dernier forfait de la liste.

## 8. Tourner le téléphone

Mets-le **à l'horizontale**.

Attendu : l'en-tête et la recherche s'aplatissent, il reste des forfaits à l'écran. Remets-le droit,
tout revient.

## 9. Grossir le texte

**Menu ☰ → Taille du texte → Grand**.

Attendu : tout grossit, et **rien ne déborde** — regarde surtout les fenêtres qui s'ouvrent
(un filtre, le Total) et la barre du bas. Remets « Normal » après.

## 10. La mise à jour

Quand je livre une nouvelle version, l'outil ouvert doit afficher un bandeau **« Recharger »**.
Pour l'essayer : laisse l'onglet ouvert, préviens-moi, je pousse une version, tu regardes si le
bandeau arrive (il peut mettre une minute). Appuie sur Recharger → la nouvelle version.

---

## Ce que je veux savoir en retour

1. Les quatre boutons de filtre sont-ils bien tous visibles ?
2. Les cartes repliées : pratique, ou tu préfères les cartes entières par défaut ?
3. Y a-t-il un endroit où tu dois **faire glisser sur le côté** ? (il ne devrait plus y en avoir)
4. Quelque chose de trop petit pour le doigt ?
5. L'installation sur l'écran d'accueil a-t-elle marché, et l'outil marche-t-il sans réseau ?
