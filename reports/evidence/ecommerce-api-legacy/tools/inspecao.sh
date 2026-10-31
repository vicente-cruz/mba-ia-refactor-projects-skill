#!/usr/bin/env bash
# Nova inspeção estática do código refatorado (somente leitura). Uso: bash inspecao.sh <dir-do-projeto>
set -u
P="${1:?informe o diretório do projeto}"
cd "$P" || exit 2
check() { # descrição, padrão, [arquivos]
  local desc="$1" pat="$2"; shift 2
  local hits; hits=$(grep -rnE "$pat" "${@:-src}" 2>/dev/null)
  if [ -z "$hits" ]; then echo "OK    | $desc"; else echo "ACHOU | $desc"; echo "$hits" | sed 's/^/        /'; fi
}
echo "== Arquivos e linhas"; find src -name '*.js' | sort | xargs wc -l
echo "== Verificações"
check "AP-02 literais de credencial/chave"            'pk_live_|senha_su[a-z_]|admin_m[a-z]+_?|no-reply@|dbPass|smtpUser|paymentGatewayKey'
check "AP-03 log de cartão/chave/corpo"               'console\.(log|error)\(.*(card|cc\b|req\.body|pwd|password|Key)'
check "AP-04 badCrypto/base64/senha padrão"           "badCrypto|toString\('base64'\)|123456|'123'"
check "AP-01 SQL com interpolação"                    '(run|get|all)\(\s*`[^`]*\$\{'
check "AP-08 estado global (cache/receita)"           'globalCache|totalRevenue|logAndCache'
check "AP-10 listen/abertura no carregamento"         '^(app\.listen|const manager|manager\.)'
check "AP-12 consulta dentro de forEach/loop"         'forEach\(.*\b(db|handle)\.(get|all|run)'
check "AP-16 callbacks sqlite com err ignorado"       '\(err\) => \{\s*$'
check "AP-18 nomes de 1-2 letras do original"         '\blet (u|e|p|cc|cid) ='
check "AP-19 módulos removidos referenciados"         "require\('\./(AppManager|utils)'\)"
check "SQL fora de models/database.js"                "(INSERT|SELECT|DELETE|UPDATE|CREATE TABLE) " src/routes src/controllers src/middlewares src/app.js
check "req/res fora de routes/middlewares"            '\b(req|res)\.' src/models src/controllers src/database.js
echo "== Rotas registradas"; grep -rnE "router\.(get|post|delete|put|patch)\(" src/routes
