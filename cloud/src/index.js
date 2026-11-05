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
const VU_INTERVALLE = 3_600_000; // « vu le » noté une fois par heure au plus (économise les écritures)
const TOMBE_MS = 90 * 86_400_000; // on se souvient 90 jours d'un appareil retiré, pour qu'il s'efface
const ROLES = ['responsable', 'consultation'];

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
    /^[A-Za-z0-9+/]+={0,2}$/.test(blob) &&
    tailleBase64(blob) >= MIN_CHIFFRE
  );
}

const nomPropre = (v) => (typeof v === 'string' ? v.replace(/[\u0000-\u001f]/g, ' ').trim().slice(0, 40) : '');

async function lireJson(request) {
  try {
    return await request.json();
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
    if (Number(request.headers.get('Content-Length') || 0) > MAX_CORPS + 4096) {
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
   inv:<emp>     : { role, usages, expire, nom }                                             */

export class Equipe {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
    this.seau = { jetons: SEAU_CAPACITE, dernier: Date.now() };
  }

  // Limite de débit pour les requêtes sans jeton valable : un inconnu qui inonde ne gêne que les
  // inconnus. Compteur en mémoire : perdu si l'objet s'endort, ce qui est sans conséquence pour un
  // frein, et surtout : zéro écriture (le gratuit en compte 100 000 par jour).
  freine() {
    const maintenant = Date.now();
    this.seau.jetons = Math.min(
      SEAU_CAPACITE,
      this.seau.jetons + ((maintenant - this.seau.dernier) * SEAU_PAR_MINUTE) / 60_000,
    );
    this.seau.dernier = maintenant;
    if (this.seau.jetons < 1) return true;
    this.seau.jetons -= 1;
    return false;
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

  async refus(raison) {
    await dodo(PAUSE_REFUS);
    return json(401, { erreur: 'acces refuse', raison });
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
    const qui = await this.appareilDe(request);
    if (qui.statut !== 'ok' && this.freine()) return json(429, { erreur: 'trop de requetes' });
    if (qui.statut === 'retire') return this.refus('retire'); // sur ce motif, l'appli efface ses forfaits

    /* --- sans jeton : appairage et secours --- */

    if (chemin === '/api/appairage' && methode === 'POST') {
      const demande = await lireJson(request);
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
      const demande = await lireJson(request);
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
      if (!patron) return this.refus('lecture seule');
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
      if (!patron) return this.refus('lecture seule');
      const hist = (await this.ctx.storage.get('hist')) || [];
      const lignes = [];
      for (const v of [...hist].reverse()) {
        const h = await this.ctx.storage.get('hist:' + v);
        if (h) lignes.push({ version: v, date: h.date, par: h.par, taille: tailleBase64(h.blob) });
      }
      return json(200, { versions: lignes, version: (await this.etat()).version });
    }

    if (chemin === '/api/revenir' && methode === 'POST') {
      if (!patron) return this.refus('lecture seule');
      const demande = await lireJson(request);
      const h = Number.isInteger(demande?.version) ? await this.ctx.storage.get('hist:' + demande.version) : null;
      if (!h) return json(404, { erreur: 'version introuvable' });
      // On remet l'ancien contenu comme une NOUVELLE version : les autres appareils le voient arriver.
      const nouveau = await this.enregistrer(h.blob, app.nom);
      return json(200, { version: nouveau.version, revenu_a: demande.version });
    }

    if (chemin === '/api/invitation' && methode === 'POST') {
      if (!patron) return this.refus('lecture seule');
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
      });
      return json(200, { code, expire, role, usages });
    }

    if (chemin === '/api/appareils' && methode === 'GET') {
      if (!patron) return this.refus('lecture seule');
      const apps = await this.ctx.storage.list({ prefix: 'app:' });
      const liste = [];
      for (const [cle, a] of apps) {
        liste.push({ id: cle.slice(4), nom: a.nom, role: a.role, cree: a.cree, vu: a.vu, moi: cle === 'app:' + id });
      }
      liste.sort((x, y) => (y.vu || 0) - (x.vu || 0));
      return json(200, { appareils: liste });
    }

    if (chemin.startsWith('/api/appareils/') && methode === 'DELETE') {
      if (!patron) return this.refus('lecture seule');
      const cible = chemin.slice('/api/appareils/'.length);
      const a = await this.ctx.storage.get('app:' + cible);
      if (!a) return json(404, { erreur: 'appareil introuvable' });
      // Garde-fou : retirer le dernier responsable bloquerait tout le monde dehors.
      if (a.role === 'responsable' && (await this.responsablesRestants(cible)) === 0) {
        return json(409, { erreur: 'dernier responsable' });
      }
      await this.ctx.storage.delete(['app:' + cible, 'jeton:' + a.emp]);
      await this.ctx.storage.put('retire:' + a.emp, Date.now());
      // Ménage plus tard : la trace ne doit pas rester pour toujours.
      if (!(await this.ctx.storage.getAlarm())) await this.ctx.storage.setAlarm(Date.now() + TOMBE_MS);
      return json(200, { retire: cible });
    }

    if (chemin === '/api/tout' && methode === 'DELETE') {
      if (!patron) return this.refus('lecture seule');
      if (!(await memeSecret(request.headers.get('X-Code-Secours'), this.env.CODE_SECOURS))) {
        return this.refus('code de secours incorrect');
      }
      await this.ctx.storage.deleteAll();
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
