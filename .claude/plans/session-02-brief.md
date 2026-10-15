# Session 02 (15/10/2026) : serveur de synchro, en pause

## État
- Branche `feat/serveur` poussée, **sans PR ni fusion** : le site public ne change pas. Décision de l'utilisateur : en pause (pas abandonnée), en attendant l'avis du patron.
- Contenu, fini et testé (121 tests verts sur Chromium, Edge, Firefox ; `cargo test`, clippy, ruff, vulture propres) :
  - `serveur/` : serveur Rust (axum), n'écoute que sur 127.0.0.1, ne garde que des données chiffrées par l'appli, historique de 200 versions, 409 si deux responsables écrivent en même temps, limite de débit, 7 Mo de mémoire, empêche la veille de la Surface tant qu'il tourne.
  - `index.html` : Menu → « Serveur de mise à jour ». Chiffrement dans le navigateur (PBKDF2 600 000 tours + HKDF + AES-256-GCM). Mot de passe d'équipe = lire ; code responsable = envoyer. Synchro à l'ouverture, au retour sur l'appli, toutes les 5 min, et 2 s après chaque modification.
  - `serveur/installer.ps1` : compile, copie dans `%LOCALAPPDATA%\Forfaits-serveur`, demande les mots de passe, crée la tâche planifiée S4U (demande l'autorisation administrateur). Testé sans la tâche ; l'étape administrateur n'a pas été lancée.
  - `tests/test_synchro.py` : vrai serveur lancé, coupé et relancé pendant les tests.
- Page pour le patron (non versionnée) : `prive/serveur-pour-le-patron.md`.

## Reste à faire (si le patron dit oui)
1. Compte Tailscale avec l'e-mail du travail (essai gratuit), installer Tailscale sur la Surface, l'activer « sans session ouverte ».
2. `powershell -ExecutionPolicy Bypass -File serveur\installer.ps1` (depuis la branche `feat/serveur`), puis `tailscale funnel --bg 8787`.
3. Essai réel avec les données EXEMPLE seulement : responsable sur PC, 2 téléphones en 4G, Surface éteinte puis rallumée.
4. Puis `/review-local` complet (les relecteurs conformité et câblage n'ont pas tourné ; constats mineurs restants : [roadmap#260](https://github.com/Nationaliste/roadmap/issues/260)), PR, fusion. Une fois l'adresse `*.ts.net` connue, la mettre telle quelle dans la CSP à la place de `https://*.ts.net`.

## Pièges
- Tailscale gratuit = usage non commercial seulement. Usage pro : formule Standard, environ 8 $ par mois pour 1 utilisateur (les téléphones n'installent rien).
- Fermer le clavier sur la Surface ou appuyer sur son bouton la met en veille malgré tout : serveur injoignable.
- Tests : la page doit venir d'un vrai serveur local (Chrome bloque l'appel vers 127.0.0.1 depuis une page modifiée par Playwright) ; les interceptions `page.route` ne tournent que pendant un appel Playwright (attendre avec `page.wait_for_timeout`, pas `time.sleep`).
- Compiler Rust avec `CARGO_TARGET_DIR` hors de OneDrive (`%LOCALAPPDATA%\forfaits-cargo-target`) ; cargo n'est pas dans le PATH de Git Bash (`$USERPROFILE/.cargo/bin`).
- Thèmes : main (noir et rouge, puis thème clair PR #8) est fusionné dans `feat/serveur` le 15/10 (commit 000bb74, 147 tests verts, fenêtre « Serveur » vérifiée en clair par `test_fenetre_du_serveur_en_theme_clair`). Chaque nouvelle PR sur main sera à refusionner de la même façon avant la PR du serveur (conflits habituels : la CSP, gardée avec `*.ts.net`, et le gestionnaire `storage`). Pas encore refusionnée dans `feat/serveur` : la PR #10 (rouge de la marque `#e30613`, 15/10 ; ne touche que le CSS, les icônes et `outils/icones.py`, donc sans conflit attendu).
