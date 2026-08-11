#!/bin/bash
set -uo pipefail

REPO_DIR="${REPO_DIR:-/repo}"
COMPOSE_FILE="${COMPOSE_FILE:-/repo/docker-compose.yml}"
UPDATE_BRANCH="${UPDATE_BRANCH:-main}"
CHECK_INTERVAL="${CHECK_INTERVAL:-60}"
NTFY_TOPIC="${NTFY_TOPIC:-}"
NTFY_SERVER="${NTFY_SERVER:-https://ntfy.sh}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

notify() {
    local title="$1"
    local message="$2"
    local priority="${3:-default}"

    if [ -n "$NTFY_TOPIC" ]; then
        curl -s \
            -H "Title: $title" \
            -H "Priority: $priority" \
            -H "Tags: gear" \
            -d "$message" \
            "$NTFY_SERVER/$NTFY_TOPIC" > /dev/null || true
    fi
}

wait_for_backend() {
    local waited=0
    while [ $waited -lt 90 ]; do
        if curl -sf http://fws-backend:8000/api/system/health > /dev/null 2>&1; then
            return 0
        fi
        sleep 5
        waited=$((waited + 5))
    done
    return 1
}

check_and_update() {
    cd "$REPO_DIR"
    local current_hash
    current_hash=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

    if ! git fetch origin "$UPDATE_BRANCH" --quiet 2>&1; then
        log "ERROR: git fetch failed"
        return 1
    fi

    local remote_hash
    remote_hash=$(git rev-parse "origin/$UPDATE_BRANCH" 2>/dev/null || echo "unknown")

    # Up to date, wenn alle Remote-Commits bereits enthalten sind
    # (lokale Deployment-Commits duerfen voraus sein)
    if git merge-base --is-ancestor "$remote_hash" "$current_hash" 2>/dev/null; then
        return 0
    fi

    local changes
    changes=$(git log --oneline "HEAD..origin/$UPDATE_BRANCH" 2>/dev/null || echo "")
    local change_count
    change_count=$(echo "$changes" | grep -c . || echo "0")

    log "Update available: ${current_hash:0:8} -> ${remote_hash:0:8} ($change_count commits)"
    echo "$changes"
    notify "FWS Update wird angewendet" \
        "${current_hash:0:8} -> ${remote_hash:0:8} ($change_count Commits)" "default"

    log "Pulling changes..."
    if ! git pull --no-edit origin "$UPDATE_BRANCH" 2>&1; then
        log "ERROR: git pull failed (Konflikt mit lokalen Deployment-Commits?)"
        notify "FWS Update FEHLGESCHLAGEN" \
            "Git pull fehlgeschlagen (Merge-Konflikt?). Manuell pruefen: /opt/fruewarnsystem" "high"
        git merge --abort 2>/dev/null || true
        git reset --hard "$current_hash"
        return 1
    fi

    local new_hash
    new_hash=$(git rev-parse HEAD)

    # Immer bauen: Docker-Cache macht das billig, wenn nichts Relevantes geaendert wurde.
    # Noetig, weil Frontend-Code in das Image eingebacken wird.
    log "Building containers..."
    if ! docker compose -f "$COMPOSE_FILE" build --parallel backend frontend 2>&1 | tail -5; then
        log "ERROR: Docker build failed, rolling back"
        notify "FWS Update FEHLGESCHLAGEN" "Docker build fehlgeschlagen! Rollback auf ${current_hash:0:8}" "high"
        git reset --hard "$current_hash"
        docker compose -f "$COMPOSE_FILE" build --parallel backend frontend 2>&1 | tail -3 || true
        return 1
    fi

    log "Applying services (up -d)..."
    if ! docker compose -f "$COMPOSE_FILE" up -d 2>&1; then
        log "ERROR: Service restart failed"
        notify "FWS Update FEHLGESCHLAGEN" "Service-Neustart fehlgeschlagen!" "urgent"
        return 1
    fi

    # Backend-Code ist als Volume gemountet: bei Aenderungen explizit neu starten
    local diff_files
    diff_files=$(git diff --name-only "$current_hash" "$new_hash")
    if echo "$diff_files" | grep -q '^backend/'; then
        log "Backend code changed, restarting backend..."
        docker compose -f "$COMPOSE_FILE" restart backend 2>&1 || true
    fi
    if echo "$diff_files" | grep -q '^docker/nginx/'; then
        log "Nginx config changed, restarting internal nginx..."
        docker compose -f "$COMPOSE_FILE" restart nginx 2>&1 || true
    fi
    if echo "$diff_files" | grep -q '^docker/prometheus/'; then
        docker compose -f "$COMPOSE_FILE" restart prometheus 2>&1 || true
    fi
    if echo "$diff_files" | grep -q '^docker/mosquitto/'; then
        docker compose -f "$COMPOSE_FILE" restart mqtt 2>&1 || true
    fi

    if wait_for_backend; then
        log "Update successful: ${current_hash:0:8} -> ${new_hash:0:8}"
        notify "FWS Update ERFOLGREICH" \
            "${current_hash:0:8} -> ${new_hash:0:8}: ${change_count} Commits angewendet, alle Services gesund" \
            "default"
    else
        log "WARNING: Health check failed after update, keeping new version"
        notify "FWS Update angewendet, Health-Check FEHLGESCHLAGEN" \
            "${current_hash:0:8} -> ${new_hash:0:8}: Backend antwortet nicht. Bitte manuell pruefen." \
            "high"
    fi

    # Zuletzt: eigenes Image aktualisieren, falls der Updater selbst geaendert wurde.
    # Recreate beendet dieses Skript - der neue Container uebernimmt.
    if echo "$diff_files" | grep -q '^docker/autoupdate/'; then
        log "Updater selbst geaendert, baue und ersetze fws-autoupdate..."
        docker compose -f "$COMPOSE_FILE" --profile with-autoupdate build autoupdate 2>&1 | tail -3 || true
        docker compose -f "$COMPOSE_FILE" --profile with-autoupdate up -d --no-deps autoupdate 2>&1 || true
    fi
}

log "=== DRK Fruehwarnsystem Auto-Updater ==="
log "Repository: $REPO_DIR"
log "Branch: $UPDATE_BRANCH"
log "Check interval: ${CHECK_INTERVAL}s"
log "Notifications: ${NTFY_TOPIC:-disabled}"

sleep 10

while true; do
    check_and_update || log "Update check encountered an error"
    sleep "$CHECK_INTERVAL"
done
