# Comandos executados — Fase 3 (ecommerce-api-legacy)

`<tmp>` = diretório temporário de trabalho fora do repositório (scratchpad da sessão); `<repo>` = raiz do repositório;
`<tools>` = `reports/evidence/ecommerce-api-legacy/tools`. Senhas, tokens e cartões de teste foram gerados em tempo de
execução pelos scripts e não aparecem aqui.

| # | Comando | Resultado resumido |
|---:|---|---|
| 1 | `git status --porcelain` (raiz) | só `?? ecommerce-api-legacy/.claude/` e `?? requirements.txt` (alheio); nenhum arquivo do alvo alterado |
| 2 | gravação de `reports/audit-project-2.md` (revisão 3) | relatório salvo antes de qualquer alteração de código |
| 3 | `rsync -a --exclude .claude --exclude node_modules ecommerce-api-legacy/ <tmp>/original/` | cópia isolada do original |
| 4 | `cd <tmp>/original && npm ci && npm ls --depth=0` | express@4.22.1, sqlite3@5.1.7 |
| 5 | `node <tools>/run_matrix.js original <tmp>/original <tmp>/baseline.json` | 25 registros; exit 0 |
| 6 | `node <tools>/process_cases.js original <tmp>/original <tmp>/baseline-process.json 3000` | P-01 sobe; P-02 e P-03 derrubam o processo (exit 1) |
| 7 | refatoração do código em `ecommerce-api-legacy/` (ver validation.md) | — |
| 8 | `rsync ... ecommerce-api-legacy/ <tmp>/refatorado/ && cd <tmp>/refatorado && npm ci && npm ls --depth=0` | express@4.22.1, sqlite3@5.1.7 |
| 9 | `node <tools>/run_matrix.js refatorado <tmp>/refatorado <tmp>/refatorado.json` | 25 registros; exit 0 |
| 10 | `node <tools>/compare.js <tmp>/baseline.json <tmp>/refatorado.json <tmp>/matriz.md` | 25 casos, "0 regressões" — resultado da versão antiga do comparador, que tinha falso negativo (ver abaixo) |
| 11 | `node <tools>/process_cases.js refatorado <tmp>/refatorado <tmp>/refatorado-process.json 3000` | P-01..P-07 conforme esperado (ver validation.md) |
| 12 | `REF_DIR=<tmp>/refatorado node --test --test-reporter=spec <tools>/concurrency_rollback.test.js` | 21 testes, 21 passaram |
| 13 | `bash <tools>/inspecao.sh <repo>/ecommerce-api-legacy` | 11 verificações OK; 1 falso positivo (AP-16, `start().catch`) |
| 14 | `node -r <tools>/preload_trace_open.js -e "require('./src/app.js')"` (na cópia refatorada) | exporta `createApp,start`; nenhum banco aberto, nenhuma porta |
| 15 | `env -u SEED_USER_PASSWORD npm start` (cópia refatorada) | `Configuração inválida: SEED_USER_PASSWORD é obrigatória`; exit 1 |
| 16 | `SEED_USER_PASSWORD=<aleatória> ADMIN_TOKEN=<…> PORT=3000 timeout 4 npm start` | `Frankenstein LMS rodando na porta 3000...`; encerrado pelo timeout (124) |
| 17 | `grep -cE 'pk_(live\|test)_\|[0-9]{12,19}\|scrypt\$…\|senha_su…\|Processando cartão'` nos logs do refatorado | 0 ocorrências (R-14) |
| 18 | `node <tools>/sanitize_file.js <log/json> <evidência>` para cada arquivo preservado | todos sem padrões sensíveis após sanitização |

Correções feitas nos scripts durante a validação (não no código da aplicação):
- valor de senha numérica de teste passou a ser gerado em execução (aparecia no stack trace do original);
- ordem da sanitização corrigida (substituição de valores conhecidos gerava JSON inválido);
- `process_cases.js`: variável vazia de P-05 era sobrescrita pela senha de teste; após a correção, P-05 encerra com exit 1;
- `concurrency_rollback.test.js` (R-05): asserção de "id diferente" substituída — o SQLite reaproveita o maior rowid
  excluído em `INTEGER PRIMARY KEY` sem `AUTOINCREMENT` (schema original preservado).

Ajuste final das ferramentas: o sanitizador (`lib.js`) e `inspecao.sh` continham as credenciais literais do original como
padrão de busca; foram trocadas por padrões de prefixo mascarado (`senha_su…`, `admin_m…`). Em seguida, todos os passos
5, 6 e 9–13 foram reexecutados com a versão final das ferramentas; os arquivos preservados vêm dessa execução final
(mesmos resultados: 25 casos / 0 regressões; 21/21 testes; P-01..P-07 iguais; C-OBS1 2×10 → 1×10).

## Correção do comparador (após revisão independente)

Falso negativo confirmado pela revisão: na versão anterior de `compare.js`, casos em `INTENTIONAL` aceitavam qualquer
diferença (S1-01 com HTTP 500 → exit 0). Apenas ferramentas e evidências foram alteradas; aplicação, Skill e dependências não.

| # | Comando | Resultado resumido |
|---:|---|---|
| 19 | reescrita de `<tools>/compare.js` (expectativas explícitas, comportamento antigo, ausências, erros) e criação de `<tools>/compare.test.js` | — |
| 20 | `node <tools>/compare.js <evidências antigas>` | 25 casos, 0 reprovações, 0 avisos |
| 21 | `git archive 209d251… ecommerce-api-legacy \| tar -x` → `<tmp>/original`; `rsync` do working tree → `<tmp>/refatorado`; `npm ci` em ambos | express@4.22.1, sqlite3@5.1.7 nos dois |
| 22 | `node <tools>/run_matrix.js original …` e `… refatorado …` | 25 registros cada; exit 0 |
| 23 | `node <tools>/compare.js <tmp>/baseline.json <tmp>/refatorado.json <tmp>/matriz.md` | 25 casos, 0 reprovações, 0 avisos; exit 0 |
| 24 | `CMP_BASE=<tmp>/baseline.json CMP_REF=<tmp>/refatorado.json node --test <tools>/compare.test.js` | 15/15 passaram |
| 25 | `REF_DIR=<tmp>/refatorado node --test <tools>/concurrency_rollback.test.js` | 21/21 passaram |
| 26 | sanitização e cópia de `baseline.json`, `refatorado.json`, logs; `node <tools>/compare.js` e `node --test <tools>/compare.test.js` sobre os arquivos preservados | 0 reprovações; 15/15 |

Os casos em nível de processo (P-01..P-07) não foram reexecutados nesta rodada: não dependem do comparador e não houve
alteração na aplicação; permanecem os resultados da execução final anterior (`baseline-process.json`, `refatorado-process.json`).

## Ajuste do comparador (segunda revisão independente)

Falso positivo com resultados reais: S5-01 reprovado só pela ordem dos alunos do original
(`[Aluno Recusado, Unknown, Leonan]` × refatorado `[Aluno Recusado, Leonan, Unknown]`).

| # | Comando | Resultado resumido |
|---:|---|---|
| 27 | `compare.js`: relação `same-unordered` normaliza a ordem de cursos **e** alunos sobre cópias; comparação exata com `EXPECTATIONS` mantida | — |
| 28 | `compare.test.js`: inversão de alunos no original passa a ser aceita; inversão no refatorado, `paid` alterado, aluno removido/duplicado reprovam; registros recebidos inalterados | — |
| 29 | `node --test <tools>/compare.test.js` | 18/18 passaram |
| 30 | `node <tools>/compare.js <evidências>/baseline.json <evidências>/refatorado.json <evidências>/matriz.md` | 25 casos, 0 reprovações, 0 avisos |

Aplicação, Skill, dependências e `reports/audit-project-2.md` não foram alterados. A matriz da aplicação não foi
reexecutada nesta rodada: a mudança afeta só o comparador, que foi reaplicado sobre os resultados preservados.
