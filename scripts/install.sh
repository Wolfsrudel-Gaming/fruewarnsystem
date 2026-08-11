#!/bin/bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { echo -e "${GREEN}[FWS]${NC} $*"; }
warn()  { echo -e "${YELLOW}[FWS]${NC} $*"; }
error() { echo -e "${RED}[FWS]${NC} $*" >&2; }
header(){ echo -e "\n${BLUE}━━━ $* ━━━${NC}\n"; }

header "DRK Troisdorf Frühwarnsystem - Installation"

# Check prerequisites
header "Prüfe Voraussetzungen"

if ! command -v docker &> /dev/null; then
    error "Docker ist nicht installiert!"
    log "Installiere Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    log "Docker installiert"
fi

if ! docker compose version &> /dev/null; then
    error "Docker Compose Plugin ist nicht installiert!"
    exit 1
fi

if ! command -v git &> /dev/null; then
    apt-get update && apt-get install -y git
fi

log "Docker $(docker --version | cut -d' ' -f3)"
log "Docker Compose $(docker compose version --short)"
log "Git $(git --version | cut -d' ' -f3)"

# Setup .env
header "Konfiguration"

if [ ! -f .env ]; then
    cp .env.example .env
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/HIER_SICHEREN_KEY_GENERIEREN/$SECRET_KEY/" .env
    warn "Die Datei .env wurde erstellt. Bitte passe die Werte an:"
    warn "  - FWS_ADMIN_PASSWORD"
    warn "  - FWS_TELEGRAM_BOT_TOKEN (optional)"
    warn "  - FWS_NTFY_TOPIC (optional)"
    echo ""
    read -p "Möchtest du die .env jetzt bearbeiten? [j/N] " edit_env
    if [[ "$edit_env" =~ ^[jJyY]$ ]]; then
        ${EDITOR:-nano} .env
    fi
else
    log ".env existiert bereits"
fi

# Build & Start
header "Baue Container"
docker compose build --parallel

header "Starte Services"
docker compose up -d

# Wait for health
log "Warte auf Service-Start..."
sleep 15

MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8000/api/system/health > /dev/null 2>&1; then
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
done

if curl -sf http://localhost:8000/api/system/health > /dev/null 2>&1; then
    log "Backend ist bereit"
else
    warn "Backend antwortet noch nicht, startet möglicherweise noch..."
fi

# Pull Ollama model
header "Lade LLM-Modell"
OLLAMA_MODEL=$(grep FWS_OLLAMA_MODEL .env | cut -d= -f2)
OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.1:8b}
log "Lade Ollama-Modell: $OLLAMA_MODEL (kann einige Minuten dauern)..."
docker exec fws-ollama ollama pull "$OLLAMA_MODEL" || warn "Ollama-Modell konnte nicht geladen werden, wird beim ersten Start nachgeladen"

# Setup auto-update systemd timer (as backup)
header "Richte Auto-Update ein"
log "Auto-Update Container läuft bereits in Docker"
log "Prüfintervall: alle 30 Minuten"

# Summary
header "Installation abgeschlossen!"
echo ""
log "Services:"
echo "  Dashboard:      http://localhost:3000"
echo "  API:            http://localhost:8000"
echo "  API Docs:       http://localhost:8000/docs"
echo "  Prometheus:     http://localhost:9090"
echo "  Grafana:        http://localhost:3001"
echo "  Uptime Kuma:    http://localhost:3002"
echo ""
log "Nächste Schritte:"
echo "  1. .env anpassen (falls noch nicht geschehen)"
echo "  2. Telegram Bot Token eintragen für Benachrichtigungen"
echo "  3. Nginx für HTTPS konfigurieren (empfohlen)"
echo "  4. Uptime Kuma unter :3002 einrichten"
echo ""
log "Auto-Update ist AKTIV - das System hält sich automatisch aktuell."
echo ""
