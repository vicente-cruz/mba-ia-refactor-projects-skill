> Relatório gerado na Fase 2 em 2026-10-31 e aprovado pelo usuário em 2026-10-31. Linhas referem-se ao commit `209d251268b702c9dbb76e5d32139d861ed48889`; o código pode ter sido alterado pela Fase 3.

================================
RELATÓRIO DE AUDITORIA ARQUITETURAL
================================

## 1. Identificação

| Campo | Valor |
|---|---|
| Projeto | ecommerce-api-legacy (`ecommerce-api-legacy/`) |
| Data | 2026-10-31 |
| Revisão | 3 (revisão 2 com os ajustes pedidos pelo usuário na aprovação: F-05, linha de base com triggers, trade-off da serialização) |
| Versão de referência | commit `209d251268b702c9dbb76e5d32139d861ed48889`; working tree limpo para o código do alvo (apenas `.claude/` não rastreado, não auditado) |
| Stack | JavaScript (Node.js v20.20.0, runtime global da máquina) + Express (declarada: ^4.18.2; lock: 4.22.1; instalada: não verificado) |
| Banco | SQLite em memória (`sqlite3` declarada ^5.1.6; lock 5.1.7; instalada: não verificado) |
| Domínio | LMS com checkout de cursos (usuários, cursos, matrículas, pagamentos, auditoria) |
| Ferramenta | refactor-arch (Claude Code) |

## 2. Escopo

- Arquivos de código analisados: 3 | Linhas físicas: 180
- Lista: `src/AppManager.js` (141), `src/utils.js` (25), `src/app.js` (14)
- Exclusões: `.claude/` (instruções da Skill); `package.json`, `package-lock.json` (apenas versões); `README.md`, `api.http` (apenas cruzamento de endpoints).
- Natureza da análise: leitura estática e consulta à documentação oficial (seção 6), sem execução da aplicação, sem instalação de dependências e sem exploração de vulnerabilidades.

## 3. Resumo por severidade

| CRITICAL | HIGH | MEDIUM | LOW | Total |
|---:|---:|---:|---:|---:|
| 5 | 4 | 3 | 4 | 16 |

Confirmados por leitura: 16 | Hipóteses não verificadas: 0 (partes de F-06, F-08, F-11 e F-12 que dependem de execução estão marcadas como hipótese dentro de cada achado).

## 4. Achados

### F-01 — [CRITICAL] Credenciais e chave de pagamento hardcoded (AP-02)

- **Localização:** `src/utils.js:1-7`; `src/utils.js:25`; `src/AppManager.js:45`
- **Status:** Confirmado por leitura (presença dos literais); a validade ou realidade dos valores não foi verificada
- **Evidência:** `config` contém `dbUser: "admin_m…"`, `dbPass: "senha_su…"`, `smtpUser: "no-reply@…"` — os três sem uso no projeto — e `paymentGatewayKey: "pk_live_12…"`, usado apenas no log de `AppManager.js:45`. O prefixo `pk_live_` imita o formato de uma chave de produção, mas não há indício de que seja real ou válida, e isso não foi testado; o restante do valor tem aparência de sequência fictícia. Arquivo versionado (`git ls-files`).
- **Impacto:** credenciais e chaves no código ficam acessíveis a quem lê o repositório e não podem ser trocadas por ambiente; se algum valor for (ou vier a ser) real, ele está exposto.
- **Justificativa da severidade:** exemplo explícito da escala (credenciais hardcoded em código versionado); a classificação decorre do padrão, não da validade dos valores.
- **Recomendação:** `src/config.js` lendo `process.env` (`PORT` com padrão 3000; `PAYMENT_GATEWAY_KEY` opcional sem fallback); remover `dbUser`, `dbPass`, `smtpUser` (sem uso); documentar em `.env.example` com valores fictícios (T-02, T-13).

### F-02 — [CRITICAL] Número do cartão e chave do gateway gravados em log (AP-03)

- **Localização:** `src/AppManager.js:45`
- **Status:** Confirmado por leitura
- **Evidência:** ``console.log(`Processando cartão ${cc} na chave ${config.paymentGatewayKey}`);`` — `cc` é `req.body.card` (linha 33), sem mascaramento.
- **Impacto:** número completo do cartão e o valor configurado como chave vão para a saída padrão a cada checkout que chega ao pagamento.
- **Justificativa da severidade:** exposição de dado de cartão e de segredo configurado — exemplo explícito da escala.
- **Recomendação:** remover o log; se necessário, registrar apenas resultado do pagamento e id da matrícula, sem cartão nem chave (T-03, T-13).

### F-03 — [CRITICAL] Armazenamento inseguro de senhas e credencial conhecida no seed (AP-04)

- **Localização:** `src/utils.js:17-23`; `src/AppManager.js:68-69`; `src/AppManager.js:18`
- **Status:** Confirmado por leitura
- **Evidência:** `badCrypto` devolve os 2 primeiros caracteres Base64 da senha repetidos 5 vezes — depende só dos primeiros 12 bits, é reversível nessa parte e colide trivialmente (ex.: toda senha iniciada por `1` seguida de caractere entre `0x30` e `0x3F`); sem sal nem custo (o laço de 10000 iterações não altera o resultado). Linha 68 aplica a senha padrão literal `"123456"` quando `pwd` falta. O seed (linha 18) grava `'123'` em texto puro para o usuário inicial — apenas aplicar hash a esse valor **não** elimina a credencial, que continua conhecida por estar no código.
- **Impacto:** colisões triviais, reversibilidade, senha padrão conhecida e credencial inicial pública.
- **Justificativa da severidade:** codificação reversível com colisões triviais — CRITICAL pela regra do AP-04.
- **Recomendação:** hash `scrypt` com sal (`node:crypto`, sem dependência nova); remover a senha padrão literal (comportamento substituto em D-4); senha do usuário inicial fornecida por variável de ambiente, sem fallback no código (D-6), preservando o usuário 1 e seus vínculos com a matrícula 1 e o pagamento 1 (T-04, T-02).

### F-04 — [CRITICAL] Relatório financeiro e exclusão de usuários sem controle de acesso (AP-06)

- **Localização:** `src/AppManager.js:80-129`; `src/AppManager.js:131-137`; `src/app.js:5-10`
- **Status:** Confirmado por leitura
- **Evidência:** `GET /api/admin/financial-report` devolve receita por curso e nome/valor de cada aluno; `DELETE /api/users/:id` apaga qualquer usuário. Nenhuma verificação de identidade/permissão; não há middleware global além de `express.json()` (`app.js:6`).
- **Impacto:** qualquer cliente com acesso à porta lê dados financeiros e pessoais e apaga contas.
- **Justificativa da severidade:** exposição de dados financeiros e operação destrutiva — CRITICAL pelo AP-06. O checkout, operação pública do domínio, não foi incluído.
- **Recomendação:** proteger por token administrativo de ambiente, remover ou manter documentando o risco, conforme D-1 e D-2 (T-15).

### F-05 — [CRITICAL] God Class `AppManager` (AP-05)

- **Localização:** `src/AppManager.js:4-139`
- **Status:** Confirmado por leitura
- **Evidência:** conexão (7); schema e seed (10-23); registro de rotas (25-137); regras — aprovação pelo prefixo do cartão (46), criação implícita de usuário (66-72), receita somente de `PAID` (108-110); SQL nos handlers (37, 40, 50, 54, 57, 83, 92, 104, 106, 133); respostas HTTP (35, 38, 48, 60, 87, 135).
- **Impacto (dificuldades concretas de teste):** o construtor só abre a conexão (7) e **não** executa `initDb`, e `manager.db` é uma propriedade pública; portanto, testes com dados controlados e algumas falhas induzidas (ex.: triggers instalados no banco isolado) são possíveis sem editar os arquivos originais. As dificuldades reais são outras: (1) as regras (aprovação, criação implícita de usuário, cálculo de receita) só existem dentro de closures registradas em `app.post(...)`/`app.get(...)`, então qualquer teste precisa montar um app Express, chamar `setupRoutes` e fazer requisições HTTP; (2) nenhuma função recebe as consultas como dependência, de modo que não é possível substituir uma escrita específica por um dublê nem pausar a operação entre dois passos para observar intercalações sem instrumentação adicional; (3) o callback hell de 5 níveis dificulta leitura e manutenção.
- **Justificativa da severidade:** persistência + regras + HTTP — exemplo explícito da escala.
- **Recomendação:** decompor em `database.js`, `models/`, `controllers/`, `routes/` (seção 5.1) e remover `AppManager.js` (T-05, T-06).

### F-06 — [HIGH] Checkout sem transação nem isolamento na conexão compartilhada (AP-09)

- **Localização:** `src/AppManager.js:37-75`
- **Status:** Confirmado por leitura (ausência de transação e ordem das escritas); condições de corrida são hipóteses deduzidas do fluxo assíncrono, não reproduzidas
- **Evidência:** sequência users (69) → enrollments (50) → payments (54) → audit_logs (57), sem `BEGIN/COMMIT/ROLLBACK`. Falha em `payments` deixa matrícula sem pagamento (500, linha 55). O usuário novo é criado (69) **antes** da decisão do pagamento (46); em pagamento recusado (48), ele permanece gravado. Erro da auditoria ignorado (57-60). *Hipótese:* a leitura do usuário (40) e a criação (69) são passos assíncronos separados e o schema não tem `UNIQUE` em `email` (12), então dois checkouts simultâneos com o mesmo e-mail novo podem criar dois usuários; e o relatório executado entre a inserção da matrícula e a do pagamento observa a matrícula com `paid: 0`.
- **Impacto:** dados parciais, duplicados e leituras de estado intermediário.
- **Justificativa da severidade:** base; operação de negócio parcialmente gravada.
- **Recomendação:** unidade de trabalho exclusiva na conexão única, incluindo leituras e decisões dependentes do banco (seção 5.2.1); decisão de pagamento antes de qualquer escrita; auditoria dentro ou fora da transação conforme D-5 (T-07, T-08).

### F-07 — [HIGH] Exclusão de usuário deixa matrículas e pagamentos órfãos (AP-09)

- **Localização:** `src/AppManager.js:131-137`
- **Status:** Confirmado por leitura
- **Evidência:** só `DELETE FROM users WHERE id = ?`; a resposta admite: "Usuário deletado, mas as matrículas e pagamentos ficaram sujos no banco." Sem chaves estrangeiras no schema (12-15).
- **Impacto:** o relatório continua somando receita de matrículas órfãs e exibe `'Unknown'` (113).
- **Justificativa da severidade:** inconsistência entre escritas relacionadas, admitida pelo código e refletida em relatório financeiro.
- **Recomendação:** tratar dependências na mesma unidade de trabalho, conforme D-3 (T-08).

### F-08 — [HIGH] Acoplamento forte e efeitos colaterais na inicialização (AP-10)

- **Localização:** `src/app.js:5-14`; `src/AppManager.js:5-8`; `src/AppManager.js:10-23`
- **Status:** Confirmado por leitura e documentação oficial; comportamento de erros de fase de execução sem callback é hipótese
- **Evidência:**
  - *Acoplamento e efeitos de carga:* carregar `app.js` cria o app, abre o banco, agenda schema/seed e chama `listen(3000)` (8-12); não há `createApp` exportado; o construtor instancia `sqlite3.Database(':memory:')` sem parâmetro de injeção (a única forma de usar outra conexão é substituir a propriedade pública `db` depois de construir o objeto, e `app.js` não oferece nenhum ponto de substituição).
  - *Erros sem tratamento (não silenciosos):* `new sqlite3.Database(':memory:')` (7) e os `db.run` de `initDb` (12-21) não têm callback. Segundo a wiki oficial do `node-sqlite3`, sem callback um erro na abertura emite evento `error` no objeto Database, e uma falha de *preparação* em `run` emite `error` no objeto Statement. Segundo a documentação do Node.js (Error events), um evento `error` sem listener é lançado, imprime o stack trace e encerra o processo. Logo, uma falha de preparação no schema/seed (ex.: SQL inválido) **derruba o processo** sem mensagem controlada — possivelmente depois de `listen` ter sido chamado (12), pois `initDb` apenas enfileira os comandos. Para erros na fase de *execução* sem callback (ex.: violação de restrição em `INSERT`), a documentação consultada não descreve o comportamento: *hipótese não verificada*. Erros **silenciosos** (callback que recebe `err` e o ignora) estão em F-12.
- **Impacto (dificuldades concretas de teste):** um teste que faça `require('./app')` abre a porta fixa 3000 (conflito se ocupada) e mantém o processo vivo; o ponto de entrada não permite passar uma conexão com dados controlados ou falhas simuladas; uma falha de schema/seed encerra o processo em vez de produzir erro de inicialização tratável.
- **Justificativa da severidade:** base (acoplamento sem injeção e efeitos na carga do módulo).
- **Recomendação:** composition root em `app.js` com `createApp(dataAccess)` e `start()` sob `require.main === module`; `database.js` com `openDatabase` (aguardando o callback de abertura) e `initSchema` que propaga erros e roda schema e seed numa única transação; `listen` só após a inicialização concluída; falha → mensagem clara e código de saída 1 (T-14, T-07).

### F-09 — [HIGH] Estado global mutável compartilhado (AP-08)

- **Localização:** `src/utils.js:9-15`; `src/utils.js:25`; `src/AppManager.js:59`
- **Status:** Confirmado por leitura
- **Evidência:** `let globalCache = {}` é gravado a cada checkout bem-sucedido via `logAndCache` (`AppManager.js:59`) e exportado, sem nenhum leitor no projeto.
- **Impacto:** estado de processo alterado por requisições, sem uso, crescendo com o número de usuários; prejudica isolamento de testes.
- **Justificativa da severidade:** base; efeito funcional limitado por não haver leitores, mas o padrão é o do catálogo.
- **Recomendação:** remover o cache e `logAndCache` (T-07, T-13).

### F-10 — [MEDIUM] Consultas N+1 no relatório financeiro (AP-12)

- **Localização:** `src/AppManager.js:83-127`
- **Status:** Confirmado por leitura (contagem derivada do código; ordem real a observar na linha de base)
- **Evidência:** **1 + C + 2E** consultas (cursos; matrículas por curso — 92; usuário — 104 — e pagamento — 106 — por matrícula). Semântica atual a preservar: `revenue` soma `payment.amount` **somente quando** `status === 'PAID'` (108-110), enquanto `students[].paid` exibe `payment.amount` **sempre que existe um pagamento, qualquer que seja o status** (114); matrícula sem pagamento aparece com `paid: 0`; curso sem matrículas aparece com `revenue: 0, students: []` (95-99); usuário inexistente aparece como `'Unknown'` (113). Pelo fluxo da API, pagamentos não `PAID` nunca são inseridos (a recusa retorna antes do insert, 48), então a divergência só aparece com dados gravados por outro meio — ainda assim será preservada. `db.get` (106) devolve uma única linha sem `ORDER BY`: com vários pagamentos por matrícula, qual é usado não é garantido. A ordem de cursos e alunos segue a ordem de conclusão dos callbacks.
- **Impacto:** custo linear em matrículas; montagem frágil por contadores manuais.
- **Justificativa da severidade:** base.
- **Recomendação:** consulta com `LEFT JOIN` de courses, enrollments, users e subconsulta que escolhe **um** pagamento por matrícula (o de menor `id`, regra explícita a registrar); soma da receita em JavaScript na mesma ordem, para evitar diferenças de ponto flutuante; `ORDER BY` por id de curso e de matrícula, comparado com a ordem observada na linha de base (T-09).

### F-11 — [MEDIUM] Validação de entrada insuficiente (AP-13)

- **Localização:** `src/AppManager.js:29-35`; `src/AppManager.js:46`; `src/AppManager.js:68`; `src/AppManager.js:132`
- **Status:** Confirmado por leitura; as quedas descritas são hipóteses não verificadas
- **Evidência:** só checagem de presença (35). `cc.startsWith("4")` (46) pressupõe string: `card` numérico lançaria `TypeError` dentro de um callback do sqlite3; pela documentação do Node.js (`'uncaughtException'`), a exceção não capturada imprime o stack trace e encerra o processo com código 1 — e, com e-mail novo, o usuário já teria sido inserido (69). `pwd` numérico diferente de 0 chegaria a `Buffer.from(número)` (`utils.js:20`), que deve lançar `TypeError` (não verificado nesta execução). Sem validação de tipo para `usr`, `eml`, `c_id`, nem de formato do `id` do DELETE (132).
- **Impacto:** possível queda do servidor por uma requisição; dados inválidos aceitos.
- **Justificativa da severidade:** base; não elevada porque as quedas não foram verificadas.
- **Recomendação:** `validateCheckout` junto ao modelo, chamado pelo controller: `usr`, `eml`, `card` strings não vazias (400 `Bad Request`); `c_id` aceita inteiro positivo ou string de dígitos, como hoje; `pwd` conforme D-4; `id` conforme 5.4 (T-10).

### F-12 — [MEDIUM] Erros silenciosos, mascarados e sem tratamento central (AP-16)

- **Localização:** `src/AppManager.js:38`; `src/AppManager.js:57-60`; `src/AppManager.js:92-93`; `src/AppManager.js:104-106`; `src/AppManager.js:133-135`; `src/app.js:5-10`
- **Status:** Confirmado por leitura; a queda em 92-93 é hipótese
- **Evidência:** sem middleware `(err, req, res, next)`. **Silenciosos:** erro da auditoria ignorado com resposta 200 (57-60); erros ao ler usuário/pagamento ignorados, resultando em `'Unknown'`/`paid: 0` (104-106); DELETE responde sucesso com erro ou id inexistente (133-135). **Mascarado:** erro de banco ao buscar o curso vira 404 "Curso não encontrado" (`err || !course`, 38). **Sem tratamento:** em 92, `err` é ignorado e `enrollments` fica indefinido; `enrollments.length` (93) lança `TypeError` no callback, o que, pelo comportamento padrão do Node.js, encerra o processo (*hipótese*).
- **Impacto:** falhas invisíveis, respostas enganosas e possível queda.
- **Justificativa da severidade:** base; sem vazamento de detalhes internos ao cliente.
- **Recomendação:** `HttpError`, `asyncHandler` e `errorHandler` central após as rotas; respostas em texto puro; preservar mensagens existentes (`Bad Request`, `Curso não encontrado`, `Pagamento recusado`, `Erro DB`, `Erro ao criar usuário`, `Erro Matrícula`, `Erro Pagamento`); erro inesperado → 500 `Internal Server Error` com detalhe só no log, sem dados sensíveis (T-12).

### F-13 — [LOW] Regras de negócio em literais sem nome (AP-17)

- **Localização:** `src/AppManager.js:46`; `src/AppManager.js:21`; `src/AppManager.js:48`; `src/AppManager.js:108`; `src/utils.js:19-22`
- **Status:** Confirmado por leitura
- **Evidência:** prefixo de aprovação `"4"`; status `'PAID'`/`'DENIED'` repetidos; `10000`, `2`, `10` em `badCrypto`.
- **Impacto:** regra implícita e repetida.
- **Justificativa da severidade:** base.
- **Recomendação:** constantes `APPROVED_CARD_PREFIX` e `PAYMENT_STATUS` em `paymentModel`; `badCrypto` sai com F-03 (T-13).

### F-14 — [LOW] Nomes pouco descritivos (AP-18)

- **Localização:** `src/AppManager.js:26-33`; `src/AppManager.js:89`; `src/AppManager.js:102`; `src/utils.js:17`
- **Status:** Confirmado por leitura
- **Evidência:** `u`, `e`, `p`, `cid`, `cc`, `c`, `enr`, `self`/`this` misturados, `badCrypto`.
- **Impacto:** leitura difícil.
- **Justificativa da severidade:** base.
- **Recomendação:** renomear apenas variáveis internas; chaves da API (`usr`, `eml`, `pwd`, `c_id`, `card`) inalteradas (T-13).

### F-15 — [LOW] Código morto (AP-19)

- **Localização:** `src/utils.js:10`; `src/utils.js:25`; `src/AppManager.js:2`
- **Status:** Confirmado por leitura (busca no projeto inteiro)
- **Evidência:** `totalRevenue` declarado, exportado e importado, nunca usado; por ser primitivo exportado por valor, nem poderia servir como acumulador compartilhado.
- **Impacto:** ruído e falsa impressão de contador de receita.
- **Justificativa da severidade:** base.
- **Recomendação:** remover (T-13).

### F-16 — [LOW] Logging ad hoc (AP-20)

- **Localização:** `src/utils.js:13`
- **Status:** Confirmado por leitura
- **Evidência:** `console.log(\`[LOG] Salvando no cache: ${key}\`)`. A mensagem de inicialização em `app.js:13` é falso positivo permitido pelo catálogo.
- **Impacto:** log sem nível nem propósito.
- **Justificativa da severidade:** base.
- **Recomendação:** removido com o cache (F-09); erros inesperados logados apenas pelo handler central (T-13).

**APIs obsoletas (AP-15):** nenhum achado — nenhuma das APIs Express 4/Node deprecated do catálogo aparece no código.

**Observação (não contada como achado):** um checkout com e-mail existente associa a matrícula a esse usuário sem verificar senha (`AppManager.js:73-74`). Fora do escopo por não existir modelo de autenticação na API; o comportamento será preservado.

## 5. Plano de refatoração proposto

### 5.1 Estrutura-alvo

```
ecommerce-api-legacy/
├── package.json                 # mantido (start: node src/app.js)
├── README.md                    # atualizado apenas com variáveis de ambiente (se D-6 = b, documenta a obrigatória)
├── .env.example                 # novo: PORT, PAYMENT_GATEWAY_KEY, ADMIN_TOKEN, SEED_USER_PASSWORD (valores fictícios)
└── src/
    ├── app.js                   # composition root: createApp(dataAccess, deps?) + start()
    ├── config.js                # process.env + validação de configuração obrigatória (D-6 b)
    ├── database.js              # openDatabase, helpers run/get/all, fila exclusiva (read/transaction), initSchema
    ├── errors.js                # HttpError
    ├── passwordHash.js          # scrypt
    ├── models/
    │   ├── userModel.js
    │   ├── courseModel.js
    │   ├── enrollmentModel.js
    │   ├── paymentModel.js      # PAYMENT_STATUS, APPROVED_CARD_PREFIX, authorize(card)
    │   ├── auditLogModel.js
    │   ├── financialReport.js   # read-model do relatório
    │   └── checkoutValidation.js
    ├── controllers/  checkoutController.js, reportController.js, userController.js
    ├── routes/       checkoutRoutes.js, adminRoutes.js, userRoutes.js
    └── middlewares/  asyncHandler.js, errorHandler.js, requireAdminToken.js (se D-1 ou D-2 = b)
```

Removidos: `src/AppManager.js`, `src/utils.js`. Sem `services/`: não há integração externa real. Os controllers recebem dependências (acesso a dados, models) por factory, o que permite aos testes injetar falhas sem alterar o código de produção.

### 5.2 Transformações, em ordem de aplicação

| Ordem | Transformação | Achados tratados | Arquivos afetados |
|---:|---|---|---|
| 1 | T-02 Configuração por ambiente | F-01, F-03 (seed, D-6) | config.js, .env.example, README.md, utils.js (removido) |
| 2 | T-03 Remover cartão e chave do log | F-02 | código do checkout |
| 3 | T-14 + T-07 Composition root, abertura/inicialização explícitas, fila exclusiva de acesso ao banco | F-08, base de F-06 | app.js, database.js |
| 4 | T-05 + T-06 Decompor AppManager em Models, Controllers, Routes | F-05 | models/, controllers/, routes/ |
| 5 | T-12 Erros centralizados | F-12 | errors.js, middlewares/ |
| 6 | T-10 Validação | F-11 (D-4) | checkoutValidation.js, controllers |
| 7 | T-04 Hash scrypt e senha do seed | F-03 (D-4, D-6) | passwordHash.js, userModel.js, database.js |
| 8 | T-08 Transações de checkout e DELETE | F-06 (D-5), F-07 (D-3) | database.js, controllers |
| 9 | T-09 Relatório com consulta única | F-10 | financialReport.js |
| 10 | T-15 Acesso administrativo | F-04 (D-1, D-2) | adminRoutes.js, userRoutes.js, requireAdminToken.js |
| 11 | T-13 Constantes, nomes, código morto, logs | F-09, F-13, F-14, F-15, F-16 | todos |

#### 5.2.1 Estratégia de acesso à conexão única (F-06, F-07)

**Problema.** Uma transação SQLite pertence à **conexão**, não à requisição. Com uma única conexão `:memory:` (conexões separadas não são opção sem mudar o armazenamento), qualquer instrução de outra requisição executada entre `BEGIN` e `COMMIT` participa da transação aberta: uma escrita alheia seria desfeita num `ROLLBACK`, e uma leitura alheia (ex.: o relatório) observaria dados não confirmados. `db.serialize()` não resolve: segundo a wiki oficial (Control Flow), só as consultas agendadas diretamente no callback são serializadas; consultas agendadas em callbacks posteriores "não necessariamente" — e o checkout atravessa vários callbacks, permitindo que outras requisições se intercalem entre seus passos.

**Estratégia — fila exclusiva (mutex FIFO) para *todo* acesso ao banco:**
1. `database.js` expõe um objeto de acesso com duas operações: `read(work)` (executa `work(handle)` com acesso exclusivo, sem transação) e `transaction(work)` (acesso exclusivo + `BEGIN` → `work(handle)` → `COMMIT`; qualquer exceção → `ROLLBACK` e propagação). Ambas passam pela **mesma fila**; a fila é liberada em `finally`, inclusive após erro.
2. A conexão crua (`sqlite3.Database`) não é entregue a controllers nem models. Models recebem apenas o `handle`, que é invalidado ao término da operação (uso posterior lança erro), impedindo acesso acidental fora da fila. Chamada de `read`/`transaction` aninhada dentro de outra operação lança erro em vez de travar a fila.
3. **Leituras e decisões dependentes do banco ficam dentro da mesma unidade de trabalho:**
   - checkout: busca do curso, busca do usuário por e-mail, decisão "usuário novo × existente", exigência de senha para usuário novo (D-4) e escritas — tudo numa só `transaction` (fecha a corrida de e-mail duplicado);
   - DELETE: existência do usuário, contagem de matrículas (D-3 b), exclusões e efeitos — numa só `transaction`;
   - relatório: uma `read`; como nenhuma transação pode estar aberta enquanto ele roda, ele só observa dados confirmados;
   - inicialização: `initSchema` roda schema + seed numa `transaction` antes de `listen`.
4. **Fora da fila** (para não segurar a conexão): parsing do corpo, validação de tipos (400 `Bad Request`), decisão de pagamento (função pura do cartão) e cálculo do `scrypt` — este é feito antes de entrar na fila quando `pwd` válido é enviado, e o hash só é usado se o usuário for novo. Nenhuma chamada externa ocorre dentro da fila.
5. **Ordem das respostas de erro do checkout (preservada):** campos ausentes/tipo inválido (400 `Bad Request`) → curso inexistente/inativo (404 `Curso não encontrado`) → usuário novo sem senha válida (D-4 a: 400 `Bad Request`) → cartão recusado (400 `Pagamento recusado`, sem nenhuma escrita) → escritas.
6. **Trade-off assumido:** a serialização de todas as operações de banco elimina a concorrência entre elas — uma operação longa (ex.: relatório com muitas matrículas) atrasa as demais, e uma operação travada bloquearia a fila. Em troca, obtém-se isolamento entre requisições na conexão única. O SQLite já executa uma instrução por vez na mesma conexão, mas a fila acrescenta espera também *entre* as instruções de operações diferentes; o impacto em latência e vazão **não foi medido** e não se afirma ausência de impacto. Mitigações no plano: manter fora da fila todo trabalho que não dependa do banco (item 4) e não executar chamadas externas dentro dela. A limitação e a falta de medição serão registradas no relatório da Fase 3.

### 5.3 Contratos preservados
- Comando `npm start` e porta padrão 3000.
- Rotas e métodos: `POST /api/checkout`, `GET /api/admin/financial-report`, `DELETE /api/users/:id` (salvo D-1/D-2).
- Campos de entrada: `usr`, `eml`, `pwd`, `c_id`, `card`.
- Checkout com sucesso: 200 `{ "msg": "Sucesso", "enrollment_id": <id> }`.
- Erros em texto puro com as mensagens existentes: `Bad Request`, `Curso não encontrado`, `Pagamento recusado`, `Erro DB`, `Erro ao criar usuário`, `Erro Matrícula`, `Erro Pagamento`.
- Relatório: forma e semântica (F-10) — `revenue` só soma `PAID`; `paid` mostra o valor de qualquer pagamento existente; matrícula sem pagamento com `paid: 0`; curso sem matrículas presente; `'Unknown'` para usuário ausente.
- Regra de aprovação (prefixo `4`), criação implícita de usuário, reaproveitamento por e-mail sem verificação de senha.
- Schema e seed: mesmas tabelas, dados e ids; usuário 1 ligado à matrícula 1 e ao pagamento 1 (`PAID`, 997). Muda apenas a coluna `pass` do seed (D-6).

### 5.4 Mudanças de contrato intencionais

| # | Mudança | Motivo |
|---|---|---|
| C-1 | Log sem cartão e sem chave (nenhuma resposta muda) | F-02 |
| C-2 | Senhas gravadas como `scrypt$<salt>$<hash>`; fim da senha padrão `"123456"` (substituto em D-4); senha do seed vinda do ambiente (D-6) | F-03 |
| C-3 | Pagamento recusado não cria mais o usuário novo; falha em qualquer escrita desfaz a operação (alcance conforme D-5) | F-06 |
| C-4 | `usr`, `eml` ou `card` de tipo não textual → 400 `Bad Request` (antes: possível queda) | F-11 |
| C-5 | Erro de banco ao buscar curso → 500 `Erro DB` (antes: 404); erros antes ignorados no relatório → 500 `Erro DB` (antes: dados mascarados ou queda); demais inesperados → 500 `Internal Server Error` | F-12 |
| C-6 | DELETE com `id` que não seja inteiro positivo decimal (`/^[1-9]\d*$/`) → 400 `ID inválido`; id inexistente → 404 `Usuário não encontrado` (antes: 200 com mensagem de sucesso em ambos). Vale para qualquer opção de D-3 | F-11, F-12 |
| C-7 | Relatório com ordem determinística (curso por id, aluno por id da matrícula) e, havendo vários pagamentos por matrícula, uso do de menor `id`; divergência da linha de base, se houver, será registrada | F-10 |
| C-8 | Conforme as opções de D-1 a D-6 (contratos detalhados em 5.5) | F-03, F-04, F-06, F-07 |

### 5.5 Decisões pendentes do usuário

| ID | Decisão | Opções | Transformações/arquivos que dependem dela |
|---|---|---|---|
| D-1 | Acesso a `GET /api/admin/financial-report` | (a) remover; (b) token administrativo; (c) manter público e documentar o risco | T-15; adminRoutes.js, requireAdminToken.js, config.js |
| D-2 | Acesso a `DELETE /api/users/:id` | (a) remover; (b) token administrativo (o mesmo de D-1 b); (c) manter público e documentar o risco | T-15; userRoutes.js, requireAdminToken.js |
| D-3 | Matrículas e pagamentos do usuário excluído | (a) excluir em cascata na mesma transação; (b) recusar com 409 se houver matrículas; (c) manter órfãos e documentar | T-08; userController.js, enrollmentModel.js, paymentModel.js |
| D-4 | Usuário novo no checkout sem `pwd` válido | (a) exigir senha apenas para usuário novo; (b) criar sem credencial (`pass` nulo) | T-04, T-10; checkoutValidation.js, userModel.js |
| D-5 | Auditoria do checkout | (a) dentro da transação; (b) fora, após o `COMMIT` | T-08; checkoutController.js |
| D-6 | Senha do usuário inicial (seed) | (a) `SEED_USER_PASSWORD` opcional: se definida, grava hash; se ausente, cria o usuário 1 sem credencial; (b) `SEED_USER_PASSWORD` obrigatória: se ausente, a aplicação não inicia | T-02, T-04, T-14; config.js, database.js, README.md, .env.example |

Nenhuma opção é padrão. Contratos de cada opção:

**D-1(b) / D-2(b) — token administrativo** (verificação antes de validar `id` e antes de qualquer acesso ao banco):

| Situação | Status | Corpo (texto) | Efeito |
|---|---|---|---|
| `ADMIN_TOKEN` ausente ou vazio no ambiente | 403 | `Operação administrativa desabilitada` | nenhum |
| Cabeçalho `X-Admin-Token` ausente | 401 | `Não autorizado` | nenhum |
| Cabeçalho incorreto (inclusive tamanho diferente) | 401 | `Não autorizado` | nenhum |
| Cabeçalho correto | conforme contrato do endpoint (5.3 / D-3) | — | o do endpoint |

Comparação em tempo constante sobre os digests SHA-256 dos dois valores (não revela o tamanho do token); o token nunca é logado. Em (a), a rota removida cai no 404 padrão do Express (HTML `Cannot GET …`/`Cannot DELETE …`). Em (c), comportamento atual, com o risco documentado.

**D-3 — exclusão de usuário** (C-6 vale em todas; tudo numa única `transaction`, 5.2.1):

| Situação | (a) cascata | (b) recusar | (c) manter |
|---|---|---|---|
| `id` inválido | 400 `ID inválido` | 400 `ID inválido` | 400 `ID inválido` |
| `id` inexistente | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` |
| Usuário com matrículas | 200 `Usuário deletado`; remove pagamentos das matrículas dele, as matrículas e o usuário | 409 `Usuário possui matrículas`; nenhuma alteração em users, enrollments, payments | 200 mensagem original; remove só o usuário |
| Usuário sem matrículas | 200 `Usuário deletado` | 200 `Usuário deletado`; remove o usuário | 200 mensagem original |
| Falha de banco no meio | 500 `Erro DB`; rollback de tudo | 500 `Erro DB`; rollback | 500 `Erro DB` |

Em (b), `DELETE /api/users/1` (exemplo do `api.http`) passa a responder 409, porque o usuário do seed tem a matrícula 1.

**D-4(a) — senha obrigatória só para usuário novo:**
- Verificada **dentro** da unidade de trabalho, após ler o usuário pelo e-mail (5.2.1, ordem 5).
- Usuário novo: `pwd` deve ser `string` com pelo menos 1 caractere (espaços contam). Ausente, `null`, string vazia, número, booleano, objeto ou array → 400 `Bad Request`, sem nenhuma escrita. Tamanho máximo: limite padrão do corpo em `express.json()` (100 kB); nenhum limite novo.
- Usuário existente: `pwd` continua **ignorado**, como hoje — pode faltar ou ter qualquer tipo; a senha gravada não muda e o checkout prossegue.
- Usuário novo sem senha válida e com cartão recusado: prevalece 400 `Bad Request` (senha verificada antes do pagamento).

**D-4(b) — sem credencial:** `pwd` ausente → usuário criado com `pass` nulo; `pwd` presente deve ser string não vazia, senão 400 `Bad Request`. Existente: ignorado, como hoje.

**D-5 — auditoria:**
- (a) Usuário (se novo), matrícula, pagamento e auditoria numa só transação. Falha em qualquer um faz `ROLLBACK` de **todas** as escritas da operação, inclusive o usuário criado nela. Respostas: usuário → 500 `Erro ao criar usuário`; matrícula → 500 `Erro Matrícula`; pagamento → 500 `Erro Pagamento`; auditoria → 500 `Erro Auditoria` (mensagem nova); `COMMIT` → 500 `Erro DB`.
- (b) Usuário, matrícula e pagamento na transação (mesmas mensagens); auditoria gravada após o `COMMIT`, numa `read` própria da fila; falha da auditoria vai para o log (sem dados sensíveis) e a resposta continua 200, como hoje.

**D-6 — senha do seed** (em ambas: usuário 1 `Leonan`, mesmo e-mail, matrícula 1 e pagamento 1 preservados; configuração validada **antes** de abrir o banco e de qualquer gravação; schema + seed numa única transação, de modo que falha no meio desfaz tudo e encerra com mensagem clara e código 1, sem chegar a `listen`):
- (a) Sem a variável: usuário 1 criado com `pass` nulo (sem credencial utilizável); aviso no log `SEED_USER_PASSWORD não definida; usuário inicial criado sem senha`, sem valor. Com a variável: `pass` recebe o hash `scrypt` dela. `npm start` funciona sem configuração.
- (b) Sem a variável: o processo grava em stderr `Configuração inválida: SEED_USER_PASSWORD é obrigatória` e encerra com código 1, sem abrir banco, sem seed e sem abrir porta. Com a variável: inicia normalmente. `npm start` sem configuração deixa de funcionar; README e `.env.example` documentam.

Variável definida porém vazia é tratada como ausente em ambas.

### 5.6 Validação planejada

**Ambiente.** Cópias em diretório temporário fora do repositório (`original/` e `refatorado/`); `npm ci` em cada cópia (exige acesso ao registro npm); `npm ls --depth=0` para registrar versões instaladas. Nada instalado no projeto nem globalmente. Scripts usam apenas módulos nativos do Node 20 (`node:test`, `node:http`, `fetch`), sem dependência nova. **O original tem a chave hardcoded:** definir `PAYMENT_GATEWAY_KEY` vazia **não** a substitui; o original gravará a chave literal e números de cartão na saída padrão. Esses logs brutos ficam só no diretório temporário e passam por sanitização antes de qualquer cópia para as evidências (passo 6). Não há chamada externa: o gateway é simulado e a chave só é logada.

**Linha de base (original, sem editar seus arquivos).**
1. `node src/app.js` na cópia (porta 3000, se livre): registro de inicialização e matriz HTTP.
2. Script de apoio `baseline_harness.js` na cópia: instancia `AppManager` diretamente (o construtor não executa `initDb`; o harness chama `initDb` explicitamente e aguarda o seed), registra as rotas num app Express em porta efêmera e usa `manager.db` para montar dados e consultar efeitos. Isso permite:
   - casos de dados para a semântica do relatório (F-10): pagamento `DENIED`/`PENDING` inserido diretamente, matrícula sem pagamento, curso sem matrículas, vários pagamentos numa matrícula;
   - **falhas induzidas por triggers**, instalados **após o seed** e somente no banco isolado, com `RAISE(ABORT, ...)`: (B-T1) trigger que falha `INSERT` em `payments`; (B-T2) trigger que falha `INSERT` em `audit_logs` — cada um em instância separada. Para cada caso, registrar resposta (status e corpo) e contagens/dados de users, enrollments, payments e audit_logs antes e depois. **Nenhuma transação é acrescentada ao original**: o objetivo é observar seu comportamento real diante das falhas (esperado pela leitura: B-T1 → 500 `Erro Pagamento` com usuário e matrícula mantidos; B-T2 → 200 com matrícula e pagamento mantidos e auditoria ausente).
3. Matriz: checkout (usuário novo; existente; recusado com contagem de users após; campo ausente; curso inexistente; curso inativo), relatório (antes e depois dos checkouts), DELETE (existente, inexistente, id não numérico; relatório após exclusão). Casos que podem derrubar o processo — `card` numérico com e-mail novo e `pwd` numérico — em instâncias isoladas, registrados como "queda" se ocorrerem.
4. **Intercalações de concorrência no original** são distintas das falhas induzidas: sem instrumentação adicional não é possível pausar o original entre dois passos, então elas são registradas apenas como observação não determinística — dois checkouts simultâneos com o mesmo e-mail novo (quantos usuários surgem); relatório disparado junto a vários checkouts. Intercalações controladas (pausa num ponto exato) são feitas apenas no refatorado, por injeção de dependências.

**Refatorado.** A mesma matriz HTTP, com as mesmas entradas, e os mesmos triggers B-T1/B-T2 (além de triggers em `users` e `enrollments`) para comparação direta; mais os casos das decisões escolhidas e os testes controlados em `concurrency_rollback.test.js` (`node:test`), com `createApp` sobre banco em memória próprio e models injetados que podem pausar num "portão" ou falhar num ponto escolhido:

| ID | Teste | Critério |
|---|---|---|
| R-01 | Rollback por ponto de falha: usuário, matrícula, pagamento, auditoria (se D-5 a), `COMMIT` | status/mensagem de D-5; contagens de users, enrollments, payments, audit_logs iguais às anteriores; nenhum usuário com o e-mail do teste |
| R-02 | **Relatório durante checkout que depois falha**: checkout pausado após inserir matrícula e pagamento; relatório disparado; checkout liberado para falhar | o relatório só responde após o fim do checkout e é idêntico ao relatório anterior; checkout 500; contagens inalteradas |
| R-03 | Relatório durante checkout que conclui | relatório reflete o estado completo antes ou depois, nunca parcial |
| R-04 | Dois checkouts simultâneos, mesmo e-mail novo | 1 usuário, 2 matrículas, 2 pagamentos |
| R-05 | Checkout e DELETE simultâneos do mesmo usuário | resultado equivalente a uma ordem serial; sem órfãos (D-3 a/b) |
| R-06 | Falha forçada no meio do DELETE em cascata (D-3 a) | nada removido |
| R-07 | Fila liberada após erro de validação, de domínio e inesperado | requisição seguinte é atendida |
| R-08 | Uso do `handle` após o fim da operação; `transaction` aninhada | lançam erro e não travam a fila |
| R-09 | Token (D-1 b/D-2 b): sem configuração, cabeçalho ausente, incorreto, correto | 403 / 401 / 401 / contrato do endpoint; sem alteração de dados nos três primeiros |
| R-10 | DELETE conforme D-3: com matrículas, sem matrículas, id inválido, id inexistente | tabela de D-3; em (b), contagens iguais após 409 |
| R-11 | D-4: novo sem `pwd`, novo com `pwd` numérico, novo com `pwd` vazio, existente sem `pwd`, existente com `pwd` numérico | conforme a opção; nenhuma escrita nos casos 400; existente → 200 com senha gravada intacta |
| R-12 | D-6: início com e sem `SEED_USER_PASSWORD`; falha forçada no seed | conforme a opção; usuário 1, matrícula 1 e pagamento 1 intactos e relatório inicial igual ao da linha de base; (b): código 1, mensagem clara, porta não aberta; falha no seed → nada gravado e código 1 |
| R-13 | Semântica do relatório com os mesmos dados montados na linha de base | `revenue` só soma `PAID`; `paid` mostra valor de pagamento não `PAID`; matrícula sem pagamento → `paid: 0`; curso vazio presente; `'Unknown'` preservado; comparação com a linha de base |
| R-14 | Logs do refatorado | nenhum cartão, chave, senha, hash ou token |

**Evidências e limpeza.**
5. Scripts reutilizáveis (`baseline_harness.js`, `run_matrix.js`, `compare.js`, `concurrency_rollback.test.js`, `sanitize.js`) **geram dados sensíveis de teste em tempo de execução** (cartões montados a partir do prefixo, senhas e tokens aleatórios via `crypto`), para que os arquivos preservados não contenham literais sensíveis.
6. **Sanitização antes de preservar:** `sanitize.js` substitui por `<removido>`: padrões `pk_(live|test)_…`, sequências de 12 a 19 dígitos (cartões), valores de `pwd`/`pass`/`password`/`card` em corpos, prefixos `scrypt$…`, valores de `X-Admin-Token`, `ADMIN_TOKEN` e `SEED_USER_PASSWORD`, e os literais de credencial de `utils.js`. Em seguida, busca por esses padrões nos arquivos gravados deve retornar vazio antes da limpeza.
7. Ordem: gravar evidências → encerrar processos → remover diretório temporário → conferir `git status --porcelain`.

### 5.7 Destino do relatório e das evidências
Caminhos relativos à raiz do repositório; ambos podem ser substituídos pelo usuário. Nada é gravado antes da confirmação.
- Relatório de auditoria (este documento, sem alterações): `reports/audit-project-2.md`
- Evidências da Fase 3: `reports/evidence/ecommerce-api-legacy/` — `validation.md` (data, commit, versões instaladas, comandos com resultado resumido, matriz antes × depois com classificação de cada diferença, resultados R-01 a R-14, nova inspeção, limitações), `commands.md`, `matriz.md`, `baseline.json`/`refatorado.json` sanitizados, `tools/` (scripts reutilizáveis), `logs/` (trechos sanitizados).

## 6. Limitações
- Versões instaladas não verificadas (sem `node_modules/`); as citadas vêm do lockfile.
- Node v20.20.0 é o runtime global da máquina, não um runtime fixado pelo projeto.
- Documentação consultada: `node-sqlite3` — wiki oficial *API* (https://github.com/TryGhost/node-sqlite3/wiki/API) e *Control Flow* (https://github.com/TryGhost/node-sqlite3/wiki/Control-Flow), sem versionamento (vale para o projeto atual; não conferida contra a 5.1.7 instalada) e sem descrição de erros de fase de execução sem callback (hipótese em F-08); Node.js v20 — *Error events* (https://nodejs.org/docs/latest-v20.x/api/events.html#error-events) e *Event: 'uncaughtException'* (https://nodejs.org/docs/latest-v20.x/api/process.html#event-uncaughtexception).
- Comportamento em execução não verificado: quedas (F-11, F-12), condições de corrida (F-06) e ordem real do relatório (F-10) — a observar na linha de base da Fase 3.
- Linha de base: dados controlados e falhas induzidas por triggers (B-T1, B-T2) são possíveis no original sem editar seus arquivos, via `AppManager` e `manager.db` no `baseline_harness.js`. Já intercalações controladas (pausar o original entre dois passos de uma operação) exigiriam instrumentação adicional do código original e não serão feitas; a concorrência no original será registrada apenas como observação não determinística, e o isolamento sob intercalação controlada será verificado somente no refatorado.
- O impacto em desempenho da serialização (5.2.1) não foi medido.

================================
Total: 16 achados (CRITICAL: 5 | HIGH: 4 | MEDIUM: 3 | LOW: 4)
================================
