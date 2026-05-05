#!/usr/bin/env bash
# Apply pending database migrations using yoyo.
#
# Reads connection settings from the project .env file (DB_HOST, DB_PORT,
# DB_NAME, DB_USER, DB_PASSWORD) and runs `yoyo apply` non-interactively.
# Intended to be called from systemd (ExecStartPre) or manually before
# starting the API service.
#
# Usage:
#   ./scripts/migrate.sh           # apply pending migrations
#   ./scripts/migrate.sh list      # show migration state
#   ./scripts/migrate.sh rollback  # roll back the most recent migration

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"
MIGRATIONS_DIR="${PROJECT_ROOT}/migrations"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: .env file not found at ${ENV_FILE}" >&2
    exit 1
fi

# shellcheck disable=SC1090
set -a
source "${ENV_FILE}"
set +a

: "${DB_HOST:?DB_HOST not set in .env}"
: "${DB_PORT:?DB_PORT not set in .env}"
: "${DB_NAME:?DB_NAME not set in .env}"
: "${DB_USER:?DB_USER not set in .env}"
: "${DB_PASSWORD:?DB_PASSWORD not set in .env}"

# urlencode the password so special characters (@%!) survive the URL
DB_PASSWORD_ENC="$(python3 -c 'import os, urllib.parse; print(urllib.parse.quote(os.environ["DB_PASSWORD"], safe=""))')"
DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD_ENC}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

CMD="${1:-apply}"

case "${CMD}" in
    apply)
        yoyo apply --batch --database "${DATABASE_URL}" "${MIGRATIONS_DIR}"
        ;;
    list)
        yoyo list --database "${DATABASE_URL}" "${MIGRATIONS_DIR}"
        ;;
    rollback)
        yoyo rollback --batch --database "${DATABASE_URL}" "${MIGRATIONS_DIR}"
        ;;
    mark)
        # Register all current migrations as applied without executing them.
        # Used once on existing databases to adopt yoyo without re-running
        # the baseline.
        yoyo mark --batch --database "${DATABASE_URL}" "${MIGRATIONS_DIR}"
        ;;
    *)
        echo "Usage: $0 [apply|list|rollback|mark]" >&2
        exit 2
        ;;
esac
