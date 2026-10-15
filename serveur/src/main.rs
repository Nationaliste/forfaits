//! forfaits-serveur : petit serveur de synchronisation des forfaits (voir lib.rs).
//!
//!   forfaits-serveur configurer   choisir le mot de passe d'équipe et le code responsable
//!   forfaits-serveur              démarrer le serveur (127.0.0.1 seulement)

use std::io::{self, BufRead};
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::{env, fs};

use base64::Engine;
use base64::engine::general_purpose::STANDARD as B64;
use forfaits_serveur::{App, Config, ITERATIONS, Stockage, empreinte, jeton, routeur};

const AIDE: &str = "\
forfaits-serveur : synchronisation des forfaits (données chiffrées par l'appli)

Utilisation :
  forfaits-serveur configurer [options]   choisir le mot de passe d'équipe et le code responsable
  forfaits-serveur [servir] [options]     démarrer le serveur

Options :
  --dossier <chemin>   dossier des données (par défaut : %LOCALAPPDATA%\\Forfaits-serveur)
  --port <numéro>      port local (configurer ; par défaut 8787)
  --origine <adresse>  site autorisé (configurer ; répétable ; par défaut https://nationaliste.github.io)
  --copie <chemin>     recopier chaque version dans ce dossier, ex. OneDrive (configurer)
  --stdin              lire les mots de passe sur l'entrée standard (tests)";

const ORIGINE_PAR_DEFAUT: &str = "https://nationaliste.github.io";
const PORT_PAR_DEFAUT: u16 = 8787;
const LONGUEUR_MIN: usize = 12;

struct Options {
    commande: String,
    dossier: PathBuf,
    port: Option<u16>,
    origines: Vec<String>,
    copie: Option<PathBuf>,
    depuis_stdin: bool,
}

fn main() -> ExitCode {
    let options = match lire_options() {
        Ok(Some(o)) => o,
        Ok(None) => {
            println!("{AIDE}");
            return ExitCode::SUCCESS;
        }
        Err(message) => {
            eprintln!("Erreur : {message}\n\n{AIDE}");
            return ExitCode::from(2);
        }
    };
    let resultat = match options.commande.as_str() {
        "servir" => servir(&options.dossier),
        "configurer" => configurer(&options),
        autre => Err(format!("commande inconnue : {autre}")),
    };
    match resultat {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("Erreur : {message}");
            ExitCode::FAILURE
        }
    }
}

fn lire_options() -> Result<Option<Options>, String> {
    let mut args = env::args().skip(1);
    let mut options = Options {
        commande: String::new(),
        dossier: env::var_os("LOCALAPPDATA").map(PathBuf::from).unwrap_or_else(|| PathBuf::from(".")).join("Forfaits-serveur"),
        port: None,
        origines: Vec::new(),
        copie: None,
        depuis_stdin: false,
    };
    while let Some(arg) = args.next() {
        let mut valeur = |nom: &str| args.next().ok_or_else(|| format!("{nom} attend une valeur"));
        match arg.as_str() {
            "-h" | "--aide" | "aide" => return Ok(None),
            "--dossier" => options.dossier = PathBuf::from(valeur("--dossier")?),
            "--port" => options.port = Some(valeur("--port")?.parse().map_err(|_| "port invalide")?),
            "--origine" => options.origines.push(valeur("--origine")?),
            "--copie" => options.copie = Some(PathBuf::from(valeur("--copie")?)),
            "--stdin" => options.depuis_stdin = true,
            autre if options.commande.is_empty() && !autre.starts_with('-') => options.commande = autre.to_owned(),
            autre => return Err(format!("argument inconnu : {autre}")),
        }
    }
    if options.commande.is_empty() {
        options.commande = "servir".into();
    }
    Ok(Some(options))
}

fn servir(dossier: &Path) -> Result<(), String> {
    let config = Config::lire(dossier).map_err(|e| {
        format!("pas de configuration dans {} ({e}). Lance d'abord : forfaits-serveur configurer", dossier.display())
    })?;
    let app = App::avec_config(dossier, &config).map_err(|e| e.to_string())?;
    if garder_eveille() {
        app.journal.ecrire("Mise en veille automatique bloquée tant que le serveur tourne");
    }
    let execution = tokio::runtime::Runtime::new().map_err(|e| e.to_string())?;
    execution.block_on(async move {
        // 127.0.0.1 seulement : le serveur n'est pas visible sur le réseau du magasin.
        let adresse = SocketAddr::from(([127, 0, 0, 1], config.port));
        let ecoute = tokio::net::TcpListener::bind(adresse)
            .await
            .map_err(|e| format!("port {} indisponible ({e}) : le serveur tourne peut-être déjà", config.port))?;
        app.journal.ecrire(&format!("Démarrage sur http://{adresse}"));
        println!("Serveur prêt sur http://{adresse} (Ctrl+C pour arrêter)");
        axum::serve(ecoute, routeur(app.clone()))
            .with_graceful_shutdown(async {
                let _ = tokio::signal::ctrl_c().await;
            })
            .await
            .map_err(|e| e.to_string())?;
        app.journal.ecrire("Arrêt");
        Ok(())
    })
}

/// Empêche Windows de mettre le PC en veille par inactivité tant que le serveur tourne
/// (un PC en veille ne répond plus). Fermer le clavier ou appuyer sur le bouton reste possible.
#[cfg(windows)]
fn garder_eveille() -> bool {
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn SetThreadExecutionState(drapeaux: u32) -> u32;
    }
    const ES_CONTINUOUS: u32 = 0x8000_0000;
    const ES_SYSTEM_REQUIRED: u32 = 0x0000_0001;
    // Vaut pour le fil d'exécution appelant : ici le fil principal, qui vit jusqu'à l'arrêt du serveur.
    unsafe { SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) != 0 }
}

#[cfg(not(windows))]
fn garder_eveille() -> bool {
    false
}

fn configurer(options: &Options) -> Result<(), String> {
    fs::create_dir_all(&options.dossier).map_err(|e| format!("dossier {} : {e}", options.dossier.display()))?;
    let ancienne = Config::lire(&options.dossier).ok();
    // Un serveur en marche garderait les anciens mots de passe en mémoire et mélangerait les deux clés.
    if let Some(port) = ancienne.as_ref().map(|c| c.port)
        && std::net::TcpListener::bind(("127.0.0.1", port)).is_err()
    {
        return Err(format!(
            "le serveur tourne encore (port {port}). Arrête-le d'abord : taskkill /im forfaits-serveur.exe /f\n\
             puis relance cette commande. La tâche planifiée le redémarrera ensuite dans les 5 minutes."
        ));
    }
    if ancienne.is_some() {
        println!(
            "Une configuration existe déjà. Les données actuelles seront archivées (chiffrées avec l'ancien mot de passe) ;\n\
             l'appli d'un responsable renverra les siennes à sa prochaine synchronisation, et chaque appareil devra se reconnecter."
        );
    }
    let mut lignes = io::stdin().lock().lines();
    let mut demander = |invite: &str| -> Result<String, String> {
        if options.depuis_stdin {
            lignes.next().ok_or("entrée terminée trop tôt")?.map_err(|e| e.to_string())
        } else {
            rpassword::prompt_password(format!("{invite} : ")).map_err(|e| e.to_string())
        }
    };
    let mut secret = |nom: &str| -> Result<String, String> {
        let valeur = demander(&format!("{nom} ({LONGUEUR_MIN} caractères minimum)"))?;
        if valeur.chars().count() < LONGUEUR_MIN {
            return Err(format!("{nom} trop court : {LONGUEUR_MIN} caractères minimum (une phrase, c'est très bien)"));
        }
        if demander(&format!("{nom}, encore une fois"))? != valeur {
            return Err(format!("{nom} : les deux saisies sont différentes"));
        }
        Ok(valeur)
    };
    let equipe = secret("Mot de passe d'équipe")?;
    let responsable = secret("Code responsable")?;
    if equipe == responsable {
        return Err("le code responsable doit être différent du mot de passe d'équipe".into());
    }

    let mut sel = [0u8; 16];
    getrandom::fill(&mut sel).map_err(|e| format!("tirage aléatoire impossible : {e}"))?;
    println!("Calcul des clés…");
    let config = Config {
        port: options.port.or(ancienne.as_ref().map(|c| c.port)).unwrap_or(PORT_PAR_DEFAUT),
        origines: if !options.origines.is_empty() {
            options.origines.clone()
        } else {
            ancienne.as_ref().map(|c| c.origines.clone()).unwrap_or_else(|| vec![ORIGINE_PAR_DEFAUT.into()])
        },
        sel: B64.encode(sel),
        iterations: ITERATIONS,
        empreinte_lecture: empreinte(&jeton(&equipe, &sel, ITERATIONS, "lecture")),
        empreinte_ecriture: empreinte(&jeton(&responsable, &sel, ITERATIONS, "ecriture")),
        dossier_copie: options.copie.clone().or(ancienne.as_ref().and_then(|c| c.dossier_copie.clone())),
    };
    if ancienne.is_some() {
        Stockage::new(&options.dossier, None).archiver().map_err(|e| format!("archivage impossible : {e}"))?;
    }
    config.ecrire(&options.dossier).map_err(|e| format!("écriture de la configuration impossible : {e}"))?;
    println!("Configuration enregistrée dans {}", Config::chemin(&options.dossier).display());
    println!("Port local : {} · sites autorisés : {}", config.port, config.origines.join(", "));
    Ok(())
}
