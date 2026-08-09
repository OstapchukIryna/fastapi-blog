#!/usr/bin/env bash
#
# Runs the Postman collection against a throwaway copy of the app.
#
# Targets the same throwaway database tests/conftest.py points pytest at
# (bloguser@localhost/test_blog) — one fixed name for every automated
# check in this project, not derived from whatever DATABASE_URL a
# developer's shell happens to have set. Its schema is dropped and
# rebuilt by `alembic upgrade head` — the collection creates whatever
# data it needs itself, so nothing seeds it beforehand.
#
# ! Do not run this alongside pytest: both point at the same database,
# ! and this script drops its schema outright.
#
#   ./scripts/api-tests.sh              # start a server, run, tear down
#   ./scripts/api-tests.sh --url URL    # run against something already up
#
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${PORT:-8765}"
BASE_URL=""
SERVER_PID=""
WORK_DIR=""

# core/config.py requires a secret and reads it from .env, which is not in the
# repository — so a fresh clone, and CI, have none and the app refuses to
# start. The run supplies its own: it signs tokens that live exactly as
# long as the server started below, and is overridden by a real SECRET_KEY
# if one is already set.
export SECRET_KEY="${SECRET_KEY:-throwaway-secret-for-the-api-test-run}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --url) BASE_URL="$2"; shift 2 ;;
        -h|--help) sed -n '3,16p' "$0" | sed -E 's/^#[[:space:]]?//'; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

cleanup() {
    # Killed before the temp directory goes, or the app writes into a
    # path that no longer exists on its way down.
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    [[ -n "$WORK_DIR" ]] && rm -rf "$WORK_DIR"
}
trap cleanup EXIT

if [[ -z "$BASE_URL" ]]; then
    WORK_DIR="$(mktemp -d)"
    BASE_URL="http://127.0.0.1:${PORT}"

    export DATABASE_URL="postgresql+psycopg://bloguser:blogpassword@localhost/test_blog"
    echo "==> resetting $(echo "$DATABASE_URL" | sed 's/:[^:@]*@/:***@/')"
    uv run python -c '
import os, psycopg
url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
conn = psycopg.connect(url, autocommit=True)
conn.execute("DROP SCHEMA public CASCADE")
conn.execute("CREATE SCHEMA public")
'
    echo "==> migrating"
    uv run alembic upgrade head >/dev/null

    echo "==> starting the app on ${BASE_URL}"
    uv run uvicorn blog.main:app --port "$PORT" --log-level warning >"${WORK_DIR}/server.log" 2>&1 &
    SERVER_PID=$!

    for _ in $(seq 1 60); do
        if curl -sf -o /dev/null "${BASE_URL}/api/posts"; then break; fi
        if ! kill -0 "$SERVER_PID" 2>/dev/null; then
            echo "the app exited before it answered:" >&2
            cat "${WORK_DIR}/server.log" >&2
            exit 1
        fi
        sleep 0.5
    done

    if ! curl -sf -o /dev/null "${BASE_URL}/api/posts"; then
        echo "the app never answered on ${BASE_URL}:" >&2
        cat "${WORK_DIR}/server.log" >&2
        exit 1
    fi
fi

# Postman keeps the collection as a tree of YAML — one file per request,
# which is what makes a changed test readable in review. Newman reads only
# the single-file v2.1 JSON, so it is built here rather than committed: a
# second copy in the repository would be a second thing to keep in step.
if [[ -z "$WORK_DIR" ]]; then
    WORK_DIR="$(mktemp -d)"   # --url was passed, so nothing made one yet
fi
COLLECTION="${WORK_DIR}/collection.json"

# One endpoint takes a file, and a file cannot live inside the
# collection. They are written next to the built JSON because Newman only
# reads files from its working directory, which is set to the same place.
echo "==> writing the upload fixtures"
uv run python -c "
import sys
from pathlib import Path
from PIL import Image
work = Path(sys.argv[1])
Image.new('RGB', (640, 480), (30, 120, 200)).save(work / 'picture.png')
(work / 'not-an-image.jpg').write_bytes(b'a name ending in .jpg proves nothing')
" "$WORK_DIR"

echo "==> building the collection from postman/collections"
uv run python scripts/build_postman_collection.py "$COLLECTION"

echo "==> running the collection against ${BASE_URL}"
set +e
npx --yes newman@6 run "$COLLECTION" \
    --working-dir "$WORK_DIR" \
    --env-var "baseUrl=${BASE_URL}" \
    --env-var "jwtSecret=${SECRET_KEY}" \
    --env-var "pictureFile=picture.png" \
    --env-var "notAnImageFile=not-an-image.jpg" \
    --reporters cli \
    --color auto \
    "$@"
NEWMAN_EXIT=$?
set -e

# A failing request only says "500" — the traceback that explains it went
# to the server's own log, not Newman's. Surfaced here rather than left
# for someone to reproduce locally, since the log this app started
# writing to no longer exists once the temp directory is cleaned up.
if [[ $NEWMAN_EXIT -ne 0 && -f "${WORK_DIR}/server.log" ]]; then
    echo "==> the collection failed; here is the tail of the server log" >&2
    tail -n 100 "${WORK_DIR}/server.log" >&2
fi

exit $NEWMAN_EXIT
