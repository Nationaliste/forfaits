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
const SOURCES_MAX = 200; // seaux gardés en mémoire : au-delà on repart à neuf
const CORPS_COURT = 4096; // appairage et secours : deux champs courts, jamais un paquet de forfaits
const VU_INTERVALLE = 3_600_000; // « vu le » noté une fois par heure au plus (économise les écritures)
const TOMBE_MS = 90 * 86_400_000; // on se souvient 90 jours d'un appareil retiré, pour qu'il s'efface
const ROLES = ['responsable', 'consultation'];
const LIMITE_CORPS = MAX_CORPS + 4096; // marge pour l'enveloppe JSON autour du paquet
const CODE_SECOURS_MIN = 12; // le minimum de la page ne protège pas : un attaquant n'exécute pas la page

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
   etat          : { version, blob, enregistre_le, par }
   hist          : [versions gardées]        hist:<n>     : { blob, date, par }
   app:<id>      : { emp, role, nom, cree, vu }
   jeton:<emp>   : <id>                      retire:<emp> : date (pour que l'appareil s'efface)
   inv:<emp>     : { role, usages, expire, nom, par } (par = l'appareil qui l'a émise)        */

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
    const source = request.headers.get('CF-Connecting-IP') || 'sans-source';
    // Un attaquant qui change d'adresse ne doit pas nous remplir la mémoire. Repartir à neuf ne
    // profite qu'aux appelants honnêtes (leur seau revient plein).
    if (this.seaux.size > SOURCES_MAX) this.seaux.clear();
    const siens = this.seaux.get(source) || {};
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

  async etat() {
    return (await this.ctx.storage.get('etat')) || { version: 0, blob: null, enregistre_le: null, par: null };
  }

  async enregistrer(blob, nom) {
    const etat = await this.etat();
    const nouveau = { version: etat.version + 1, blob, enregistre_le: new Date().toISOString(), par: nom };
    const hist = (await this.ctx.storage.get('hist')) || [];
    hist.push(nouveau.version);
    await this.ctx.storage.put('hist:' + nouveau.version, { blob, date: nouveau.enregistre_le, par: nom });
    while (hist.length > VERSIONS_GARDEES) await this.ctx.storage.delete('hist:' + hist.shift());
    await this.ctx.storage.put({ etat: nouveau, hist });
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
    // Sans jeton valable, un second frein plus serré : c'est le chemin qui mène à un jeton.
    if (qui.statut !== 'ok' && this.freine(request, SEAU_CAPACITE, SEAU_PAR_MINUTE, 'serre')) {
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
      return json(200, await this.creerAppareil(inv.role, nomPropre(demande.nom) || inv.nom));
    }

    if (chemin === '/api/initialiser' && methode === 'POST') {
      const mal = this.codeSecoursInvalide();
      if (mal) return mal;
      const demande = await lireJson(request, CORPS_COURT);
      if (!(await memeSecret(demande?.code_secours, this.env.CODE_SECOURS))) return this.refus('code de secours incorrect');
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
      for (const v of [...hist].reverse()) {
        const h = await this.ctx.storage.get('hist:' + v);
        if (h) lignes.push({ version: v, date: h.date, par: h.par, taille: tailleBase64(h.blob) });
      }
      return json(200, { versions: lignes, version: (await this.etat()).version });
    }

    if (chemin === '/api/revenir' && methode === 'POST') {
      if (!patron) return this.refus('lecture seule', false);
      const demande = await lireJson(request);
      const h = Number.isInteger(demande?.version) ? await this.ctx.storage.get('hist:' + demande.version) : null;
      if (!h) return json(404, { erreur: 'version introuvable' });
      // On remet l'ancien contenu comme une NOUVELLE version : les autres appareils le voient arriver.
      const nouveau = await this.enregistrer(h.blob, app.nom);
      return json(200, { version: nouveau.version, revenu_a: demande.version });
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
        expire,
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
      const mal = this.codeSecoursInvalide();
      if (mal) return mal;
      if (!(await memeSecret(request.headers.get('X-Code-Secours'), this.env.CODE_SECOURS))) {
        return this.refus('code de secours incorrect');
      }
      await this.ctx.storage.deleteAll();
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
