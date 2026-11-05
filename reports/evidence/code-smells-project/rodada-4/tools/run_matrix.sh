#!/usr/bin/env bash
# Uso: run_matrix.sh <dir_projeto> <saida.json> <log> — inicia `python -B app.py` com banco novo e roda matrix4.py.
set -u
DIR=$1; OUT=$2; LOG=$3; B=$(cd "$(dirname "$0")/.." && pwd)
source "$B/secrets.env"
DB=$(mktemp -d "$B/mdb.XXXX")/loja.db
(cd "$DIR" && DATABASE_PATH=$DB exec "$B/venv/bin/python" -B app.py > "$LOG" 2>&1) & PID=$!
for i in $(seq 30); do curl -s --noproxy '*' -o /dev/null http://127.0.0.1:5000/health && break; sleep 0.5; done
"$B/venv/bin/python" "$B/tools/${MATRIZ:-matrix.py}" http://127.0.0.1:5000 "$DB" "$OUT" --refatorado
kill $PID; wait $PID 2>/dev/null; rm -rf "$(dirname "$DB")"
