# Validação da Fase 3 — ecommerce-api-legacy

- Data: 2026-10-31
- Commit de referência: `209d251268b702c9dbb76e5d32139d861ed48889` (linhas do relatório referem-se a ele)
- Relatório de auditoria (histórico, não alterado por esta validação): `reports/audit-project-2.md`
- Decisões aplicadas: `decisions.md` — D-1(b), D-2(b), D-3(b), D-4(a), D-5(a), D-6(b); C-1 a C-8 nas formas aplicáveis
- Comandos: `commands.md` · Versões: `versions.txt` · Matriz: `matriz.md` · Inspeção: `inspecao.txt` · Logs: `logs/`
- Atualização posterior (revisão independente): comparador corrigido e matriz reexecutada — ver §3.1
- Scripts reutilizáveis: `tools/` (geram cartões, senhas e tokens de teste em tempo de execução)

## 1. Ambiente

| Item | Original (linha de base) | Refatorado |
|---|---|---|
| Local | cópia em diretório temporário fora do repositório | cópia em diretório temporário fora do repositório |
| Node.js / npm | v20.20.0 / 10.8.2 (runtime global) | idem |
| express (instalada) | 4.22.1 (declarada ^4.18.2) | 4.22.1 |
| sqlite3 (instalada) | 5.1.7 (declarada ^5.1.6) | 5.1.7 |
| Banco | `:memory:` por instância | `:memory:` por instância |
| Integrações externas | nenhuma real (gateway simulado; chave hardcoded só era logada) | nenhuma |

O original tem a chave do gateway hardcoded: variável de ambiente não a substitui, e o original gravou cartão e chave em
stdout. Esses logs brutos ficaram apenas no diretório temporário; os trechos preservados em `logs/` foram sanitizados.

## 2. Estrutura resultante

```
ecommerce-api-legacy/
├── .env.example            (novo)      README.md (atualizado)      api.http (cabeçalho X-Admin-Token)
└── src/
    ├── app.js              composition root: createApp(dataAccess, { adminToken, models }) + start()
    ├── config.js           loadConfig(): PORT, ADMIN_TOKEN, SEED_USER_PASSWORD (obrigatória), validação
    ├── database.js         openDatabase/closeDatabase, fila exclusiva (read/transaction), handle expirável, initSchema
    ├── errors.js           HttpError
    ├── passwordHash.js     scrypt com sal
    ├── models/             userModel, courseModel, enrollmentModel, paymentModel, auditLogModel,
    │                       financialReport, checkoutValidation
    ├── controllers/        checkoutController, reportController, userController, dbErrors (helper)
    ├── routes/             checkoutRoutes, adminRoutes, userRoutes
    └── middlewares/        asyncHandler, errorHandler, requireAdminToken
```

Removidos: `src/AppManager.js`, `src/utils.js`. 22 arquivos, 518 linhas físicas.

Desvios em relação ao plano (5.1), sem efeito em contrato:
- `PAYMENT_GATEWAY_KEY` **não** foi criada: o único uso da chave era o log removido (F-02); o gateway é simulado e não
  há consumidor. Criar a variável deixaria configuração morta (AP-19).
- `controllers/dbErrors.js`: helper de 13 linhas que converte erro inesperado de banco em `HttpError(500, <mensagem>)`,
  usado pelos três controllers para preservar as mensagens existentes (`Erro DB`, `Erro Matrícula` etc.).
- Validação adicional não listada em C-4: `c_id` que não seja número nem string (ex.: objeto) → 400 `Bad Request`;
  `PORT` inválida → encerramento com mensagem clara (P-07). Strings não numéricas em `c_id` continuam aceitas e resultam
  em 404, como no original.

## 3. Matriz de endpoints antes × depois

Detalhe completo em `matriz.md` (gerado por `tools/compare.js`). Mesmas entradas nos dois lados; 25 casos;
**0 reprovações, 0 avisos** com o comparador corrigido (§3.1). Matriz reexecutada após a correção, em cópias isoladas
novas (original extraído do commit de referência com `git archive`; refatorado copiado do working tree).

### 3.1 Correção do comparador (revisão independente)

A revisão independente confirmou um **falso negativo** na versão anterior de `tools/compare.js`: toda diferença em um caso
listado em `INTENTIONAL` era aceita apenas pela justificativa — alterar S1-01 para HTTP 500 produzia exit 0 e
"0 regressões". O resultado "0 regressões" relatado antes desta correção não tinha essa garantia.

Comparador atual:
- **Expectativas explícitas por caso** (`EXPECTATIONS`) para o refatorado: status, content-type, corpo exato (relatórios
  inclusive), efeito em **todas** as tabelas (depois − antes) e campos observados (`usersWithEmail`, `usersPerTrial`…).
  Uma justificativa não autoriza mais nenhuma diferença por si só.
- **Relação com a linha de base**: `same` (registro idêntico), `same-unordered` (idêntico ignorando **somente** a ordem
  dos cursos e a ordem dos alunos dentro de cada curso — C-7; a normalização é feita sobre cópias, preserva conteúdo e
  multiplicidade, e não altera os registros recebidos), `differs` (correção intencional) e `observation` (não determinístico).
- **Ordem determinística no refatorado**: a folga de ordenação vale apenas na relação com o original. Contra
  `EXPECTATIONS` o corpo do refatorado é comparado de forma exata, então ele continua obrigado a apresentar cursos por id
  e alunos por id da matrícula.
- **Comportamento antigo**: casos de correção têm uma assinatura explícita do comportamento antigo (ex.: S1-13 status 200
  ou usuário removido; B-T1 escrita mantida; S1-03 usuário criado na recusa; C-OBS1 usuário duplicado). O refatorado é
  reprovado se exibi-la, **mesmo que coincida com a linha de base**; a linha de base é reprovada se não a exibir
  (a comparação perderia sentido; em `observation`, gera aviso).
- Reprovam também: caso ausente em qualquer lado, registro de erro de execução (`*-ERRO` ou campo `error`), caso duplicado
  e caso sem expectativa definida. A CLI sai com código 1 em qualquer reprovação.

Ajuste posterior (segunda revisão independente): a versão com 15 testes reprovava S5-01 com resultados reais em que o
original devolveu os alunos de Docker como `[Aluno Recusado, Unknown, Leonan]` e o refatorado como
`[Aluno Recusado, Leonan, Unknown]` — mesmos dados, só a ordem dos alunos diferia (**falso positivo**). O original ordena
pela conclusão dos callbacks, então essa ordem não é determinística; C-7 autoriza a ordem por curso e por matrícula. A
normalização da relação `same-unordered` passou a incluir os alunos.

Testes do comparador (`tools/compare.test.js`, `logs/testes-comparador.log`) — **18 testes, 18 passaram**:

| Cenário adulterado | Resultado exigido | Obtido |
|---|---|---|
| resultados válidos (sem adulteração) | aprova, 0 reprovações/avisos; CLI exit 0 | aprovado |
| S1-01 com HTTP 500 (cenário da revisão), via CLI | exit 1, `status 500` | reprovado |
| HTTP 500 inesperado em S1-01 e S1-13 | reprova por status | reprovado |
| receita incorreta (S1-06 Docker +1; S5-01 somando DENIED) | reprova por corpo | reprovado |
| escrita mantida após rollback (B-T1 users/enrollments +1; B-T2 payments +1) | reprova por efeito e por comportamento antigo | reprovado |
| caso ausente no refatorado (S1-02) e na linha de base (B-T4) | reprova | reprovado |
| erro de execução (`S1-ERRO`; campo `error` em S3-01) | reprova | reprovado |
| refatorado idêntico ao original em S1-03, S1-10, S1-12, S1-13, S1-15, S1-16, S3-01, B-T1, B-T2, B-T4; C-OBS1 com duplicata | reprova por retorno ao comportamento antigo | reprovado |
| corpo/content-type/campo observado alterados em caso preservado (S1-02, S1-08, S1-03) | reprova | reprovado |
| caso sem expectativa (S9-01) | reprova | reprovado |
| linha de base sem o comportamento antigo (S1-13) | reprova | reprovado |
| ordem dos cursos invertida na **linha de base** (S1-01, S1-06, S5-01) | **aprova** (C-7) | aprovado |
| ordem dos cursos fora de id no **refatorado** (S5-01) | reprova | reprovado |
| ordem dos alunos na **linha de base** como observada pela revisão (S5-01 `[Aluno Recusado, Unknown, Leonan]`) e invertida em S1-06/S1-14 | **aprova** (C-7) | aprovado |
| ordem dos alunos fora de id no **refatorado** (S1-06, S5-01) | reprova | reprovado |
| linha de base com `paid` alterado, aluno removido, duplicado, nome trocado (S5-01) ou duplicação compensada por remoção (S1-06) | reprova | reprovado |
| registros recebidos antes × depois da comparação | inalterados | inalterados |
| conteúdo/efeito diferente na linha de base em caso preservado (S1-01, S1-04) | reprova | reprovado |

| Caso | Entrada | Antes | Depois | Classificação |
|---|---|---|---|---|
| S1-01 | relatório inicial | 200; Docker antes de Clean Architecture | 200; mesmo conteúdo, ordem por id | C-7 |
| S1-02 | checkout usuário novo aprovado | 200 `{msg, enrollment_id: 2}`; +1 em 4 tabelas | idêntico | preservado |
| S1-03 | checkout novo recusado | 400 `Pagamento recusado`; **users +1** | 400; nenhuma escrita | C-3 |
| S1-04/05 | checkout usuário existente (sem pwd / pwd numérico) | 200; +1 matrícula, pagamento, auditoria | idêntico | preservado |
| S1-06 | relatório após checkouts | 200 | idêntico | preservado |
| S1-07 | sem `card` | 400 `Bad Request` | idêntico | preservado |
| S1-08 / S2-01 | curso inexistente / inativo | 404 `Curso não encontrado` | idêntico | preservado |
| S1-09 | `c_id` string numérica | 200 | idêntico | preservado |
| S1-10/11 | usuário novo sem pwd / pwd vazio | 200 (senha padrão literal) | 400 `Bad Request`; sem escrita | D-4(a) |
| S1-12 | JSON inválido | 400 HTML com stack trace | 400 `Bad Request` (texto) | C-5/T-12 |
| S1-13 | DELETE usuário 1 (com matrícula) | 200 "…ficaram sujos no banco."; users −1 | 409 `Usuário possui matrículas`; sem alteração | D-3(b) |
| S1-14 | relatório após DELETE | 200 com `Unknown` | 200 sem `Unknown` (usuário mantido) | consequência de D-3(b) + C-7 |
| S1-15 | DELETE id inexistente | 200 (mensagem de sucesso) | 404 `Usuário não encontrado` | C-6 |
| S1-16 | DELETE id `abc` | 200 (mensagem de sucesso) | 400 `ID inválido` | C-6 |
| S3-01 | DELETE usuário sem matrículas | 200 "…sujos no banco."; users −1 | 200 `Usuário deletado`; users −1 | D-3(b) |
| B-T1 | trigger falha `payments` | 500 `Erro Pagamento`; **users +1, enrollments +1** | 500 `Erro Pagamento`; nenhuma escrita | D-5(a)/C-3 |
| B-T2 | trigger falha `audit_logs` | **200**; users, enrollments, payments +1; auditoria ausente | 500 `Erro Auditoria`; nenhuma escrita | D-5(a) |
| B-T3 | trigger falha `users` | 500 `Erro ao criar usuário`; nenhuma escrita | idêntico | preservado |
| B-T4 | trigger falha `enrollments` | 500 `Erro Matrícula`; **users +1** | 500; nenhuma escrita | D-5(a) |
| S5-01 | relatório com DENIED, PENDING, sem pagamento, órfã, curso vazio, 2 pagamentos | ver §4 | mesmo conteúdo, ordem por id | C-7 |
| C-OBS1 | 10× dois checkouts simultâneos, mesmo e-mail novo | **2 usuários em 10/10 tentativas** | 1 usuário em 10/10 | F-06 |
| C-OBS2 | 20 checkouts + 20 relatórios simultâneos | 0/20 relatórios com estado parcial | 0/20 | preservado (observação não determinística) |

Falhas induzidas (B-T1..B-T4): triggers `BEFORE INSERT ... RAISE(ABORT, ...)` instalados após o seed, somente no banco
isolado de cada instância; nenhuma transação foi acrescentada ao original. Em C-OBS2 o original não exibiu leitura de
estado intermediário em 20 tentativas; a hipótese de F-06 sobre o relatório não foi reproduzida no original sem
instrumentação (limitação registrada no relatório) — o isolamento do refatorado foi provado com intercalação controlada (R-02/R-03).

### Casos em nível de processo (`node src/app.js`)

| Caso | Original | Refatorado |
|---|---|---|
| P-01 inicialização | sobe; `Frankenstein LMS rodando na porta 3000...` | idem (com `SEED_USER_PASSWORD` e `ADMIN_TOKEN`) |
| P-02 `card` numérico, e-mail novo | **processo encerra, exit 1** (`TypeError: cc.startsWith is not a function`) | 400 `Bad Request`; processo segue |
| P-03 `pwd` numérico, e-mail novo | **processo encerra, exit 1** (`TypeError [ERR_INVALID_ARG_TYPE]` em `Buffer.from`) | 400 `Bad Request`; processo segue |
| P-04 sem `SEED_USER_PASSWORD` | n/a | exit 1; `Configuração inválida: SEED_USER_PASSWORD é obrigatória`; porta fechada; **nenhuma abertura de `sqlite3.Database`** (preload de rastreio) |
| P-05 `SEED_USER_PASSWORD` vazia | n/a | idem P-04 |
| P-06 falha no seed (preload de teste) | n/a | exit 1; `Falha na inicialização: falha induzida no seed`; porta fechada |
| P-07 `PORT=abc` | n/a | exit 1; mensagem clara; sem abrir banco |

Também verificado: `require('./src/app.js')` exporta `createApp,start` sem abrir banco nem porta; `npm start` sem
`SEED_USER_PASSWORD` encerra com a mensagem acima (exit 1) e com as variáveis sobe normalmente.

## 4. Testes controlados (R-01 a R-14)

`tools/concurrency_rollback.test.js` — **21 testes, 21 passaram** (`logs/testes-controlados.log`; reexecutado junto com a matriz após a correção do comparador).

| ID | Resultado | Evidência |
|---|---|---|
| R-01 | aprovado | falha em users/enrollments/payments/audit_logs (trigger) e no `COMMIT` (wrapper da conexão): 500 com a mensagem do passo (`Erro DB` no COMMIT); contagens das 4 tabelas iguais às anteriores; nenhum usuário com o e-mail; requisição seguinte 200 |
| R-02 | aprovado | checkout pausado após inserir matrícula e pagamento; relatório disparado ficou pendente ≥300 ms; após a falha, checkout 500 `Erro Pagamento` e relatório **idêntico** ao anterior; contagens inalteradas |
| R-03 | aprovado | mesmo cenário concluindo: relatório entregue só após o commit, com o aluno novo e `paid`/`revenue` 497 (nunca `paid: 0`) |
| R-04 | aprovado | intercalação forçada (1ª operação pausada após decidir "usuário novo"): 2ª aguardou a fila; 1 usuário, +2 matrículas e pagamentos. Sem portão: 10/10 tentativas com 1 usuário |
| R-05 | aprovado | checkout pausado + DELETE: DELETE esperou e recebeu 409; DELETE pausado + checkout: checkout esperou e recriou o usuário; 0 matrículas órfãs nos dois |
| R-06 | não se aplica | D-3(b) não faz exclusão em cascata |
| R-07 | aprovado | após 400 (validação), 404, 400 (recusado) e 500 inesperado (`Erro DB`), nova requisição atendida em < 3 s; relatório 200 |
| R-08 | aprovado | handle usado após a operação → `Handle de banco expirado`; `read`/`transaction` aninhados → `aninhada`; leitura seguinte responde |
| R-09 | aprovado | sem `ADMIN_TOKEN`: 403 `Operação administrativa desabilitada` (relatório e DELETE, com e sem cabeçalho), sem alteração; com token: ausente, incorreto de mesmo tamanho, curto e vazio → 401 `Não autorizado` sem alteração; correto → 200 |
| R-10 | aprovado | com matrículas 409 e contagens iguais; `0`, `-1`, `1.5`, `01`, `abc`, `1e3` → 400 `ID inválido`; 9999 → 404 `Usuário não encontrado`; sem matrículas → 200 `Usuário deletado` |
| R-11 | aprovado | usuário novo com pwd ausente/null/""/número/booleano/objeto/array → 400 sem escrita; existente com pwd ausente/número/""/outro → 200 e senha gravada intacta; `" "` aceito e gravado como `scrypt$<32 hex>$<128 hex>`; novo sem senha + cartão recusado → 400 `Bad Request` |
| R-12 | aprovado | seed: usuário 1 `Leonan`/mesmo e-mail com `pass` em scrypt (≠ `123`), matrícula 1, pagamento 1 `PAID` 997 e cursos idênticos; falha forçada no meio do seed → nenhuma tabela criada (`sqlite_master` vazio); nível de processo em P-04..P-06 |
| R-13 | aprovado | `revenue` soma só `PAID` (Docker 0 com DENIED 497 e PENDING 100); `paid` mostra 497 (DENIED) e 100 (PENDING); matrícula sem pagamento → 0; órfã → `Unknown`; curso vazio presente; 2 pagamentos → usa o de menor id (997). Mesmo conteúdo do original em S5-01 |
| R-14 | aprovado | logs do refatorado (matriz, processos, testes): 0 ocorrências de chave, sequência de cartão, hash scrypt, senha literal ou "Processando cartão"; erros 5xx logam apenas mensagem controlada e causa técnica |

## 5. Nova inspeção — achados da Fase 2

Base: leitura do código refatorado, `inspecao.txt` (`tools/inspecao.sh`) e os resultados acima.

| Achado | Situação | Evidência |
|---|---|---|
| F-01 credenciais hardcoded | **corrigido** | nenhum literal de credencial/chave em `src/` (inspeção AP-02); `config.js` lê `ADMIN_TOKEN`/`SEED_USER_PASSWORD` sem fallback; `dbUser`/`dbPass`/`smtpUser` removidos |
| F-02 cartão e chave no log | **corrigido** | log removido; R-14 sem ocorrências |
| F-03 senhas inseguras / seed conhecido | **corrigido** | `passwordHash.js` (scrypt + sal); sem `badCrypto`/senha padrão (inspeção AP-04); seed com `SEED_USER_PASSWORD` (R-12, P-04/P-05) |
| F-04 endpoints administrativos sem acesso | **corrigido** | `requireAdminToken` em relatório e DELETE (R-09) |
| F-05 God Class | **corrigido** | `AppManager.js` removido; SQL só em `models/` e `database.js`; `req`/`res` só em `routes/`/`middlewares/` (inspeção) |
| F-06 checkout sem transação/isolamento | **corrigido** | `dataAccess.transaction` com fila exclusiva (R-01..R-05, B-T1/B-T2/B-T4, C-OBS1 1 vs 2 usuários). Remanescente: o schema continua sem `UNIQUE` em `email` (preservado); a unicidade depende de todo acesso passar pela fila |
| F-07 órfãos na exclusão | **corrigido** (D-3 b) | 409 com matrículas, sem alteração (S1-13, R-10, R-05) |
| F-08 acoplamento e efeitos de inicialização | **corrigido** | `require` sem efeitos; abertura aguardando callback; schema+seed transacional; config antes do banco; falhas → exit 1 com mensagem (P-04..P-07, R-12) |
| F-09 estado global | **corrigido** | `globalCache`/`logAndCache` removidos (inspeção AP-08) |
| F-10 N+1 no relatório | **corrigido** | `financialReport.js`: 1 consulta; semântica preservada (R-13, S5-01); ordem agora por id (C-7) |
| F-11 validação insuficiente | **corrigido** | P-02/P-03 → 400 em vez de queda; R-10/R-11 |
| F-12 erros silenciosos/mascarados | **corrigido** | `errorHandler` central; sem callbacks com `err` ignorado (inspeção: único resultado é falso positivo `start().catch`); JSON inválido sem stack trace (S1-12) |
| F-13 magic numbers | **corrigido** | `PAYMENT_STATUS`, `APPROVED_CARD_PREFIX`, `UNKNOWN_STUDENT`, `USER_ID_PATTERN` |
| F-14 nomes pouco descritivos | **corrigido** | inspeção AP-18 sem ocorrências; chaves públicas (`usr`, `eml`, `pwd`, `c_id`, `card`) preservadas |
| F-15 código morto | **corrigido** | `totalRevenue` removido; nenhuma referência a módulos removidos |
| F-16 logging ad hoc | **corrigido** | restam apenas a mensagem de inicialização (permitida) e o log de erro central |

Nenhum achado ficou parcial. Problemas remanescentes ou novos:
1. **Serialização (trade-off assumido, 5.2.1):** todas as operações de banco passam por uma única fila; o impacto em
   latência/vazão **não foi medido** (não houve teste de carga, conforme combinado).
2. **Checkout com e-mail existente sem verificar senha** (observação do relatório, fora do escopo): preservado.
3. **Reaproveitamento de ids:** `INTEGER PRIMARY KEY` sem `AUTOINCREMENT` (schema original) reaproveita o maior id
   excluído (observado em R-05). Com D-3(b) a API não deixa matrículas órfãs, mas dados inseridos por fora da API ainda
   poderiam se associar a um usuário recriado com o mesmo id.
4. **Sem `UNIQUE` em `users.email`:** integridade garantida pela fila, não pelo schema (alterar o schema não foi aprovado).
5. **Dependências:** `npm ci` sugeriu `npm audit`; vulnerabilidades de dependências não foram avaliadas nesta fase.

## 6. Limitações

- Intercalações controladas não foram aplicadas ao original (exigiriam instrumentá-lo); lá a concorrência foi apenas
  observada (C-OBS1/C-OBS2).
- A documentação do `node-sqlite3` consultada na Fase 2 é a wiki sem versão; o comportamento relevante (abertura com
  callback, erros em `run`) foi exercitado na prática com sqlite3 5.1.7.
- Logs do original preservados apenas como trecho (40 linhas da matriz) e sanitizados; os brutos foram descartados com o
  diretório temporário.
