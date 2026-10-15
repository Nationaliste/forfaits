<#
  Installe (ou met à jour) le serveur des forfaits sur ce PC.

  1. Compile le serveur (Rust) et le copie dans %LOCALAPPDATA%\Forfaits-serveur.
  2. La première fois : demande le mot de passe d'équipe et le code responsable.
  3. Crée la tâche planifiée « Forfaits serveur » : elle démarre le serveur avec Windows,
     même sans session ouverte, et le relance s'il s'arrête.
     Cette étape demande l'autorisation administrateur (fenêtre Windows).

  Lancer depuis le dossier du projet :
    powershell -ExecutionPolicy Bypass -File serveur\installer.ps1
#>
param(
  [string]$Dossier = (Join-Path $env:LOCALAPPDATA 'Forfaits-serveur'),
  [switch]$SansTache,          # essais : installe sans créer la tâche planifiée
  [string]$EnregistrerTache    # usage interne : étape relancée en administrateur
)
$ErrorActionPreference = 'Stop'
$NomTache = 'Forfaits serveur'
$Exe = Join-Path $Dossier 'forfaits-serveur.exe'

# ---- Étape administrateur (relancée par l'étape normale, voir plus bas)
if ($EnregistrerTache) {
  $action = New-ScheduledTaskAction -Execute $Exe -Argument "--dossier `"$Dossier`"" -WorkingDirectory $Dossier
  $auDemarrage = New-ScheduledTaskTrigger -AtStartup
  # Toutes les 5 minutes : relance le serveur s'il s'est arrêté (jamais deux à la fois).
  $surveillance = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
  # S4U : tourne sans session ouverte, sans mot de passe enregistré ; Limited : sans droits administrateur.
  $principal = New-ScheduledTaskPrincipal -UserId $EnregistrerTache -LogonType S4U -RunLevel Limited
  $reglages = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName $NomTache -Action $action -Trigger @($auDemarrage, $surveillance) `
    -Principal $principal -Settings $reglages -Force | Out-Null
  Start-ScheduledTask -TaskName $NomTache
  exit 0
}

# ---- 1. Compilation (hors de OneDrive : des milliers de fichiers temporaires)
$cargo = (Get-Command cargo -ErrorAction SilentlyContinue).Source
if (-not $cargo) { $cargo = Join-Path $env:USERPROFILE '.cargo\bin\cargo.exe' }
if (-not (Test-Path $cargo)) { throw "Rust n'est pas installé (cargo introuvable)." }
$env:CARGO_TARGET_DIR = Join-Path $env:LOCALAPPDATA 'forfaits-cargo-target'
Write-Host 'Compilation du serveur…'
& $cargo build --release --quiet --manifest-path (Join-Path $PSScriptRoot 'Cargo.toml')
if ($LASTEXITCODE) { throw 'La compilation a échoué.' }

# ---- 2. Arrêt de l'ancienne version, puis copie
New-Item -ItemType Directory -Force $Dossier | Out-Null
Stop-ScheduledTask -TaskName $NomTache -ErrorAction SilentlyContinue
Get-Process forfaits-serveur -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $Exe } | Stop-Process -Force
Start-Sleep -Milliseconds 500
Copy-Item (Join-Path $env:CARGO_TARGET_DIR 'release\forfaits-serveur.exe') $Exe -Force

# ---- 3. Mots de passe (première fois seulement ; pour les changer : forfaits-serveur.exe configurer)
if (-not (Test-Path (Join-Path $Dossier 'config.json'))) {
  Write-Host ''
  Write-Host "Choisis le MOT DE PASSE D'ÉQUIPE (donné à tout le comptoir) puis le CODE RESPONSABLE (1 ou 2 personnes)."
  Write-Host 'Une phrase fait un bon mot de passe. Rien ne s’affiche pendant la frappe : c’est normal.'
  & $Exe configurer --dossier $Dossier
  if ($LASTEXITCODE) { throw 'Configuration annulée : relance le script.' }
}
if ($SansTache) { Write-Host "Installé dans $Dossier (sans tâche planifiée)."; exit 0 }

# ---- 4. Tâche planifiée (autorisation administrateur)
Write-Host ''
Write-Host "Windows va demander l'autorisation administrateur : elle sert seulement à créer la tâche"
Write-Host "qui démarre le serveur avec Windows (le serveur lui-même tourne SANS droits administrateur)."
$hote = (Get-Process -Id $PID).Path
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Dossier `"$Dossier`" -EnregistrerTache `"$env:USERDOMAIN\$env:USERNAME`""
$admin = Start-Process $hote -Verb RunAs -Wait -PassThru -ArgumentList $arguments
if ($admin.ExitCode) { throw "La tâche planifiée n'a pas été créée (code $($admin.ExitCode))." }

# ---- 5. Vérification
$port = (Get-Content (Join-Path $Dossier 'config.json') -Raw | ConvertFrom-Json).port
for ($i = 0; $i -lt 20; $i++) {
  try {
    Invoke-RestMethod "http://127.0.0.1:$port/api/sel" -TimeoutSec 2 | Out-Null
    Write-Host "Serveur en marche sur http://127.0.0.1:$port (seulement sur ce PC)." -ForegroundColor Green
    Write-Host "Étape suivante : Tailscale Funnel vers le port $port."
    exit 0
  } catch { Start-Sleep -Milliseconds 500 }
}
Write-Host "Le serveur ne répond pas : regarde $Dossier\serveur.log" -ForegroundColor Red
exit 1
