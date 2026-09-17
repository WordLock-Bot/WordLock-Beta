#!/bin/sh
# tunnel-watcher: erkennt die aktuelle trycloudflare-URL aus den cloudflared-Logs
# und pusht sie als config/instance-url.json ins Git-Repo. Eine GitHub Action
# deployed das Dashboard anschliessend automatisch neu.

set -e

LOG="/tunnel-log/tunnel.log"
REPO_DIR="/repo"
BRANCH="${REPO_BRANCH:-main}"
INTERVAL="${INTERVAL:-15}"
FILE="${REPO_FILE:-config/instance-url.json}"

: "${REPO_URL:?REPO_URL is required (e.g. https://github.com/user/repo.git)}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"

GIT_USER_NAME="${GIT_USER_NAME:-wordlock-tunnel-watcher}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-tunnel-watcher@users.noreply.github.com}"

AUTH_URL="https://x-access-token:${GITHUB_TOKEN}@${REPO_URL#https://}"

log() { echo "[watcher] $*"; }

get_url() {
    [ -f "$LOG" ] || return 1
    grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | tail -n 1
}

clone_or_pull() {
    if [ ! -d "$REPO_DIR/.git" ]; then
        log "Cloning repository ..."
        rm -rf "$REPO_DIR"
        git clone --depth 1 --branch "$BRANCH" "$AUTH_URL" "$REPO_DIR"
    else
        git -C "$REPO_DIR" remote set-url origin "$AUTH_URL"
        log "Pulling latest changes ..."
        git -C "$REPO_DIR" pull --ff-only origin "$BRANCH" || true
    fi
}

push_url() {
    local url="$1"
    clone_or_pull
    local payload
    payload="{\"url\":\"$url\"}"
    if [ -f "$REPO_DIR/$FILE" ] && [ "$(cat "$REPO_DIR/$FILE")" = "$payload" ]; then
        log "URL unchanged in repo, nothing to do."
        return
    fi
    cd "$REPO_DIR"
    git config user.name "$GIT_USER_NAME"
    git config user.email "$GIT_USER_EMAIL"
    mkdir -p "$(dirname "$FILE")"
    printf '%s\n' "$payload" > "$FILE"
    git add "$FILE"
    git commit -m "chore: tunnel URL -> $url" || { log "Nothing to commit"; return; }
    log "Pushing tunnel URL to $BRANCH ..."
    git push origin "$BRANCH"
    log "Done."
}

last=""
while :; do
    url=$(get_url || true)
    if [ -n "$url" ] && [ "$url" != "$last" ]; then
        log "Detected tunnel URL: $url"
        last="$url"
        if push_url "$url"; then
            log "Pushed."
        fi
    fi
    sleep "$INTERVAL"
done
