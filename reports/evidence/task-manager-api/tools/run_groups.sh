#!/usr/bin/env bash
# Uso: run_groups.sh <original|refatorado> <grupo...>
# Cada grupo roda num subprocesso novo, com o banco da cópia removido antes.
set -u
S="$(cd "$(dirname "$0")/.." && pwd)"
MODE="$1"; shift
COPY="$S/base/$MODE"
OUTD="$S/out/$MODE"
LOGD="$S/rawlogs/$MODE"
mkdir -p "$OUTD" "$LOGD"
# segredos de teste: gerados por execução, nunca gravados nas evidências
if [ ! -f "$S/out/secret_key" ]; then
  "$S/venv/bin/python" -c 'import secrets;print(secrets.token_urlsafe(36))' > "$S/out/secret_key"
fi
export SECRET_KEY="$(cat "$S/out/secret_key")"
export SEED_ADMIN_PASSWORD=<removido> SEED_USER_PASSWORD=<removido> SEED_MANAGER_PASSWORD=<removido>
for G in "$@"; do
  rm -rf "$COPY/instance"
  ( cd "$COPY" && "$S/venv/bin/python" -I -B "$S/harness/h.py" "$COPY" "$MODE" "$G" "$OUTD/$G.json" \
      > "$LOGD/$G.stdout" 2> "$LOGD/$G.stderr" )
  echo "[$MODE/$G] exit=$?"; grep -h "registros\|FALHOU" "$LOGD/$G.stdout" | head -60
done
