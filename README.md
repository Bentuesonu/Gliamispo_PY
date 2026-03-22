# Gliamispo

Software di produzione cinematografica per breakdown di sceneggiature, scheduling e gestione produzione.

## Requisiti

- Python 3.13+
- macOS 12+ (per build native)
- Xcode Command Line Tools (per build e notarizzazione)

## Installazione per sviluppo

```bash
# Clone del repository
git clone https://github.com/your-org/gliamispo.git
cd gliamispo

# Crea virtual environment
python -m venv .venv
source .venv/bin/activate

# Installa dipendenze
pip install -e ".[dev]"

# Scarica modelli spaCy
python -m spacy download it_core_news_lg
python -m spacy download en_core_web_sm

# Avvia applicazione
python -m gliamispo
```

## Build & Distribuzione macOS

### Prerequisiti

1. **Xcode Command Line Tools**
   ```bash
   xcode-select --install
   ```

2. **Certificato Developer ID** da [Apple Developer Portal](https://developer.apple.com/account/resources/certificates/list):
   - Accedi con il tuo Apple ID iscritto al Developer Program ($99/anno)
   - Vai su Certificates, Identifiers & Profiles → Certificates
   - Crea un nuovo certificato "Developer ID Application"
   - Scarica e installa il certificato nel Keychain

3. **App-Specific Password**:
   - Vai su [appleid.apple.com](https://appleid.apple.com)
   - Sign-In & Security → App-Specific Passwords
   - Genera una nuova password (es. "gliamispo-notarize")
   - Conserva la password in formato `xxxx-xxxx-xxxx-xxxx`

### Configurazione variabili d'ambiente

Lo script di notarizzazione richiede 4 variabili d'ambiente:

| Variabile | Descrizione | Esempio |
|-----------|-------------|---------|
| `APPLE_DEVELOPER_ID` | Nome completo del certificato | `Developer ID Application: Mario Rossi (ABC123DEF4)` |
| `APPLE_ID` | Email Apple ID | `mario.rossi@email.com` |
| `APPLE_APP_PASSWORD` | App-specific password | `abcd-efgh-ijkl-mnop` |
| `APPLE_TEAM_ID` | Team ID (10 caratteri) | `ABC123DEF4` |

Per trovare il nome esatto del certificato:
```bash
security find-identity -v -p codesigning
```

### Build locale

```bash
# 1. Attiva virtual environment
source .venv/bin/activate

# 2. Installa PyInstaller
pip install pyinstaller

# 3. Build applicazione
pyinstaller gliamispo.spec --clean --noconfirm

# 4. Verifica build
ls -la dist/Gliamispo.app

# 5. Firma e notarizza (richiede variabili d'ambiente)
export APPLE_DEVELOPER_ID="Developer ID Application: ..."
export APPLE_ID="tua@email.com"
export APPLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
export APPLE_TEAM_ID="XXXXXXXXXX"

bash scripts/notarize_mac.sh
```

Il DMG firmato e notarizzato sarà in `dist/Gliamispo.dmg`.

### Build automatica con GitHub Actions

Il workflow `.github/workflows/build_mac.yml` automatizza build e notarizzazione.

**Configurazione secrets in GitHub:**

1. Vai su Repository → Settings → Secrets and variables → Actions
2. Aggiungi i seguenti secrets:
   - `APPLE_DEVELOPER_ID`
   - `APPLE_ID`
   - `APPLE_APP_PASSWORD`
   - `APPLE_TEAM_ID`

**Trigger automatico:**
- Push di un tag `v*` (es. `v1.0.0`)

```bash
git tag v1.0.0
git push origin v1.0.0
```

**Trigger manuale:**
- Actions → Build macOS → Run workflow
- Opzione "Skip notarization" per test veloci

### Struttura file di build

```
scripts/
├── notarize_mac.sh      # Script firma + notarizzazione
└── entitlements.plist   # Entitlements per PyInstaller/Python

.github/workflows/
└── build_mac.yml        # GitHub Actions workflow

gliamispo.spec           # Configurazione PyInstaller
```

### Note tecniche

- **Entitlements**: Gli entitlements `allow-unsigned-executable-memory` e `disable-library-validation` sono necessari per PyInstaller + Python embedded. Senza di essi, l'app non si avvia su macOS con Gatekeeper attivo.

- **Firma ricorsiva**: Lo script firma prima tutte le `.dylib` e `.so` interne, poi i frameworks, e infine il bundle principale. Questo ordine è necessario per superare la validazione.

- **Timeout notarizzazione**: Il processo di notarizzazione Apple richiede tipicamente 2-5 minuti, ma può arrivare a 10 minuti in periodi di carico elevato.

## Test

```bash
pytest tests/ -v
```

## Licenza

Proprietario - Tutti i diritti riservati.
