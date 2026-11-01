#!/usr/bin/env bash
# Importação, inicialização e CLI do seed, nas cópias isoladas.
set -u
S="$(cd "$(dirname "$0")/.." && pwd)"
PY="$S/venv/bin/python"; L="$S/rawlogs/cli"; mkdir -p "$L"
KEY="$(cat "$S/out/secret_key")"
tree() { ( cd "$1" && find . -path ./instance -prune -o -type f -print | sort; find . -path './instance/*' -type f -printf '%p %s\n' 2>/dev/null | sort ) | md5sum | cut -c1-12; }
echo "### importação (-I -B, caminho inserido explicitamente, sem SECRET_KEY)"
for m in original refatorado; do
  C="$S/base/$m"; rm -rf "$C/instance"; before="$(cd "$C" && find . -type f | sort)"
  out="$(cd "$C" && env -u SECRET_KEY "$PY" -I -B -c 'import sys, os; sys.path.insert(0, sys.argv[1]); import app; print(os.path.realpath(app.__file__))' "$C" 2>"$L/import-$m.stderr")"; rc=$?
  after="$(cd "$C" && find . -type f | sort)"
  if [ $rc -ne 0 ]; then verdict="FALHA DE IMPORTAÇÃO"; elif [ "$out" != "$C/app.py" ]; then verdict="MÓDULO ERRADO ($out)"; else
    novos="$(comm -13 <(echo "$before") <(echo "$after") | tr '\n' ' ')"; verdict="importou $C/app.py; arquivos novos: ${novos:-nenhum}"; fi
  echo "$m: exit=$rc; $verdict"
done
echo "### controle do harness: python -I sem inserir o caminho"
( cd "$S/base/refatorado" && "$PY" -I -B -c 'import app' 2>&1; echo "exit=$?" ) | tail -2
echo "### inicialização sem SECRET_KEY / chave curta (refatorado)"
C="$S/base/refatorado"
for k in "" "curta-demais"; do
  rm -rf "$C/instance"
  ( cd "$C" && if [ -z "$k" ]; then env -u SECRET_KEY "$PY" -B app.py; else SECRET_KEY="$k" "$PY" -B app.py; fi ) >"$L/start-sem-chave.out" 2>&1; rc=$?
  echo "chave='${k:-<ausente>}': exit=$rc; instance/tasks.db existe? $( [ -e "$C/instance/tasks.db" ] && echo SIM || echo não ); msg: $(tail -1 "$L/start-sem-chave.out")"
done
echo "### inicialização normal (refatorado, porta livre)"
PORT=$("$PY" -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
rm -rf "$C/instance"
( cd "$C" && SECRET_KEY="$KEY" PORT=$PORT exec setsid "$PY" -B app.py ) >"$L/start-refatorado.log" 2>&1 & PID=$!
for i in $(seq 1 30); do curl --noproxy '*' -s "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 1; done
echo "health: $(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/health)"
ss -ltnp 2>/dev/null | grep ":$PORT " | awk '{print "escuta em:", $4}'
kill -- -$PID 2>/dev/null; wait $PID 2>/dev/null; sleep 1
ss -ltn | grep -q ":$PORT " && echo "PORTA AINDA OCUPADA" || echo "porta liberada"
grep -E "Running on|Debugger|Debug mode" "$L/start-refatorado.log" | sed "s/$PORT/<porta>/"
echo "### inicialização do original (porta 5000 fixa)"
if ss -ltn | grep -q ':5000 '; then echo "porta 5000 ocupada: não executado"; else
  rm -rf "$S/base/original/instance"
  ( cd "$S/base/original" && exec setsid "$PY" -B app.py ) >"$L/start-original.log" 2>&1 & PID=$!
  for i in $(seq 1 30); do curl --noproxy '*' -s http://127.0.0.1:5000/health >/dev/null && break; sleep 1; done
  echo "health: $(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5000/health)"
  ss -ltn | grep ':5000 ' | awk '{print "escuta em:", $4}' | sort -u
  kill -- -$PID 2>/dev/null; sleep 2
  grep -E "Running on|Debugger|Debug mode" "$L/start-original.log" | grep -v PIN
  ss -ltn | grep -q ':5000 ' && echo "PORTA 5000 AINDA OCUPADA" || echo "porta 5000 liberada"
fi
echo "### seed CLI"
for m in original refatorado; do
  C="$S/base/$m"; rm -rf "$C/instance"
  ( cd "$C" && SECRET_KEY="$KEY" SEED_ADMIN_PASSWORD=<removido> SEED_USER_PASSWORD=<removido> SEED_MANAGER_PASSWORD=<removido> "$PY" -B seed.py ) >"$L/seed-$m.out" 2>&1
  echo "$m seed normal: exit=$? | $(tr '\n' ' ' < "$L/seed-$m.out" | grep -v Warning)"
done
C="$S/base/refatorado"
"$S/harness/run_groups.sh" refatorado marcador >/dev/null
snap() { "$PY" -c "
import sqlite3,hashlib,json;c=sqlite3.connect('$C/instance/tasks.db')
print(hashlib.sha256(json.dumps([c.execute(f'SELECT * FROM {t} ORDER BY id').fetchall() for t in ('users','categories','tasks')]).encode()).hexdigest()[:16])"; }
s1=$(snap)
( cd "$C" && SECRET_KEY="$KEY" SEED_ADMIN_PASSWORD=<removido> SEED_MANAGER_PASSWORD=<removido> env -u SEED_USER_PASSWORD "$PY" -B seed.py ) >"$L/seed-sem-var.out" 2>&1; rc=$?
s2=$(snap)
echo "refatorado seed sem SEED_USER_PASSWORD: exit=$rc; snapshot idêntico? $( [ "$s1" = "$s2" ] && echo sim || echo NÃO ); msg: $(cat "$L/seed-sem-var.out")"
( cd "$C" && SEED_ADMIN_PASSWORD=<removido> SEED_USER_PASSWORD=<removido> SEED_MANAGER_PASSWORD=<removido> env -u SECRET_KEY "$PY" -B seed.py ) >"$L/seed-sem-chave.out" 2>&1; rc=$?
s3=$(snap); echo "refatorado seed sem SECRET_KEY: exit=$rc; snapshot idêntico? $( [ "$s1" = "$s3" ] && echo sim || echo NÃO ); msg: $(cat "$L/seed-sem-chave.out")"
