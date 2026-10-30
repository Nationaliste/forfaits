// Service worker : garde l'outil disponible sans internet.
// Stratégie : on répond tout de suite avec la copie gardée sur l'appareil, et on la met à jour
// en arrière-plan. Quand la page téléchargée n'est plus la même que la copie gardée, on le dit
// à la page ouverte, qui propose « Recharger » (sinon la nouveauté n'arrive qu'à l'ouverture suivante).
// Les forfaits eux-mêmes ne passent jamais par ici : ils restent dans le navigateur.
const CACHE = 'forfaits-v1';
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

// Range la copie fraîche et, s'il s'agit de la page et qu'elle a changé, prévient les onglets ouverts.
// L'avertissement part après la mise en cache : un « Recharger » donne donc bien la nouvelle version.
async function ranger(requete, copie, estLaPage) {
  const cache = await caches.open(CACHE);
  let change = false;
  if (estLaPage) {
    const gardee = await cache.match(requete, { ignoreSearch: true });
    if (gardee) {
      const [avant, apres] = await Promise.all([gardee.text(), copie.clone().text()]);
      change = avant !== apres;
    }
  }
  await cache.put(requete, copie);
  if (!change) return;
  const onglets = await self.clients.matchAll({ type: 'window' });
  for (const onglet of onglets) onglet.postMessage({ type: 'nouvelle-version' });
}

self.addEventListener('fetch', (ev) => {
  const requete = ev.request;
  if (requete.method !== 'GET' || new URL(requete.url).origin !== self.location.origin) return;
  const chemin = new URL(requete.url).pathname;
  const estLaPage = requete.mode === 'navigate' || chemin.endsWith('/') || chemin.endsWith('/index.html');

  // Copie fraîche depuis internet (si disponible), rangée pour la prochaine fois.
  const reseau = fetch(requete).then((reponse) => {
    if (reponse.ok) ev.waitUntil(ranger(requete, reponse.clone(), estLaPage));
    return reponse;
  }).catch(() => null);
  ev.waitUntil(reseau);

  ev.respondWith((async () => {
    const gardee = await caches.match(requete, { ignoreSearch: true });
    if (gardee) return gardee;
    const reponse = await reseau;
    if (reponse) return reponse;
    if (requete.mode === 'navigate') {
      const page = await caches.match('./');
      if (page) return page;
    }
    return new Response('Hors ligne', { status: 503, statusText: 'Hors ligne' });
  })());
});
