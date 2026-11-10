// Service worker : garde l'outil disponible sans internet.
// Stratégie : on répond tout de suite avec la copie gardée sur l'appareil, et on la met à jour
// en arrière-plan. Quand la page téléchargée n'est plus la même que la copie gardée, on le dit
// à la page ouverte, qui propose « Recharger » (sinon la nouveauté n'arrive qu'à l'ouverture suivante).
// Les forfaits eux-mêmes ne passent jamais par ici : ils restent dans le navigateur.
// Changer ce nom fait repartir chaque appareil d'une copie neuve, et jette l'ancienne (voir « activate »).
// v2 : les copies v1 pouvaient rester bloquées sur une vieille page (voir « cle »).
const CACHE = 'forfaits-v2';
const FICHIERS = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png', './icon-maskable-512.png'];

self.addEventListener('install', (ev) => {
  ev.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(FICHIERS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (ev) => {
  ev.waitUntil(
    caches.keys()
      // Seulement nos anciennes copies : d'autres pages du même site peuvent avoir les leurs.
      .then((noms) => Promise.all(noms.filter((nom) => nom.startsWith('forfaits-') && nom !== CACHE).map((nom) => caches.delete(nom))))
      .then(() => self.clients.claim()),
  );
});

// Une copie se range et se relit sous son adresse SANS paramètres : « /?x=1 » et « / » sont la même page.
// Rangée sous l'adresse complète puis relue sans regarder les paramètres, la copie de « /?x=1 » passait
// devant celle de « / » et plus rien ne la rafraîchissait : l'appareil restait sur la page de ce jour-là.
function cle(requete) {
  const adresse = new URL(requete.url);
  adresse.search = '';
  adresse.hash = '';
  return adresse.href;
}

// Range la copie fraîche et, s'il s'agit de la page et qu'elle a changé, prévient les onglets ouverts.
// L'avertissement part après la mise en cache : un « Recharger » donne donc bien la nouvelle version.
// `futur` : l'identifiant de l'onglet que cette demande de page va faire naître (vide pour tout le reste).
async function ranger(requete, copie, estLaPage, futur) {
  const cache = await caches.open(CACHE);
  let change = false;
  if (estLaPage) {
    const gardee = await cache.match(cle(requete));
    if (gardee) {
      const [avant, apres] = await Promise.all([gardee.text(), copie.clone().text()]);
      change = avant !== apres;
    }
  }
  await cache.put(cle(requete), copie);
  if (!change) return;
  const onglets = await self.clients.matchAll({ type: 'window' });
  for (const onglet of onglets) onglet.postMessage({ type: 'nouvelle-version' });
  // L'onglet qui vient de demander la page reçoit l'ancienne copie, mais n'existe pas encore ici : la liste est vide,
  // ou ne contient que la page qu'il remplace, et l'avertissement ne lui arrivait pas. On l'attend donc, 3 s au plus.
  // En boucle, parce que clients.get() n'attend pas partout (Firefox répond « rien » tant que l'onglet n'est pas né).
  if (!futur || onglets.some((onglet) => onglet.id === futur)) return;
  for (let essai = 0; essai < 30; essai++) {
    const onglet = await self.clients.get(futur);
    if (onglet) {
      onglet.postMessage({ type: 'nouvelle-version' });
      return;
    }
    await new Promise((fin) => setTimeout(fin, 100));
  }
}

self.addEventListener('fetch', (ev) => {
  const requete = ev.request;
  if (requete.method !== 'GET' || new URL(requete.url).origin !== self.location.origin) return;
  const chemin = new URL(requete.url).pathname;
  const estLaPage = requete.mode === 'navigate' || chemin.endsWith('/') || chemin.endsWith('/index.html');

  // Copie fraîche depuis internet (si disponible), rangée pour la prochaine fois.
  const reseau = fetch(requete).then((reponse) => {
    if (reponse.ok) ev.waitUntil(ranger(requete, reponse.clone(), estLaPage, ev.resultingClientId));
    return reponse;
  }).catch(() => null);
  ev.waitUntil(reseau);

  ev.respondWith((async () => {
    // Dans notre copie seulement : d'autres pages du même site peuvent garder les leurs.
    const cache = await caches.open(CACHE);
    const gardee = await cache.match(cle(requete));
    if (gardee) return gardee;
    const reponse = await reseau;
    if (reponse) return reponse;
    if (requete.mode === 'navigate') {
      const page = await cache.match('./');
      if (page) return page;
    }
    return new Response('Hors ligne', { status: 503, statusText: 'Hors ligne' });
  })());
});
