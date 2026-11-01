#!/usr/bin/env bash
# Driver dos testes de migração. Banco base criado pela versão ORIGINAL (seed + marcador).
set -u
S="$(cd "$(dirname "$0")/.." && pwd)"
PY="$S/venv/bin/python"; O="$S/base/original"; R="$S/base/refatorado"; M="$S/out/migracao"
mkdir -p "$M" "$S/rawlogs/migracao"
export SECRET_KEY="$(cat "$S/out/secret_key")"
run() { ( cd "$1" && "$PY" -I -B "$S/harness/mig.py" "$1" "$2" "$M/$3.json" 2>>"$S/rawlogs/migracao/$3.stderr" ); }
# banco base pelo original
"$S/harness/run_groups.sh" original marcador >/dev/null
cp "$O/instance/tasks.db" "$M/base.db"
echo "== base criada pelo original: colunas users:"; "$PY" -c "import sqlite3;print([r[1] for r in sqlite3.connect('$M/base.db').execute('PRAGMA table_info(users)')])"
# leitura do original sobre o banco base (referência)
rm -rf "$O/instance"; mkdir -p "$O/instance"; cp "$M/base.db" "$O/instance/tasks.db"
echo "== original lê base"; run "$O" leitura_original original_le_base
for step in falha ingenuo; do
  rm -rf "$R/instance"; mkdir -p "$R/instance"; cp "$M/base.db" "$R/instance/tasks.db"
  echo "== $step"; run "$R" "$step" "$step"
done
rm -rf "$R/instance"; mkdir -p "$R/instance"; cp "$M/base.db" "$R/instance/tasks.db"
echo "== normal"; run "$R" normal normal
echo "== segunda"; run "$R" segunda segunda
cp "$R/instance/tasks.db" "$M/migrado.db"
rm -rf "$O/instance"; mkdir -p "$O/instance"; cp "$M/migrado.db" "$O/instance/tasks.db"
echo "== original lê banco migrado"; run "$O" leitura_original original_le_migrado
