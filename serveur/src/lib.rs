//! Serveur de synchronisation des forfaits.
//!
//! Il ne voit jamais les forfaits en clair : l'appli les chiffre avant de les envoyer
//! (AES-256-GCM, clé tirée du mot de passe d'équipe, que le serveur ne connaît pas).
//! Il garde seulement : la dernière version chiffrée, un historique des versions,
//! et l'empreinte des deux jetons d'accès (lecture pour tous, écriture pour les responsables).
//!
//! Il n'écoute que sur 127.0.0.1 : personne sur le réseau local ne peut s'y connecter.
//! L'accès depuis internet passe par Tailscale Funnel, qui relaie vers ce port.

use std::fs::{self, File, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex as VerrouSimple};
use std::time::{Duration, Instant};

use axum::body::to_bytes;
use axum::extract::{Request, State};
use axum::http::{HeaderMap, HeaderValue, Method, StatusCode, header};
use axum::middleware::{self, Next};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::{Json, Router};
use base64::Engine;
use base64::engine::general_purpose::STANDARD as B64;
use serde::{Deserialize, Serialize};
use serde_json::json;
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;
use tokio::sync::Mutex;
use tower_http::cors::{AllowOrigin, CorsLayer};

/// Tours de PBKDF2-SHA256 (recommandation OWASP) : deviner un mot de passe coûte cher.
pub const ITERATIONS: u32 = 600_000;
/// Taille maximale d'une version chiffrée (texte base64), soit des milliers de forfaits.
pub const TAILLE_MAX_BLOB: usize = 4 * 1024 * 1024;
/// Plus petite donnée chiffrée possible : 12 octets d'IV + 16 octets d'étiquette AES-GCM.
const TAILLE_MIN_CHIFFRE: usize = 28;
/// Nombre de versions gardées dans l'historique.
const VERSIONS_GARDEES: usize = 200;
const TAILLE_MAX_JOURNAL: u64 = 2 * 1024 * 1024;
/// Pause après un jeton refusé : ralentit les essais au hasard.
const PAUSE_REFUS: Duration = Duration::from_millis(300);

// ---------------------------------------------------------------- dérivation des clés
// Même calcul que l'appli (WebCrypto) : mot de passe → PBKDF2 → HKDF selon l'usage.

/// Clé maîtresse tirée d'un mot de passe (normalisé NFC, comme l'appli).
pub fn cle_maitre(secret: &str, sel: &[u8], iterations: u32) -> [u8; 32] {
    use unicode_normalization::UnicodeNormalization;
    let normalise: String = secret.nfc().collect();
    let mut sortie = [0u8; 32];
    pbkdf2::pbkdf2_hmac::<Sha256>(normalise.as_bytes(), sel, iterations, &mut sortie);
    sortie
}

/// Sous-clé pour un usage (« lecture », « ecriture », « chiffrement »).
pub fn deriver(maitre: &[u8; 32], usage: &str) -> [u8; 32] {
    let mut sortie = [0u8; 32];
    hkdf::Hkdf::<Sha256>::new(None, maitre)
        .expand(format!("forfaits:{usage}").as_bytes(), &mut sortie)
        .expect("32 octets est une longueur valide pour HKDF-SHA256");
    sortie
}

pub fn hex(octets: &[u8]) -> String {
    octets.iter().map(|o| format!("{o:02x}")).collect()
}

fn depuis_hex(texte: &str) -> Option<[u8; 32]> {
    if texte.len() != 64 {
        return None;
    }
    let mut sortie = [0u8; 32];
    for (i, octet) in sortie.iter_mut().enumerate() {
        *octet = u8::from_str_radix(texte.get(2 * i..2 * i + 2)?, 16).ok()?;
    }
    Some(sortie)
}

/// Jeton envoyé par l'appli (64 caractères hexadécimaux).
pub fn jeton(secret: &str, sel: &[u8], iterations: u32, usage: &str) -> String {
    hex(&deriver(&cle_maitre(secret, sel, iterations), usage))
}

/// Ce que le serveur garde d'un jeton : son empreinte SHA-256 (le jeton lui-même n'est jamais écrit).
pub fn empreinte(jeton: &str) -> String {
    hex(&Sha256::digest(jeton.as_bytes()))
}

// ---------------------------------------------------------------- fichiers

/// Écrit d'abord un fichier temporaire puis le renomme : jamais de fichier à moitié écrit.
fn ecrire_atomique(chemin: &Path, contenu: &[u8]) -> io::Result<()> {
    let temporaire = chemin.with_extension("tmp");
    let mut fichier = File::create(&temporaire)?;
    fichier.write_all(contenu)?;
    fichier.sync_all()?;
    drop(fichier);
    fs::rename(&temporaire, chemin)
}

fn horodatage() -> String {
    chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Config {
    pub port: u16,
    /// Adresses des sites autorisés à appeler le serveur (en-tête Origin).
    pub origines: Vec<String>,
    /// Sel de dérivation (base64), public : l'appli en a besoin pour dériver les clés.
    pub sel: String,
    pub iterations: u32,
    pub empreinte_lecture: String,
    pub empreinte_ecriture: String,
    /// Dossier où recopier chaque version (ex. OneDrive), en plus du dossier du serveur.
    #[serde(default)]
    pub dossier_copie: Option<PathBuf>,
}

impl Config {
    pub fn chemin(dossier: &Path) -> PathBuf {
        dossier.join("config.json")
    }

    pub fn lire(dossier: &Path) -> io::Result<Config> {
        serde_json::from_str(&fs::read_to_string(Self::chemin(dossier))?).map_err(io::Error::other)
    }

    pub fn ecrire(&self, dossier: &Path) -> io::Result<()> {
        ecrire_atomique(&Self::chemin(dossier), &serde_json::to_vec_pretty(self).map_err(io::Error::other)?)
    }
}

/// Dernière version enregistrée : numéro, données chiffrées (base64) et date.
#[derive(Serialize, Deserialize, Clone, Default, Debug, PartialEq)]
pub struct Etat {
    pub version: u64,
    pub blob: Option<String>,
    pub enregistre_le: Option<String>,
}

pub struct Stockage {
    dossier: PathBuf,
    copie: Option<PathBuf>,
}

impl Stockage {
    pub fn new(dossier: &Path, copie: Option<PathBuf>) -> Self {
        Stockage { dossier: dossier.to_path_buf(), copie }
    }

    fn chemin(&self) -> PathBuf {
        self.dossier.join("donnees.json")
    }

    fn historique(&self) -> PathBuf {
        self.dossier.join("historique")
    }

    pub fn charger(&self) -> io::Result<Etat> {
        match fs::read_to_string(self.chemin()) {
            Ok(texte) => serde_json::from_str(&texte).map_err(io::Error::other),
            Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(Etat::default()),
            Err(e) => Err(e),
        }
    }

    /// Enregistre la version (fichier donnees.json) ; renvoie le contenu écrit.
    pub fn enregistrer(&self, etat: &Etat) -> io::Result<Vec<u8>> {
        let contenu = serde_json::to_vec(etat).map_err(io::Error::other)?;
        ecrire_atomique(&self.chemin(), &contenu)?;
        Ok(contenu)
    }

    /// Range la version dans l'historique et élague les plus anciennes.
    pub fn historiser(&self, version: u64, contenu: &[u8]) -> io::Result<()> {
        let historique = self.historique();
        fs::create_dir_all(&historique)?;
        fs::write(historique.join(format!("v{version:08}.json")), contenu)?;
        let mut versions: Vec<PathBuf> = fs::read_dir(&historique)?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.file_name().and_then(|n| n.to_str()).is_some_and(|n| n.starts_with('v') && n.ends_with(".json")))
            .collect();
        versions.sort();
        let surplus = versions.len().saturating_sub(VERSIONS_GARDEES);
        for ancienne in &versions[..surplus] {
            fs::remove_file(ancienne)?;
        }
        Ok(())
    }

    /// Recopie de secours (ex. dans OneDrive). Une erreur ici ne bloque pas l'enregistrement.
    pub fn recopier(&self, contenu: &[u8]) -> io::Result<()> {
        match &self.copie {
            Some(copie) => {
                fs::create_dir_all(copie)?;
                ecrire_atomique(&copie.join("donnees.json"), contenu)
            }
            None => Ok(()),
        }
    }

    /// Met de côté les données et l'historique actuels (quand on change les mots de passe) :
    /// chiffrés avec l'ancienne clé, ils ne doivent pas se mélanger aux nouvelles versions.
    pub fn archiver(&self) -> io::Result<()> {
        let archive = self.dossier.join(format!("archive-{}", chrono::Local::now().format("%Y%m%d-%H%M%S")));
        for (actuel, nom) in [(self.chemin(), "donnees.json"), (self.historique(), "historique")] {
            if actuel.exists() {
                fs::create_dir_all(&archive)?;
                fs::rename(actuel, archive.join(nom))?;
            }
        }
        Ok(())
    }
}

/// Journal des requêtes (méthode, chemin, statut). Jamais de jeton ni de donnée.
pub struct Journal {
    chemin: PathBuf,
    fichier: VerrouSimple<Option<File>>,
}

impl Journal {
    pub fn ouvrir(dossier: &Path) -> Self {
        Journal { chemin: dossier.join("serveur.log"), fichier: VerrouSimple::new(None) }
    }

    pub fn ecrire(&self, message: &str) {
        let mut fichier = self.fichier.lock().unwrap_or_else(|e| e.into_inner());
        let trop_gros = fichier.as_ref().and_then(|f| f.metadata().ok()).is_some_and(|m| m.len() > TAILLE_MAX_JOURNAL);
        if trop_gros {
            *fichier = None;
            let _ = fs::rename(&self.chemin, self.chemin.with_extension("log.1"));
        }
        if fichier.is_none() {
            *fichier = OpenOptions::new().create(true).append(true).open(&self.chemin).ok();
        }
        if let Some(f) = fichier.as_mut() {
            let _ = writeln!(f, "{} {message}", horodatage());
        }
    }
}

// ---------------------------------------------------------------- serveur web

/// Limite globale de débit (seau à jetons) : protège contre les appels en rafale.
struct Seau {
    jetons: f64,
    dernier: Instant,
}

impl Seau {
    const CAPACITE: f64 = 60.0;
    const PAR_SECONDE: f64 = 10.0;

    fn prendre(&mut self) -> bool {
        let maintenant = Instant::now();
        let ecoule = maintenant.duration_since(self.dernier).as_secs_f64();
        self.jetons = (self.jetons + ecoule * Self::PAR_SECONDE).min(Self::CAPACITE);
        self.dernier = maintenant;
        if self.jetons >= 1.0 {
            self.jetons -= 1.0;
            true
        } else {
            false
        }
    }
}

pub struct App {
    sel: String,
    iterations: u32,
    lecture: [u8; 32],
    ecriture: [u8; 32],
    origines: Vec<HeaderValue>,
    stockage: Stockage,
    etat: Mutex<Etat>,
    seau: VerrouSimple<Seau>,
    pub journal: Journal,
}

impl App {
    pub fn avec_config(dossier: &Path, config: &Config) -> io::Result<Arc<App>> {
        let invalide = |quoi: &str| io::Error::other(format!("config.json : {quoi} invalide"));
        let stockage = Stockage::new(dossier, config.dossier_copie.clone());
        Ok(Arc::new(App {
            sel: config.sel.clone(),
            iterations: config.iterations,
            lecture: depuis_hex(&config.empreinte_lecture).ok_or_else(|| invalide("empreinte_lecture"))?,
            ecriture: depuis_hex(&config.empreinte_ecriture).ok_or_else(|| invalide("empreinte_ecriture"))?,
            origines: config
                .origines
                .iter()
                .map(|o| HeaderValue::from_str(o).map_err(|_| invalide("origines")))
                .collect::<io::Result<_>>()?,
            etat: Mutex::new(stockage.charger()?),
            stockage,
            seau: VerrouSimple::new(Seau { jetons: Seau::CAPACITE, dernier: Instant::now() }),
            journal: Journal::ouvrir(dossier),
        }))
    }
}

pub fn routeur(app: Arc<App>) -> Router {
    let cors = CorsLayer::new()
        .allow_origin(AllowOrigin::list(app.origines.clone()))
        .allow_methods([Method::GET, Method::PUT])
        .allow_headers([header::AUTHORIZATION, header::CONTENT_TYPE, header::IF_NONE_MATCH])
        .expose_headers([header::ETAG])
        .max_age(Duration::from_secs(600));
    Router::new()
        .route("/api/sel", get(sel))
        .route("/api/donnees", get(lire).put(ecrire))
        .route("/api/acces-ecriture", get(verifier_ecriture))
        .layer(middleware::from_fn_with_state(app.clone(), garde))
        .layer(cors) // en dernier : les réponses d'erreur (401, 429) restent lisibles par l'appli
        .with_state(app)
}

/// Passe par toutes les requêtes : limite de débit, en-têtes de sécurité, journal.
async fn garde(State(app): State<Arc<App>>, requete: Request, suivant: Next) -> Response {
    let debut = Instant::now();
    let methode = requete.method().clone();
    let chemin: String = requete.uri().path().chars().take(100).collect(); // un chemin géant ne remplit pas le journal
    // Les appareils qui ont un bon jeton ne sont jamais freinés : un inconnu qui inonde le serveur
    // ne bloque que les autres inconnus.
    let accepte = jeton_connu(&app, requete.headers()) || app.seau.lock().unwrap_or_else(|e| e.into_inner()).prendre();
    let mut reponse = if accepte {
        suivant.run(requete).await
    } else {
        (StatusCode::TOO_MANY_REQUESTS, "Trop de requetes : reessaie dans un instant").into_response()
    };
    let entetes = reponse.headers_mut();
    entetes.insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    entetes.insert(header::X_CONTENT_TYPE_OPTIONS, HeaderValue::from_static("nosniff"));
    entetes.insert(header::REFERRER_POLICY, HeaderValue::from_static("no-referrer"));
    app.journal.ecrire(&format!("{methode} {chemin} {} {} ms", reponse.status().as_u16(), debut.elapsed().as_millis()));
    reponse
}

/// Empreinte du jeton reçu dans l'en-tête « Authorization: Bearer … ».
fn empreinte_recue(entetes: &HeaderMap) -> Option<[u8; 32]> {
    let jeton = entetes.get(header::AUTHORIZATION)?.to_str().ok()?.strip_prefix("Bearer ")?;
    Some(Sha256::digest(jeton.as_bytes()).into())
}

fn jeton_connu(app: &App, entetes: &HeaderMap) -> bool {
    empreinte_recue(entetes).is_some_and(|e| bool::from(e.ct_eq(&app.lecture) | e.ct_eq(&app.ecriture)))
}

/// Compare le jeton reçu à l'empreinte attendue, en temps constant.
async fn autorise(attendue: &[u8; 32], entetes: &HeaderMap) -> bool {
    let valide = empreinte_recue(entetes).is_some_and(|e| bool::from(e.ct_eq(attendue)));
    if !valide {
        tokio::time::sleep(PAUSE_REFUS).await;
    }
    valide
}

fn refus() -> Response {
    (StatusCode::UNAUTHORIZED, Json(json!({ "erreur": "acces refuse" }))).into_response()
}

async fn sel(State(app): State<Arc<App>>) -> Response {
    Json(json!({ "sel": app.sel, "iterations": app.iterations })).into_response()
}

async fn lire(State(app): State<Arc<App>>, entetes: HeaderMap) -> Response {
    if !autorise(&app.lecture, &entetes).await {
        return refus();
    }
    let etat = app.etat.lock().await.clone();
    let etag = format!("\"{}\"", etat.version);
    let etag_entete = HeaderValue::from_str(&etag).expect("un nombre entre guillemets est un en-tête valide");
    if entetes.get(header::IF_NONE_MATCH).and_then(|v| v.to_str().ok()) == Some(etag.as_str()) {
        return (StatusCode::NOT_MODIFIED, [(header::ETAG, etag_entete)]).into_response();
    }
    (StatusCode::OK, [(header::ETAG, etag_entete)], Json(etat)).into_response()
}

async fn verifier_ecriture(State(app): State<Arc<App>>, entetes: HeaderMap) -> Response {
    if autorise(&app.ecriture, &entetes).await { StatusCode::NO_CONTENT.into_response() } else { refus() }
}

#[derive(Deserialize)]
struct Ecriture {
    version_precedente: u64,
    blob: String,
}

fn blob_valide(blob: &str) -> bool {
    blob.len() <= TAILLE_MAX_BLOB && B64.decode(blob).is_ok_and(|octets| octets.len() >= TAILLE_MIN_CHIFFRE)
}

async fn ecrire(State(app): State<Arc<App>>, requete: Request) -> Response {
    // Jeton vérifié avant de lire le corps : un inconnu ne peut pas faire charger 4 Mo au serveur.
    if !autorise(&app.ecriture, requete.headers()).await {
        return refus();
    }
    let Ok(corps) = to_bytes(requete.into_body(), TAILLE_MAX_BLOB + 1024).await else {
        return (StatusCode::PAYLOAD_TOO_LARGE, Json(json!({ "erreur": "donnees trop grosses" }))).into_response();
    };
    let Ok(demande) = serde_json::from_slice::<Ecriture>(&corps) else {
        return (StatusCode::BAD_REQUEST, Json(json!({ "erreur": "demande illisible" }))).into_response();
    };
    if !blob_valide(&demande.blob) {
        return (StatusCode::BAD_REQUEST, Json(json!({ "erreur": "donnees chiffrees invalides" }))).into_response();
    }
    // Tâche à part : même si l'appareil coupe la connexion, l'enregistrement va jusqu'au bout
    // (sinon le disque et la mémoire du serveur pourraient ne plus être d'accord).
    tokio::spawn(enregistrer(app, demande))
        .await
        .unwrap_or_else(|_| (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({ "erreur": "erreur interne" }))).into_response())
}

async fn enregistrer(app: Arc<App>, demande: Ecriture) -> Response {
    let mut etat = app.etat.lock().await;
    // Quelqu'un a écrit entre-temps : l'appli doit d'abord récupérer et fusionner.
    if demande.version_precedente != etat.version {
        return (StatusCode::CONFLICT, Json(json!({ "version": etat.version }))).into_response();
    }
    let nouveau =
        Etat { version: etat.version + 1, blob: Some(demande.blob), enregistre_le: Some(chrono::Utc::now().to_rfc3339()) };
    let app_disque = app.clone();
    let a_enregistrer = nouveau.clone();
    let resultat = tokio::task::spawn_blocking(move || {
        let contenu = app_disque.stockage.enregistrer(&a_enregistrer)?;
        // Historique et copie de secours : un échec est noté mais n'annule pas l'enregistrement.
        if let Err(e) = app_disque.stockage.historiser(a_enregistrer.version, &contenu) {
            app_disque.journal.ecrire(&format!("Historique impossible : {e}"));
        }
        if let Err(e) = app_disque.stockage.recopier(&contenu) {
            app_disque.journal.ecrire(&format!("Copie de secours impossible : {e}"));
        }
        io::Result::Ok(())
    })
    .await;
    match resultat {
        Ok(Ok(())) => {
            *etat = nouveau;
            Json(json!({ "version": etat.version })).into_response()
        }
        Ok(Err(e)) => {
            app.journal.ecrire(&format!("Enregistrement impossible : {e}"));
            (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({ "erreur": "enregistrement impossible" }))).into_response()
        }
        Err(_) => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({ "erreur": "erreur interne" }))).into_response(),
    }
}
