# Validação da Fase 3 — task-manager-api

> **Rodada 2 (2026-10-31):** uma revisão independente pediu correções no código e na suíte de testes. Seus resultados estão em [`rodada-2/validation.md`](rodada-2/validation.md). **Na rodada 3, foram corrigidos a exceção de C-07 no comparador, o inventário explícito de casos e a contagem de verificações; os resultados vigentes estão em [`rodada-3/validation.md`](rodada-3/validation.md).** Este arquivo registra a rodada 1. O conteúdo original foi mantido, com estas correções:
> - **Contagens da rodada 1, corrigidas:**
>   - 353 registros no total, sendo 333 comparados com a linha de base e 20 só no refatorado;
>   - dos 333 comparados, 154 foram preservados e 179 tiveram diferenças intencionais;
>   - 335 registros são requisições HTTP (tabela da seção 3) e 18 são fatos transversais.
>   - O texto anterior dizia "353 casos comparados + 20 só no refatorado", o que estava errado.
> - **Erros 500:** "nenhuma entrada de cliente produz 500" foi substituído por "nenhuma das entradas testadas gerou 500, fora as falhas de banco induzidas". A rodada 2 achou entradas não testadas na rodada 1 que geravam 500: inteiros fora da faixa do SQLite.
> - **Código mudado na rodada 2:**
>   - tags `0`, `false` e `0.0` no PUT agora geram 400 (o desvio 3 abaixo foi revertido);
>   - a cor passa a exigir correspondência integral;
>   - inteiros fora da faixa do SQLite são tratados;
>   - o cabeçalho `Allow` é preservado no 405;
>   - o PUT de recurso inexistente responde 404 antes de interpretar o corpo.
> - **Scripts:** os de `tools/` (rodada 1) ficaram não executáveis por causa da sanitização. Foram substituídos por `rodada-2/tools/`.

| Campo | Valor |
|---|---|
| Data | 2026-10-31 |
| Commit de referência | `f6eaae357672157858e16e4b58b49d0e6839a506` (working tree do alvo limpo antes da Fase 3, exceto `.claude/`) |
| Plano aprovado | `reports/audit-project-3.md`, revisão 3, gravado antes de alterar os fontes e não modificado depois (md5 `31374c5a78aade2114e8474803aa9f66`, idêntico ao documento aprovado) |
| Decisões | D-1(a), D-2(a), D-3(b), D-4(a), D-5(a), D-6(a) |
| Ambiente | Cópias isoladas em diretório temporário da sessão (`<tmp>/base/original`, `<tmp>/base/refatorado`), venv temporário. Nada foi executado no repositório. |
| Resultado (rodada 1) | 353 registros: 333 comparados + 20 só no refatorado (335 HTTP + 18 fatos). 154 preservados + 179 diferenças intencionais. **0 expectativas falhas, 0 regressões** com a suíte da rodada 1. Migração atômica comprovada com controle negativo. |

## 1. Versões instaladas (mesmas na linha de base e no refatorado)

Python 3.14.0. Flask 3.0.0, Flask-SQLAlchemy 3.1.1, Flask-Cors 4.0.0, **SQLAlchemy 2.1.6** (a auditoria estimou ≥ 2.0.16), Werkzeug 3.1.9, itsdangerous 2.2.0, marshmallow 3.20.1, requests 2.31.0, python-dotenv 1.0.0. Lista completa em `versions.txt`. `requirements.txt` não foi alterado.

## 2. Comandos executados (ordem)

1. `cp` do relatório aprovado → `reports/audit-project-3.md` (não existia; md5 conferido).
2. `python3 -m venv <tmp>/venv && <tmp>/venv/bin/pip install -r task-manager-api/requirements.txt`.
3. Cópia do original: `git ls-files | tar` → `<tmp>/base/original` (sem `.claude/`, sem banco).
4. Linha de base: `tools/run_groups.sh original seed_leitura vazio bordas tasks_escrita users_escrita categories_escrita auth ciclo_token rollback seed_falha` → 302 registros, 0 expectativas falhas.
5. Refatoração no `task-manager-api/` (seção 7).
6. Cópia do refatorado (`tar` excluindo `.claude`, `instance`, `__pycache__`) → `<tmp>/base/refatorado`.
7. `run_groups.sh refatorado <mesmos grupos>` → 0 expectativas falhas.
8. `compare.py out out/matriz.md`: testes negativos do comparador primeiro, depois a comparação.
9. Correções **do harness** (não do código) e nova execução dos grupos afetados nas duas versões (seção 6, D-8).
10. `tools/run_mig.sh`: migração de schema (falha induzida, controle ingênuo, normal, segunda execução, leitura pelo original).
11. `tools/run_cli.sh`: importação, inicialização, CLI do seed.
12. Grupo `tasks_escrita` com `python -W always` nas duas versões (avisos de runtime).
13. `tools/scan_logs.py`: varredura dos logs brutos antes da sanitização.
14. Gravação das evidências sanitizadas e varredura das evidências por segredos.

Os scripts estão em `tools/`, numa versão sanitizada (senhas de teste → `<removido>`). Os SHA-256 das versões executadas estão em `tools/SHA256SUMS-executados.txt`.

## 3. Matriz de endpoints (antes × depois)

Detalhe por caso, com status, mensagem de erro e classificação, em `matriz.md`.

| Método | Caminho | Casos | Status antes | Status depois | Preservados | Diferenças intencionais | Só no refatorado | Regressões |
|---|---|---:|---|---|---:|---:|---:|---:|
| GET | `/` | 1 | 200 | 200 | 1 | 0 | 0 | 0 |
| GET | `/health` | 1 | 200 | 200 | 1 | 0 | 0 | 0 |
| GET | `/tasks` | 3 | 200 | 200 | 3 | 0 | 0 | 0 |
| GET | `/tasks/<id>` | 6 | 200, 404 | 200, 404 | 5 | 1 | 0 | 0 |
| POST | `/tasks` | 74 | 201, 400, 404, 415, 500 | 201, 400, 404, 415, 500* | 33 | 41 | 0 | 0 |
| PUT | `/tasks/<id>` | 35 | 200, 400, 404, 500 | 200, 400, 404 | 19 | 16 | 0 | 0 |
| DELETE | `/tasks/<id>` | 2 | 200, 404 | 200, 404 | 2 | 0 | 0 | 0 |
| GET | `/tasks/search` | 17 | 200, 500 | 200, 400 | 14 | 3 | 0 | 0 |
| GET | `/tasks/stats` | 4 | 200 | 200 | 4 | 0 | 0 | 0 |
| GET | `/users` | 4 | 200 | 200 | 4 | 0 | 0 | 0 |
| GET | `/users/<id>` | 2 | 200, 404 | 200, 404 | 1 | 1 | 0 | 0 |
| POST | `/users` | 26 | 201, 400, 409, 500 | 201, 400, 401, 403, 409 | 9 | 17 | 0 | 0 |
| PUT | `/users/<id>` | 79 | 200, 400, 404, 409, 500 | 200, 400, 401, 403, 404, 409, 500* | 2 | 64 | 13 | 0 |
| DELETE | `/users/<id>` | 9 | 200, 404 | 200, 401, 403, 404 | 5 | 4 | 0 | 0 |
| GET | `/users/<id>/tasks` | 4 | 200, 404 | 200, 404 | 4 | 0 | 0 | 0 |
| POST | `/login` | 24 | 200, 400, 401, 403, 500 | 200, 400, 401, 403 | 16 | 8 | 0 | 0 |
| GET | `/reports/summary` | 3 | 200 | 200 | 3 | 0 | 0 | 0 |
| GET | `/reports/user/<id>` | 5 | 200, 404 | 200, 404 | 5 | 0 | 0 | 0 |
| GET | `/categories` | 3 | 200 | 200 | 3 | 0 | 0 | 0 |
| POST | `/categories` | 12 | 201, 400, 500 | 201, 400 | 5 | 7 | 0 | 0 |
| PUT | `/categories/<id>` | 16 | 200, 404, 500 | 200, 400, 404 | 4 | 12 | 0 | 0 |
| DELETE | `/categories/<id>` | 3 | 200, 404 | 200, 404 | 3 | 0 | 0 | 0 |
| GET | `/nao-existe` (rota inexistente) | 1 | 404 HTML | 404 JSON | 0 | 1 (M-03) | 0 | 0 |
| POST | `/` (método não permitido) | 1 | 405 HTML | 405 JSON | 0 | 1 (M-03) | 0 | 0 |

\* Os únicos 500 restantes vêm das **falhas forçadas pelo harness** (flush ou commit), que respondem com a mensagem da operação (`'Erro ao criar task'`, `'Erro ao atualizar'`), como especificado em 5.2.1. Nenhuma das entradas testadas na rodada 1 gerou 500 no refatorado, fora as falhas de banco induzidas. A rodada 2 encontrou entradas que geravam 500 (inteiros fora da faixa) e as corrigiu.

Diferenças intencionais por tipo (`matriz.md`, resumo): F-01: 36 · D-1a: 31 · C-01: 19 · C-06: 9 · R-04: 8 · R-01: 7 · C-02: 6+1 · R-03: 5 · C-10: 4 · C-03: 4 · M-02: 4+2 · R-08: 4 · C-05: 3 · C-08: 3 · M-03: 3 · R-02: 3 · R-05: 3+2 · R-06: 3 · R-09: 3 · C-04, C-07, M-01, M-04, R-07, F-06: 2 cada · C-09, D-2a: 1 cada · 415/400 de corpo em JSON: 2. Os 154 casos restantes foram preservados.

**Comparador.** Antes da comparação real, ele falhou como esperado para as 8 mutações: status, chave removida, `password` adicionada, mensagem de erro, contagem, ordem de lista, campo temporal fora do formato e cópia de resposta de outro endpoint. Com registros idênticos, classificou como "preservado". Cada caso trouxe uma expectativa escrita antes da execução; itens † ficaram como "medir" no original. A proteção contra execução vazia conferiu que nenhum caso da linha de base faltou no refatorado.

## 4. Resultados por tema

### 4.1 Itens † medidos na linha de base (original)

| Entrada | Original (medido) | Refatorado |
|---|---|---|
| Content-Type não JSON / JSON malformado | 415 / 400 em **HTML** | 415 / 400 `{'error': 'Dados inválidos'}` |
| `title` lista com 3+ itens | 500 `'Erro ao criar task'` | 400 `'Título inválido'` |
| `description` número / `true` | 201, gravado como `'5'` / `'1'` | 400 `'Descrição inválida'` |
| `description` lista / objeto | 500 | 400 |
| `priority` `true` | 201, gravado 1 | 400 `'Prioridade inválida'` |
| `priority` `2.0` | 201, gravado 2 | 201, gravado 2 (preservado) |
| `priority` `2.5` | 201, **gravado 2.5** | 400 |
| `priority` `NaN` (o parser aceita) | 201, **gravado NULL** | 400 |
| `priority` `±Infinity` | 400 com mensagem de faixa | 400 `'Prioridade inválida'` |
| `user_id` `"1"` / `true` | 201, vinculado ao usuário 1 | 400 `'Usuário inválido'` |
| `user_id` `-1` / `1.5` / `"abc"` | 404 | 400 |
| `user_id` lista / objeto | 500 | 400 |
| `tags` número / `true` | 201, `['5']` / `['1']` | 400 `'Tags inválidas'` |
| `tags` objeto | 500 | 400 |
| PUT `tags` `0` / `false` | 200, `['0']` | 200, `[]` (desvio D-3) |
| PUT `active` `0` / `null` | 200, gravado `false` / `null` | 400 `'Campo active inválido'` |
| PUT `active` `"x"` | 500 | 400 |
| PUT `name` número | 200, gravado `'5'` | 400 `'Nome inválido'` |
| Login: email número / `true` | 401, com 1 consulta | 401, **0 consultas** (M-05) |
| Login: email lista / objeto | **500 HTML** | 401, 0 consultas (C-08) |
| `DELETE /categories/1` com 6 tasks | `category_id` → NULL nas 6 (hipótese confirmada) | Idêntico (preservado) |
| Caminho efetivo do banco | `instance/tasks.db` | `instance/tasks.db` |
| Reutilização de ID no SQLite | Confirmada: excluir o maior ID e criar outro reutiliza o ID; o seed reinicia em 1 | (base do teste de token) |

### 4.2 Consultas por requisição (F-10, medido com `before_cursor_execute`)

| Endpoint | Original: seed (10 tasks) / bordas (7) / vazio | Refatorado |
|---|---|---|
| GET /tasks | 17 / 3 / 1 (limite teórico 21: o identity map evita parte, mas não todo o N+1) | 1 / 1 / 1 |
| GET /users | 4 / 3 / 1 | 1 / 1 / 1 |
| GET /categories | 5 / 3 / 1 | 1 / 1 / 1 |
| GET /reports/summary | 19 / 18 / 16 | 9 / 9 / 9 |

### 4.3 Controle de acesso e ciclo do token (D-1a)

Todos os casos com a expectativa atendida:
- Sem cabeçalho → 401 `'Token ausente'` com `WWW-Authenticate: Bearer`.
- 401 `'Token inválido'` para: `Bearer` sem token, `Basic`, dois espaços, token vazio, token adulterado, outra chave, token com mais de 4096 caracteres, e 11 payloads assinados com tipos inválidos (`uid` str/bool/0/negativo/inexistente, sem `sid`, `sid` curto/inválido/de outra conta, chave extra, lista).
- `bearer` em minúsculas é aceito.
- Token expirado (`TOKEN_MAX_AGE=1`, espera de 2,2 s) → 401 `'Token expirado'`.
- Toda a matriz de permissões passou (17 células). Conta inativa → 403 e volta a valer depois de reativada. Rebaixamento vale na requisição seguinte. Um admin pode excluir a si mesmo sendo o último admin (regra retirada, conforme aprovado).
- `POST /users`:
  - `Bearer` inválido num cadastro anônimo válido → 401, sem conta criada;
  - `Bearer` de conta excluída → 401;
  - `Bearer` de conta inativa → 403.
- **Reutilização de ID:** nos dois cenários, Y recebeu o mesmo ID de X (confirmado). O token antigo de X → 401, e Y ficou inalterado. Com Y admin, o token de X não herdou o privilégio (DELETE → 401). O token novo de Y funciona.
- **Novo seed:** o admin manteve o id 1 com outro `auth_nonce`. O token antigo → 401; o token novo → 200.
- **Troca de senha:**
  - T1 e T2 da mesma conta → 401 após a troca; a senha antiga → 401; a nova → token funcional;
  - admin troca a senha de outro → os tokens dele → 401, e o token do admin segue válido;
  - commit forçado a falhar → 500 `'Erro ao atualizar'`, hash e nonce inalterados, T1 continua válido.
- **MD5 legado (D-2a):** login aceito, hash regravado em formato werkzeug (scrypt), nonce mantido, token anterior válido.
- **Hashes malformados** (vazio, `abc`, werkzeug truncado, MD5 com 31 caracteres, MD5 em maiúsculas) → 401 nas duas versões.
- **`auth_nonce`:** nunca aparece como campo nas respostas (0 ocorrências em todas as respostas do refatorado; o original expõe `password` 87 vezes). Aparece só como `sid` dentro do token assinado de `/login`, como autorizado.

### 4.4 Migração `users.auth_nonce` (atomicidade no SQLite)

O banco base foi criado pela **versão original** (seed + categoria marcadora; `users` sem a coluna). Resultados de `logs/migracao.txt`:

| Cenário | Resultado |
|---|---|
| **Falha induzida** no 2º `secrets.token_urlsafe` (depois do `ALTER TABLE` e do 1º `UPDATE`) | `create_app()` propaga `RuntimeError`; **coluna ausente** depois da falha; snapshot de todas as tabelas e `sqlite_master` **idênticos** ao estado anterior. |
| **Controle negativo:** a mesma migração só envolvida em `engine.begin()` | Depois da mesma falha, a **coluna permanece** e o snapshot difere. Envolver em bloco de transação não basta (o driver sqlite3 em modo legado não abre transação antes de DDL), e o teste distingue as duas implementações. |
| Migração normal | Coluna criada; 3/3 usuários com nonce não nulo e distinto; dados preservados (fora a nova coluna); login do admin com MD5 legado → 200 e hash migrado; nonce não alterado pelo login. |
| Segunda inicialização | Nenhuma alteração: schema e nonces idênticos (idempotente). |
| Original lendo o banco migrado | `/users`, `/tasks`, `/categories` e `/reports/summary` idênticos (digest) à leitura do banco base. `/users/1` difere só porque o hash do admin foi migrado para werkzeug no passo anterior (o original expõe `password`). |

### 4.5 Erros, transações e sessão (F-15)

- Caso combinado `PUT /tasks/1` (título válido + prioridade 9): 400, e o GET mostra o título original **nas duas versões**. O original descarta a alteração no teardown, como corrigido em F-15.
- Conflito de email forçado no commit (linha inserida por outra conexão em `before_flush`):
  - original → 500 `'Erro ao criar usuário'` / `'Erro ao atualizar'`;
  - refatorado → 409 `'Email já cadastrado'` (C-07);
  - a requisição seguinte → 200 (recuperação da aplicação).
- **Mesma sessão** (refatorado, um único `app_context`):
  - `ConflictError('Email já cadastrado')`;
  - `db.session()` é o mesmo objeto;
  - `is_active` verdadeiro;
  - o `commit_or_rollback` seguinte persistiu o registro (confirmado por conexão separada).
- Falha forçada de flush → 500 `'Erro ao criar task'` nas duas versões, contagens inalteradas, e a requisição seguinte → 201.

### 4.6 Seed (F-06, D-5a)

| Cenário | Original | Refatorado |
|---|---|---|
| Execução normal pela CLI | exit 0; 3/4/10; 5 `DeprecationWarning` de `utcnow` | exit 0; 3/4/10; sem avisos |
| Falha induzida na 5ª task (banco com seed + marcadores) | Exceção; **perda de dados**: antes 3 usuários, 5 categorias, 11 tasks; depois 3, 4, 0 (marcadores e tasks perdidos) | Exceção; snapshot **idêntico** (contagens, IDs, nonces, marcadores) |
| Sem `SEED_USER_PASSWORD` | n.a. | exit 1; mensagem só com o nome da variável; snapshot idêntico |
| Sem `SECRET_KEY` | n.a. | exit 2; snapshot idêntico |

### 4.7 Importação e inicialização (F-08, F-09, F-03)

- **Importação** (`python -I -B -c 'sys.path.insert(0, <cópia>); import app'`, sem `SECRET_KEY`, conferindo `app.__file__`):
  - original → importa e **cria `instance/tasks.db`**;
  - refatorado → importa sem criar arquivos.
  - Controle: `python -I -c 'import app'` sem inserir o caminho → `ModuleNotFoundError` (exit 1). O harness trata esse caso como falha de importação, não como "sem efeitos".
- **Sem `SECRET_KEY` ou com chave curta:** exit 2, `Erro de configuração: SECRET_KEY ausente ou com menos de 32 caracteres`, nenhum `instance/tasks.db` criado.
- **`python app.py`:**
  - refatorado → `Debug mode: off`, escuta em `127.0.0.1:<porta>`, `/health` 200;
  - original → `Debug mode: on`, `Running on all addresses (0.0.0.0)`, `Debugger is active!`.
  - Os processos foram encerrados e as portas liberadas (`logs/inicializacao.txt`).

### 4.8 Logs (F-05, F-18) — varredura dos logs brutos antes da sanitização

| Padrão | Original | Refatorado | Migração/CLI |
|---|---:|---:|---:|
| `parameters:` | 10 | 0 | 0 |
| Hash MD5 de senha | 2 | 0 | 0 |
| Hash werkzeug, senhas de teste, tokens emitidos (1679 verificados), nonces, `SECRET_KEY` | 0 | 0 | 0 |

**F-05 confirmado no original.** Num conflito de email no commit, o `print(f"ERRO: {str(e)}")` grava `[parameters: (..., '<hash md5>', ...)]` (trecho sanitizado em `logs/f05-conflito-commit.txt`). No refatorado, o mesmo cenário registra só `Conflito de unicidade de email em "<operação>"`.

Avisos de runtime (`tasks_escrita`, `-W always`): original com 3613 `DeprecationWarning` (`utcnow`) e 160 `LegacyAPIWarning` (`Query.get`); refatorado com 0 e 0. As duas versões emitem 1 `ResourceWarning: unclosed database`, não investigado (provavelmente conexões do harness ou do pool no encerramento).

## 5. Nova inspeção (catálogo reaplicado ao código refatorado)

| Achado | Situação | Evidência |
|---|---|---|
| F-01 hash nas respostas | **Corrigido** | `User.to_dict` sem `password`/`auth_nonce`; 87 → 0 ocorrências nas respostas |
| F-02 MD5 sem sal | **Corrigido** | werkzeug (scrypt); MD5 só para verificar e migrar o legado (D-2a), com `hmac.compare_digest` |
| F-03 segredos fixos | **Corrigido no código** | `SECRET_KEY` obrigatória no ambiente; SMTP removido; senhas do seed vindas do ambiente. **Remanescente:** os valores antigos seguem no histórico do git e devem ser trocados se forem reais |
| F-04 contas sem autenticação | **Corrigido** (D-1a) | 4.3. Remanescente documentado: leituras e CRUD de tasks/categorias continuam públicos |
| F-05 parâmetros SQL no log | **Confirmado no original e corrigido** | 4.8 |
| F-06 seed não atômico | **Corrigido** | 4.6 |
| F-07 regras nas rotas | **Corrigido** | `routes/` só extrai a requisição e serializa; casos de uso em `controllers/`; regras e consultas em `models/` |
| F-08 efeitos na importação | **Corrigido** | 4.7; `create_app()` só sob `__main__` |
| F-09 debug e 0.0.0.0 | **Corrigido** | 4.7 |
| F-10 N+1 | **Corrigido** | 4.2 |
| F-11 validação | **Corrigido** | 5.3.1 aplicada; nenhuma das entradas testadas gerou 500 (seção 3; ver rodada 2) |
| F-12 regras duplicadas | **Corrigido** | Atraso só em `Task.is_overdue`; constantes únicas; `utils/helpers.py` removido. Diferenças de mensagem entre POST e PUT preservadas de propósito |
| F-13 `Query.get` | **Corrigido**; parcial quanto à interface | `db.session.get` em `find_by_id`; 160 → 0 `LegacyAPIWarning`. **Remanescente:** `Model.query.filter_by/order_by` (interface que o Flask-SQLAlchemy chama de legada, sem aviso) continua em `models/` |
| F-14 `utcnow` | **Corrigido** | `models/clock.utc_now`; 3613 → 0 avisos |
| F-15 erros dispersos | **Corrigido** | `errors.py` com handlers centrais; `commit_or_rollback`; 409 no conflito; 4.5 |
| F-16 código morto | **Corrigido** | `services/` e `utils/` removidos; imports sem uso eliminados. `requirements.txt` mantido (marshmallow, requests e python-dotenv seguem sem uso, conforme o plano) |
| F-17 literais | **Corrigido** | Constantes em `models/` e `controllers/report_controller.py` |
| F-18 `print` | **Corrigido** | `logging`, só com IDs; os `print` restantes estão em `seed.py` (saída de CLI, excluída na auditoria) |
| F-19 nomes | **Corrigido** nos identificadores reescritos | |

Busca no código refatorado: nenhuma ocorrência de `.query.get(`, `utcnow`, `except:`, `debug=True`, `0.0.0.0`, `super-secret`, `smtplib` ou `str(e)`. `py_compile` OK em todos os módulos.

**Problemas novos ou remanescentes (não corrigidos):** endpoints públicos fora de F-04 (inclusive `GET /users` com emails); CORS `*` por padrão; sem limite de tentativas de login; tokens só são revogados por troca de senha ou expiração; `status` não validado em `/tasks/search` (mantido); a migração manual cobre só `users.auth_nonce`.

## 6. Desvios em relação ao plano aprovado

1. **Ordem das verificações em `PUT /users`.** O plano (5.5.1) lista "validação (400) → unicidade (409)". Mantive a ordem do original, campo a campo, com o 409 na etapa do email, para preservar o contrato quando há email duplicado e outro campo inválido no mesmo corpo. Autenticação → 404 → corpo → autorização seguem antes, como no plano.
2. **`POST /tasks` com `title` lista de menos de 3 itens:** passa de `'Título muito curto'` para `'Título inválido'` (400 → 400; classificado C-02/M). O plano não fixava essa mensagem.
3. **`PUT /tasks` com `tags` `0`/`false`:** o original grava `'0'` (lido como `['0']`); o refatorado trata valor falso como "sem tags" (`[]`), como o POST. Classificado R-05/M.
4. **Mensagens de 404/405 do framework:** o plano não fixava o texto. Usei `'Recurso não encontrado'` e `'Método não permitido'`; 400/415 de corpo → `'Dados inválidos'`.
5. **Login:** quando a conta não tem `auth_nonce` (criada pela versão antiga num banco já migrado), o nonce é gerado e confirmado antes de emitir o token; falha nesse commit → 500 `'Erro interno'`.
6. **Teste da fronteira exata de 7 dias** com relógio controlado no refatorado: **não executado**. A janela foi verificada com fixtures em −6 e −8 dias.
7. **`GET /reports/user/<id>`:** `high_priority` ignora tasks com `priority` nulo. No original, isso geraria `TypeError` (dado corrompido, por exemplo o NaN gravado como NULL).
8. **Correções no harness durante a validação** (o código da aplicação não mudou por causa delas):
   - a linha de "corrida" inserida sem `created_at` gerava `'None'` nas duas versões;
   - um PUT só do refatorado alterava o nome usado no caso seguinte;
   - os fatos de D-2a e F-06 receberam classificação.

   Os grupos afetados foram reexecutados nas **duas** versões.
9. **Armadilhas encontradas e corrigidas na validação:**
   - `python -I script.py` também impede o diretório do script em `sys.path`. Na 1ª tentativa, os testes de inicialização sem `SECRET_KEY` "passaram" por `ModuleNotFoundError`. Detectei isso pela mensagem, e os testes de CLI passaram a usar `python -B`.
   - O ambiente tem proxy HTTP: o `curl` precisou de `--noproxy '*'`.
   - O reloader do original deixou um processo na porta 5000 na 1ª tentativa; foi encerrado e o teste refeito com encerramento por grupo de processos.
10. **Efeitos colaterais no repositório, já desfeitos:**
    - `git rm` de `services/` e `utils/` havia colocado as exclusões no índice; desfeito com `git restore --staged` (as exclusões ficam só no working tree);
    - `py_compile` criou `__pycache__/` no `task-manager-api/` (ignorados pelo `.gitignore`); removidos.

## 7. Arquivos alterados (working tree, sem commit)

- **Modificados:** `app.py`, `database.py`, `seed.py`, `README.md`, `models/{task,user,category}.py`, `routes/{task,user,report}_routes.py`.
- **Novos:** `config.py`, `errors.py`, `auth.py`, `models/clock.py`, `controllers/{__init__,validation,task_controller,user_controller,category_controller,report_controller}.py`, `routes/{category,system}_routes.py`, `.env.example`.
- **Removidos:** `services/__init__.py`, `services/notification_service.py`, `utils/__init__.py`, `utils/helpers.py`.
- **Relatórios:** `reports/audit-project-3.md` (plano aprovado, sem alterações) e `reports/evidence/task-manager-api/` (este diretório).

## 8. Limitações

- Python 3.14.0 e SQLAlchemy 2.1.6 instalados; outras versões não foram testadas.
- A migração para bancos que não são SQLite (`_migrate_transactional`) não foi validada.
- **Downgrade:** o original lê o banco migrado, mas não autentica contas cujo hash já foi migrado para werkzeug (D-2a); essas contas exigiriam redefinição de senha.
- A fronteira de 7 dias não foi testada com relógio controlado (desvio 6).
- O `ResourceWarning` presente nas duas versões não foi investigado.
- Os scripts em `tools/` estão sanitizados e não rodam como estão; os executados ficam identificados pelo SHA-256.
- Os testes usaram o cliente de teste do Flask e, na inicialização, o servidor de desenvolvimento; não houve teste com servidor WSGI de produção.
