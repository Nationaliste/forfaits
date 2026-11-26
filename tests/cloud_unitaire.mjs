// Essais du Durable Object seul, dans Node, avec un faux stockage en mémoire : ce que le Worker lancé par
// wrangler ne permet pas de préparer (adresse de l'appelant, historique écrit par une version d'avant).
// Lancé par tests/test_cloud_unitaire.py ; écrit un objet JSON de constats sur la sortie.
import { createHash, timingSafeEqual } from 'node:crypto';
import { Equipe } from '../cloud/src/index.js';

// Extension propre aux Workers, absente de Node : même comparaison à temps constant.
if (!crypto.subtle.timingSafeEqual) crypto.subtle.timingSafeEqual = (a, b) => timingSafeEqual(Buffer.from(a), Buffer.from(b));

function fauxStockage() {
  const d = new Map();
  const copie = (v) => (v === undefined ? undefined : structuredClone(v));
  return {
    d,
    async get(k) {
      return copie(d.get(k));
    },
    async put(k, v) {
      if (typeof k === 'object') for (const [a, b] of Object.entries(k)) d.set(a, copie(b));
      else d.set(k, copie(v));
    },
    async delete(k) {
      for (const x of [].concat(k)) d.delete(x);
    },
    async list({ prefix = '' } = {}) {
      return new Map([...d].filter(([k]) => k.startsWith(prefix)).sort(([a], [b]) => (a < b ? -1 : 1)));
    },
    async deleteAll() {
      d.clear();
    },
    async setAlarm() {},
    async getAlarm() {
      return null;
    },
  };
}

// Les refus attendent 250 ms (frein des devinettes) : sans délai ici, les seaux ne se remplissent pas pendant l'essai.
globalThis.setTimeout = (f) => {
  queueMicrotask(f);
  return 0;
};

const empreinte = (t) => createHash('sha256').update(t).digest('hex');
const constats = {};

// ---- Frein par source : le /64 d'une adresse IPv6 compte pour une seule source, et remplir la mémoire
// d'adresses nouvelles n'efface pas le seau d'une source déjà épuisée.
{
  const equipe = new Equipe({ storage: fauxStockage() }, { CODE_SECOURS: 'c'.repeat(29) });
  const appel = (ip) => equipe.fetch(new Request('http://cloud/api/donnees', { headers: { 'CF-Connecting-IP': ip } }));
  let statut = 0;
  for (let i = 0; i < 200 && statut !== 429; i++) statut = (await appel(`2001:db8:0:1::${(i % 9000) + 1}`)).status;
  constats.ipv6_epuisee = statut;
  constats.ipv6_meme_64 = (await appel('2001:db8:0:1:ffff:ffff:ffff:ffff')).status;
  constats.ipv6_autre_64 = (await appel('2001:db8:0:2::1')).status;

  // Une source épuisée (192.0.2.1) puis assez d'autres pour remplir la mémoire (200 sources).
  for (let i = 0; i < 200 && (await appel('192.0.2.1')).status !== 429; i++);
  for (let i = 0; i < 197; i++) await appel(`2001:db8:a:${i}::1`);
  constats.epuisee_avant = (await appel('192.0.2.1')).status;
  // 198 sources gardées : la 3e nouvelle fait passer la mémoire au plafond.
  for (let i = 1; i <= 3; i++) await appel(`203.0.113.${i}`);
  constats.epuisee_apres = (await appel('192.0.2.1')).status;
}

// ---- Historique écrit avant la taille mémorisée (numéros seuls) : listé quand même, avec sa taille.
{
  const stockage = fauxStockage();
  const equipe = new Equipe({ storage: stockage }, { CODE_SECOURS: 'c'.repeat(29) });
  const jeton = 'j'.repeat(43);
  const blob = (n, octets) => Buffer.alloc(octets, n).toString('base64');
  await stockage.put({
    'app:app-patron': { emp: empreinte(jeton), role: 'responsable', nom: 'Patron', cree: Date.now(), vu: Date.now() },
    ['jeton:' + empreinte(jeton)]: 'app-patron',
    etat: { version: 2, blob: blob(2, 90), enregistre_le: '2026-11-02T10:00:00.000Z', par: 'Ancien' },
    hist: [1, 2],
    'hist:1': { blob: blob(1, 60), date: '2026-11-01T10:00:00.000Z', par: 'Ancien' },
    'hist:2': { blob: blob(2, 90), date: '2026-11-02T10:00:00.000Z', par: 'Ancien' },
  });
  const entetes = { Authorization: 'Bearer ' + jeton, 'Content-Type': 'application/json' };
  const envoi = await equipe.fetch(new Request('http://cloud/api/donnees', {
    method: 'PUT', headers: entetes, body: JSON.stringify({ version_precedente: 2, blob: blob(3, 120) }),
  }));
  constats.envoi = envoi.status;
  const r = await equipe.fetch(new Request('http://cloud/api/versions', { headers: entetes }));
  constats.versions = (await r.json()).versions;
  constats.hist = stockage.d.get('hist');
}

// ---- Code de secours : bloqué pour la source qui se trompe, pas pour les autres (récupération toujours possible).
{
  const code = 'c'.repeat(29);
  const equipe = new Equipe({ storage: fauxStockage() }, { CODE_SECOURS: code });
  const essai = (ip, essaye) => equipe.fetch(new Request('http://cloud/api/initialiser', {
    method: 'POST', headers: { 'CF-Connecting-IP': ip, 'Content-Type': 'application/json' },
    body: JSON.stringify({ code_secours: essaye }),
  }));
  for (let i = 0; i < 5; i++) await essai('203.0.113.7', '');
  constats.secours_meme_source = (await essai('203.0.113.7', code)).status;
  constats.secours_meme_64 = (await essai('2001:db8:5:5::1', 'x'.repeat(29))).status;
  for (let i = 0; i < 4; i++) await essai('2001:db8:5:5::1', 'x'.repeat(29));
  constats.secours_ipv6_bloquee = (await essai('2001:db8:5:5:ffff::9', code)).status;
  constats.secours_autre_source = (await essai('198.51.100.20', code)).status;
}

process.stdout.write(JSON.stringify(constats));
