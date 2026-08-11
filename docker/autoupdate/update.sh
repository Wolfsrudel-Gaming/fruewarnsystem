#!/bin/bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/repo}"
COMPOSE_FILE="${COMPOSE_FILE:-/repo/docker-compose.yml}"
UPDATE_BRANCH="${UPDATE_BRANCH:-main}"
CHECK_INTERVAL="${CHECK_INTERVAL:-1800}"
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
            "$NTFY_SERVER/$NTFY_TOPIC" || true
    fi
}

get_current_hash() {
    cd "$REPO_DIR" && git rev-parse HEAD 2>/dev/null || echo "unknown"
}

get_remote_hash() {
    cd "$REPO_DIR" && git rev-parse "origin/$UPDATE_BRANCH" 2>/dev/null || echo "unknown"
}

check_and_update() {
    cd "$REPO_DIR"
    local current_hash
    current_hash=$(get_current_hash)

    log "Checking for updates on branch '$UPDATE_BRANCH'..."
    if ! git fetch origin "$UPDATE_BRANCH" 2>&1; then
        log "ERROR: git fetch failed"
        return 1
    fi

    local remote_hash
    remote_hash=$(get_remote_hash)

    if [ "$current_hash" = "$remote_hash" ]; then
        log "System is up to date ($current_hash)"
        return 0
    fi

    local changes
    changes=$(git log --oneline "$current_hash..$remote_hash" 2>/dev/null || echo "")
    local change_count
    change_count=$(echo "$changes" | grep -c . || echo "0")

    log "Update available: ${current_hash:0:8} -> ${remote_hash:0:8} ($change_count commits)"
    log "Changes:"
    echo "$changes"

    notify "FWS Update verfügbar" \
        "Update: ${current_hash:0:8} → ${remote_hash:0:8}\n${change_count} neue Commits\n\nUpdate wird angewendet..." \
        "default"

    log "Pulling changes..."
    if ! git pull origin "$UPDATE_BRANCH" 2>&1; then
        log "ERROR: git pull failed"
        notify "FWS Update FEHLGESCHLAGEN" "Git pull fehlgeschlagen!" "high"
        git reset --hard "$current_hash"
        return 1
    fi

    log "Checking for dependency changes..."
    local needs_rebuild=false
    if git diff --name-only "$current_hash" "$remote_hash" | grep -qE "(requirements\.txt|package\.json|Dockerfile)"; then
        needs_rebuild=true
        log "Dependency changes detected, full rebuild required"
    fi

    log "Building updated containers..."
    if [ "$needs_rebuild" = true ]; then
        if ! docker compose -f "$COMPOSE_FILE" build --parallel 2>&1; then
            log "ERROR: Docker build failed"
            notify "FWS Update FEHLGESCHLAGEN" "Docker build fehlgeschlagen! Rollback..." "high"
            git reset --hard "$current_hash"
            return 1
        fi
    fi

    log "Restarting services..."
    if ! docker compose -f "$COMPOSE_FILE" up -d --remove-orphans 2>&1; then
        log "ERROR: Service restart failed"
        notify "FWS Update FEHLGESCHLAGEN" "Service-Neustart fehlgeschlagen!" "urgent"
        return 1
    fi

    sleep 30

    local health_ok=true
    if ! curl -sf http://fws-backend:8000/api/system/health > /dev/null 2>&1; then
        health_ok=false
    fi

    if [ "$health_ok" = true ]; then
        log "Update successful: ${current_hash:0:8} -> ${remote_hash:0:8}"
        notify "FWS Update ERFOLGREICH ✅" \
            "Update: ${current_hash:0:8} → ${remote_hash:0:8}\n${change_count} Commits angewendet\nAlle Services gesund" \
            "default"
    else
        log "WARNING: Health check failed after update, but keeping new version"
        notify "FWS Update angewendet ⚠️" \
            "Update: ${current_hash:0:8} → ${remote_hash:0:8}\nHealth-Check fehlgeschlagen!\nBitte manuell prüfen." \
            "high"
    fi
}

log "=== DRK Frühwarnsystem Auto-Updater ==="
log "Repository: $REPO_DIR"
log "Branch: $UPDATE_BRANCH"
log "Check interval: ${CHECK_INTERVAL}s"
log "Notifications: ${NTFY_TOPIC:-disabled}"

sleep 60

while true; do
    if ! check_and_update; then
        log "Update check encountered an error"
    fi
    log "Next check in ${CHECK_INTERVAL}s"
    sleep "$CHECK_INTERVAL"
done
