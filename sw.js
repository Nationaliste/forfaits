// Service worker : garde l'outil disponible sans internet.
// Stratégie : on répond tout de suite avec la copie gardée sur l'appareil, et on la met à jour
// en arrière-plan. Une nouvelle version de l'outil s'affiche donc à l'ouverture suivante.
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

self.addEventListener('fetch', (ev) => {
  const requete = ev.request;
  if (requete.method !== 'GET' || new URL(requete.url).origin !== self.location.origin) return;

  // Copie fraîche depuis internet (si disponible), rangée pour la prochaine fois.
  const reseau = fetch(requete).then((reponse) => {
    if (reponse.ok) {
      const copie = reponse.clone();
      ev.waitUntil(caches.open(CACHE).then((cache) => cache.put(requete, copie)));
    }
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
