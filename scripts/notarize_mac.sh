#!/bin/bash
# ============================================================================
# Gliamispo - macOS Code Signing & Notarization Script
# ============================================================================
# Firma e notarizza l'app per distribuzione fuori Mac App Store.
# Richiede Xcode Command Line Tools e un certificato Developer ID.
#
# Variabili d'ambiente richieste:
#   APPLE_DEVELOPER_ID    - es. "Developer ID Application: Nome Cognome (TEAMID)"
#   APPLE_ID              - email Apple ID
#   APPLE_APP_PASSWORD    - app-specific password (https://appleid.apple.com)
#   APPLE_TEAM_ID         - Team ID (10 caratteri)
# ============================================================================

set -euo pipefail

# ── Configurazione ──────────────────────────────────────────────────────────
APP="dist/Gliamispo.app"
DMG="dist/Gliamispo.dmg"
BUNDLE_ID="it.gliamispo.app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENTITLEMENTS="$SCRIPT_DIR/entitlements.plist"

# ── Verifica variabili d'ambiente ───────────────────────────────────────────
check_env() {
    local missing=()
    [[ -z "${APPLE_DEVELOPER_ID:-}" ]] && missing+=("APPLE_DEVELOPER_ID")
    [[ -z "${APPLE_ID:-}" ]] && missing+=("APPLE_ID")
    [[ -z "${APPLE_APP_PASSWORD:-}" ]] && missing+=("APPLE_APP_PASSWORD")
    [[ -z "${APPLE_TEAM_ID:-}" ]] && missing+=("APPLE_TEAM_ID")

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Errore: variabili d'ambiente mancanti:"
        printf '  - %s\n' "${missing[@]}"
        echo ""
        echo "Esempio di configurazione:"
        echo "  export APPLE_DEVELOPER_ID='Developer ID Application: Nome Cognome (TEAMID)'"
        echo "  export APPLE_ID='tua@email.com'"
        echo "  export APPLE_APP_PASSWORD='xxxx-xxxx-xxxx-xxxx'"
        echo "  export APPLE_TEAM_ID='XXXXXXXXXX'"
        exit 1
    fi
}

# ── Verifica prerequisiti ───────────────────────────────────────────────────
check_prerequisites() {
    echo "Verifica prerequisiti..."

    if [[ ! -d "$APP" ]]; then
        echo "Errore: $APP non trovato. Esegui prima PyInstaller."
        exit 1
    fi

    if [[ ! -f "$ENTITLEMENTS" ]]; then
        echo "Errore: $ENTITLEMENTS non trovato."
        exit 1
    fi

    if ! command -v codesign &>/dev/null; then
        echo "Errore: codesign non disponibile. Installa Xcode Command Line Tools."
        exit 1
    fi

    if ! command -v xcrun &>/dev/null; then
        echo "Errore: xcrun non disponibile. Installa Xcode Command Line Tools."
        exit 1
    fi

    echo "Prerequisiti OK"
}

# ── Step 1: Firma ricorsiva ─────────────────────────────────────────────────
sign_app() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "Step 1: Firma ricorsiva dell'applicazione"
    echo "═══════════════════════════════════════════════════════════════════"

    # Firma dylib e shared objects
    echo "Firmando librerie dinamiche..."
    find "$APP" -type f \( -name "*.dylib" -o -name "*.so" \) -print0 | while IFS= read -r -d '' lib; do
        echo "  → $(basename "$lib")"
        codesign \
            --force \
            --verify \
            --verbose \
            --sign "$APPLE_DEVELOPER_ID" \
            --options runtime \
            --timestamp \
            "$lib"
    done

    # Firma eseguibili interni (Python, etc.)
    echo "Firmando eseguibili interni..."
    find "$APP/Contents/MacOS" -type f -perm +111 -print0 2>/dev/null | while IFS= read -r -d '' exe; do
        echo "  → $(basename "$exe")"
        codesign \
            --force \
            --verify \
            --verbose \
            --sign "$APPLE_DEVELOPER_ID" \
            --options runtime \
            --timestamp \
            "$exe"
    done

    # Firma frameworks
    if [[ -d "$APP/Contents/Frameworks" ]]; then
        echo "Firmando frameworks..."
        find "$APP/Contents/Frameworks" -type d -name "*.framework" -print0 | while IFS= read -r -d '' fw; do
            echo "  → $(basename "$fw")"
            codesign \
                --force \
                --verify \
                --verbose \
                --sign "$APPLE_DEVELOPER_ID" \
                --options runtime \
                --timestamp \
                "$fw"
        done
    fi

    # Firma bundle principale
    echo "Firmando bundle principale con entitlements..."
    codesign \
        --force \
        --verify \
        --verbose \
        --sign "$APPLE_DEVELOPER_ID" \
        --options runtime \
        --timestamp \
        --entitlements "$ENTITLEMENTS" \
        "$APP"

    echo "Firma completata"
}

# ── Step 2: Verifica firma ──────────────────────────────────────────────────
verify_signature() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "Step 2: Verifica firma"
    echo "═══════════════════════════════════════════════════════════════════"

    echo "Verifica codesign..."
    codesign --verify --deep --strict --verbose=2 "$APP"

    echo ""
    echo "Verifica Gatekeeper..."
    if spctl --assess --verbose "$APP" 2>&1; then
        echo "Gatekeeper: OK"
    else
        echo "Avviso: spctl potrebbe fallire prima della notarizzazione"
    fi
}

# ── Step 3: Creazione DMG ───────────────────────────────────────────────────
create_dmg() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "Step 3: Creazione DMG"
    echo "═══════════════════════════════════════════════════════════════════"

    # Rimuovi DMG esistente
    [[ -f "$DMG" ]] && rm -f "$DMG"

    echo "Creando $DMG..."
    hdiutil create \
        -volname "Gliamispo" \
        -srcfolder "$APP" \
        -ov \
        -format UDZO \
        "$DMG"

    echo "Firmando DMG..."
    codesign \
        --sign "$APPLE_DEVELOPER_ID" \
        --timestamp \
        "$DMG"

    echo "DMG creato e firmato"
}

# ── Step 4: Notarizzazione ──────────────────────────────────────────────────
notarize() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "Step 4: Notarizzazione Apple"
    echo "═══════════════════════════════════════════════════════════════════"

    echo "Invio a Apple per notarizzazione..."
    echo "(Questo processo può richiedere alcuni minuti)"

    xcrun notarytool submit "$DMG" \
        --apple-id "$APPLE_ID" \
        --password "$APPLE_APP_PASSWORD" \
        --team-id "$APPLE_TEAM_ID" \
        --wait \
        --timeout 600
}

# ── Step 5: Staple ──────────────────────────────────────────────────────────
staple() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "Step 5: Stapling del ticket di notarizzazione"
    echo "═══════════════════════════════════════════════════════════════════"

    echo "Applicando staple al DMG..."
    xcrun stapler staple "$DMG"

    echo "Validando staple..."
    xcrun stapler validate "$DMG"
}

# ── Main ────────────────────────────────────────────────────────────────────
main() {
    echo "╔═══════════════════════════════════════════════════════════════════╗"
    echo "║        Gliamispo - macOS Notarization Script                      ║"
    echo "╚═══════════════════════════════════════════════════════════════════╝"
    echo ""

    check_env
    check_prerequisites
    sign_app
    verify_signature
    create_dmg
    notarize
    staple

    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════╗"
    echo "║  Notarizzazione completata con successo!                          ║"
    echo "╚═══════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "File distribuibile: $DMG"
    echo ""
}

main "$@"
