# Validação — rodada 3 (task-manager-api)

| Campo | Valor |
|---|---|
| Data | 2026-10-31 |
| Escopo | Só a suíte (harness, comparador, testes) e as evidências. Nenhuma alteração em fontes da aplicação, dependências, Skill ou `reports/audit-project-3.md` (md5 `31374c5a78aade2114e8474803aa9f66`, inalterado). |
| Base | Ferramentas da rodada 2 copiadas para `rodada-3/tools/` e ajustadas; a rodada 2 foi preservada sem alterações, exceto por uma nota de correção no topo do seu `validation.md`. |
| Resultado | **APROVADO**: `rodada-3/tools/run_all.sh` saiu com código 0 (`resultados/resultado-final.txt`). |

## 1. Reprodução

```bash
# na raiz do repositório (cria venv temporário, exige rede; ou VENV=<venv com requirements>)
reports/evidence/task-manager-api/rodada-3/tools/run_all.sh     # grava em rodada-3/resultados
```

O procedimento é o mesmo da rodada 2:
- cópias temporárias por `git archive` do commit auditado e do working tree;
- segredos gerados a cada execução;
- limpeza ao final;
- código de saída diferente de zero em qualquer falha.

Duas etapas são novas: os **meta-testes do comparador** e o registro do SHA-256 do inventário.

## 2. Ajuste 1 — exceção de C-07 fechada

**Problema da rodada 2.** Em C-07, qualquer `has` em `post.*` liberava todas as diferenças de `.post.*` e `.resp.*`. Com isso, `post.get.json.role = "admin"` e `post.counts.tasks = 0` eram aprovados como "intencional C-07".

**Mudanças no harness** (`tools/h.py`, `tools/expect.py`):
- **Visão anterior:** em toda escrita com verificação posterior, o harness registra também a visão pública **anterior** (`pre_view`), com a mesma função.
- **Visão inalterada:** com `unchanged`, além do digest do banco, a visão pública posterior deve ser **igual** à anterior.
- **Estado completo nos dois casos C-07** (POST e PUT): contagens, usuário-alvo, `GET /users`, `GET /tasks`, `GET /categories` e a linha concorrente lida do banco.
- **Expectativas, iguais nas duas versões:**
  - contagens exatas `{tasks: 10, users: 4, categories: 4}`;
  - a linha concorrente exata `['Corrida', <email>, 'user']`;
  - usuário-alvo com email, nome e role originais;
  - `pre_eq`: usuário-alvo, tarefas e categorias iguais ao estado anterior, e a lista de usuários igual à anterior depois de remover **só** a linha concorrente.

**Mudanças no comparador** (`tools/compare.py`, classes de rejeição e correção):

| Onde | O que pode diferir |
|---|---|
| `resp` | Só status, `is_json`, texto, `WWW-Authenticate` e o corpo. Em erro, o corpo deve ser **exatamente** `{'error': <mensagem>}`; campo extra reprova. |
| `post` | Só quando o **original gravou** (2xx) e o refatorado provou banco **e** visão pública inalterados. Quando o original não gravou (C-07 com 500, demais 500), o estado posterior deve ser igual nas duas versões, exceto as folhas globais aprovadas (`password` removido, etc.). Nenhuma verificação isolada de `post.*` libera diferenças. |

**Verificação:**
- As duas mutações relatadas pela revisão, aplicadas diretamente aos arquivos de resultado, agora reprovam com código 1 e mensagem específica do caso (`resultados/meta-testes.txt`):
  - `rollback/conflito forçado PUT /users/2: FALHA … post.get.json.role: 'admin' != 'user'; … post.get: estado posterior difere do anterior`;
  - `… post.counts: {'tasks': 0, …} != {'tasks': 10, …}`.
- Mutações adicionais em C-07, todas detectadas: tarefas removidas da listagem, outro usuário alterado, categoria alterada, email do alvo alterado, linha concorrente ausente, campo extra no corpo de erro e `password` exposto no estado posterior.
- Duas mutações novas em R-05: campo extra no corpo de erro e visão posterior alterada mantendo o digest.

## 3. Ajuste 2 — inventário explícito

**Problema da rodada 2.** Remover "POST /tasks minimo" das duas versões fazia o comparador aprovar 399 registros, porque a presença de casos era verificada só entre os próprios resultados.

**Correção.**
- `tools/inventario.json` lista explicitamente, por grupo e versão, os nomes dos casos que devem executar: 377 no original e 400 no refatorado.
- O comparador confronta os resultados com esse arquivo. Reprovam:
  - caso do inventário ausente;
  - caso fora do inventário;
  - grupo sem inventário.
- As verificações de duplicados, grupo ausente e execução vazia foram mantidas.
- **Origem do inventário:** foi congelado a partir da execução já revisada e aprovada da rodada 2 (`rodada-2/resultados`). Fica versionado como arquivo e **não é regenerado** a partir dos resultados que valida. SHA-256: `22cb7101432f8b7d37b2a192dc61b1e71f315264fe19e8150e6136b7f525bd9f` (gravado também em `resultados/inventario.sha256`). Mudar o conjunto de casos exige editar esse arquivo explicitamente.

**Meta-testes de ponta a ponta** (`tools/meta_tests.py`). Cada um altera uma cópia dos resultados e roda `compare.py` como processo separado:

| Meta-teste | Exit | Mensagem |
|---|---:|---|
| Controle: resultados sem alteração | 0 | — |
| "POST /tasks minimo" removido das **duas** versões | 1 | `original/tasks_escrita: caso do inventário AUSENTE nos resultados: "POST /tasks minimo"` (idem refatorado) |
| Removido só do refatorado | 1 | `refatorado/tasks_escrita: caso do inventário AUSENTE …` |
| Caso duplicado | 1 | `casos duplicados ['GET /tasks seed']` |
| Grupo ausente | 1 | `refatorado/bigint: resultado ausente` |
| Execução vazia | 1 | `original/vazio: execução vazia` |
| Caso fora do inventário | 1 | `caso FORA do inventário: "caso inventado"` |
| C-07 role → admin | 1 | ver seção 2 |
| C-07 `post.counts.tasks` → 0 | 1 | ver seção 2 |
| C-07 campo extra no corpo de erro | 1 | `FALHA corpo de erro com campos além de "error" em C-07` |

## 4. Resultados da matriz completa (comparador corrigido, `resultados/resumo.json`)

Todos os 13 grupos foram reexecutados nas duas versões. Os testes transversais também, sem mudanças em relação à rodada 2: migração, importação, inicialização, seed, avisos e varreduras.

| Medida | Valor |
|---|---:|
| Registros do original / inventário | 377 / 377 (367 HTTP + 10 fatos) |
| Registros do refatorado / inventário | 400 / 400 (383 HTTP + 17 fatos) |
| Comparados com a linha de base | 377 |
| Só no refatorado (declarados) | 23 |
| Preservados | 166 |
| Diferenças intencionais aprovadas | 211 |
| Falhas, regressões e problemas | 0 |
| Verificações do comparador | **43 = 37 mutações negativas (37 detectadas) + 6 controles positivos (6 aprovados)** |
| Meta-testes de ponta a ponta | 10 (1 controle + 9 alterações), todos com o comportamento esperado |

Os casos C-07 continuam aprovados como "intencional C-07" com o estado completo verificado:
- POST: original 500 `Erro ao criar usuário`, refatorado 409;
- PUT: original 500 `Erro ao atualizar`, refatorado 409.

Mais detalhes nos arquivos de resultado:

| Tema | Resultado | Arquivo |
|---|---|---|
| Migração | Falha induzida reverte a coluna; o controle ingênuo a mantém | `resultados/migracao/` |
| Importação, inicialização e seed | Iguais à rodada 2 | `resultados/cli.txt` |
| Avisos de runtime | Nenhum `DeprecationWarning` ou `LegacyAPIWarning` no refatorado | `resultados/avisos-runtime.txt` |
| Logs | F-05 só no original; 0 ocorrências no refatorado | `resultados/varredura-logs.txt` |
| Evidências | 0 arquivos com segredo | `resultados/varredura-evidencias.txt` |

## 5. Correção de contagem da rodada 2

Na rodada 2, as **30 verificações** do comparador são **26 mutações negativas + 4 controles positivos**, e não 30 mutações mais 4 controles. Uma nota com essa correção foi adicionada ao topo de `rodada-2/validation.md`; os resultados da rodada 2 não foram alterados.

## 6. Pendências e limitações

- O inventário cobre o conjunto atual de casos. Se a suíte ganhar ou perder casos, `inventario.json` precisa ser editado explicitamente (não há geração automática, de propósito).
- As demais pendências da rodada 2 continuam valendo: email com `\n` final aceito por preservação de contrato, `ResourceWarning` não investigado, downgrade após D-2a, migração fora do SQLite não validada, `Model.query` e riscos residuais do plano.

## 7. Arquivos da rodada 3

- `rodada-3/tools/`:
  - **novos:** `inventario.json`, `meta_tests.py`;
  - **alterados em relação à rodada 2:** `h.py`, `expect.py`, `compare.py`, `run_all.sh`;
  - **iguais:** `mig.py`, `scan_logs.py`.
- `rodada-3/resultados/`: resultados estruturados sanitizados por grupo e versão, `matriz.md`, `resumo.json`, `meta-testes.txt`, `inventario.sha256`, migração, CLI, avisos, varreduras, versões e trechos de F-05.
- `rodada-3/validation.md` (este arquivo).
