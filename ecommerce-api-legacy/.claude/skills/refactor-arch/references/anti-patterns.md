# Catálogo de anti-patterns (Fase 2)

Catálogo aplicado ao código real do projeto-alvo. Os padrões são gerais: nomes de projetos, arquivos e linhas só aparecem no relatório, como evidência local.

## Escala de severidade

- **CRITICAL:** falhas graves de arquitetura ou segurança que impedem o funcionamento correto, expõem dados sensíveis (ex.: credenciais hardcoded, SQL Injection) ou violam completamente a separação de responsabilidades (ex.: God Class com banco, lógica complexa e roteamento).
- **HIGH:** fortes violações de MVC/SOLID que dificultam muito manutenção e testes (ex.: regras de negócio pesadas em controllers/rotas, acoplamento forte sem injeção de dependência, estado global mutável).
- **MEDIUM:** padronização, duplicação, performance moderada (ex.: N+1, middlewares inadequados, validações ausentes nas rotas).
- **LOW:** legibilidade, nomenclatura, magic numbers.

## Regras de aplicação

1. **Leia antes de afirmar.** Um achado exige o trecho lido, com arquivo e linhas conferidos. Busca textual (`grep`) só indica onde olhar.
2. **Confirmado × hipótese.** "Confirmado por leitura" quando o código demonstra o problema (ex.: valor da requisição concatenado ao SQL). "Hipótese não verificada" quando depende de algo não observado (versão instalada, comportamento em execução, exploração). Não execute explorações.
3. **Severidade base e ajuste.** Use a severidade indicada para cada padrão. Ajuste (para cima ou para baixo) apenas com justificativa escrita baseada no contexto (ex.: endpoint exposto sem autenticação, dado realmente sensível, código morto).
4. **Consolidação.** Mesma causa + mesma correção = um achado com várias localizações. Problemas distintos no mesmo trecho (ex.: SQL Injection dentro de uma God Class) são achados distintos. Não conte o mesmo trecho em dois achados pelo mesmo motivo.
5. **Sem diagnóstico por analogia.** Não transfira um achado de uma stack ou arquivo para outro sem ler o código correspondente (ex.: consultas parametrizadas não são SQL Injection só porque outro arquivo concatena SQL).
6. **Estrutura nominal não é separação.** Pastas `models/`, `routes/`, `services/` não provam separação de responsabilidades; avalie o conteúdo.

## Índice

| ID | Anti-pattern | Severidade base |
|---|---|---|
| AP-01 | SQL Injection e execução de SQL arbitrário | CRITICAL |
| AP-02 | Segredos e credenciais hardcoded | CRITICAL |
| AP-03 | Exposição de dados sensíveis em respostas ou logs | CRITICAL |
| AP-04 | Armazenamento inseguro de senhas | CRITICAL |
| AP-05 | God Class / God Module | CRITICAL |
| AP-06 | Operações administrativas ou destrutivas sem controle de acesso | CRITICAL |
| AP-07 | Regras de negócio e persistência na camada HTTP | HIGH |
| AP-08 | Estado global mutável compartilhado | HIGH |
| AP-09 | Escritas relacionadas sem transação | HIGH |
| AP-10 | Acoplamento forte e efeitos colaterais na inicialização | HIGH |
| AP-11 | Configuração de execução insegura (debug, bind, CORS) | HIGH |
| AP-12 | Consultas N+1 | MEDIUM |
| AP-13 | Validação de entrada ausente ou insuficiente | MEDIUM |
| AP-14 | Regras ou validações duplicadas e divergentes | MEDIUM |
| AP-15 | Uso de API obsoleta (deprecated/legacy) | MEDIUM |
| AP-16 | Tratamento de erros disperso ou que vaza detalhes internos | MEDIUM |
| AP-17 | Magic numbers e literais de regra sem nome | LOW |
| AP-18 | Nomes pouco descritivos | LOW |
| AP-19 | Código morto: imports, variáveis e funções sem uso | LOW |
| AP-20 | Logging ad hoc (print/console.log) | LOW |

Distribuição: 6 CRITICAL, 5 HIGH, 5 MEDIUM, 4 LOW.

---

## CRITICAL

### AP-01 — SQL Injection e execução de SQL arbitrário

**Sinais concretos**
- Python: `cursor.execute("... '" + valor + "'")`, f-strings (`f"... {valor}"`), `%` ou `.format()` montando SQL com dados externos.
- Node: template literals (`` `... ${req.body.x}` ``) ou `+` em `db.run/get/all/exec`, `query(`.
- Endpoint que recebe SQL no corpo/query e o executa (`execute(dados["sql"])`).
- ORM com SQL textual interpolado (`text(f"...")`, `.raw(`).

**Evidências necessárias:** o fluxo do valor desde a entrada HTTP (`request.args`, `request.get_json()`, `req.body`, `req.query`, `req.params`) até a string SQL, sem parametrização no caminho.

**Severidade:** CRITICAL — permite alterar a lógica da consulta, contornar autenticação, ler ou destruir dados; exemplo explícito da escala.

**Falsos positivos**
- Placeholders (`?`, `%s`, `:nome`, `$1`) com valores passados separadamente **não** são injeção.
- Concatenação de valores já convertidos para inteiro (`int(id)`) ou de identificadores vindos de lista fixa no código tem risco muito menor; registre como má prática (MEDIUM) ou não registre, explicando.
- Construção de uma lista de placeholders (`",".join("?" * n)`) com valores parametrizados é segura.

### AP-02 — Segredos e credenciais hardcoded

**Sinais concretos:** `SECRET_KEY = "..."`, `password`, `pass`, `token`, `api_key`, `*_KEY`, `pk_live_`, `sk_live_`, URIs com usuário e senha (`postgres://user:senha@`), credenciais SMTP literais em código ou config versionada.

**Evidências necessárias:** a linha com o literal e o uso (ou a exportação) do valor. Indique se o arquivo é versionado (`git ls-files`).

**Severidade:** CRITICAL — o segredo fica acessível a quem lê o repositório e não pode ser trocado por ambiente; exemplo explícito da escala. Não reproduza o valor completo do segredo no relatório: mascare (ex.: `pk_live_12…`).

**Falsos positivos:** valores lidos de `os.environ`/`process.env` sem fallback secreto; placeholders evidentes em `.env.example`; segredos de teste em fixtures claramente isoladas (rebaixe e justifique). Um fallback literal (`os.environ.get("KEY", "segredo-fixo")`) **continua** sendo hardcoded.

### AP-03 — Exposição de dados sensíveis em respostas ou logs

**Sinais concretos:** `to_dict()`/serializadores que incluem `password`, `senha`, `hash`, `token`, `secret`; `SELECT *` de tabela de usuários devolvido em JSON; `jsonify(user.__dict__)`; logs que imprimem corpo de requisição com senha, número de cartão ou token; endpoints de "debug" que devolvem configuração.

**Evidências necessárias:** o ponto onde o campo entra na representação **e** a rota que devolve essa representação (ou o log que a imprime). Diga com precisão o que é exposto (texto puro, hash, token parcial).

**Severidade:** CRITICAL — exposição de dados sensíveis está no exemplo explícito da escala. Exposição de hash continua CRITICAL quando o hash é fraco (permite ataque offline); descreva-a como hash, não como senha em texto puro.

**Falsos positivos:** campo sensível presente no modelo mas removido antes da resposta; serialização usada apenas internamente (confirme todos os chamadores).

### AP-04 — Armazenamento inseguro de senhas

**Sinais concretos:** `INSERT` da senha recebida sem transformação; comparação `senha == senha_recebida` contra valor do banco; `md5`, `sha1` ou `sha256` sem sal e sem fator de custo; Base64 ou outra codificação usada como "criptografia"; funções caseiras (truncar, repetir, inverter); senha padrão literal aplicada quando o campo falta.

**Evidências necessárias:** a função que transforma/grava a senha e o ponto de verificação no login (se existir).

**Severidade:** CRITICAL quando a senha é armazenada em texto puro, de forma reversível ou com transformação que gera colisões triviais. Hash rápido sem sal (MD5/SHA-1) também é CRITICAL quando combinado com exposição (AP-03) ou acesso facilitado ao banco; isolado, pode ser classificado como HIGH com justificativa.

**Falsos positivos:** `bcrypt`, `argon2`, `scrypt`, `pbkdf2` (ex.: `werkzeug.security.generate_password_hash`) com sal são adequados; não marque só por usar `hashlib` se for para outro fim (ex.: checksum de arquivo).

### AP-05 — God Class / God Module

**Sinais concretos:** uma classe ou módulo que, ao mesmo tempo, cria conexão/schema/seed, registra rotas, executa regras de negócio (checkout, cálculo, relatório) e monta respostas HTTP; módulo que concentra várias entidades/domínios sem relação; métodos longos que misturam SQL, cálculo e `res.json`/`jsonify`.

**Evidências necessárias:** intervalo de linhas da classe/módulo e a lista de responsabilidades distintas observadas, cada uma com linhas de exemplo.

**Severidade:** CRITICAL quando reúne **persistência + regras complexas + roteamento/HTTP** (exemplo explícito da escala). Se reúne só duas dessas responsabilidades, avalie AP-07 (HIGH).

**Falsos positivos:** tamanho, por si só, não é God Class; um arquivo grande de um único domínio e uma única camada não se enquadra. Um composition root que **apenas** conecta módulos é esperado.

### AP-06 — Operações administrativas ou destrutivas sem controle de acesso

**Sinais concretos:** rotas como `/admin/*`, `reset`, `drop`, `query`, `delete` de usuários, relatórios financeiros, que não verificam autenticação/autorização; endpoint que apaga ou recria o banco; endpoint que executa comandos ou SQL recebidos.

**Evidências necessárias:** a rota, a operação executada e a ausência de verificação de identidade/permissão no caminho (middleware, decorator ou checagem inline).

**Severidade:** CRITICAL quando a operação destrói dados, executa SQL/comandos arbitrários ou expõe dados sensíveis/financeiros; HIGH quando o efeito é limitado. Justifique com o efeito observado.

**Falsos positivos:** APIs de exemplo sem nenhum modelo de autenticação não justificam marcar **todo** endpoint; restrinja o achado às operações administrativas, destrutivas ou sensíveis. Confirme que não há middleware global de autenticação antes de registrar.

---

## HIGH

### AP-07 — Regras de negócio e persistência na camada HTTP

**Sinais concretos:** funções de rota/controller que leem `request`/`req`, validam, executam várias consultas, calculam (descontos, totais, estatísticas, prazos), gravam e montam a resposta; SQL ou chamadas ORM (`Model.query`, `db.session`, `db.run`) dentro de handlers; regras já existentes nos modelos reimplementadas na rota.

**Evidências necessárias:** funções e intervalos de linhas, indicando quais trechos são HTTP, regra e persistência.

**Severidade:** HIGH — "lógica de negócio pesada presa em controllers" é exemplo explícito; dificulta testes sem HTTP e reuso.

**Falsos positivos:** handler que só converte entrada, chama uma função de domínio e serializa o resultado é adequado. Um CRUD simples com uma consulta pode ser aceitável; registre só se houver regra relevante ou repetição.

### AP-08 — Estado global mutável compartilhado

**Sinais concretos:** conexão de banco em variável global reutilizada por todas as requisições (`global conn`, `_db = None ... return _db`); `sqlite3.connect(..., check_same_thread=False)` compartilhado; caches/contadores globais (`let cache = {}`, `let total = 0`) alterados por requisições; listas globais usadas como armazenamento.

**Evidências necessárias:** a declaração, os pontos de escrita e os consumidores.

**Severidade:** HIGH — "estado global mutável" é exemplo explícito; prejudica isolamento de testes, coordenação de transações e concorrência. Não alegue condição de corrida reproduzida se não houve execução.

**Falsos positivos:** objetos de extensão do framework (ex.: `db = SQLAlchemy()` do Flask-SQLAlchemy, cuja sessão tem escopo gerenciado pelo contexto da aplicação), constantes imutáveis, loggers e o objeto `app` não são estado global mutável no sentido do anti-pattern. Uma única conexão em banco `:memory:` pode ser necessária para manter os dados; aponte o problema de acoplamento, não a existência da conexão.

### AP-09 — Escritas relacionadas sem transação

**Sinais concretos:** sequência de `INSERT/UPDATE/DELETE` que forma uma operação de negócio (pedido + itens + estoque; matrícula + pagamento) com `commit` intermediário ou sem `BEGIN/COMMIT/ROLLBACK`; callbacks aninhados em que a falha de uma escrita responde erro sem desfazer as anteriores.

**Evidências necessárias:** as escritas em ordem, o ponto de falha possível e a ausência de reversão.

**Severidade:** HIGH — deixa dados parcialmente gravados e viola a consistência da regra de negócio.

**Falsos positivos:** escrita única; operações independentes por desenho (registre a justificativa); ORM com unidade de trabalho e um único `commit` ao final (verifique se não há `commit` intermediário).

### AP-10 — Acoplamento forte e efeitos colaterais na inicialização

**Sinais concretos:** módulos que criam conexões, tabelas, seeds ou clientes externos no momento da **importação**; controllers/serviços que instanciam diretamente dependências concretas (cliente SMTP, gateway, conexão) sem permitir substituição; `require`/`import` circulares; app criado em escopo global sem factory, impedindo configuração de teste.

**Evidências necessárias:** a linha que produz o efeito ou a instanciação e quem depende dela.

**Severidade:** HIGH — "forte acoplamento sem injeção de dependência" é exemplo explícito; impede testes com dados isolados e dublês.

**Falsos positivos:** instanciar objetos de valor ou utilitários puros; singletons do framework usados conforme a documentação.

### AP-11 — Configuração de execução insegura

**Sinais concretos:** `app.run(debug=True)` ou `DEBUG = True` fixo; `host="0.0.0.0"` junto com debug; CORS liberado para qualquer origem com credenciais; stack traces habilitados em respostas por padrão.

**Evidências necessárias:** a linha de configuração e o ponto de entrada que a usa.

**Severidade:** HIGH — o depurador interativo do Werkzeug permite execução de código se exposto; configuração fixa impede separar desenvolvimento de produção. Eleve para CRITICAL só com evidência de exposição em produção.

**Falsos positivos:** debug lido de variável de ambiente com padrão desligado; CORS aberto em API pública sem credenciais pode ser intencional (registre como observação, não como achado HIGH).

---

## MEDIUM

### AP-12 — Consultas N+1

**Sinais concretos:** consulta dentro de laço sobre o resultado de outra consulta (`for pedido in pedidos: cursor.execute(...)`); acesso a relacionamento lazy em laço (`for c in categorias: Model.query.filter_by(...).count()`); callbacks de banco aninhados em `forEach` no Node.

**Evidências necessárias:** a consulta externa, as internas e a fórmula do número de consultas (ex.: `1 + N + N×M`). Diga que a contagem é derivada do código, não medida.

**Severidade:** MEDIUM — gargalo de performance moderada, exemplo explícito da escala.

**Falsos positivos:** laço sobre lista fixa e pequena; relacionamento já carregado com `joinedload`/`selectinload`; consulta em lote única antes do laço.

### AP-13 — Validação de entrada ausente ou insuficiente

**Sinais concretos:** campos obrigatórios não verificados; verificação só de presença (`if not x`) seguida de uso que pressupõe tipo (`x.startswith`, `x.lower()`, aritmética); ausência de limites (tamanho, faixa, enum de status); `request.get_json()` usado sem tratar corpo ausente ou inválido.

**Evidências necessárias:** a entrada, a validação existente (ou falta dela) e a operação que falharia ou aceitaria dado inválido.

**Severidade:** MEDIUM — "validações ausentes nas rotas" é exemplo explícito. Eleve se a falta de validação levar a falha de segurança (nesse caso, o achado provavelmente é AP-01/AP-06).

**Falsos positivos:** validação feita em camada anterior (schema, middleware, decorator) — confirme o caminho antes de registrar.

### AP-14 — Regras ou validações duplicadas e divergentes

**Sinais concretos:** blocos de validação copiados entre criar/atualizar; mesma regra de negócio (ex.: cálculo de atraso, status permitidos) implementada na rota e no modelo; listas de valores permitidos repetidas em vários arquivos.

**Evidências necessárias:** todas as cópias com linhas, e se há divergência observável entre elas (uma aplica uma regra que a outra não aplica).

**Severidade:** MEDIUM — duplicação é exemplo explícito; a divergência já observável reforça a classificação.

**Falsos positivos:** diferenças legítimas entre operações (ex.: atualização parcial que não exige todos os campos); semelhança sintática sem mesma regra de negócio.

### AP-15 — Uso de API obsoleta (deprecated/legacy)

**Sinais concretos (exemplos que exigem confirmação na versão pertinente):**
- SQLAlchemy 2.x: `Query.get()` (legado; equivalente `Session.get()`), em Flask-SQLAlchemy `Model.query.get(id)` → `db.session.get(Model, id)`.
- Flask 2.3+: `@app.before_first_request` (removido), `flask.json.JSONEncoder` (removido); prefira o código de inicialização explícito e o provider JSON.
- Python 3.12+: `datetime.utcnow()`/`utcfromtimestamp()` (deprecated) → `datetime.now(timezone.utc)`.
- Express 4: `res.send(status, body)`, `res.json(status, obj)`, `req.param()` (deprecated; removidos no Express 5) → `res.status(s).send(...)`, `req.params`/`req.query`/`req.body`.
- Node.js: `new Buffer()` → `Buffer.from()`/`Buffer.alloc()`; `crypto.createCipher` → `crypto.createCipheriv`.

**Evidências necessárias:** (1) a linha com a chamada; (2) a versão declarada e, se verificável, a instalada; (3) a página oficial da documentação **da versão pertinente** que marca a API como deprecated/legacy/removida, com URL. Se a documentação não puder ser consultada, registre como **hipótese não verificada**.

**Severidade:** MEDIUM — padronização e manutenção de compatibilidade. Eleve para HIGH/CRITICAL apenas se a API estiver **removida** na versão instalada e quebrar a execução (com evidência).

**Falsos positivos:** não generalize o status de um método para toda a interface (ex.: outros métodos de `Query` não têm, necessariamente, o mesmo status de `Query.get()`); APIs deprecated apenas em versões mais novas que a usada; avisos de documentação de outra biblioteca com nome semelhante.

### AP-16 — Tratamento de erros disperso ou que vaza detalhes internos

**Sinais concretos:** `try/except Exception as e: return jsonify({"erro": str(e)}), 500` repetido em cada rota; `res.status(500).send(err.message)`; ausência de handler central (`@app.errorhandler`, middleware `(err, req, res, next)`); exceções não tratadas em callbacks Node que derrubam o processo; formatos de erro diferentes entre rotas; middlewares registrados em ordem que impede seu efeito.

**Evidências necessárias:** as ocorrências e a ausência de mecanismo central; se houver vazamento, o que é devolvido ao cliente.

**Severidade:** MEDIUM — padronização e "uso inadequado de middlewares". Eleve se a mensagem expuser dados sensíveis (então avalie AP-03).

**Falsos positivos:** tratamento local que converte um erro de domínio específico em 4xx com mensagem controlada é adequado.

---

## LOW

### AP-17 — Magic numbers e literais de regra sem nome

**Sinais concretos:** limites, percentuais, faixas, prazos e códigos de status de negócio usados diretamente em condições (`if total > 5000: desconto = 0.05`); limites repetidos quando já existe constante declarada.

**Evidências necessárias:** os literais, a regra que representam e, se houver, a constante existente não utilizada.

**Severidade:** LOW — legibilidade e manutenção; exemplo explícito da escala. Não alegue erro de cálculo sem prova.

**Falsos positivos:** `0`, `1`, `-1` em contexto óbvio; códigos HTTP padrão (`404`, `201`); valores já nomeados por parâmetro ou dicionário de configuração.

### AP-18 — Nomes pouco descritivos

**Sinais concretos:** variáveis de uma ou duas letras fora de laços curtos (`u`, `e`, `p`, `cc`), abreviações opacas, nomes genéricos (`data`, `tmp`, `obj2`), nomes enganosos (função `get_` que grava).

**Evidências necessárias:** os nomes e o que de fato representam.

**Severidade:** LOW — nomenclatura ruim é exemplo explícito da escala.

**Falsos positivos:** convenções consolidadas (`i`, `e` em `except ... as e`, `req`, `res`, `db`); **nomes de campos públicos da API** — renomeá-los muda o contrato; o achado deve propor renomear apenas variáveis internas.

### AP-19 — Código morto: imports, variáveis e funções sem uso

**Sinais concretos:** `import` cujo nome não aparece no arquivo; variável declarada/exportada sem consumidores; funções nunca chamadas; arquivos não importados por ninguém.

**Evidências necessárias:** a declaração e a busca de usos no **projeto inteiro** (incluindo exportações e importações dinâmicas). Uma análise estática sem execução pode ser feita com `python3 -I -B -c` lendo o arquivo via `ast` (não importa o módulo).

**Severidade:** LOW — ruído e falsa sinalização de dependências.

**Falsos positivos:** imports com efeito colateral intencional (registro de modelos, `import models` antes de `create_all`); símbolos usados por reflexão, templates ou `__all__`; re-exportações em `__init__.py`.

### AP-20 — Logging ad hoc

**Sinais concretos:** `print()`/`console.log()` como log de operação, auditoria ou erro; ausência de níveis; mensagens com dados pessoais.

**Evidências necessárias:** as ocorrências e o propósito aparente.

**Severidade:** LOW — padronização e observabilidade. Se o log contiver dado sensível, registre em AP-03.

**Falsos positivos:** scripts de linha de comando e seeds em que a saída no terminal é o objetivo; mensagem de inicialização do servidor.

---

## Relação com o playbook

| Anti-pattern | Transformações ([refactoring-playbook.md](refactoring-playbook.md)) |
|---|---|
| AP-01 | T-01 |
| AP-02, AP-11 | T-02 |
| AP-03 | T-03 |
| AP-04 | T-04 |
| AP-05, AP-07 | T-05, T-06 |
| AP-06 | T-15 |
| AP-08, AP-10 | T-07, T-14 |
| AP-09 | T-08 |
| AP-12 | T-09 |
| AP-13, AP-14 | T-10 |
| AP-15 | T-11 |
| AP-16 | T-12 |
| AP-17, AP-18, AP-19, AP-20 | T-13 |
