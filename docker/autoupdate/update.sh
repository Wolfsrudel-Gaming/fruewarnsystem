#!/bin/bash
set -uo pipefail

REPO_DIR="${REPO_DIR:-/repo}"
COMPOSE_FILE="${COMPOSE_FILE:-/repo/docker-compose.yml}"
UPDATE_BRANCH="${UPDATE_BRANCH:-main}"
CHECK_INTERVAL="${CHECK_INTERVAL:-60}"
NTFY_TOPIC="${NTFY_TOPIC:-}"
NTFY_SERVER="${NTFY_SERVER:-https://ntfy.sh}"
# KRITISCH: Ohne festen Projektnamen nimmt Compose den Ordnernamen (/repo -> "repo")
# und versucht neue Container zu erzeugen -> Name-Konflikt mit laufenden fws-* Containern.
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-fruewarnsystem}"
export COMPOSE_PROJECT_NAME

dc() {
    docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
}

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
        # Fallback: Host-Port falls Netzwerk-DNS im Moment nicht greift
        if curl -sf http://172.17.0.1:8010/api/system/health > /dev/null 2>&1; then
            return 0
        fi
        sleep 5
        waited=$((waited + 5))
    done
    return 1
}

# Lokale Commits nach GitHub pushen (Deploy-Key noetig)
push_local_commits() {
    local ahead
    ahead=$(git rev-list --count "origin/$UPDATE_BRANCH..HEAD" 2>/dev/null || echo 0)
    if [ "$ahead" -gt 0 ]; then
        if git push --quiet origin "HEAD:$UPDATE_BRANCH" 2>/dev/null; then
            log "$ahead lokale Commits nach GitHub gepusht"
            notify "FWS: Server-Commits gepusht" "$ahead lokale Commits nach GitHub uebertragen" "default"
        fi
    fi
}

apply_services() {
    local diff_files="$1"

    # Bestehende Stack-Services anwenden (kein neuer Projektname!)
    if ! dc --profile with-autoupdate up -d --remove-orphans 2>&1; then
        log "WARN: compose up fehlgeschlagen, versuche gezielte Restarts..."
    fi

    # Frontend: Code ist im Image -> immer neu deployen wenn frontend/ geaendert
    if echo "$diff_files" | grep -qE '^frontend/|^docker-compose\.yml'; then
        log "Frontend neu deployen..."
        dc up -d --no-deps --force-recreate frontend 2>&1 || true
    fi

    # Backend: Volume-Mount -> Restart reicht fuer Code; Image-Rebuild bei Dockerfile/requirements
    if echo "$diff_files" | grep -qE '^backend/|^docker-compose\.yml'; then
        log "Backend neu starten..."
        dc up -d --no-deps --force-recreate backend 2>&1 || dc restart backend 2>&1 || true
    fi

    if echo "$diff_files" | grep -q '^docker/nginx/'; then
        log "Nginx neu starten..."
        dc restart nginx 2>&1 || true
    fi
    if echo "$diff_files" | grep -q '^docker/prometheus/'; then
        dc restart prometheus 2>&1 || true
    fi
    if echo "$diff_files" | grep -q '^docker/mosquitto/'; then
        dc restart mqtt 2>&1 || true
    fi
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

    if git merge-base --is-ancestor "$remote_hash" "$current_hash" 2>/dev/null; then
        push_local_commits
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
        log "ERROR: git pull failed"
        notify "FWS Update FEHLGESCHLAGEN" \
            "Git pull fehlgeschlagen. Manuell pruefen: /opt/fruewarnsystem" "high"
        git merge --abort 2>/dev/null || true
        git reset --hard "$current_hash"
        return 1
    fi

    local new_hash
    new_hash=$(git rev-parse HEAD)
    local diff_files
    diff_files=$(git diff --name-only "$current_hash" "$new_hash")

    log "Building containers..."
    if ! dc build --parallel backend frontend 2>&1 | tail -8; then
        log "ERROR: Docker build failed, rolling back"
        notify "FWS Update FEHLGESCHLAGEN" "Docker build fehlgeschlagen! Rollback" "high"
        git reset --hard "$current_hash"
        return 1
    fi

    log "Applying services..."
    apply_services "$diff_files"

    if wait_for_backend; then
        log "Update successful: ${current_hash:0:8} -> ${new_hash:0:8}"
        notify "FWS Update ERFOLGREICH" \
            "${current_hash:0:8} -> ${new_hash:0:8}: ${change_count} Commits live" "default"
    else
        log "WARNING: Health check failed after update"
        notify "FWS Update angewendet, Health-Check FEHLGESCHLAGEN" \
            "${current_hash:0:8} -> ${new_hash:0:8}: Backend antwortet nicht" "high"
    fi

    if echo "$diff_files" | grep -q '^docker/autoupdate/'; then
        log "Updater selbst geaendert, ersetze fws-autoupdate..."
        dc --profile with-autoupdate build autoupdate 2>&1 | tail -3 || true
        dc --profile with-autoupdate up -d --no-deps --force-recreate autoupdate 2>&1 || true
    fi

    push_local_commits
}

log "=== DRK Fruehwarnsystem Auto-Updater ==="
log "Repository: $REPO_DIR"
log "Branch: $UPDATE_BRANCH"
log "Project: $COMPOSE_PROJECT_NAME"
log "Check interval: ${CHECK_INTERVAL}s"
log "Notifications: ${NTFY_TOPIC:-disabled}"

sleep 5

while true; do
    check_and_update || log "Update check encountered an error"
    sleep "$CHECK_INTERVAL"
done
