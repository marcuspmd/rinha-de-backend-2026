#!/usr/bin/env bash
set -euo pipefail

COMPOSE="docker-compose.local-test.yml"

cleanup() {
    echo "Parando stack..."
    docker compose -f "$COMPOSE" down --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Derrubando stack anterior..."
docker compose -f "$COMPOSE" down --remove-orphans 2>/dev/null || true

echo "==> Subindo backend + k6..."
docker compose -f "$COMPOSE" up --abort-on-container-exit --exit-code-from k6

echo ""
echo "==> Resultado em test/results-local.json"
cat test/results-local.json 2>/dev/null || true
