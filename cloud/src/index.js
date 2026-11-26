/* Cloud de mise à jour des forfaits — un Worker Cloudflare + un seul Durable Object.
   Le cloud ne voit JAMAIS les forfaits : l'appli les chiffre sur l'appareil (AES-256-GCM) et la clé
   ne quitte jamais les appareils (elle voyage dans la partie « # » du lien d'appairage, que le
   navigateur n'envoie pas au serveur). Ici on ne garde qu'un paquet illisible, des empreintes de
   jetons et des noms d'appareils. Un seul Durable Object = tout est sérialisé : brûler une invitation
   ou refuser une version périmée ne peut pas partir en course. */

const MAX_CORPS = 1_400_000; // ~1 Mo de paquet chiffré, une fois en base64
const MIN_CHIFFRE = 28; // 12 octets d'IV + 16 d'étiquette AES-GCM : en dessous, ce n'est pas du chiffré
const VERSIONS_GARDEES = 10; // filet de sécurité : « revenir à une version »
const USAGES_MAX = 20; // une invitation en lot équipe toute l'équipe en une séance
const MINUTES_MAX = 1440;
const PAUSE_REFUS = 250; // ms : ralentit les essais au hasard
const SEAU_CAPACITE = 30; // requêtes sans jeton valable d'affilée (de quoi équiper 20 appareils en une séance)...
const SEAU_PAR_MINUTE = 10; // ...puis 10 par minute : un inconnu ne peut plus brûler le quota de stockage du compte
const SEAU_LARGE_CAPACITE = 120; // frein de tout appelant, jeton valable compris (20 appareils qui se synchronisent passent)
const SEAU_LARGE_PAR_MINUTE = 60;
const SOURCES_MAX = 200; // seaux gardés en mémoire : au-delà, on oublie la source la moins récente
const CORPS_COURT = 4096; // appairage et secours : deux champs courts, jamais un paquet de forfaits
const VU_INTERVALLE = 3_600_000; // « vu le » noté une fois par heure au plus (économise les écritures)
const TOMBE_MS = 90 * 86_400_000; // on se souvient 90 jours d'un appareil retiré, pour qu'il s'efface
const ROLES = ['responsable', 'consultation'];
const LIMITE_CORPS = MAX_CORPS + 4096; // marge pour l'enveloppe JSON autour du paquet
// Le code de secours ouvre un accès responsable complet : il se tire au hasard (outils/code_secours.py,
// 29 caractères). Le minimum de la page ne protège pas : un attaquant n'exécute pas la page.
const CODE_SECOURS_MIN = 24;
// Frein du code de secours, COMMUN à toutes les sources et gardé dans le stockage : changer d'adresse,
// attendre que l'objet s'endorme ou porter un jeton n'y change rien. Après ESSAIS_SECOURS_LIBRES échecs
// d'affilée, chaque essai attend 1 min, puis 2, 4… jusqu'à 1 h : une vingtaine d'essais par jour. Le
// responsable qui a vraiment perdu ses appareils attend au pire une heure ; le bon code remet à zéro.
const ESSAIS_SECOURS_LIBRES = 5;
const ATTENTE_SECOURS_MS = 60_000;
const ATTENTE_SECOURS_MAX = 3_600_000;

/* ---------- petits outils ---------- */

const utf8 = new TextEncoder();
const hex = (octets) => Array.from(new Uint8Array(octets), (o) => o.toString(16).padStart(2, '0')).join('');

async function empreinte(texte) {
  return hex(await crypto.subtle.digest('SHA-256', utf8.encode(texte)));
}

// Secret tiré au hasard, lisible dans une adresse (base64url, sans « = »).
function secret(octets = 32) {
  const b = crypto.getRandomValues(new Uint8Array(octets));
  return btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

// Comparaison en temps constant, sur les empreintes : même longueur de part et d'autre,
// et la durée de la réponse ne dit rien du secret attendu.
async function memeSecret(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || !b) return false;
  const [x, y] = await Promise.all([
    crypto.subtle.digest('SHA-256', utf8.encode(a)),
    crypto.subtle.digest('SHA-256', utf8.encode(b)),
  ]);
  return crypto.subtle.timingSafeEqual(x, y);
}

const dodo = (ms) => new Promise((r) => setTimeout(r, ms));

// Taille du chiffré sans le décoder : « atob » sur 1 Mo coûterait du temps de processeur pour rien
// (l'offre gratuite en donne 10 ms par requête).
function tailleBase64(texte) {
  const pad = texte.endsWith('==') ? 2 : texte.endsWith('=') ? 1 : 0;
  return Math.floor((texte.length * 3) / 4) - pad;
}

function blobValide(blob) {
  return (
    typeof blob === 'string' &&
    blob.length <= MAX_CORPS &&
    blob.length % 4 === 0 && // « atob » refuserait : un paquet pareil mettrait toute l'équipe en erreur
    /^[A-Za-z0-9+/]+={0,2}$/.test(blob) &&
    tailleBase64(blob) >= MIN_CHIFFRE
  );
}

// Source d'une requête pour le frein. Une adresse IPv6 se change à volonté à l'intérieur de son /64
// (chaque box en reçoit au moins un) : on freine donc le /64 entier, pas l'adresse.
function sourceDe(ip) {
  if (!ip) return 'sans-source';
  if (!ip.includes(':')) return ip;
  const [debut, fin = ''] = ip.toLowerCase().split('::');
  const avant = debut ? debut.split(':') : [];
  const apres = fin ? fin.split(':') : [];
  const groupes = [...avant, ...Array(Math.max(0, 8 - avant.length - apres.length)).fill('0'), ...apres];
  return groupes.slice(0, 4).map((g) => g.replace(/^0+(?=.)/, '')).join(':') + '::/64';
}

const numeroVersion = (e) => (typeof e === 'number' ? e : e.v);

const nomPropre = (v) => (typeof v === 'string' ? v.replace(/[\u0000-\u001f]/g, ' ').trim().slice(0, 40) : '');

// L'en-tête Content-Length n'est qu'un premier filtre : une requête « chunked » n'en a pas, et
// « request.json() » avalerait alors un corps de taille illimitée. On lit donc par morceaux en
// comptant les octets, et on abandonne dès que la limite est franchie. Les morceaux sont assemblés
// une seule fois à la fin (pas de concaténation dans la boucle : 10 ms de processeur par requête).
async function lireJson(request, max = LIMITE_CORPS) {
  if (Number(request.headers.get('Content-Length') || 0) > max) return null;
  if (!request.body) return null;
  const lecteur = request.body.getReader();
  try {
    const morceaux = [];
    let total = 0;
    for (;;) {
      const { done, value } = await lecteur.read();
      if (done) break;
      total += value.byteLength;
      if (total > max) {
        await lecteur.cancel(); // on libère le flux : le reste du corps n'est pas lu
        return null;
      }
      morceaux.push(value);
    }
    const tout = new Uint8Array(total);
    let position = 0;
    for (const m of morceaux) {
      tout.set(m, position);
      position += m.byteLength;
    }
    return JSON.parse(new TextDecoder().decode(tout));
  } catch {
    return null;
  }
}

function json(statut, corps, entetes = {}) {
  return new Response(JSON.stringify(corps), {
    status: statut,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'X-Heure': String(Date.now()), ...entetes },
  });
}

/* ---------- le Worker : origine, taille, en-têtes, puis tout part au Durable Object ---------- */

function origineOk(origine, env) {
  if (!origine) return null;
  if (origine === env.ORIGINE) return origine;
  // Pendant les tests, la page est servie par http://127.0.0.1:<port> ; jamais en production.
  if (env.DEV === '1' && /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(origine)) return origine;
  return null;
}

function avecCors(reponse, origine) {
  const r = new Response(reponse.body, reponse);
  if (origine) {
    r.headers.set('Access-Control-Allow-Origin', origine);
    r.headers.set('Vary', 'Origin');
    // Sans ça, la page ne peut lire ni ETag (rien de neuf) ni X-Heure (contrôle d'horloge).
    r.headers.set('Access-Control-Expose-Headers', 'ETag, X-Heure');
  }
  r.headers.set('Cache-Control', 'no-store');
  r.headers.set('X-Content-Type-Options', 'nosniff');
  r.headers.set('Referrer-Policy', 'no-referrer');
  return r;
}

// L'objet de l'équipe, en Europe. La juridiction n'existe pas dans l'exécution locale : on retombe
// alors sur une simple préférence d'emplacement, et de toute façon le cloud ne voit que du chiffré.
function objetEquipe(env) {
  try {
    const eu = env.EQUIPE.jurisdiction('eu');
    return eu.get(eu.idFromName('equipe'));
  } catch {
    return env.EQUIPE.get(env.EQUIPE.idFromName('equipe'), { locationHint: 'weur' });
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origine = origineOk(request.headers.get('Origin'), env);
    if (request.method === 'OPTIONS') {
      return avecCors(
        new Response(null, {
          status: origine ? 204 : 403,
          headers: origine
            ? {
                'Access-Control-Allow-Methods': 'GET, PUT, POST, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type, If-None-Match, X-Code-Secours',
                'Access-Control-Max-Age': '600',
              }
            : {},
        }),
        origine,
      );
    }
    if (!url.pathname.startsWith('/api/')) return avecCors(new Response('Rien ici.', { status: 404 }), origine);
    if (!origine) return avecCors(json(403, { erreur: 'origine refusee' }), null);
    if (Number(request.headers.get('Content-Length') || 0) > LIMITE_CORPS) {
      return avecCors(json(413, { erreur: 'donnees trop grosses' }), origine);
    }
    return avecCors(await objetEquipe(env).fetch(request), origine);
  },
};

/* ---------- le Durable Object : tout l'état de l'équipe ----------
   etat          : { version, blob, enregistre_le, par, revenu_a }
   hist          : [{ v, date, par, taille }] (anciennes entrées : numéros)   hist:<n> : { blob, date, par }
   app:<id>      : { emp, role, nom, cree, vu }
   jeton:<emp>   : <id>                      retire:<emp> : date (pour que l'appareil s'efface)
   inv:<emp>     : { role, usages, total, expire, cree, nom, par } (par = l'appareil qui l'a émise)
   secours:echecs : { n, dernier } (frein commun du code de secours)                             */

export class Equipe {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
    // Une source -> ses seaux. Un seul seau partagé fermait l'appairage de TOUTE l'équipe, et la
    // récupération par code de secours avec, dès qu'un inconnu inondait.
    this.seaux = new Map();
  }

  // Limite de débit par source. Compteurs en mémoire : perdus si l'objet s'endort, ce qui est sans
  // conséquence pour un frein, et surtout zéro écriture (le gratuit en compte 100 000 par jour).
  // Derrière le NAT du magasin tous les appareils partagent une source : les seaux sont donc
  // dimensionnés pour l'équipe entière. Sans en-tête de source (wrangler dev), tout le monde
  // partage un seau, comme avant : jamais plus permissif que l'ancien comportement.
  freine(request, capacite, parMinute, nom) {
    const source = sourceDe(request.headers.get('CF-Connecting-IP'));
    const siens = this.seaux.get(source) || {};
    // Rangée en dernier : la Map garde l'ordre d'arrivée, donc la première est la moins récente.
    this.seaux.delete(source);
    // Un attaquant qui change d'adresse ne doit pas nous remplir la mémoire : on oublie la source la
    // moins récente, une seule. Tout vider rendait un seau plein à une source épuisée.
    if (this.seaux.size >= SOURCES_MAX) this.seaux.delete(this.seaux.keys().next().value);
    const seau = siens[nom] || { jetons: capacite, dernier: Date.now() };
    const maintenant = Date.now();
    seau.jetons = Math.min(capacite, seau.jetons + ((maintenant - seau.dernier) * parMinute) / 60_000);
    seau.dernier = maintenant;
    const trop = seau.jetons < 1;
    if (!trop) seau.jetons -= 1;
    siens[nom] = seau;
    this.seaux.set(source, siens);
    return trop;
  }

  async appareilDe(request) {
    const brut = (request.headers.get('Authorization') || '').replace(/^Bearer /, '');
    if (brut.length < 20) return { statut: 'inconnu' };
    const emp = await empreinte(brut);
    const id = await this.ctx.storage.get('jeton:' + emp);
    if (!id) return { statut: (await this.ctx.storage.get('retire:' + emp)) ? 'retire' : 'inconnu' };
    const app = await this.ctx.storage.get('app:' + id);
    if (!app) return { statut: 'inconnu' };
    return { statut: 'ok', id, app };
  }

  async noterVu(id, app) {
    if (Date.now() - (app.vu || 0) < VU_INTERVALLE) return;
    await this.ctx.storage.put('app:' + id, { ...app, vu: Date.now() });
  }

  // pause : ralentit la devinette d'un secret (invitation, code de secours). Un refus « lecture
  // seule » n'en est pas une (l'appelant a déjà un jeton valable et le refus ne lui apprend rien) :
  // garder la pause offrirait 250 ms de Durable Object facturées par requête à qui inonde avec un
  // jeton de consultation.
  async refus(raison, pause = true) {
    if (pause) await dodo(PAUSE_REFUS);
    return json(401, { erreur: 'acces refuse', raison });
  }

  // Le code de secours donne un jeton « responsable » complet : s'il est court, le seul frein
  // contre les essais au hasard est le seau en mémoire. C'est une erreur de configuration du
  // Worker (pas une intrusion) : 503, sans pause ni « acces refuse », et sans rien qui aide à
  // deviner le secret réel.
  codeSecoursInvalide() {
    const code = this.env.CODE_SECOURS;
    if (typeof code === 'string' && code.length >= CODE_SECOURS_MIN) return null;
    return json(503, { erreur: 'configuration du serveur', raison: 'le code de secours du Worker est trop court' });
  }

  // Contrôle du code de secours, freiné PAR SOURCE (adresse, /64 en IPv6 : voir sourceDe) et gardé dans le
  // stockage (voir ESSAIS_SECOURS_LIBRES). Un compteur commun à tous laissait n'importe qui, sans jeton, tenir la
  // récupération bloquée pour de bon : 5 essais vides, puis un à chaque fin d'attente. Par source, il ne bloque
  // que lui ; et deviner un code de 124 bits reste hors de portée, même réparti sur beaucoup d'adresses.
  // Rend la réponse de refus, ou null si le code est le bon. Pendant l'attente, la réponse ne dit rien du code
  // (429, même pour le bon) : sinon le frein ne freinerait rien. Une écriture par échec seulement (quota gratuit).
  async refusSecours(code, source) {
    const mal = this.codeSecoursInvalide();
    if (mal) return mal;
    // Comparé AVANT de lire le compteur : entre la lecture et l'écriture, plus aucune attente hors du stockage
    // (le Durable Object laisserait passer d'autres requêtes, qui liraient le même compte et en perdraient).
    // Le résultat ne sert qu'après le contrôle de l'attente : pendant un blocage, il ne dit toujours rien.
    const bon = await memeSecret(code, this.env.CODE_SECOURS);
    // { source: { n, dernier } }. L'ancienne forme (un seul compteur { n, dernier }) est oubliée.
    const lu = await this.ctx.storage.get('secours:echecs');
    const tous = Object.fromEntries(Object.entries(lu && typeof lu === 'object' ? lu : {})
      .filter(([, e]) => e && typeof e === 'object' && Number.isInteger(e.n) && Number.isFinite(e.dernier)));
    const echecs = tous[source] || null;
    if (echecs && echecs.n >= ESSAIS_SECOURS_LIBRES) {
      // Réglable en essai local seulement (DEV), pour que les tests n'attendent pas une minute.
      const base = this.env.DEV === '1' && Number(this.env.ATTENTE_SECOURS_MS) > 0 ? Number(this.env.ATTENTE_SECOURS_MS) : ATTENTE_SECOURS_MS;
      const attente = Math.min(base * 2 ** (echecs.n - ESSAIS_SECOURS_LIBRES), ATTENTE_SECOURS_MAX);
      const reste = echecs.dernier + attente - Date.now();
      if (reste > 0) {
        const secondes = Math.ceil(reste / 1000);
        return json(429, { erreur: 'trop d essais', raison: 'code de secours bloque', attente: secondes }, { 'Retry-After': String(secondes) });
      }
    }
    if (!bon) {
      tous[source] = { n: (echecs?.n || 0) + 1, dernier: Date.now() };
      // Mémoire bornée : au-delà, les sources les moins récentes sont oubliées (seule la leur en profite).
      const cles = Object.keys(tous).sort((a, b) => tous[a].dernier - tous[b].dernier);
      for (const k of cles.slice(0, Math.max(0, cles.length - SOURCES_MAX))) delete tous[k];
      await this.ctx.storage.put('secours:echecs', tous);
      return this.refus('code de secours incorrect');
    }
    if (echecs) {
      delete tous[source];
      if (Object.keys(tous).length) await this.ctx.storage.put('secours:echecs', tous);
      else await this.ctx.storage.delete('secours:echecs');
    }
    return null;
  }

  async etat() {
    return (await this.ctx.storage.get('etat')) || { version: 0, blob: null, enregistre_le: null, par: null };
  }

  // hist : les versions gardées, de la plus ancienne à la plus récente, { v, date, par, taille } —
  // « Revenir à une version » lit cette seule clé au lieu des 10 paquets entiers (jusqu'à 14 Mo, porte
  // d'entrée de l'objet fermée pendant ce temps). Les entrées écrites avant étaient de simples numéros.
  // revenuA : numéro de la version reprise par « Revenir à une version » (null pour un envoi normal) ;
  // l'appareil qui a demandé le retour s'en sert pour le terminer si la réponse s'est perdue.
  async enregistrer(blob, nom, revenuA = null) {
    const etat = await this.etat();
    const nouveau = { version: etat.version + 1, blob, enregistre_le: new Date().toISOString(), par: nom, revenu_a: revenuA };
    const hist = (await this.ctx.storage.get('hist')) || [];
    hist.push({ v: nouveau.version, date: nouveau.enregistre_le, par: nom, taille: tailleBase64(blob) });
    const ecrire = { etat: nouveau, hist, ['hist:' + nouveau.version]: { blob, date: nouveau.enregistre_le, par: nom } };
    const perimees = [];
    while (hist.length > VERSIONS_GARDEES) perimees.push('hist:' + numeroVersion(hist.shift()));
    // Une seule écriture groupée (et une suppression) au lieu d'une suite d'appels séparés.
    await this.ctx.storage.put(ecrire);
    if (perimees.length) await this.ctx.storage.delete(perimees);
    return nouveau;
  }

  async creerAppareil(role, nom) {
    const jeton = secret(32);
    const emp = await empreinte(jeton);
    const id = 'app-' + secret(6).replace(/[-_]/g, 'a');
    await this.ctx.storage.put({
      ['app:' + id]: { emp, role, nom: nom || 'Appareil', cree: Date.now(), vu: Date.now() },
      ['jeton:' + emp]: id,
    });
    return { jeton, id, role };
  }

  async responsablesRestants(sauf) {
    const apps = await this.ctx.storage.list({ prefix: 'app:' });
    let n = 0;
    for (const [cle, app] of apps) if (app.role === 'responsable' && cle !== 'app:' + sauf) n += 1;
    return n;
  }

  async fetch(request) {
    const chemin = new URL(request.url).pathname;
    const methode = request.method;
    // Frein par source avant la moindre lecture de stockage : un jeton bidon ne doit pas faire
    // travailler le Durable Object, et un porteur de jeton n'était freiné par rien du tout.
    if (this.freine(request, SEAU_LARGE_CAPACITE, SEAU_LARGE_PAR_MINUTE, 'large')) {
      return json(429, { erreur: 'trop de requetes' });
    }
    const qui = await this.appareilDe(request);
    // Sans jeton valable, un second frein plus serré : c'est le chemin qui mène à un jeton. Le code de
    // secours y passe aussi AVEC un jeton (celui de n'importe quel vendeur ouvrait 86 400 essais par jour).
    // « Tout effacer » demande déjà un jeton responsable ET le code : le frein commun du code suffit.
    const serre = qui.statut !== 'ok' || chemin === '/api/initialiser';
    if (serre && this.freine(request, SEAU_CAPACITE, SEAU_PAR_MINUTE, 'serre')) {
      return json(429, { erreur: 'trop de requetes' });
    }
    if (qui.statut === 'retire') return this.refus('retire'); // sur ce motif, l'appli efface ses forfaits

    /* --- sans jeton : appairage et secours --- */

    if (chemin === '/api/appairage' && methode === 'POST') {
      const demande = await lireJson(request, CORPS_COURT);
      if (typeof demande?.code !== 'string' || demande.code.length < 16) return json(400, { erreur: 'code illisible' });
      const cle = 'inv:' + (await empreinte(demande.code));
      const inv = await this.ctx.storage.get(cle);
      if (!inv) return this.refus('invitation inconnue');
      if (inv.expire < Date.now()) {
        await this.ctx.storage.delete(cle);
        return this.refus('invitation expiree');
      }
      if (inv.usages <= 1) await this.ctx.storage.delete(cle);
      else await this.ctx.storage.put(cle, { ...inv, usages: inv.usages - 1 });
      // Lien de lot sans nom choisi par l'appareil : tous portaient le même nom, et retirer « le bon »
      // dans la liste devenait une devinette. Ils sont numérotés dans l'ordre d'arrivée.
      const total = Number.isInteger(inv.total) ? inv.total : 1;
      const nom = nomPropre(demande.nom) || (total > 1 ? `${inv.nom || 'Appareil'} ${total - inv.usages + 1}` : inv.nom);
      return json(200, await this.creerAppareil(inv.role, nom));
    }

    if (chemin === '/api/initialiser' && methode === 'POST') {
      const demande = await lireJson(request, CORPS_COURT);
      const refus = await this.refusSecours(demande?.code_secours, sourceDe(request.headers.get('CF-Connecting-IP')));
      if (refus) return refus;
      return json(200, await this.creerAppareil('responsable', nomPropre(demande.nom) || 'Responsable'));
    }

    /* --- jeton obligatoire au-delà --- */

    if (qui.statut !== 'ok') return this.refus('inconnu');
    const { id, app } = qui;
    const patron = app.role === 'responsable';

    if (chemin === '/api/donnees' && methode === 'GET') {
      await this.noterVu(id, app);
      const etat = await this.etat();
      const etag = `"${etat.version}"`;
      if (request.headers.get('If-None-Match') === etag) {
        return new Response(null, { status: 304, headers: { ETag: etag, 'X-Heure': String(Date.now()) } });
      }
      return json(200, { ...etat, role: app.role }, { ETag: etag });
    }

    if (chemin === '/api/donnees' && methode === 'PUT') {
      if (!patron) return this.refus('lecture seule', false);
      const demande = await lireJson(request);
      if (!Number.isInteger(demande?.version_precedente) || demande.version_precedente < 0) {
        return json(400, { erreur: 'demande illisible' });
      }
      if (!blobValide(demande.blob)) return json(400, { erreur: 'donnees chiffrees invalides' });
      const etat = await this.etat();
      // Quelqu'un a écrit entre-temps : l'appli relit, fusionne et renvoie.
      if (demande.version_precedente !== etat.version) return json(409, { version: etat.version });
      const nouveau = await this.enregistrer(demande.blob, app.nom);
      return json(200, { version: nouveau.version });
    }

    if (chemin === '/api/versions' && methode === 'GET') {
      if (!patron) return this.refus('lecture seule', false);
      const hist = (await this.ctx.storage.get('hist')) || [];
      const lignes = [];
      for (const e of [...hist].reverse()) {
        if (typeof e !== 'number') {
          lignes.push({ version: e.v, date: e.date, par: e.par, taille: e.taille });
          continue;
        }
        // Entrée écrite avant la taille mémorisée : il faut encore lire son paquet (elles partent seules au fil des envois).
        const h = await this.ctx.storage.get('hist:' + e);
        if (h) lignes.push({ version: e, date: h.date, par: h.par, taille: tailleBase64(h.blob) });
      }
      return json(200, { versions: lignes, version: (await this.etat()).version });
    }

    if (chemin === '/api/revenir' && methode === 'POST') {
      if (!patron) return this.refus('lecture seule', false);
      const demande = await lireJson(request);
      const h = Number.isInteger(demande?.version) ? await this.ctx.storage.get('hist:' + demande.version) : null;
      if (!h) return json(404, { erreur: 'version introuvable' });
      // On remet l'ancien contenu comme une NOUVELLE version : les autres appareils le voient arriver.
      const nouveau = await this.enregistrer(h.blob, app.nom, demande.version);
      // Le paquet repart dans la réponse : l'appareil n'a pas à le relire (un appel de moins qui peut
      // échouer), et un autre responsable qui enverrait entre-temps ne peut pas se glisser à sa place.
      return json(200, { version: nouveau.version, revenu_a: demande.version, blob: h.blob });
    }

    if (chemin === '/api/invitation' && methode === 'POST') {
      if (!patron) return this.refus('lecture seule', false);
      const demande = await lireJson(request);
      const role = ROLES.includes(demande?.role) ? demande.role : 'consultation';
      const usages = Number.isInteger(demande?.usages) ? Math.min(Math.max(demande.usages, 1), USAGES_MAX) : 1;
      const minutes = Number.isInteger(demande?.minutes) ? Math.min(Math.max(demande.minutes, 1), MINUTES_MAX) : 10;
      const code = secret(16);
      const expire = Date.now() + minutes * 60_000;
      await this.ctx.storage.put('inv:' + (await empreinte(code)), {
        role,
        usages,
        total: usages, // pour numéroter les appareils d'un lot
        expire,
        cree: Date.now(),
        nom: nomPropre(demande?.nom),
        par: id, // pour que retirer cet appareil annule les liens qu'il a émis
      });
      return json(200, { code, expire, role, usages });
    }

    if (chemin === '/api/appareils' && methode === 'GET') {
      if (!patron) return this.refus('lecture seule', false);
      const apps = await this.ctx.storage.list({ prefix: 'app:' });
      const liste = [];
      for (const [cle, a] of apps) {
        liste.push({ id: cle.slice(4), nom: a.nom, role: a.role, cree: a.cree, vu: a.vu, moi: cle === 'app:' + id });
      }
      liste.sort((x, y) => (y.vu || 0) - (x.vu || 0));
      return json(200, { appareils: liste });
    }

    // Liens d'appairage encore valables : un lien parti chez le mauvais destinataire (24 h, 20 appareils)
    // ne s'annulait qu'en retirant l'appareil qui l'avait créé. L'identifiant montré est le début de
    // l'empreinte : il désigne le lien sans rien dire du code.
    if (chemin === '/api/invitations' && methode === 'GET') {
      if (!patron) return this.refus('lecture seule', false);
      const invs = await this.ctx.storage.list({ prefix: 'inv:' });
      const apps = await this.ctx.storage.list({ prefix: 'app:' });
      const liste = [];
      const perimees = [];
      for (const [cle, inv] of invs) {
        if (inv.expire < Date.now()) { perimees.push(cle); continue; }
        liste.push({ id: cle.slice(4, 20), role: inv.role, usages: inv.usages, expire: inv.expire, cree: inv.cree || null, nom: inv.nom, par: apps.get('app:' + inv.par)?.nom || '' });
      }
      if (perimees.length) await this.ctx.storage.delete(perimees);
      liste.sort((x, y) => x.expire - y.expire);
      return json(200, { invitations: liste });
    }

    if (chemin.startsWith('/api/invitations/') && methode === 'DELETE') {
      if (!patron) return this.refus('lecture seule', false);
      const debut = chemin.slice('/api/invitations/'.length);
      if (!/^[0-9a-f]{16}$/.test(debut)) return json(404, { erreur: 'lien introuvable' });
      const trouvees = [...(await this.ctx.storage.list({ prefix: 'inv:' + debut })).keys()];
      if (!trouvees.length) return json(404, { erreur: 'lien introuvable' });
      await this.ctx.storage.delete(trouvees);
      return json(200, { annule: debut });
    }

    // L'appareil se retire lui-même (« Déconnecter », ou premier appareil qui renonce à remplacer le
    // cloud) : sans ça, son jeton restait valable et il comptait encore comme responsable, ce qui
    // désarmait la garde du dernier responsable. Pas de marque de retrait : il ne doit rien effacer.
    if (chemin === '/api/moi' && methode === 'DELETE') {
      // Ses liens d'appairage partent avec lui, comme pour un appareil retiré.
      const invs = await this.ctx.storage.list({ prefix: 'inv:' });
      const siens = [...invs].filter(([, inv]) => inv.par === id).map(([cle]) => cle);
      await this.ctx.storage.delete(['app:' + id, 'jeton:' + app.emp, ...siens]);
      return json(200, { retire: id });
    }

    if (chemin.startsWith('/api/appareils/') && methode === 'DELETE') {
      if (!patron) return this.refus('lecture seule', false);
      const cible = chemin.slice('/api/appareils/'.length);
      const a = await this.ctx.storage.get('app:' + cible);
      if (!a) return json(404, { erreur: 'appareil introuvable' });
      // Garde-fou : retirer le dernier responsable bloquerait tout le monde dehors.
      if (a.role === 'responsable' && (await this.responsablesRestants(cible)) === 0) {
        return json(409, { erreur: 'dernier responsable' });
      }
      // Retirer un appareil doit AUSSI annuler les liens d'appairage qu'il a créés : sinon un
      // téléphone perdu reste une porte d'entrée pendant 24 h (un lien en lot vaut 20 jetons),
      // et l'appareil retiré revient avec un nouvel id, donc sans que personne ne le voie.
      const invs = await this.ctx.storage.list({ prefix: 'inv:' });
      const mortes = [];
      for (const [cle, inv] of invs) if (inv.par === cible) mortes.push(cle);
      if (mortes.length) await this.ctx.storage.delete(mortes);
      await this.ctx.storage.delete(['app:' + cible, 'jeton:' + a.emp]);
      await this.ctx.storage.put('retire:' + a.emp, Date.now());
      // Ménage plus tard : la trace ne doit pas rester pour toujours.
      if (!(await this.ctx.storage.getAlarm())) await this.ctx.storage.setAlarm(Date.now() + TOMBE_MS);
      return json(200, { retire: cible });
    }

    if (chemin === '/api/tout' && methode === 'DELETE') {
      if (!patron) return this.refus('lecture seule', false);
      const refus = await this.refusSecours(request.headers.get('X-Code-Secours'), sourceDe(request.headers.get('CF-Connecting-IP')));
      if (refus) return refus;
      // Les marques de retrait survivent : un appareil retiré resté éteint doit encore s'effacer en se
      // rallumant (après un effacement complet, le cloud lui répondait « inconnu » et il gardait tout).
      const tombes = await this.ctx.storage.list({ prefix: 'retire:' });
      await this.ctx.storage.deleteAll();
      if (tombes.size) {
        const toutes = [...tombes];
        // 128 clés au plus par écriture groupée.
        for (let i = 0; i < toutes.length; i += 128) await this.ctx.storage.put(Object.fromEntries(toutes.slice(i, i + 128)));
        await this.ctx.storage.setAlarm(Date.now() + TOMBE_MS);
      }
      this.seaux.clear(); // le frein fait partie de « tout »
      return json(200, { efface: true });
    }

    return json(404, { erreur: 'route inconnue' });
  }

  // Ménage : les traces d'appareils retirés ne s'accumulent pas indéfiniment.
  async alarm() {
    const tombes = await this.ctx.storage.list({ prefix: 'retire:' });
    const vieilles = [];
    let reste = false;
    for (const [cle, date] of tombes) {
      if (Date.now() - date > TOMBE_MS) vieilles.push(cle);
      else reste = true;
    }
    if (vieilles.length) await this.ctx.storage.delete(vieilles);
    if (reste) await this.ctx.storage.setAlarm(Date.now() + TOMBE_MS);
  }
}
