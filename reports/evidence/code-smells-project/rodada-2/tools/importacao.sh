#!/usr/bin/env bash
# Uso: importacao.sh <dir_projeto_origem> <python> <saida>
# Copia o projeto para um diretório novo (sem banco), importa app.py por caminho explícito
# a partir de um cwd temporário vazio e registra app.__file__, exit code e arquivos criados.
SRC=$1; PY=$2; OUT=$3
BASE=$(mktemp -d); PROJ=$BASE/projeto; CWD=$BASE/cwd
mkdir -p $CWD && rsync -a --exclude .claude --exclude __pycache__ --exclude '*.db' --exclude tests "$SRC/" "$PROJ/"
CODE="import sys; sys.path.insert(0, '$PROJ'); import app; print('app.__file__ =', app.__file__); print('create_app callable:', callable(app.create_app))"
{
  echo "# Verificação de importação — rodada 2"
  echo "projeto (cópia nova, sem banco): $PROJ"
  echo "cwd (vazio): $CWD"
  echo "*.db antes: $(find $PROJ $CWD -name '*.db' | wc -l)"
  ls -A $PROJ > $BASE/antes.txt
  echo "comando:"
  echo "  cd $CWD && env -u DATABASE_PATH $PY -I -B -c \"$CODE\""
  echo "saída:"
  cd $CWD && env -u DATABASE_PATH $PY -I -B -c "$CODE" > $BASE/out.txt 2>&1; RC=$?
  sed 's/^/  /' $BASE/out.txt
  echo "exit code: $RC"
  ls -A $PROJ > $BASE/depois.txt
  echo "arquivos no cwd após importar: [$(ls -A $CWD)]"
  echo "*.db depois (projeto + cwd): $(find $PROJ $CWD -name '*.db' | wc -l)"
  if diff -q $BASE/antes.txt $BASE/depois.txt >/dev/null; then echo "listagem do projeto idêntica antes/depois"; else echo "listagem do projeto MUDOU:"; diff $BASE/antes.txt $BASE/depois.txt; fi
  echo
  echo "# Controle: comando registrado na rodada 1, 'python -I -c \"import app\"', no mesmo cwd (sem app.py)"
  cd $CWD && $PY -I -c "import app" > $BASE/ctl.txt 2>&1; RC=$?
  tail -1 $BASE/ctl.txt | sed 's/^/  /'
  echo "exit code: $RC"
} > "$OUT"
rm -rf "$BASE"
