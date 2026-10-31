================================
RELATÓRIO DE AUDITORIA ARQUITETURAL
================================

> Relatório gerado na Fase 2 em 2026-10-30 e aprovado pelo usuário em 2026-10-30. Linhas referem-se ao commit `40d29863fed86442a86df1e37567cd2ec3d46ede`; o código pode ter sido alterado pela Fase 3.

## 1. Identificação

| Campo | Valor |
|---|---|
| Projeto | code-smells-project (`code-smells-project/`) |
| Data | 2026-10-30 |
| Versão de referência | commit `40d29863fed86442a86df1e37567cd2ec3d46ede`, working tree limpo para o alvo |
| Stack | Python + Flask (declarada: 3.1.1; instalada: não verificado) + flask-cors (declarada: 5.0.1) |
| Banco | SQLite, arquivo `loja.db` relativo ao diretório de execução (nenhum arquivo de banco existe hoje no projeto) |
| Domínio | E-commerce (produtos, usuários, pedidos, relatório de vendas) |
| Ferramenta | refactor-arch (Claude Code) |

## 2. Escopo

- Arquivos de código analisados: 4 | Linhas físicas: 780
- Lista: `app.py` (88), `controllers.py` (292), `database.py` (86), `models.py` (314). Todos foram lidos por inteiro.
- Exclusões: `.claude/` (a Skill, não é código do projeto), `README.md` (documentação), `requirements.txt` (manifesto, usado só como evidência de versões), `../requirements.txt` (raiz do repositório, fora do alvo).
- Natureza da análise: leitura estática, sem executar a aplicação, sem instalar dependências e sem explorar vulnerabilidades. A verificação de bancos existentes foi só por listagem de arquivos, sem abrir nenhum arquivo de banco.

## 3. Resumo por severidade

| CRITICAL | HIGH | MEDIUM | LOW | Total |
|---:|---:|---:|---:|---:|
| 7 | 6 | 4 | 4 | 21 |

Confirmados por leitura: 21 | Hipóteses não verificadas: 0. Algumas afirmações dentro dos achados são hipóteses e estão marcadas assim: F-08 (exploração do depurador), F-09 (efeito entre requisições e concorrência) e F-14 (status exato de JSON inválido).

## 4. Achados

### F-01 — [CRITICAL] SQL Injection em várias consultas (AP-01)

- **Localização:** `models.py:47-50`; `models.py:57-61`; `models.py:109-111`; `models.py:126-129`; `models.py:140`; `models.py:148-151`; `models.py:155-166`; `models.py:289-299`
- **Status:** Confirmado por leitura
- **Evidência:** valores vindos da requisição entram na string SQL por concatenação.
  - Login: `"SELECT * FROM usuarios WHERE email = '" + email + "' AND senha = '" + senha + "'"` (`models.py:110`), com `email` e `senha` do JSON (`controllers.py:170-171`).
  - Criar e atualizar produto: `nome`, `descricao`, `categoria`.
  - Criar usuário: `nome`, `email`, `senha`.
  - Criar pedido: `usuario_id`, `item["produto_id"]` e `item["quantidade"]` do JSON passam só por `str()`, sem conversão para `int`.
  - Busca: `termo` e `categoria` da query string (`models.py:291,293`).
  - Nas consultas por id de path (`models.py:28,68,92,174,280`), o valor já chega como `int` pelo conversor `<int:>`, então o risco é baixo. O `novo_status` de `models.py:280` passa antes por uma lista fixa (`controllers.py:242`). Esses trechos são má prática e serão corrigidos junto, mas não aumentam o achado.
- **Impacto:** login sem senha (por exemplo `email = "admin@loja.com' --"`), leitura e alteração de qualquer tabela, corrupção de dados.
- **Justificativa da severidade:** caso explícito de CRITICAL na escala, em endpoints públicos.
- **Recomendação:** parametrizar todas as consultas com `?` (T-01) e validar os tipos dos ids do corpo (T-10).

### F-02 — [CRITICAL] Endpoint que executa SQL arbitrário sem controle de acesso (AP-06)

- **Localização:** `app.py:59-78`
- **Status:** Confirmado por leitura
- **Evidência:** `cursor.execute(query)` com `query = dados.get("sql", "")` vindo do corpo; faz `commit` em instruções que não são SELECT. Nenhuma autenticação no caminho e nenhum middleware global.
- **Impacto:** qualquer cliente lê, altera ou apaga todo o banco, inclusive senhas.
- **Justificativa da severidade:** executa SQL recebido, o caso CRITICAL de AP-06 (também cai em AP-01).
- **Recomendação:** não manter a execução de SQL arbitrário. As alternativas, inclusive manter o endpoint só com consultas predefinidas, estão em D-1 e na seção 5.5.1 (T-15).

### F-03 — [CRITICAL] Senhas devolvidas nas respostas de usuários (AP-03)

- **Localização:** `models.py:79-86`; `models.py:95-102`; `controllers.py:128-144`
- **Status:** Confirmado por leitura
- **Evidência:** os dicts de usuário incluem `"senha": row["senha"]` (`models.py:83,99`) e são devolvidos em `GET /usuarios` e `GET /usuarios/<id>`. Como a senha é gravada sem transformação (F-04), o que sai na resposta é a senha em texto puro.
- **Impacto:** qualquer cliente obtém as credenciais de todos os usuários, inclusive do admin.
- **Justificativa da severidade:** exposição de dado sensível, explícita na escala.
- **Recomendação:** criar uma representação pública sem `senha` (T-03).

### F-04 — [CRITICAL] Senhas guardadas e comparadas em texto puro, com senha de admin conhecida no seed (AP-04)

- **Localização:** `models.py:122-131`; `models.py:109-111`; `database.py:75-83`
- **Status:** Confirmado por leitura
- **Evidência:** `criar_usuario` grava a `senha` recebida sem transformação. O login compara a senha dentro do SQL. O seed cria `admin@loja.com` com senha literal conhecida (`admin1…`, tipo `admin`) e outros dois clientes com senhas literais.
- **Impacto:** quem lê o banco (veja F-02 e F-03) recupera todas as senhas. Toda instalação nova tem um admin com senha pública.
- **Justificativa da severidade:** texto puro somado a exposição é CRITICAL pela regra de AP-04.
- **Recomendação:** usar `werkzeug.security.generate_password_hash`/`check_password_hash` e verificar a senha em Python após buscar o usuário pelo e-mail (T-04). O tratamento do seed e dos bancos legados depende de D-3 e D-4.

### F-05 — [CRITICAL] `/admin/reset-db` apaga todos os dados sem controle de acesso (AP-06)

- **Localização:** `app.py:47-57`
- **Status:** Confirmado por leitura
- **Evidência:** executa `DELETE` nas 4 tabelas e `commit`, sem nenhuma checagem de identidade.
- **Impacto:** perda total de dados com uma única requisição anônima.
- **Justificativa da severidade:** operação destrutiva sem proteção.
- **Recomendação:** remover ou preservar com proteção por `ADMIN_TOKEN` e o SQL movido para o model (T-15, T-05). Depende de D-2; a seção 5.5.2 detalha a opção protegida.

### F-06 — [CRITICAL] SECRET_KEY fixa no código (AP-02)

- **Localização:** `app.py:7`; `controllers.py:289`
- **Status:** Confirmado por leitura (os dois arquivos são versionados, conforme `git ls-files`)
- **Evidência:** `app.config["SECRET_KEY"] = "minha-chave-s…"`, com o mesmo literal repetido em `controllers.py:289`.
- **Impacto:** a chave fica visível no repositório, e trocá-la exige editar o código. Qualquer assinatura feita com ela pode ser forjada.
- **Justificativa da severidade:** credencial no código, exemplo explícito da escala.
- **Recomendação:** ler `SECRET_KEY` do ambiente sem fallback literal; sem a variável, gerar uma chave efêmera com aviso no log (T-02).

### F-07 — [CRITICAL] `/health` expõe SECRET_KEY e configuração interna (AP-03)

- **Localização:** `controllers.py:276-290`
- **Status:** Confirmado por leitura
- **Evidência:** a resposta pública inclui `"secret_key"`, `"db_path": "loja.db"`, `"debug": True` e `"ambiente": "producao"`, todos fixos no código e não lidos da configuração real.
- **Impacto:** entrega a chave de assinatura a qualquer cliente e informa um estado de debug e ambiente que pode nem ser o verdadeiro.
- **Justificativa da severidade:** expõe um segredo em resposta HTTP. É um problema diferente do F-06: lá o segredo está no código, aqui ele sai na resposta.
- **Recomendação:** remover `secret_key` e `db_path`; `debug` passa a refletir a configuração (T-03, T-02).

### F-08 — [HIGH] Debug ligado de forma fixa e servidor escutando em 0.0.0.0 (AP-11)

- **Localização:** `app.py:8`; `app.py:88`; `app.py:9`
- **Status:** Confirmado por leitura. A possibilidade de explorar o depurador do Werkzeug pela rede é hipótese: não foi executado.
- **Evidência:** `app.config["DEBUG"] = True` e `app.run(host="0.0.0.0", port=5000, debug=True)`. Observação: `CORS(app)` libera todas as origens, mas sem `supports_credentials`; isso fica registrado como observação, não como achado.
- **Impacto:** o depurador interativo fica acessível a outras máquinas da rede. Separar desenvolvimento de produção exige editar o código, porque nenhum desses valores vem do ambiente.
- **Justificativa da severidade:** severidade base, sem evidência de exposição em produção.
- **Recomendação:** ler `FLASK_DEBUG` (padrão desligado), `HOST` e `PORT` (padrão 5000) do ambiente (T-02, T-14). O host padrão depende de D-5.

### F-09 — [HIGH] Criação de pedido sem rollback numa conexão compartilhada (AP-09)

- **Localização:** `models.py:133-169`
- **Status:** Confirmado por leitura que não existe rollback. O efeito entre requisições é deduzido do código, sem execução.
- **Evidência:** a função grava o pedido (148-151) e depois, para cada item, grava `itens_pedido` e faz `UPDATE` no estoque (154-166), com um único `commit` no fim. Não há `rollback`: o `except` em `controllers.py:218-220` só responde 500. A conexão é global (F-10). Assim, as escritas parciais de uma falha ficam na transação aberta e seriam confirmadas pelo próximo `commit` de outra requisição. A checagem de estoque (144) e a baixa (163-166) também não são atômicas entre requisições concorrentes (hipótese).
- **Impacto:** pedido sem itens, estoque baixado só em parte, dados inconsistentes.
- **Justificativa da severidade:** severidade base.
- **Recomendação:** usar uma transação explícita (`with db:`) com rollback automático, uma conexão por requisição e baixa de estoque condicional (`estoque >= ?`) (T-08, T-07).

### F-10 — [HIGH] Conexão SQLite global compartilhada entre threads (AP-08)

- **Localização:** `database.py:4-11`
- **Status:** Confirmado por leitura
- **Evidência:** `global db_connection` com `sqlite3.connect(db_path, check_same_thread=False)`, aberta na primeira chamada e reaproveitada por todas as requisições e threads até o processo terminar (todos os `get_db()` de `models.py`, `controllers.py:266` e `app.py:49,66`). Nada fecha a conexão.
- **Impacto:**
  - Todas as requisições compartilham o mesmo estado de transação (veja F-09).
  - Para usar outro banco, é preciso alterar `database.db_path` antes da primeira chamada a `get_db()`, ou rodar o processo em outro diretório, já que o caminho é relativo ao diretório atual.
  - Trocar de banco entre testes no mesmo processo exige fechar a conexão e redefinir `database.db_connection = None` à mão. Não existe função para isso, e a próxima chamada recria schema e seed.
  - Nenhuma condição de corrida foi reproduzida.
- **Justificativa da severidade:** severidade base.
- **Recomendação:** conexão por requisição com `g` e `teardown_appcontext`, e caminho do banco vindo da configuração (T-07).

### F-11 — [HIGH] Relatório financeiro e dados pessoais de usuários sem controle de acesso (AP-06)

- **Localização:** `app.py:28` → `controllers.py:257-262`; `app.py:18-19` → `controllers.py:128-144`
- **Status:** Confirmado por leitura
- **Evidência:** `GET /relatorios/vendas` devolve faturamento, descontos e contagens, e `GET /usuarios` lista nomes, e-mails e tipos de todos os usuários. Nada verifica quem chama. A API não tem nenhum modelo de autenticação: `/login` não emite token.
- **Impacto:** vazamento de dados de negócio e de dados pessoais. A exposição de senhas já está em F-03 e não é contada aqui.
- **Justificativa da severidade:** rebaixado de CRITICAL para HIGH porque o efeito é limitado (dados agregados e de contato, sem destruição). Os demais CRUDs não foram marcados, seguindo a regra de falso positivo para APIs sem modelo de autenticação.
- **Recomendação:** depende de D-6 (T-15).

### F-12 — [HIGH] Camadas só no nome: SQL e regras de negócio na camada HTTP, e um `models.py` com 4 domínios (AP-07)

- **Localização:** `app.py:47-78`; `controllers.py:264-274`; `controllers.py:26-54`; `controllers.py:208-210`; `controllers.py:247-250`; `models.py:1-314`
- **Status:** Confirmado por leitura
- **Evidência:**
  - Os handlers administrativos em `app.py` e o `health_check` executam SQL direto.
  - As funções de `controllers.py` leem `request` e montam `jsonify`, ou seja, fazem o papel de View, e ainda acumulam validação de domínio e notificações.
  - `models.py` reúne SQL e regras (checkout em 137-146, faixas de desconto em 256-262) de produtos, usuários, pedidos e relatório num único módulo.
  - AP-05 (God Class) foi avaliado e não se aplica: nenhum módulo reúne persistência, regra complexa e HTTP ao mesmo tempo.
- **Impacto:** as validações em `controllers.py` leem `request` diretamente, então testá-las exige um contexto de requisição (`test_request_context` ou `test_client`). As funções de `models.py` podem ser chamadas fora do HTTP, mas sempre usam a conexão global (F-10). Há duplicação (F-17) e a manutenção fica difícil.
- **Justificativa da severidade:** severidade base de AP-07.
- **Recomendação:** separar em models, controllers e routes por entidade (T-05, T-06).

### F-13 — [HIGH] Acoplamento: app global sem factory, schema e seed implícitos no primeiro `get_db()` (AP-10)

- **Localização:** `app.py:6-30`; `app.py:88`; `database.py:5`; `database.py:7-86`; `controllers.py:3`; `models.py:1`
- **Status:** Confirmado por leitura
- **Evidência:**
  - O app é criado e configurado no escopo do módulo: `SECRET_KEY` e `DEBUG` fixos, rotas registradas ao importar.
  - Host, porta e debug estão fixos em `app.run`.
  - `db_path` é uma constante de módulo com caminho relativo.
  - A primeira chamada a `get_db()` cria tabelas e seed como efeito colateral.
  - Controllers, models e `app.py` importam diretamente a função concreta `get_db`, sem ponto de injeção.
- **Impacto:**
  - Isolar um teste é possível, mas por caminhos frágeis e indiretos: alterar `app.config` depois da importação, rodar o processo em outro diretório ou mudar atributos de `database` antes da primeira chamada a `get_db()`.
  - Não há como criar duas instâncias do app com configurações diferentes no mesmo processo.
  - O seed acontece sempre, sem como desligá-lo por configuração.
  - Trocar o servidor de host, porta ou debug exige editar o código.
- **Justificativa da severidade:** severidade base.
- **Recomendação:** `create_app(overrides)` e `init_db()` chamados explicitamente no ponto de entrada (T-14, T-07).

### F-14 — [MEDIUM] Validação de entrada ausente ou insuficiente (AP-13)

- **Localização:** `controllers.py:169-171`; `controllers.py:239-240`; `app.py:61-62`; `controllers.py:43-50`; `controllers.py:153-158`; `controllers.py:195-201` com `models.py:139-146`; `controllers.py:118-121`; `controllers.py:245`
- **Status:** Confirmado por leitura. O status exato devolvido para Content-Type não-JSON ou JSON inválido (415/400 do Werkzeug, capturado e transformado em 500) é hipótese até a execução.
- **Evidência:**
  - `dados.get` é chamado sem verificar se `get_json()` devolveu `None`: corpo ausente causa `AttributeError` e resposta 500.
  - `preco` e `estoque` não têm o tipo verificado: string causa `TypeError` e 500.
  - E-mail sem validação de formato nem de unicidade (o schema não tem `UNIQUE`).
  - `quantidade` não é validada: um valor negativo passa na checagem de estoque, gera total negativo e **aumenta** o estoque (`models.py:144,146,163-166`). `itens` não é validado como lista.
  - `float(preco_min)` inválido causa `ValueError` e 500.
  - Status de pedido inexistente responde 200 sem alterar nada.
- **Impacto:** erros 500 em vez de 4xx e regra de estoque violável.
- **Justificativa da severidade:** severidade base. A injeção pelos campos do pedido já está tratada em F-01.
- **Recomendação:** validação centralizada por entidade, chamada pelo controller (T-10).

### F-15 — [MEDIUM] Tratamento de erros repetido em cada rota e vazando detalhes internos (AP-16)

- **Localização:** `controllers.py:10-12, 21-22, 60-62, 95-96, 108-109, 125-126, 133-134, 143-144, 164-165, 185-186, 218-220, 226-227, 234-235, 254-255, 261-262, 291-292`; `app.py:77-78`
- **Status:** Confirmado por leitura
- **Evidência:** `except Exception as e: return jsonify({"erro": str(e)}), 500` repetido em 16 handlers. O `/health` usa outro formato (`{"status": "erro", "detalhes": ...}`). Os 404 às vezes trazem `"sucesso": False` (`controllers.py:20`) e às vezes não (`controllers.py:70`). Não há `errorhandler` central.
- **Impacto:** mensagens internas (incluindo SQL) chegam ao cliente e o formato de erro é inconsistente.
- **Justificativa da severidade:** severidade base.
- **Recomendação:** `errors.py` com exceções de domínio e handlers que mantêm a chave `erro` (T-12).

### F-16 — [MEDIUM] Consultas N+1 nas listagens de pedidos (AP-12)

- **Localização:** `models.py:171-201`; `models.py:203-233`; `models.py:139-141` com `154-156`
- **Status:** Confirmado por leitura (contagem deduzida do código, não medida)
- **Evidência:** para cada pedido há uma consulta de itens, e para cada item uma consulta de produto: 1 + N + N×M consultas. `criar_pedido` consulta cada produto duas vezes (2N).
- **Impacto:** a latência cresce linearmente com o volume de dados.
- **Justificativa da severidade:** severidade base.
- **Recomendação:** um único `LEFT JOIN` com agrupamento em Python, preservando a ordem atual e o valor `"Desconhecido"` para produto ausente (T-09).

### F-17 — [MEDIUM] Validações e serializações duplicadas e divergentes (AP-14)

- **Localização:** `controllers.py:28-54` × `controllers.py:72-90`; `models.py:12-21`, `31-40`, `304-313`; `models.py:79-86` × `95-102`; `models.py:171-201` × `203-233`
- **Status:** Confirmado por leitura
- **Evidência:** a atualização de produto repete a validação da criação, mas **não** checa o tamanho do nome nem a categoria (divergência observável: um PUT aceita categoria inválida). O dict de produto aparece 3 vezes, o de usuário 2 vezes e as listagens de pedidos são cópias quase idênticas.
- **Impacto:** regras inconsistentes e alterações que precisam ser feitas em vários lugares.
- **Justificativa da severidade:** severidade base, reforçada pela divergência.
- **Recomendação:** um validador e um serializador por entidade (T-10, T-06). Passar a aplicar as regras de nome e categoria no PUT é mudança de contrato (seção 5.4).

### F-18 — [LOW] Números mágicos em regras de negócio (AP-17)

- **Localização:** `models.py:256-262`; `controllers.py:47-50`; `controllers.py:52`; `controllers.py:242`; `app.py:36` e `controllers.py:285`
- **Status:** Confirmado por leitura
- **Evidência:** faixas de desconto (10000/5000/1000 com 0.1/0.05/0.02), limites de nome (2 e 200), listas de categorias e de status sem nome e a versão `"1.0.0"` repetida.
- **Impacto:** legibilidade e risco de divergência.
- **Justificativa da severidade:** severidade base.
- **Recomendação:** constantes nomeadas no model correspondente, preservando os operadores `>` (T-13).

### F-19 — [LOW] Logging feito com `print`, incluindo e-mails (AP-20)

- **Localização:** `controllers.py:8, 11, 57, 61, 106, 161, 179, 182, 208-210, 219, 248, 250`; `app.py:56`
- **Status:** Confirmado por leitura
- **Evidência:** `print` usado para operações, erros e "notificações" simuladas (e-mail, SMS, push). As linhas 161, 179 e 182 registram o e-mail do usuário, que é dado pessoal, mas não senha.
- **Impacto:** sem níveis de log nem como configurar a saída.
- **Justificativa da severidade:** severidade base, mantida porque não há dado sensível de autenticação no log.
- **Recomendação:** `logging` com níveis, sem e-mail nas mensagens de login (T-13). A mensagem de inicialização do servidor pode continuar.

### F-20 — [LOW] Imports sem uso (AP-19)

- **Localização:** `database.py:2`; `models.py:2`
- **Status:** Confirmado por leitura e por análise AST (`python3 -I -B`, sem importar os módulos)
- **Evidência:** `import os` (`database.py:2`) e `import sqlite3` (`models.py:2`) não são usados nos respectivos arquivos.
- **Nota:** `cursor.execute("SELECT 1")` em `controllers.py:268` **não** é código morto. É uma verificação de conectividade que roda de fato, e o descarte do resultado não a torna inútil. No máximo é redundante, porque logo em seguida (`controllers.py:269-274`) três consultas `SELECT COUNT(*)` usam a mesma conexão e falhariam do mesmo jeito. O plano mantém essa consulta.
- **Impacto:** ruído e falsa indicação de dependência.
- **Justificativa da severidade:** severidade base.
- **Recomendação:** remover os dois imports (T-13).

### F-21 — [LOW] Nomes pouco descritivos ou que sombreiam builtins (AP-18)

- **Localização:** `controllers.py:14, 56, 64, 98, 136, 160`; `models.py:24, 54, 65, 89`; `models.py:187-193, 219-225`
- **Status:** Confirmado por leitura
- **Evidência:** a variável `id` sombreia o builtin; `cursor2`, `cursor3` e `prod` são nomes opacos.
- **Impacto:** legibilidade.
- **Justificativa da severidade:** severidade base.
- **Recomendação:** renomear só as variáveis internas; nomes de campos e parâmetros de URL continuam iguais (T-13).

**AP-15 (API obsoleta):** não há chamadas candidatas no código. Não aparecem `utcnow`, `Query.get`, `before_first_request` nem adaptadores de datetime do `sqlite3`. Por isso não foi necessário consultar documentação e não há achado.

## 5. Plano de refatoração proposto

### 5.1 Estrutura-alvo

```
code-smells-project/
├── app.py                # create_app() + execução local (python app.py, porta 5000) — reaproveitado
├── config.py             # NOVO: SECRET_KEY, DATABASE_PATH (loja.db), FLASK_DEBUG, HOST, PORT,
│                         #       ADMIN_TOKEN* e SEED_SENHA_*** (conforme decisões)
├── .env.example          # NOVO: variáveis documentadas com valores fictícios
├── database.py           # reaproveitado: get_db por requisição (g), close_db, init_db (schema + seed) explícito
├── errors.py             # NOVO: DomainError/ValidationError/NotFoundError + handlers no formato {"erro": ...}
├── auth.py               # NOVO*: decorator require_admin_token (X-Admin-Token, hmac.compare_digest)
├── models/               # substitui models.py (4 domínios → 1 módulo por entidade)
│   ├── produto.py
│   ├── usuario.py        # hash de senha, representação pública sem senha
│   ├── pedido.py         # criação transacional, listagens com JOIN, status válidos
│   ├── relatorio.py      # relatório de vendas e faixas de desconto nomeadas
│   └── admin.py          # NOVO*: reset transacional (D-2 b) e/ou catálogo de consultas predefinidas (D-1 c)
├── controllers/          # substitui controllers.py: casos de uso sem request/jsonify
│   ├── produto_controller.py, usuario_controller.py, pedido_controller.py,
│   └── relatorio_controller.py, sistema_controller.py
├── routes/               # NOVO: Blueprints (papel de View)
│   └── produtos.py, usuarios.py, pedidos.py, relatorios.py, sistema.py
└── migrar_senhas.py      # NOVO***: só se D-4 = (c); script explícito, nunca chamado na inicialização
```

`*` só se alguma das decisões D-1(b/c), D-2(b) ou D-6(b) usar `ADMIN_TOKEN`. `**` só se D-3 = (b) ou (d). `***` só se D-4 = (c). Não será criado `services/`: as notificações são apenas logs e não existe integração externa real.

### 5.2 Transformações, em ordem de aplicação

| Ordem | Transformação | Achados tratados | Arquivos afetados |
|---:|---|---|---|
| 1 | T-02 Configuração por ambiente | F-06, F-08 | config.py, app.py, .env.example |
| 2 | T-07 Conexão por requisição e init explícito | F-10, F-13 | database.py |
| 3 | T-12 Tratamento de erros centralizado | F-15 | errors.py, rotas |
| 4 | T-05/T-06 Separar Models, Controllers e Routes | F-12, F-17 | models/, controllers/, routes/ |
| 5 | T-01 Parametrizar SQL | F-01 | models/* |
| 6 | T-03 Representações públicas | F-03, F-07 | models/usuario.py, sistema_controller.py |
| 7 | T-04 Hash de senha (+ D-3, D-4) | F-04 | models/usuario.py, database.py, migrar_senhas.py*** |
| 8 | T-08 Transação no pedido | F-09 | models/pedido.py |
| 9 | T-09 Eliminar N+1 | F-16 | models/pedido.py |
| 10 | T-10 Validação centralizada | F-14, F-17 | models/*, controllers/* |
| 11 | T-15 Endpoints administrativos e sensíveis (D-1, D-2, D-6) | F-02, F-05, F-11 | auth.py, models/admin.py, routes/* |
| 12 | T-14 App factory e ponto de entrada | F-13, F-08 | app.py |
| 13 | T-13 Constantes, nomes, imports sem uso e logging | F-18 a F-21 | todos |

### 5.3 Contratos preservados

- As 19 rotas, com os mesmos métodos e conversores `<int:>`, exceto o que for decidido em D-1 e D-2.
- Envelope de resposta `{"dados", "sucesso", "mensagem", "total"}`, chave `erro` nos erros e os mesmos status 200/201/400/401/404.
- Mesmas mensagens de validação.
- Ordem das listagens.
- Campos de produto, pedido e relatório, e os valores de desconto (`>` preservado).
- `"produto_nome": "Desconhecido"` quando o produto não existe.
- `python app.py` na porta 5000, arquivo `loja.db`.
- Schema e seed de produtos criados na inicialização, com a condição original: seed só quando a tabela `produtos` está vazia. Os usuários do seed seguem D-3.
- `SELECT 1` mantido no `/health`.

**Critério de preservação para endpoints protegidos:** um endpoint que só responde 403 quando o token não está configurado **não** conta como funcionalidade preservada. Nas opções que preservam endpoints com `ADMIN_TOKEN`, a validação roda com o token configurado e precisa mostrar o efeito funcional (200 e efeito no banco). A resposta 403 sem configuração é registrada à parte, como comportamento padrão seguro.

### 5.4 Mudanças de contrato intencionais

1. `GET /usuarios` e `GET /usuarios/<id>` deixam de devolver `senha` (F-03).
2. `GET /health` deixa de devolver `secret_key` e `db_path`; `debug` passa a refletir a configuração real, por padrão `false` (F-07, F-08).
3. Respostas 500 passam a trazer `{"erro": "Erro interno do servidor"}` em vez de `str(e)`; o `/health` com falha mantém `status: "erro"`, mas sem detalhes internos (F-15).
4. Entradas inválidas que hoje causam 500 passam a responder 400 com mensagem controlada (F-14).
5. `POST /pedidos`: `quantidade` menor ou igual a zero, ou não inteira, e ids não inteiros passam a responder 400 (F-14).
6. `PUT /pedidos/<id>/status` para pedido inexistente passa a responder 404 `{"erro": "Pedido não encontrado"}` (F-14).
7. `PUT /produtos/<id>` passa a aplicar as regras de nome e categoria do `POST` (F-17).
8. Entradas com aspas passam a ser tratadas como texto literal (F-01).
9. Senhas passam a ser gravadas como hash; o login com a senha correta continua respondendo 200 com os mesmos campos (F-04). Seed conforme D-3 e senhas legadas conforme D-4.
10. Debug desligado por padrão (F-08); host padrão conforme D-5.
11. Conforme as decisões:
    - D-1(c): `POST /admin/query` passa a exigir `X-Admin-Token`, aceita `{"consulta": ...}` em vez de `{"sql": ...}` e não executa mais escritas (contrato na seção 5.5.1).
    - D-2(b): `POST /admin/reset-db` passa a exigir `X-Admin-Token` e mantém corpo e efeito com autorização válida (seção 5.5.2).
    - D-3(d): os usuários de demonstração só são criados com as senhas fornecidas por configuração (seção 5.5.3).
    - D-6(b): `/relatorios/vendas` e `/usuarios` passam a exigir `X-Admin-Token`.

### 5.5 Decisões pendentes do usuário

| ID | Decisão | Opções | Transformações/arquivos que dependem dela |
|---|---|---|---|
| D-1 | Destino de `POST /admin/query` (F-02) | (a) remover; (b) manter a execução de SQL arbitrário, só protegida por `ADMIN_TOKEN` (o playbook desaconselha); (c) **manter o endpoint com `ADMIN_TOKEN` e apenas consultas predefinidas, somente leitura, sem SQL arbitrário e sem senhas ou hashes** (seção 5.5.1); (d) manter como está e documentar o risco | T-15; routes/sistema.py, models/admin.py, auth.py, config.py |
| D-2 | Destino de `POST /admin/reset-db` (F-05) | (a) remover; (b) **preservar com proteção por `ADMIN_TOKEN`** (seção 5.5.2); (c) manter sem proteção e documentar o risco | T-15; routes/sistema.py, models/admin.py, auth.py, config.py |
| D-3 | Usuários do seed (F-04) | (a) manter os mesmos usuários e senhas de exemplo, gravados como hash (as senhas continuam conhecidas no código); (b) senha só do admin vinda de configuração e clientes com as senhas literais atuais em hash; (c) não criar usuários no seed; (d) **criar os 3 usuários de demonstração com senhas vindas de configuração, sem nenhuma senha no código** (seção 5.5.3) | T-04; database.py, config.py, .env.example |
| D-4 | Senhas legadas em texto puro em bancos `loja.db` gerados pela versão original (F-04) | (a) sem compatibilidade: as contas legadas deixam de fazer login até redefinição, e a refatoração não recria nem apaga nenhum banco; (b) migração no login: aceitar o valor legado e regravá-lo como hash; (c) **migração explícita por script, só das senhas, preservando todos os outros dados** (seção 5.5.4) | T-04; models/usuario.py, migrar_senhas.py |
| D-5 | Host padrão (F-08) | (a) `127.0.0.1`, configurável por `HOST`; (b) manter `0.0.0.0` como padrão, com debug desligado | T-02; config.py, app.py |
| D-6 | `GET /relatorios/vendas` e `GET /usuarios`, `/usuarios/<id>` (F-11) | (a) manter públicos e documentar o risco; (b) exigir `ADMIN_TOKEN` | T-15; routes/relatorios.py, routes/usuarios.py |

**Mecanismo comum de token** (vale para D-1 b/c, D-2 b e D-6 b):
- O token vem da variável de ambiente `ADMIN_TOKEN`, sem fallback literal, e é enviado no header `X-Admin-Token`.
- A comparação é feita com `hmac.compare_digest`.
- A autorização é verificada **antes** de ler o corpo.
- Respostas:
  - `ADMIN_TOKEN` não configurado → `403 {"erro": "Operação administrativa desabilitada"}`;
  - header ausente ou incorreto → `401 {"erro": "Não autorizado"}`.
- O token nunca entra em logs, respostas ou evidências.

#### 5.5.1 D-1 (c): `POST /admin/query` com consultas predefinidas

**Contrato proposto**

- Requisição:
  - header `X-Admin-Token: <token>`;
  - corpo JSON `{"consulta": "<nome>", "parametros": {...}}`, em que `parametros` é opcional.
- Catálogo fixo no código (`models/admin.py`). Todas as consultas são `SELECT` parametrizados e só usam colunas não sensíveis; a coluna `senha` nunca é selecionada.

| `consulta` | Parâmetros | `dados` (lista de objetos) |
|---|---|---|
| `contagem_por_tabela` | — | `[{"tabela": "produtos", "quantidade": n}, …]` para as 4 tabelas |
| `pedidos_por_status` | — | `[{"status", "quantidade", "total"}]` |
| `produtos_estoque_baixo` | `limite`: inteiro ≥ 0, padrão 5 | `[{"id", "nome", "estoque"}]` com `estoque <= limite` |
| `usuarios_por_tipo` | — | `[{"tipo", "quantidade"}]` |

- Sucesso: `200 {"dados": [...], "sucesso": true}`, o mesmo envelope do SELECT original.
- Erros:
  - corpo ausente ou não-JSON → `400 {"erro": "Dados inválidos"}`;
  - corpo com `sql` → `400 {"erro": "Execução de SQL arbitrário não é suportada; informe 'consulta'"}`, e nada é executado;
  - `consulta` ausente → `400 {"erro": "Consulta não informada"}`, adaptando a mensagem original "Query não informada";
  - nome desconhecido → `400 {"erro": "Consulta inválida. Válidas: [...]"}`;
  - parâmetro inválido → `400`;
  - autorização → 403/401, conforme o mecanismo comum.
- Mudanças em relação ao original:
  - o endpoint exige token;
  - o campo `sql` deixa de ser aceito;
  - escritas e o `{"mensagem": "Query executada"}` desaparecem;
  - o 500 deixa de expor `str(e)`.
- O que se preserva: rota, método, envelope e a finalidade de consulta administrativa de leitura.

**Testes (no banco isolado, com `ADMIN_TOKEN` gerado na hora para o teste):**
1. Sem `ADMIN_TOKEN` no ambiente → 403. Com token configurado e sem header → 401. Header errado → 401. Nos três casos, a contagem por tabela feita direto no arquivo isolado fica igual.
2. Com o token correto, cada uma das 4 consultas → 200, e `dados` bate com a mesma consulta feita direto no banco isolado. `produtos_estoque_baixo` é testada com `limite` 0, 5 e 1000.
3. `{"sql": "DELETE FROM produtos"}` com token correto → 400, e as contagens não mudam. `{"sql": "SELECT * FROM usuarios"}` → 400, e o corpo não contém `senha`.
4. Nome desconhecido, `limite` com valor `"5; DROP TABLE produtos"`, `-1`, `true` ou `"abc"` → 400, com as tabelas intactas.
5. Busca nos corpos de todas as respostas: nenhuma ocorrência de `senha` nem de prefixos de hash (`scrypt:`, `pbkdf2:`).
6. Nenhuma resposta ou log contém o valor do token.

#### 5.5.2 D-2 (b): `POST /admin/reset-db` protegido por `ADMIN_TOKEN`

**Contrato**
- Rota e método iguais, com o header `X-Admin-Token` obrigatório.
- Com o token correto: `200 {"mensagem": "Banco de dados resetado", "sucesso": true}`, o mesmo corpo de hoje. Efeito: `DELETE` em `itens_pedido`, `pedidos`, `produtos` e `usuarios` numa única transação (`with db:`), com rollback se houver falha.
- Sem configuração ou sem autorização: 403/401, conforme o mecanismo comum, sem nenhum efeito.
- O `print` vira `logger.warning`.
- Comportamento preservado após o reset: nada é recriado no mesmo processo, e o seed volta a rodar na próxima inicialização, porque `produtos` está vazia. Isso vale para os produtos e, conforme D-3, para os usuários.

**Testes (no banco isolado, executados por último na matriz):**
1. Preparo: banco isolado com seed e um pedido criado via `POST /pedidos`. Antes de cada caso, registrar `COUNT(*)` das 4 tabelas, consultando direto o arquivo isolado com `sqlite3` fora da aplicação.
2. Sem `ADMIN_TOKEN` → 403, contagens iguais. Token configurado e sem header → 401, contagens iguais. Header incorreto → 401, contagens iguais.
3. Header correto → 200 com o corpo da linha de base. Depois, as contagens das 4 tabelas são 0, `GET /produtos` devolve `{"dados": [], "sucesso": true}` e `GET /health` devolve contagens zeradas.
4. Ao reiniciar a aplicação com o mesmo banco isolado, o seed se repete como na linha de base (comparação das contagens).
5. Teste à parte que força falha em um dos `DELETE`, num banco isolado de teste, e confirma por consulta que nenhuma tabela foi esvaziada.

#### 5.5.3 D-3 (d): seed de usuários com credenciais vindas da configuração

**Comportamento**
- Os 3 usuários de demonstração continuam com os mesmos nome, e-mail e tipo: Admin `admin@loja.com` com tipo `admin`, e João e Maria com tipo `cliente`.
- As senhas vêm de `SEED_SENHA_ADMIN`, `SEED_SENHA_JOAO` e `SEED_SENHA_MARIA` e são gravadas com `generate_password_hash`. Nenhuma senha fica no código ou no repositório; `.env.example` traz só placeholders.
- Se a variável de um usuário estiver ausente ou vazia, esse usuário **não** é criado e o log mostra um aviso com o e-mail, nunca com senha. Não há senha padrão nem senha gerada impressa no log.
- O seed de produtos não muda e a condição original continua: seed só quando `produtos` está vazia.

**Como testar no ambiente isolado**
1. Gerar senhas de teste na hora (`python -c "import secrets; print(secrets.token_urlsafe(16))"`), exportá-las só no processo da cópia isolada e apontar `DATABASE_PATH` para um arquivo no diretório temporário.
2. `POST /login` para cada um dos 3 usuários com a senha configurada → 200, e `dados` com os mesmos campos e valores (`id`, `nome`, `email`, `tipo`) da linha de base. A linha de base usa as senhas originais; a comparação é sobre os campos da resposta, não sobre a senha.
3. Senha incorreta → 401 com o corpo da linha de base.
4. Consulta direta ao banco isolado: a coluna `senha` tem prefixo de hash e não é igual à senha configurada.
5. Iniciar outra cópia isolada sem as variáveis: nenhum usuário de demonstração em `GET /usuarios`, login 401 e aviso no log.
6. Nas evidências, as senhas de teste aparecem como `<removido>`.

#### 5.5.4 D-4: senhas legadas

**Verificação por listagem** (`find . -name '*.db' -o -name '*.db-*' -o -name '*.sqlite*'` e `ls -la` no alvo): **não existe** `loja.db` nem outro arquivo de banco no projeto. Nenhum banco foi aberto. Ainda assim, o código original cria `loja.db` no diretório de onde é executado, então podem existir bancos fora do repositório. Por isso a decisão continua valendo. A refatoração **não** recria, apaga nem altera nenhum banco existente sem uma decisão explícita.

**Opção (c): migração explícita (`migrar_senhas.py`)**
- Só roda quando um operador a executa à mão: `python migrar_senhas.py --database <caminho>`. Por padrão é um dry-run, que apenas conta as senhas legadas. `--aplicar` faz a alteração. O script nunca é chamado pela aplicação.
- Considera legado todo valor de `usuarios.senha` que não tenha formato de hash do Werkzeug (`scrypt:` ou `pbkdf2:`). Cada um desses valores é trocado por `generate_password_hash(valor)`.
- Executa um único `UPDATE usuarios SET senha = ? WHERE id = ?` por registro, tudo numa só transação com rollback em caso de falha. Nenhuma outra coluna ou tabela é tocada.
- É idempotente: rodar de novo não altera nada.
- Recomenda fazer uma cópia de segurança antes, mas não a cria sozinho.
- Até a migração ser aplicada, a aplicação refatorada recusa o login das contas legadas (401) e registra um aviso na inicialização com a quantidade de senhas legadas encontradas, sem alterar dados.

**Testes da opção (c), só em cópia isolada:**
1. Gerar um banco com o código **original** no diretório temporário, criar um usuário extra e um pedido.
2. Gravar um dump de todas as tabelas, com `usuarios.senha` excluída.
3. Dry-run: informa N legados, e um hash do arquivo antes e depois confirma que nada mudou.
4. `--aplicar`: todas as senhas ficam com prefixo de hash. O dump das demais colunas e tabelas é idêntico ao anterior. O login com as senhas originais → 200 e com senha errada → 401.
5. Segunda execução: 0 alterações.
6. Falha forçada no meio, num banco de teste: nenhuma senha alterada.

### 5.6 Validação planejada

- **Linha de base:** o código original roda numa cópia isolada no diretório temporário da sessão, com `loja.db` novo criado ali.
- **Ambiente:** venv temporário fora do repositório com `pip install -r requirements.txt` (exige rede), registrando as versões instaladas. Interpretador base: 3.14.0.
- **Endpoints a verificar:** os 19, cobrindo sucesso, 404, entrada inválida e payloads com aspas, com efeitos conferidos por leitura posterior ou por consulta direta ao banco isolado. A mesma matriz é repetida na cópia refatorada.
- **Testes específicos das decisões:**
  - seções 5.5.1 a 5.5.4, conforme as opções escolhidas;
  - endpoints protegidos testados com e sem `ADMIN_TOKEN` configurado, seguindo o critério de preservação da seção 5.3;
  - falha forçada no meio da criação de pedido para confirmar o rollback;
  - destrutivos por último.
- **Integrações externas:** não existem; as notificações são apenas `print`/log.
- **Segredos de teste:** tokens e senhas gerados na hora e removidos das evidências.

### 5.7 Destino do relatório e das evidências

Caminhos relativos à raiz do repositório; os dois podem ser trocados por você. Nada é gravado antes da confirmação.
- Relatório de auditoria (este documento, sem alterações): `reports/audit-project-1.md`
- Evidências da Fase 3, com dados sensíveis removidos: `reports/evidence/code-smells-project/`

## 6. Limitações

- **Versões instaladas não verificadas:** não há ambiente virtual no alvo. Serão registradas na Fase 3.
- **Compatibilidade de Python:** a compatibilidade de Flask 3.1.1 e flask-cors 5.0.1 com Python 3.14 só será confirmada na instalação da Fase 3.
- **Comportamento só por leitura:** o comportamento em execução (status de JSON inválido, efeito da transação compartilhada, concorrência no estoque) foi deduzido do código, sem executar.
- **Bancos existentes:** a verificação foi só por listagem dentro do projeto e não encontrou nenhum. Bancos fora do repositório não foram procurados.
- **Fora do escopo do refactor:**
  - Ao mudar o status para `cancelado`, o código só imprime "Devolver estoque" e não devolve nada (`controllers.py:249-250`). Implementar isso seria uma regra nova, então só fica registrado.
  - Falta `UNIQUE` em `usuarios.email`. Mudar o schema não está no plano; isso fica como problema remanescente.

================================
Total: 21 achados (CRITICAL: 7 | HIGH: 6 | MEDIUM: 4 | LOW: 4)
================================
