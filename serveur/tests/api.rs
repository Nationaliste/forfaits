//! Tests de l'API : accès, conflits, persistance, limites et en-têtes.

use std::path::Path;
use std::sync::Arc;

use axum::Router;
use axum::body::Body;
use axum::http::{Request, StatusCode, header};
use base64::Engine;
use base64::engine::general_purpose::STANDARD as B64;
use forfaits_serveur::{App, Config, Etat, Stockage, cle_maitre, deriver, empreinte, hex, jeton, routeur};
use http_body_util::BodyExt;
use serde_json::{Value, json};
use tower::ServiceExt;

// Peu de tours pour que les tests restent rapides (le serveur, lui, ne calcule jamais PBKDF2).
const TOURS: u32 = 1000;
const SEL: [u8; 16] = [7; 16];
const EQUIPE: &str = "EXEMPLE mot de passe equipe";
const RESPONSABLE: &str = "EXEMPLE code responsable";
const ORIGINE: &str = "https://nationaliste.github.io";

fn config() -> Config {
    Config {
        port: 0,
        origines: vec![ORIGINE.into()],
        sel: B64.encode(SEL),
        iterations: TOURS,
        empreinte_lecture: empreinte(&jeton(EQUIPE, &SEL, TOURS, "lecture")),
        empreinte_ecriture: empreinte(&jeton(RESPONSABLE, &SEL, TOURS, "ecriture")),
        dossier_copie: None,
    }
}

fn demarrer(dossier: &Path, config: &Config) -> Router {
    routeur(App::avec_config(dossier, config).expect("configuration valide"))
}

fn lecture() -> String {
    jeton(EQUIPE, &SEL, TOURS, "lecture")
}

fn ecriture() -> String {
    jeton(RESPONSABLE, &SEL, TOURS, "ecriture")
}

/// Donnée « chiffrée » factice : le serveur ne vérifie que la forme (base64, 28 octets minimum).
fn blob(graine: u8) -> String {
    B64.encode([graine; 64])
}

async fn appel(app: &Router, requete: Request<Body>) -> (StatusCode, axum::http::HeaderMap, Value) {
    let reponse = app.clone().oneshot(requete).await.expect("le routeur répond toujours");
    let statut = reponse.status();
    let entetes = reponse.headers().clone();
    let octets = reponse.into_body().collect().await.expect("corps lisible").to_bytes();
    let corps = serde_json::from_slice(&octets).unwrap_or(Value::Null);
    (statut, entetes, corps)
}

fn get(chemin: &str, jeton: Option<&str>) -> Request<Body> {
    let mut r = Request::get(chemin);
    if let Some(j) = jeton {
        r = r.header(header::AUTHORIZATION, format!("Bearer {j}"));
    }
    r.body(Body::empty()).unwrap()
}

fn put(jeton: &str, version_precedente: u64, blob: &str) -> Request<Body> {
    Request::put("/api/donnees")
        .header(header::AUTHORIZATION, format!("Bearer {jeton}"))
        .header(header::CONTENT_TYPE, "application/json")
        .body(Body::from(json!({ "version_precedente": version_precedente, "blob": blob }).to_string()))
        .unwrap()
}

#[test]
fn derivation_identique_a_webcrypto() {
    // Valeurs de référence calculées avec Python (hashlib.pbkdf2_hmac + HKDF RFC 5869),
    // les mêmes que celles de l'appli : si ce test casse, l'appli ne pourrait plus se connecter.
    let maitre = cle_maitre("EXEMPLE mot de passe équipe", &SEL, TOURS);
    assert_eq!(hex(&maitre), "6823efe801f68824f0396596caa359579acf1ceaea347e231ba5f2924969ea54");
    assert_eq!(hex(&deriver(&maitre, "lecture")), "af74d7fd1df7b207267d2376227a4e2a7a3337f193bb79b27f4775be6b34bce5");
    // Même mot de passe saisi avec un « é » décomposé (e + accent) : même clé grâce à NFC.
    assert_eq!(cle_maitre("EXEMPLE mot de passe e\u{301}quipe", &SEL, TOURS), maitre);
    assert_ne!(deriver(&maitre, "lecture"), deriver(&maitre, "chiffrement"));
}

#[tokio::test]
async fn sel_public() {
    let dossier = tempfile::tempdir().unwrap();
    let app = demarrer(dossier.path(), &config());
    let (statut, _, corps) = appel(&app, get("/api/sel", None)).await;
    assert_eq!(statut, StatusCode::OK);
    assert_eq!(corps, json!({ "sel": B64.encode(SEL), "iterations": TOURS }));
}

#[tokio::test]
async fn acces_refuse_sans_bon_jeton() {
    let dossier = tempfile::tempdir().unwrap();
    let app = demarrer(dossier.path(), &config());
    for requete in [
        get("/api/donnees", None),
        get("/api/donnees", Some("faux")),
        get("/api/donnees", Some(&jeton("mauvais mot de passe", &SEL, TOURS, "lecture"))),
        // Le code responsable ne sert qu'à écrire, le mot de passe d'équipe qu'à lire.
        get("/api/donnees", Some(&ecriture())),
        get("/api/acces-ecriture", Some(&lecture())),
        put(&lecture(), 0, &blob(1)),
    ] {
        let (statut, _, corps) = appel(&app, requete).await;
        assert_eq!(statut, StatusCode::UNAUTHORIZED);
        assert_eq!(corps, json!({ "erreur": "acces refuse" }));
    }
    let (statut, _, _) = appel(&app, get("/api/acces-ecriture", Some(&ecriture()))).await;
    assert_eq!(statut, StatusCode::NO_CONTENT);
}

#[tokio::test]
async fn ecriture_lecture_et_conflit() {
    let dossier = tempfile::tempdir().unwrap();
    let app = demarrer(dossier.path(), &config());

    let (statut, entetes, corps) = appel(&app, get("/api/donnees", Some(&lecture()))).await;
    assert_eq!(statut, StatusCode::OK);
    assert_eq!(corps["version"], 0);
    assert_eq!(corps["blob"], Value::Null);
    assert_eq!(entetes[header::ETAG], "\"0\"");

    let (statut, _, corps) = appel(&app, put(&ecriture(), 0, &blob(1))).await;
    assert_eq!(statut, StatusCode::OK);
    assert_eq!(corps, json!({ "version": 1 }));

    // Un 2e responsable qui n'a pas vu la version 1 : refus, il doit d'abord fusionner.
    let (statut, _, corps) = appel(&app, put(&ecriture(), 0, &blob(2))).await;
    assert_eq!(statut, StatusCode::CONFLICT);
    assert_eq!(corps, json!({ "version": 1 }));

    let (statut, entetes, corps) = appel(&app, get("/api/donnees", Some(&lecture()))).await;
    assert_eq!(statut, StatusCode::OK);
    assert_eq!(corps["version"], 1);
    assert_eq!(corps["blob"], blob(1));
    assert_eq!(entetes[header::ETAG], "\"1\"");

    // Rien de neuf : 304 sans corps, l'appli garde ce qu'elle a.
    let mut requete = get("/api/donnees", Some(&lecture()));
    requete.headers_mut().insert(header::IF_NONE_MATCH, "\"1\"".parse().unwrap());
    let (statut, _, corps) = appel(&app, requete).await;
    assert_eq!(statut, StatusCode::NOT_MODIFIED);
    assert_eq!(corps, Value::Null);
}

#[tokio::test]
async fn donnees_invalides_refusees() {
    let dossier = tempfile::tempdir().unwrap();
    let app = demarrer(dossier.path(), &config());
    for mauvais in ["pas du base64 !", &B64.encode([1u8; 27]), ""] {
        let (statut, _, _) = appel(&app, put(&ecriture(), 0, mauvais)).await;
        assert_eq!(statut, StatusCode::BAD_REQUEST, "{mauvais}");
    }
    let requete = Request::put("/api/donnees")
        .header(header::AUTHORIZATION, format!("Bearer {}", ecriture()))
        .body(Body::from("{pas du json"))
        .unwrap();
    assert_eq!(appel(&app, requete).await.0, StatusCode::BAD_REQUEST);

    let enorme = "A".repeat(forfaits_serveur::TAILLE_MAX_BLOB + 4096);
    assert_eq!(appel(&app, put(&ecriture(), 0, &enorme)).await.0, StatusCode::PAYLOAD_TOO_LARGE);

    let (_, _, corps) = appel(&app, get("/api/donnees", Some(&lecture()))).await;
    assert_eq!(corps["version"], 0, "rien n'a été enregistré");
}

#[tokio::test]
async fn donnees_gardees_apres_redemarrage_et_historique() {
    let dossier = tempfile::tempdir().unwrap();
    let copie = tempfile::tempdir().unwrap();
    let mut reglages = config();
    reglages.dossier_copie = Some(copie.path().join("Forfaits"));
    reglages.ecrire(dossier.path()).unwrap();
    let app = demarrer(dossier.path(), &reglages);
    for version in 0..3u8 {
        assert_eq!(appel(&app, put(&ecriture(), version.into(), &blob(version))).await.0, StatusCode::OK);
    }
    drop(app);

    let app = demarrer(dossier.path(), &reglages);
    let (_, _, corps) = appel(&app, get("/api/donnees", Some(&lecture()))).await;
    assert_eq!(corps["version"], 3);
    assert_eq!(corps["blob"], blob(2));

    let historique: Vec<_> = std::fs::read_dir(dossier.path().join("historique")).unwrap().collect();
    assert_eq!(historique.len(), 3);
    let recopie: Value =
        serde_json::from_str(&std::fs::read_to_string(copie.path().join("Forfaits/donnees.json")).unwrap()).unwrap();
    assert_eq!(recopie["version"], 3);

    // Rien en clair sur le disque : ni jeton, ni mot de passe.
    for fichier in ["config.json", "donnees.json", "serveur.log"] {
        let texte = std::fs::read_to_string(dossier.path().join(fichier)).unwrap();
        for secret in [EQUIPE, RESPONSABLE, &lecture(), &ecriture()] {
            assert!(!texte.contains(secret), "{fichier} contient un secret");
        }
    }
}

#[tokio::test]
async fn cors_seulement_pour_le_site() {
    let dossier = tempfile::tempdir().unwrap();
    let app = demarrer(dossier.path(), &config());
    let preflight = |origine: &str| {
        Request::options("/api/donnees")
            .header(header::ORIGIN, origine)
            .header(header::ACCESS_CONTROL_REQUEST_METHOD, "PUT")
            .header(header::ACCESS_CONTROL_REQUEST_HEADERS, "authorization,content-type")
            .body(Body::empty())
            .unwrap()
    };
    let (_, entetes, _) = appel(&app, preflight(ORIGINE)).await;
    assert_eq!(entetes[header::ACCESS_CONTROL_ALLOW_ORIGIN], ORIGINE);
    let (_, entetes, _) = appel(&app, preflight("https://site-pirate.example")).await;
    assert!(entetes.get(header::ACCESS_CONTROL_ALLOW_ORIGIN).is_none());

    // Même un refus (401) reste lisible par le site autorisé, pour afficher « mot de passe incorrect ».
    let mut requete = get("/api/donnees", Some("faux"));
    requete.headers_mut().insert(header::ORIGIN, ORIGINE.parse().unwrap());
    let (statut, entetes, _) = appel(&app, requete).await;
    assert_eq!(statut, StatusCode::UNAUTHORIZED);
    assert_eq!(entetes[header::ACCESS_CONTROL_ALLOW_ORIGIN], ORIGINE);
    assert_eq!(entetes[header::CACHE_CONTROL], "no-store");
    assert_eq!(entetes[header::X_CONTENT_TYPE_OPTIONS], "nosniff");
}

#[tokio::test]
async fn trop_de_requetes() {
    let dossier = tempfile::tempdir().unwrap();
    let app = demarrer(dossier.path(), &config());
    let mut refus = 0;
    for _ in 0..80 {
        if appel(&app, get("/api/sel", None)).await.0 == StatusCode::TOO_MANY_REQUESTS {
            refus += 1;
        }
    }
    assert!(refus >= 10, "seulement {refus} refus sur 80 appels en rafale");
    // Un inconnu qui inonde le serveur ne bloque pas les appareils qui ont le bon jeton.
    assert_eq!(appel(&app, get("/api/sel", None)).await.0, StatusCode::TOO_MANY_REQUESTS);
    assert_eq!(appel(&app, get("/api/donnees", Some(&lecture()))).await.0, StatusCode::OK);
    assert_eq!(appel(&app, put(&ecriture(), 0, &blob(1))).await.0, StatusCode::OK);
}

#[test]
fn reconfiguration_met_donnees_et_historique_de_cote() {
    let dossier = tempfile::tempdir().unwrap();
    let stockage = Stockage::new(dossier.path(), None);
    let etat = Etat { version: 1, blob: Some(blob(1)), enregistre_le: None };
    let contenu = stockage.enregistrer(&etat).unwrap();
    stockage.historiser(1, &contenu).unwrap();
    stockage.archiver().unwrap();
    assert_eq!(stockage.charger().unwrap(), Etat::default(), "le serveur repart de zéro");
    assert!(!dossier.path().join("historique").exists(), "l'ancien historique ne se mélange pas au nouveau");
    let archive = std::fs::read_dir(dossier.path())
        .unwrap()
        .filter_map(Result::ok)
        .find(|e| e.file_name().to_string_lossy().starts_with("archive-"));
    let archive = archive.expect("dossier archive-… créé").path();
    assert!(archive.join("donnees.json").exists() && archive.join("historique/v00000001.json").exists());
}

#[test]
fn config_abimee_refusee() {
    let dossier = tempfile::tempdir().unwrap();
    let mut reglages = config();
    reglages.empreinte_lecture = "abc".into();
    assert!(App::avec_config(dossier.path(), &reglages).is_err());
    reglages.ecrire(dossier.path()).unwrap();
    assert_eq!(Config::lire(dossier.path()).unwrap().empreinte_lecture, "abc");
    let _: Arc<App> = App::avec_config(dossier.path(), &config()).unwrap();
}
