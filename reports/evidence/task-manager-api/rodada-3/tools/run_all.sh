#!/usr/bin/env bash
# Validação completa da rodada 3 (original × refatorado) em cópias temporárias.
# Rodada 3 = rodada 2 + exceção de C-07 fechada + inventário explícito + meta-testes do comparador.
#
# Uso:   reports/evidence/task-manager-api/rodada-3/tools/run_all.sh [dir_saida]
# Saída: dir_saida (padrão: rodada-3/resultados) recebe apenas resultados sanitizados.
# Variáveis opcionais:
#   BASE_REF  commit do código original (padrão: f6eaae3..., a versão auditada)
#   VENV      venv já existente com requirements.txt instalado (senão cria um temporário; exige rede)
#   KEEP_TMP=1  não apagar o diretório temporário (para depuração)
# Segredos (SECRET_KEY e senhas SEED_*) são gerados a cada execução e nunca gravados na saída.
# Código de saída: 0 só se todos os grupos, testes transversais, comparador e varreduras passarem.
set -uo pipefail
TOOLS="$(cd "$(dirname "$0")" && pwd)"
REPO="$(git -C "$TOOLS" rev-parse --show-toplevel)"
OUT="${1:-$TOOLS/../resultados}"
BASE_REF="${BASE_REF:-f6eaae357672157858e16e4b58b49d0e6839a506}"
T="$(mktemp -d)"
PIDS=()
cleanup() {
  for p in "${PIDS[@]}"; do kill -- -"$p" 2>/dev/null; done
  if [ -z "${KEEP_TMP:-}" ]; then rm -rf "$T"; else echo "temporário mantido em $T"; fi
}
trap cleanup EXIT
FAIL=0
fail() { echo "FALHA: $*"; FAIL=1; }

# ---------------------------------------------------------------- ambiente
if [ -n "${VENV:-}" ]; then PY="$VENV/bin/python"; else
  python3 -m venv "$T/venv" && "$T/venv/bin/pip" install -q -r <(git -C "$REPO" show "$BASE_REF:task-manager-api/requirements.txt") \
    || { echo "falha ao instalar dependências"; exit 2; }
  PY="$T/venv/bin/python"; fi
"$PY" -m pip freeze > "$T/versions.txt" 2>/dev/null; "$PY" --version >> "$T/versions.txt"
mkdir -p "$T/base/original" "$T/base/refatorado" "$T/res/original" "$T/res/refatorado" "$T/res/migracao" \
         "$T/res/warn" "$T/logs/"{original,refatorado,migracao,cli,warn-original,warn-refatorado}
git -C "$REPO" archive "$BASE_REF" task-manager-api | tar -x -C "$T/base/original" --strip-components=1
(cd "$REPO/task-manager-api" && tar --exclude=.claude --exclude=instance --exclude=__pycache__ -cf - .) | tar -x -C "$T/base/refatorado"
gen() { "$PY" -c 'import secrets;print("Fx-"+secrets.token_urlsafe(12))'; }
export SECRET_KEY="$("$PY" -c 'import secrets;print(secrets.token_urlsafe(36))')"
export SEED_ADMIN_PASSWORD="$(gen)" SEED_USER_PASSWORD="$(gen)" SEED_MANAGER_PASSWORD="$(gen)"
O="$T/base/original"; R="$T/base/refatorado"

# ---------------------------------------------------------------- matriz por grupos
GRUPOS="seed_leitura vazio bordas tasks_escrita users_escrita categories_escrita auth ciclo_token rollback seed_falha bigint http fronteira7"
for m in original refatorado; do
  for g in $GRUPOS; do
    rm -rf "$T/base/$m/instance"
    ( cd "$T/base/$m" && "$PY" -I -B "$TOOLS/h.py" "$T/base/$m" "$m" "$g" "$T/res/$m/$g.json" \
        > "$T/logs/$m/$g.stdout" 2> "$T/logs/$m/$g.stderr" ) || fail "grupo $m/$g"
    grep -h "registros\|FALHOU\|Traceback" "$T/logs/$m/$g.stdout" | sed "s/^/[$m] /" | head -20
  done
done

# ---------------------------------------------------------------- avisos de runtime
for m in original refatorado; do
  rm -rf "$T/base/$m/instance"
  ( cd "$T/base/$m" && "$PY" -I -B -W always "$TOOLS/h.py" "$T/base/$m" "$m" tasks_escrita "$T/res/warn/$m.json" \
      > "$T/logs/warn-$m/stdout" 2> "$T/logs/warn-$m/stderr" ) || fail "avisos $m"
  echo "avisos $m: $(grep -o '[A-Za-z]*Warning: [^:(]*' "$T/logs/warn-$m/stderr" | grep -v 'Unexpected value' | sort | uniq -c | tr -s ' ' | tr '\n' ';')"
done > "$T/res/avisos-runtime.txt"
cat "$T/res/avisos-runtime.txt"
grep -q "avisos refatorado: .*\(Deprecation\|LegacyAPI\)" "$T/res/avisos-runtime.txt" && fail "avisos de API obsoleta no refatorado"

# ---------------------------------------------------------------- migração
mig() { ( cd "$1" && "$PY" -I -B "$TOOLS/mig.py" "$1" "$2" "$T/res/migracao/$3.json" "$O" > "$T/logs/migracao/$3.stdout" 2> "$T/logs/migracao/$3.stderr" ) || fail "migração $3"; }
rm -rf "$O/instance"
( cd "$O" && "$PY" -I -B "$TOOLS/h.py" "$O" original marcador "$T/res/migracao/marcador-original.json" > "$T/logs/migracao/marcador.stdout" 2>&1 ) || fail "marcador"
cp "$O/instance/tasks.db" "$T/base.db"
mig "$O" leitura_original original_le_base
for step in falha ingenuo normal; do
  rm -rf "$R/instance"; mkdir -p "$R/instance"; cp "$T/base.db" "$R/instance/tasks.db"
  mig "$R" "$step" "$step"
done
mig "$R" segunda segunda
rm -rf "$O/instance"; mkdir -p "$O/instance"; cp "$R/instance/tasks.db" "$O/instance/tasks.db"
mig "$O" leitura_original original_le_migrado
"$PY" -I - "$T/res/migracao" <<'EOF' || fail "leitura do banco migrado pelo original"
import json, sys
d = sys.argv[1]
a = json.load(open(f'{d}/original_le_base.json'))['leituras']
b = json.load(open(f'{d}/original_le_migrado.json'))['leituras']
# /users/1 difere de propósito: o login do passo 'normal' migrou o hash MD5 do admin (D-2a) e o original expõe password.
bad = [p for p in a if p != '/users/1' and a[p] != b[p]] + [p for p in a if b[p]['status'] != 200]
print('leitura pelo original do banco migrado:', 'idêntica (exceto /users/1)' if not bad else f'DIFERENTE {bad}')
sys.exit(1 if bad else 0)
EOF
for f in falha ingenuo normal segunda; do echo "migração $f: $(cat "$T/logs/migracao/$f.stdout")"; done

# ---------------------------------------------------------------- importação, inicialização e CLI
CLI="$T/res/cli.txt"; : > "$CLI"
log() { echo "$*" | sed "s|$T|<tmp>|g" | tee -a "$CLI"; }
for m in original refatorado; do
  C="$T/base/$m"; rm -rf "$C/instance"; before="$(cd "$C" && find . -type f | sort)"
  out="$(cd "$C" && env -u SECRET_KEY "$PY" -I -B -c 'import sys, os; sys.path.insert(0, sys.argv[1]); import app; print(os.path.realpath(app.__file__))' "$C" 2>"$T/logs/cli/import-$m.stderr")"; rc=$?
  novos="$(comm -13 <(echo "$before") <(cd "$C" && find . -type f | sort) | tr '\n' ' ')"
  if [ $rc -ne 0 ]; then log "importação $m: FALHA DE IMPORTAÇÃO (exit $rc)"; fail "importação $m"
  elif [ "$out" != "$C/app.py" ]; then log "importação $m: módulo errado"; fail "importação $m"
  else log "importação $m: ok ($m/app.py); arquivos novos: ${novos:-nenhum}"; fi
  if [ "$m" = refatorado ] && [ -n "$novos" ]; then fail "importação do refatorado criou arquivos"; fi
  if [ "$m" = original ] && [ -z "$novos" ]; then fail "linha de base: importação do original deveria criar o banco"; fi
done
( cd "$R" && "$PY" -I -B -c 'import app' >/dev/null 2>&1 ); log "controle: python -I sem inserir o caminho → exit $? (esperado 1)"
for k in "" "curta-demais"; do
  rm -rf "$R/instance"
  ( cd "$R" && if [ -z "$k" ]; then env -u SECRET_KEY "$PY" -B app.py; else SECRET_KEY="$k" "$PY" -B app.py; fi ) > "$T/logs/cli/sem-chave.out" 2>&1; rc=$?
  msg="$(tail -1 "$T/logs/cli/sem-chave.out")"; db=$([ -e "$R/instance/tasks.db" ] && echo SIM || echo não)
  log "inicialização chave='${k:-<ausente>}': exit=$rc; banco criado? $db; msg: $msg"
  [ $rc -eq 2 ] && [ "$db" = não ] && [[ "$msg" == *"SECRET_KEY ausente"* ]] || fail "inicialização sem chave válida"
done
free_port() { "$PY" -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])'; }
start() {  # $1=cópia $2=log $3=porta(health)
  ( cd "$1" && exec setsid "$PY" -B app.py ) > "$2" 2>&1 & PIDS+=($!); local pid=$!
  for _ in $(seq 1 30); do curl --noproxy '*' -s "http://127.0.0.1:$3/health" >/dev/null && break; sleep 1; done
  log "  health: $(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$3/health"); escuta: $(ss -ltn | awk -v p=":$3" '$4 ~ p"$" {print $4}' | sort -u | tr '\n' ' ')"
  kill -- -"$pid" 2>/dev/null; wait "$pid" 2>/dev/null; sleep 1
  ss -ltn | grep -q ":$3 " && { log "  PORTA $3 AINDA OCUPADA"; fail "porta $3"; } || log "  porta liberada"
}
PORT=$(free_port); rm -rf "$R/instance"; log "inicialização refatorado (porta livre):"
SECRET_KEY="$SECRET_KEY" PORT=$PORT start "$R" "$T/logs/cli/start-refatorado.log" "$PORT"
grep -E "Running on|Debugger|Debug mode" "$T/logs/cli/start-refatorado.log" | sed -E "s/:$PORT/:<porta>/" | while read -r l; do log "  $l"; done
grep -q "Debug mode: off" "$T/logs/cli/start-refatorado.log" && grep -q "127.0.0.1:$PORT" "$T/logs/cli/start-refatorado.log" \
  && ! grep -q "0.0.0.0" "$T/logs/cli/start-refatorado.log" || fail "inicialização do refatorado"
if ss -ltn | grep -q ':5000 '; then log "inicialização original: porta 5000 ocupada, não executada"; else
  rm -rf "$O/instance"; log "inicialização original (porta 5000 fixa):"
  start "$O" "$T/logs/cli/start-original.log" 5000
  grep -E "Running on|Debugger is active|Debug mode" "$T/logs/cli/start-original.log" | grep -v -e PIN -e '172\.' | while read -r l; do log "  $l"; done
fi
snap() { "$PY" -c "import sqlite3,hashlib,json;c=sqlite3.connect('$R/instance/tasks.db');print(hashlib.sha256(json.dumps([c.execute(f'SELECT * FROM {t} ORDER BY id').fetchall() for t in ('users','categories','tasks')]).encode()).hexdigest()[:16])"; }
for m in original refatorado; do
  rm -rf "$T/base/$m/instance"; ( cd "$T/base/$m" && "$PY" -B seed.py ) > "$T/logs/cli/seed-$m.out" 2>&1; rc=$?
  log "seed normal $m: exit=$rc; $(grep -v -e Warning -e '^  {' -e 'Unexpected value' "$T/logs/cli/seed-$m.out" | tr '\n' ' ')"
  [ $rc -eq 0 ] || fail "seed $m"
done
rm -rf "$R/instance"
( cd "$R" && "$PY" -I -B "$TOOLS/h.py" "$R" refatorado marcador "$T/res/migracao/marcador-refatorado.json" > /dev/null 2>&1 ) || fail "marcador refatorado"
s1=$(snap)
( cd "$R" && env -u SEED_USER_PASSWORD "$PY" -B seed.py ) > "$T/logs/cli/seed-sem-var.out" 2>&1; rc=$?
log "seed sem SEED_USER_PASSWORD: exit=$rc; banco idêntico? $([ "$s1" = "$(snap)" ] && echo sim || echo NÃO); msg: $(cat "$T/logs/cli/seed-sem-var.out")"
[ $rc -eq 1 ] && [ "$s1" = "$(snap)" ] || fail "seed sem variável"
( cd "$R" && env -u SECRET_KEY "$PY" -B seed.py ) > "$T/logs/cli/seed-sem-chave.out" 2>&1; rc=$?
log "seed sem SECRET_KEY: exit=$rc; banco idêntico? $([ "$s1" = "$(snap)" ] && echo sim || echo NÃO); msg: $(cat "$T/logs/cli/seed-sem-chave.out")"
[ $rc -eq 2 ] && [ "$s1" = "$(snap)" ] || fail "seed sem chave"

# ---------------------------------------------------------------- comparador e varredura
"$PY" -I -B "$TOOLS/compare.py" "$T/res" "$T/res/matriz.md" "$T/res/resumo.json" > "$T/res/compare-saida.txt" 2>&1 || fail "comparador"
head -3 "$T/res/compare-saida.txt"; grep PROBLEMA "$T/res/compare-saida.txt" | head -20
"$PY" -I -B "$TOOLS/meta_tests.py" "$T/res" "$T/meta" "$T/res/meta-testes.txt" || fail "meta-testes do comparador"
sha256sum "$TOOLS/inventario.json" | awk '{print $1"  inventario.json"}' > "$T/res/inventario.sha256"
"$PY" -I -B "$TOOLS/scan_logs.py" "$T" "$T/res/varredura-logs.txt" > /dev/null || fail "varredura de logs"
cat "$T/res/varredura-logs.txt"

# ---------------------------------------------------------------- saída sanitizada
mkdir -p "$OUT"
rm -rf "$OUT/original" "$OUT/refatorado" "$OUT/migracao" "$OUT/warn"
cp "$T/versions.txt" "$OUT/"
(cd "$T/res" && tar --exclude='segredos-*.txt' -cf - .) | tar -x -C "$OUT"
for m in original refatorado; do
  grep -h "registros\|FALHOU" "$T"/logs/$m/*.stdout > "$OUT/$m/resumo-grupos.txt"
done
grep -h -A4 "^ERRO:" "$T/logs/original/rollback.stdout" | grep -E "ERRO:|parameters" \
  | sed -E -e 's/[0-9a-f]{32}/<removido>/g' -e 's/(scrypt|pbkdf2):[^ '"'"'"]+/<removido>/g' > "$OUT/f05-original-sanitizado.txt"
grep -h "Conflito de unicidade\|Falha de" "$T/logs/refatorado/rollback.stderr" > "$OUT/f05-refatorado.txt"
"$PY" -I -B "$TOOLS/scan_logs.py" "$T" "$T/varredura-evidencias.txt" --evidencias "$OUT" > /dev/null || fail "segredo nas evidências"
tail -1 "$T/varredura-evidencias.txt" | sed "s|$OUT|<saida>|" | tee "$OUT/varredura-evidencias.txt"
echo "resultado final: $([ $FAIL -eq 0 ] && echo APROVADO || echo REPROVADO)" | tee "$OUT/resultado-final.txt"
exit $FAIL
