# Validação — rodada 2 (task-manager-api)

> **Nota da rodada 3 (2026-10-31).** Correções nesta rodada:
> - **Contagem:** as 30 verificações do comparador relatadas abaixo são **26 mutações negativas + 4 controles positivos**. Não são 30 mutações mais 4 controles.
> - **C-07:** o comparador desta rodada aprovava mutações do estado posterior quando o caso era classificado como C-07.
> - **Inventário:** não havia um inventário explícito de casos.
>
> As correções e os novos resultados estão em [`../rodada-3/validation.md`](../rodada-3/validation.md). O restante deste arquivo e os resultados da rodada 2 foram preservados.

| Campo | Valor |
|---|---|
| Data | 2026-10-31 |
| Motivo | Correções pedidas por revisão independente antes do commit |
| Plano aprovado | `reports/audit-project-3.md`, sem alterações (md5 `31374c5a78aade2114e8474803aa9f66`) |
| Código original | `BASE_REF=f6eaae357672157858e16e4b58b49d0e6839a506` (via `git archive`) |
| Rodada 1 | Mantida em `../validation.md`, `../matriz.md`, `../logs/` e `../tools/`, com as contagens corrigidas no topo de `../validation.md` |
| Resultado | **APROVADO**: `tools/run_all.sh` saiu com código 0 (`resultados/resultado-final.txt`) |

## 1. Como reproduzir

```bash
# na raiz do repositório; cria venv temporário (exige rede) ou usa VENV=<venv com requirements>
reports/evidence/task-manager-api/rodada-2/tools/run_all.sh            # grava em rodada-2/resultados
reports/evidence/task-manager-api/rodada-2/tools/run_all.sh /outro/dir # ou em outro diretório
```

O script `run_all.sh`:
1. cria um diretório temporário com `mktemp -d`;
2. extrai o original com `git archive $BASE_REF` e copia o refatorado do working tree, sem `.claude`, `instance` e `__pycache__`;
3. gera a cada execução uma `SECRET_KEY` e senhas `SEED_*` fictícias;
4. roda os 13 grupos nas duas versões, os avisos de runtime, a migração, a importação, a inicialização, a CLI do seed, o comparador e as varreduras de segredos;
5. copia para a saída só os resultados sanitizados;
6. encerra os processos e remove o diretório temporário (`KEEP_TMP=1` mantém).

O código de saída é diferente de zero se qualquer etapa falhar.

**Credenciais.** Nenhuma senha está escrita nos scripts:
- no original, o harness lê as credenciais do `seed.py` da cópia, via `ast`;
- no refatorado, das variáveis `SEED_*` geradas pelo runner;
- as senhas de cenário (nova, outra, cadastro, errada, nova2) são aleatórias e distintas entre si e das do seed;
- nos resultados, as senhas aparecem só como rótulos (`<senha:nova>`) e os tokens como `<token>`/`<fake-token>`.

Os scripts estão em `tools/`:

| Arquivo | Função |
|---|---|
| `run_all.sh` | Orquestra a execução |
| `h.py` | Harness |
| `expect.py` | Expectativas declarativas e verificações globais |
| `compare.py` | Comparador |
| `mig.py` | Testes de migração |
| `scan_logs.py` | Varredura de segredos |

## 2. Correções no código (rodada 2)

| Item da revisão | Correção | Arquivos |
|---|---|---|
| PUT `tags` `0`/`false`/`0.0` | O PUT só aceita `null`, `""` e `[]` como limpeza; qualquer outro valor que não seja str ou lista de str → 400 `'Tags inválidas'`, validado antes de alterar a sessão (tags e `updated_at` inalterados). O POST mantém "valor falso = sem tags", como no original e no plano. | `controllers/task_controller.py` |
| Cor `"#123456\n"` | `COLOR_PATTERN.fullmatch`. Pela mesma razão, `fullmatch` também no `sid` do token e no padrão de MD5 legado. | `models/category.py`, `auth.py`, `models/user.py` |
| Inteiros fora da faixa do SQLite | `fits_integer_column` (−2^63 … 2^63−1) em `find_by_id` de Task, User e Category e nos filtros de `Task.search`. | `database.py`, `models/*.py` |
| `Allow` no 405 | O handler de `HTTPException` copia `error.get_headers()`, exceto `Content-Type` e `Content-Length`. | `errors.py` |
| 404 antes do corpo | Os PUT de task, usuário e categoria recebem `request.get_json` como carregador e só o chamam depois de localizar o recurso. Em `/users`, a autenticação vem antes. | `routes/*_routes.py`, `controllers/*_controller.py` |

**Contrato adotado para inteiros fora da faixa:**

| Onde | Comportamento |
|---|---|
| IDs no caminho | 404 com a mensagem do recurso. Em rotas protegidas, a autenticação continua antes: anônimo → 401. |
| Referências no corpo (`user_id`/`category_id`) | Um inteiro ≥ 1 continua válido em formato. Se estiver fora da faixa, não pode existir → 404 `'Usuário não encontrado'`/`'Categoria não encontrada'`, como qualquer ID inexistente. Tipos inválidos continuam 400 (R-04/M-02). |
| Filtros de busca (`priority`, `user_id`) | Um inteiro aceito por `int()` continua válido. Fora da faixa, não casa com nenhuma linha → 200 `[]`. Não inteiro continua 400 (C-05). |
| `uid` do token | Fora da faixa → 401 `'Token inválido'`, como uid inexistente. |
| Prioridade no corpo | Inalterado: um valor fora da faixa de 1 a 5, inclusive 2^63, recebe 400 com a mensagem de faixa. |

No original, todos esses casos de ID e filtro geravam 500 (`OverflowError`, medido). Classificação: **C-12**, uma correção nova da rodada 2.

## 3. Suíte e comparador (rodada 2)

- **Expectativas independentes e declarativas** (`expect.py`), gravadas em cada registro e **reavaliadas pelo comparador**. Verificam:
  - status, mensagem, valores exatos (`has`), ausência de campos (`lacks`), conjunto exato de chaves, IDs em ordem e contagens;
  - estado do banco: digest antes e depois (`unchanged`/`changed`) e leituras posteriores;
  - número de consultas (`max_queries`).
  - As leituras do seed e das bordas são conferidas campo a campo, a partir da definição das fixtures.
- **Datas verificadas antes de normalizar:**
  - valores relativos ao instante da requisição (prazo ≈ −3 dias, `created_at` ≈ agora, `generated_at` ≈ agora, `/health` no relógio local) e valores literais (`'2030-01-15 00:00:00'`);
  - em todo registro: `updated_at ≥ created_at` e janela plausível.
- **Campos públicos proibidos:** `password` e `auth_nonce` reprovam qualquer registro do refatorado, inclusive os classificados como intencionais.
- **Uma expectativa falha reprova o caso** mesmo quando as duas respostas são idênticas (há teste negativo para isso).
- **Classificações restritas:**
  - **Folhas globais aprovadas:** remoção de `password` (F-01), formato do `token` (D-1a) e tipo do hash gravado (F-02).
  - **Classes de rejeição ou correção** (C-*, R-*, M-01/02/04, D-1a com status ≥ 400): as diferenças só valem se a expectativa do refatorado for forte (status + mensagem/valores e, em escrita, banco inalterado ou estado posterior verificado).
  - **D-1a** só aprova negação de acesso.
  - **M-03:** só o formato do corpo pode mudar; `Allow` precisa ser igual.
  - **D-2a/F-06:** só o valor do fato pode mudar, com expectativa por versão.
- **Verificações do comparador** sobre registros reais, inclusive de casos intencionais (F-01, R-05 e D-1a): 30 no total, sendo 26 mutações negativas (todas detectadas) e 4 controles positivos (todos aprovados).
  - Mutações aplicadas: identidade errada, nome incorreto, `password` exposto, `auth_nonce` exposto, campo removido, contagem errada, banco não alterado ou alterado indevidamente, hash fraco, data incoerente, mensagem errada, status trocado, expectativa enfraquecida, `WWW-Authenticate` ausente, ordem alterada, prazo errado com formato válido, cópia de outro endpoint, classe inventada, e expectativa falha com respostas idênticas.
  - Os 4 controles sem mutação passaram.
- **Robustez:** o comparador e os scripts saem com código 1 em caso de falha. São rejeitados: resultado ausente, execução vazia, nomes duplicados, caso da linha de base ausente no refatorado e caso exclusivo não declarado.

## 4. Resultados (calculados de `resultados/resumo.json`)

| Medida | Valor |
|---|---:|
| Registros do original | 377 (367 HTTP + 10 fatos) |
| Registros do refatorado | 400 (383 HTTP + 17 fatos) |
| Comparados com a linha de base | 377 |
| Só no refatorado (declarados) | 23 (16 HTTP + 7 fatos) |
| Preservados | 166 |
| Diferenças intencionais aprovadas | 211 |
| Falhas, regressões e problemas | 0 |
| Verificações do comparador | 30 = 26 mutações (26 detectadas) + 4 controles (4 aprovados) |

Diferenças intencionais por classe:

| Classes | Casos |
|---|---:|
| D-1a | 32 |
| F-01 | 32 |
| F-01 + F-02 | 4 |
| F-01 + D-1a (token) | 2 |
| C-01 | 19 |
| C-12 | 17 |
| C-06 | 9 |
| C-JSON (400/415 em JSON) | 8 |
| R-04 | 8 |
| C-02, R-01 | 7 cada |
| R-05 | 6 |
| M-03, R-03, R-09 | 5 cada |
| C-03, C-10, M-02, R-08 | 4 cada |
| C-04, C-05, C-08, R-02, R-06 | 3 cada |
| C-07, C-11, F-06, M-01, M-04, R-07 | 2 cada |
| C-09, D-2a | 1 cada |

Por grupo (original/refatorado): `seed_leitura` 35/35, `vazio` 6/6, `bordas` 12/12, `tasks_escrita` 118/118, `users_escrita` 65/65, `categories_escrita` 33/33, `auth` 33/49, `ciclo_token` 29/32, `rollback` 6/10, `seed_falha` 4/4, `bigint` 16/16, `http` 19/19, `fronteira7` 1/1. Todos sem falha nas duas versões.

**Erros 500.** Nenhuma das entradas testadas gerou 500 no refatorado. Os únicos 500 vêm de **duas falhas de banco induzidas pelo harness** (`senha: commit falha (induzida)` e `falha forçada de flush POST /tasks (induzida)`), que respondem com a mensagem da operação e não alteram o banco.

**Itens da revisão verificados** (detalhe em `resultados/matriz.md`):
- **PUT `tags`:**
  - `0`, `false` e `0.0` → 400 `'Tags inválidas'`, banco inalterado e GET posterior com as tags anteriores (no original, 200 gravando `['0']`);
  - `{}` → 400 (no original, 500);
  - `null`, `""` e `[]` → 200 com `[]`;
  - no POST, `tags: 0` → 201 sem tags (preservado).
- **Cor `"#123456\n"`:** POST e PUT → 400 `'Cor inválida'`, banco inalterado (no original, 201/200 gravando o valor).
- **Inteiros 2^63:**
  - 10 rotas com ID no caminho → 404;
  - `user_id`/`category_id` no corpo (POST e PUT) → 404;
  - 4 filtros de busca → 200 `[]`;
  - `uid` 2^63 e −2^63−1 no token → 401;
  - controles dentro da faixa (2^63−1) → 404/`[]` nas duas versões.
- **405:** `Allow` idêntico ao do original em `POST /`, `DELETE /tasks` e `PATCH /tasks/1`, agora com corpo JSON.
- **404 antes do corpo:** PUT de task, categoria e usuário inexistentes, com JSON malformado e com Content-Type texto → 404 nas duas versões. Com recurso existente → 400/415 `'Dados inválidos'`. `PUT /users` anônimo → 401 antes de qualquer outra verificação.
- **Fronteira de 7 dias com relógio fixo** (`T` = agora − 1 h, sem microssegundos; no original, `routes.report_routes.datetime` substituído; no refatorado, `controllers.report_controller.utc_now`). Nas duas versões:
  - criadas em T−7d−1µs / T−7d / T−7d+1µs → 2 contadas;
  - concluídas com `updated_at` nos mesmos instantes → 2 contadas;
  - prazo = T não está atrasado; prazo = T−1µs está atrasado (`days_overdue` 0);
  - `generated_at` = `str(T)`.

**Testes transversais** (reexecutados com o código corrigido):
- **Migração** (`resultados/migracao/`):
  - falha induzida no 2º gerador → coluna ausente, snapshot e schema idênticos;
  - controle ingênuo com `engine.begin()` → coluna permanece;
  - migração normal → 3 nonces distintos, dados preservados, login com MD5 legado → 200 e hash migrado;
  - segunda execução → nada muda;
  - o original lê o banco migrado de forma idêntica, exceto `/users/1`, por causa do hash migrado.
- **Importação, inicialização e seed** (`resultados/cli.txt`):
  - importar o refatorado não cria arquivos; o original cria o banco;
  - sem `SECRET_KEY` ou com chave curta → exit 2, sem banco;
  - o refatorado sobe com debug desligado em 127.0.0.1;
  - o original sobe com debugger em 0.0.0.0:5000;
  - seed sem variável → exit 1 e banco idêntico.
- **Avisos** (`resultados/avisos-runtime.txt`): no original, 3878 `DeprecationWarning` e 171 `LegacyAPIWarning`; no refatorado, nenhum dos dois.
- **Logs** (`resultados/varredura-logs.txt`):
  - no original, F-05 se confirma de novo: o MD5 da senha de cadastro aparece em `[parameters: …]`, com 2 ocorrências de segredo anotado e 10 de `parameters:`;
  - refatorado, migração, CLI e avisos do refatorado: 0 ocorrências em todos os padrões;
  - nas evidências gravadas, 0 arquivos com segredo anotado.

## 5. Correções na suíte durante a rodada 2

1. `GROUPS` era uma variável interna do bash (IDs de grupo), e a primeira execução rodou um grupo chamado `1000`. Renomeado para `GRUPOS`; o runner já marcou a execução como reprovada.
2. A expectativa de `completion_rate` para usuário com tasks e nenhuma concluída estava como `0`; o valor real nas **duas** versões é `0.0` (`round(0.0, 2)`). A expectativa foi corrigida; o código não mudou.
3. No conflito forçado (C-07), o próprio harness insere a linha concorrente, então "banco inalterado" é impossível. A regra de expectativa forte passou a aceitar verificações explícitas do estado posterior (`post.*`); o caso verifica contagem e email.
4. A varredura das evidências passou a procurar também o MD5 de cada senha anotada, em vez da string `parameters:`. O trecho de F-05 já sanitizado era um falso positivo.

## 6. Pendências e limitações reais

- **Email com `\n` final:** a regex de email mantém o `re.match` com `$` do original. `"a@b.com\n"` continua aceito, por preservação de contrato; a correção não foi pedida nem aprovada.
- **`ResourceWarning: unclosed database`:** 1 ocorrência no refatorado e várias no original, no harness com `-W always`. Não foi investigado.
- **Downgrade:** o original não autentica contas cujo hash já foi migrado para werkzeug (D-2a).
- **Migração fora do SQLite** (`_migrate_transactional`): não validada.
- **`Model.query`** (interface legada sem aviso) continua em `models/`.
- **Riscos residuais do plano:** leituras e CRUD de tasks e categorias são públicos; CORS `*`; não há limite de tentativas de login.
- **Arquivo da revisão:** `revisao-projeto-3.tar.gz`, na raiz do repositório, não foi criado nem alterado nesta rodada.
- **Testes:** foram feitos com o cliente de teste do Flask e o servidor de desenvolvimento; não houve teste com servidor WSGI de produção.

## 7. Arquivos

- **Código alterado na rodada 2** (working tree, sem commit): `auth.py`, `database.py`, `errors.py`, `models/{task,user,category}.py`, `controllers/{task,user,category}_controller.py`, `routes/{task,user,category}_routes.py`.
- **Evidências:**
  - `rodada-2/validation.md` (este arquivo);
  - `rodada-2/tools/`;
  - `rodada-2/resultados/`, com resultados estruturados por grupo e versão, matriz, resumo, migração, CLI, avisos, varreduras, versões e trechos de F-05.
