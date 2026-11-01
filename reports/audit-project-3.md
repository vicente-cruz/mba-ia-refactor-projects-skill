================================
RELATÓRIO DE AUDITORIA ARQUITETURAL
================================

## 1. Identificação

| Campo | Valor |
|---|---|
| Projeto | task-manager-api (`task-manager-api/`) |
| Data | 2026-10-31 (revisão 3) |
| Versão de referência | commit `f6eaae357672157858e16e4b58b49d0e6839a506`. Working tree limpo para o código do alvo; a única entrada não versionada é `task-manager-api/.claude/` (a Skill, fora do escopo). |
| Stack | Python + Flask (declarada: 3.0.0; instalada: não verificado). Flask-SQLAlchemy 3.1.1 declarada; SQLAlchemy ≥ 2.0.16 pelo changelog. |
| Banco | SQLite, URI `sqlite:///tasks.db`. Pela documentação do Flask-SQLAlchemy 3.1, o arquivo efetivo fica em `<raiz do app>/instance/tasks.db`, e não na raiz como o README sugere. A confirmação em execução fica para a Fase 3. |
| Domínio | Gestão de tarefas (tasks, usuários, categorias, relatórios) |
| Ferramenta | refactor-arch (Claude Code) |
| Registro | Documento gravado com autorização explícita do usuário, antes da Fase 3: revisão 2 gravada em `reports/TaskManagerAPI-Fase02_Revisao.md` e depois movida pelo usuário para fora do repositório; revisão 3 gravada sobre esse mesmo arquivo, no local atual. Nenhum código, Skill ou dependência foi alterado e a aplicação não foi executada. A Fase 3 **não** foi iniciada. |
| Decisões | Consolidadas pelo usuário: D-1(a), D-2(a), D-3(b), D-4(a), D-5(a), D-6(a) (seção 5.5). |

## 2. Escopo

- Arquivos de código analisados: 15 | Linhas físicas: 1158
- Lista: app.py (34), database.py (3), models/__init__.py (3), models/category.py (21), models/task.py (60), models/user.py (38), routes/__init__.py (1), routes/report_routes.py (223), routes/task_routes.py (299), routes/user_routes.py (211), seed.py (99), services/__init__.py (1), services/notification_service.py (48), utils/__init__.py (1), utils/helpers.py (116)
- Exclusões:
  - `.claude/`: a Skill.
  - `README.md`: documentação, lido.
  - `requirements.txt`: manifesto, lido.
- Natureza da análise: leitura estática, sem execução da aplicação, sem instalação de dependências e sem exploração de vulnerabilidades. Os imports foram analisados com `python3 -I -B` + `ast`, sem importar o projeto. A única gravação feita foi a deste documento, autorizada pelo usuário.

## 3. Resumo por severidade

| CRITICAL | HIGH | MEDIUM | LOW | Total |
|---:|---:|---:|---:|---:|
| 4 | 5 | 6 | 4 | 19 |

Confirmados por leitura: 18 | Hipóteses não verificadas: 1 (F-05). Subitens que dependem de execução estão marcados dentro de cada achado.

## 4. Achados

### F-01 — [CRITICAL] O hash de senha é devolvido nas respostas da API (AP-03)

- **Localização:** `models/user.py:16-25`; `routes/user_routes.py:33-40`; `routes/user_routes.py:85-86`; `routes/user_routes.py:129`; `routes/user_routes.py:207-211`
- **Status:** Confirmado por leitura
- **Evidência:** `User.to_dict()` inclui `'password': self.password` (models/user.py:21). Esse dicionário é devolvido por:
  - `GET /users/<id>`
  - `POST /users`
  - `PUT /users/<id>`
  - `POST /login`, no campo `user`

  O valor é o hash MD5 sem sal, não a senha em texto puro. `GET /users` não inclui o campo (user_routes.py:15-23).
- **Impacto:** quem chama esses endpoints obtém hashes reversíveis offline.
- **Justificativa da severidade:** base CRITICAL, mantida porque o hash é fraco (F-02).
- **Recomendação:** representação pública sem `password` em todos os pontos de serialização (T-03).

### F-02 — [CRITICAL] Senhas armazenadas com MD5 sem sal (AP-04)

- **Localização:** `models/user.py:27-32`
- **Status:** Confirmado por leitura
- **Evidência:** `hashlib.md5(pwd.encode()).hexdigest()` na gravação e comparação com `==` na verificação.
- **Impacto:** o hash é rápido, sem sal e determinístico.
- **Justificativa da severidade:** combina-se com a exposição de F-01, então fica CRITICAL.
- **Recomendação:** `werkzeug.security.generate_password_hash`/`check_password_hash`. Um formato armazenado malformado deve resultar em credencial inválida, nunca em 500. Hashes MD5 existentes migram no login (D-2a). Um hash forte **não** resolve as senhas publicadas no seed (F-03) (T-04).

### F-03 — [CRITICAL] Segredos, credenciais SMTP e senhas do seed fixos no código versionado (AP-02)

- **Localização:** `app.py:13`; `services/notification_service.py:7-10`; `seed.py:17-34`
- **Status:** Confirmado por leitura (os arquivos estão em `git ls-files`)
- **Evidência:**
  - `SECRET_KEY = 'super-sec…'`
  - SMTP com usuário `taskmanager@…` e senha `'sen…'`
  - O seed cria três contas com email e senha conhecidos, entre elas o **admin** `joao@…`, com senha de 4 caracteres (mascaradas: `12…`, `ab…`, `pa…`).
- **Impacto:**
  - Quem lê o repositório conhece a chave de assinatura e a credencial SMTP.
  - Quem lê o repositório também pode entrar como admin em qualquer banco populado pelo seed. Com autenticação real (D-1a), isso dá acesso administrativo imediato, e trocar o algoritmo de hash não muda nada.
- **Justificativa da severidade:** base CRITICAL.
- **Recomendação:**
  - `SECRET_KEY` persistente, vinda do ambiente, sem fallback, validada antes de inicializar o banco (5.5.1).
  - Remover `notification_service.py` (D-4a). Os valores continuam no histórico do git; se forem credenciais reais, precisam ser trocadas fora do código.
  - Senhas do seed vindas do ambiente (D-5a) (T-02).

### F-04 — [CRITICAL] Alteração e exclusão de contas sem autenticação; token de login falso (AP-06)

- **Localização:** `routes/user_routes.py:92-132`; `routes/user_routes.py:134-151`; `routes/user_routes.py:42-78`; `routes/user_routes.py:207-211`; `models/user.py:34-38`
- **Status:** Confirmado por leitura. Não há middleware, decorator nem checagem de identidade em nenhuma rota.
- **Evidência:**
  - `PUT /users/<id>` troca `password`, `email`, `role` e `active` de qualquer usuário (114-125).
  - `DELETE /users/<id>` apaga o usuário e as suas tasks (140-146).
  - `POST /users` aceita `role: 'admin'` informado pelo cliente (52, 71-78).
  - `/login` devolve `'fake-jwt-token-' + id`, um valor previsível e nunca verificado.
  - `is_admin()` não é usado.
- **Impacto:** tomada de conta (trocar a senha via PUT e depois fazer login) e destruição de dados por qualquer cliente da rede.
- **Justificativa da severidade:** CRITICAL. O achado se restringe às operações de conta; o CRUD de tasks e categorias não foi marcado.
- **Recomendação:** token assinado vinculado à instância da conta (D-1a), detalhado em 5.5.1 (T-15).

### F-05 — [HIGH] O log de erro pode conter o hash de senha e outros parâmetros SQL (AP-03)

- **Localização:** `routes/user_routes.py:87-89`; `routes/task_routes.py:151-153`
- **Status:** Hipótese não verificada. A leitura confirma que `print(f"ERRO: {str(e)}")` imprime a exceção do `commit`. Que o texto de `IntegrityError`/`StatementError` inclua os parâmetros do `INSERT` (entre eles `password`) é o comportamento documentado do SQLAlchemy quando `hide_parameters` é falso, mas não foi observado em execução.
- **Evidência:** o caminho é alcançável quando o `commit` falha, por exemplo numa corrida em que dois cadastros passam a verificação de email (67-69) e o segundo viola `unique`.
- **Impacto:** o hash e o email ficam no stdout ou nos logs coletados.
- **Justificativa da severidade:** base CRITICAL, rebaixada para HIGH porque o caminho é de falha (corrida), a saída é local e o vazamento ainda não foi confirmado.
- **Recomendação:**
  - `SQLALCHEMY_ENGINE_OPTIONS = {"hide_parameters": True}` e `SQLALCHEMY_ECHO` fixo em falso.
  - Logging sem `str(e)` de exceções de banco em mensagens próprias.
  - Teste do log bruto antes da sanitização (5.6.5) (T-12, T-13).

### F-06 — [HIGH] O seed apaga tudo e reinsere em transações separadas (AP-09)

- **Localização:** `seed.py:11-14`; `seed.py:37`; `seed.py:63`; `seed.py:92`
- **Status:** Confirmado por leitura
- **Evidência:** `Task/User/Category.query.delete()` seguido de `commit` (14), depois `commit` dos usuários (37), das categorias (63) e das tasks (92).
- **Impacto:** qualquer falha depois da linha 14 deixa o banco vazio ou parcialmente populado, e os dados anteriores se perdem de forma irreversível.
- **Justificativa da severidade:** base HIGH. A operação é destrutiva e é uma unidade de negócio (reset + carga), embora seja um script.
- **Recomendação:**
  1. Validar as entradas, incluindo as senhas (D-5a), **antes** de qualquer exclusão.
  2. Fazer as exclusões e reinserções numa única transação, usando `db.session.flush()` para obter os IDs de usuários e categorias.
  3. Um único `commit` ao final.
  4. Em qualquer exceção, `rollback` integral e código de saída diferente de zero (T-08).

### F-07 — [HIGH] Regras de negócio, agregações e persistência dentro das rotas (AP-07)

- **Localização:** `routes/task_routes.py:11-63,85-154,156-223,240-299`; `routes/user_routes.py:42-151`; `routes/report_routes.py:12-155,157-223`
- **Status:** Confirmado por leitura
- **Evidência:**
  - Os handlers misturam `request`, validação, `Model.query`/`db.session`, cálculo de atraso e estatísticas.
  - `summary_report` faz 12 contagens, varre as tasks e calcula dias de atraso e produtividade.
  - As regras do model (`is_overdue`, `validate_*`) são reimplementadas.
  - `/categories` está no blueprint de relatórios.
- **Impacto:** as regras só podem ser testadas via HTTP e não são reutilizáveis.
- **Justificativa da severidade:** base HIGH. Não é God Class.
- **Recomendação:** `controllers/`, consultas e regras nos models, rotas finas e blueprint próprio para categorias com os mesmos caminhos (T-05, T-06).

### F-08 — [HIGH] Efeitos colaterais na importação, app sem factory e SMTP concreto (AP-10)

- **Localização:** `app.py:9-31`; `seed.py:2`; `services/notification_service.py:5-20`
- **Status:** Confirmado por leitura
- **Evidência:**
  - `db.create_all()` roda na importação (30-31).
  - O seed importa o app global.
  - `smtplib.SMTP` é instanciado diretamente.
- **Impacto:** não é possível criar o app com configuração de teste sem criar o banco padrão.
- **Justificativa da severidade:** base HIGH.
- **Recomendação:**
  - `create_app(overrides)` que valida a configuração, inclusive `SECRET_KEY`, **antes** de `db.init_app` e da preparação do schema.
  - `app.py` não cria a aplicação no nível do módulo; `create_app()` só é chamado sob `if __name__ == '__main__'`. Importar `app` não lê o ambiente nem cria arquivos.
  - Schema preparado explicitamente dentro da factory (5.5.1, migração), preservando a criação ao iniciar.
  - Seed usando a factory.
  - `notification_service.py` removido (D-4a) (T-14).

### F-09 — [HIGH] Debug ligado e bind em todas as interfaces fixos no código (AP-11)

- **Localização:** `app.py:34`; `app.py:15`
- **Status:** Confirmado por leitura
- **Evidência:** `app.run(debug=True, host='0.0.0.0', port=5000)`. `CORS(app)` libera todas as origens, sem credenciais.
- **Impacto:** o depurador do Werkzeug fica alcançável pela rede.
- **Justificativa da severidade:** base HIGH. O CORS é só uma observação.
- **Recomendação:** `FLASK_DEBUG` desligado por padrão, `HOST` com padrão `127.0.0.1` (D-3b), `PORT` com padrão 5000 e `CORS_ORIGINS` com padrão `*` (T-02).

### F-10 — [MEDIUM] Consultas N+1 em listagens e relatórios (AP-12)

- **Localização:** `routes/task_routes.py:14,41-57`; `routes/user_routes.py:12-22`; `routes/report_routes.py:53-56`; `routes/report_routes.py:159-163`
- **Status:** Confirmado por leitura. Os números abaixo são **limites derivados do código**, não contagens medidas.
- **Evidência:**
  - `GET /tasks`: até 1 + 2N consultas. É um limite potencial: `Query.get` consulta primeiro o identity map da sessão, então usuários e categorias repetidos não geram nova consulta. Na prática o número tende a 1 + (usuários distintos) + (categorias distintas), mas isso não foi medido.
  - `GET /users`: 1 + N, via lazy load de `u.tasks` (uma consulta por coleção).
  - `/reports/summary`: 1 + U consultas `filter_by`, mais 12 contagens.
  - `GET /categories`: 1 + C contagens.
- **Impacto:** custo que cresce com o volume de dados.
- **Justificativa da severidade:** base MEDIUM.
- **Recomendação:** `outerjoin` + `func.count` + `group_by` ou `selectinload`, preservando ordem, campos e zeros. A contagem real será **medida** antes e depois na Fase 3 (T-09).

### F-11 — [MEDIUM] Validação de entrada insuficiente (AP-13)

- **Localização:** `routes/task_routes.py:87-144,162-213,260-264`; `routes/user_routes.py:44-72,98-125,187-202`; `routes/report_routes.py:169-180,196-202`
- **Status:** Confirmado por leitura. Os casos que dependem do driver ou do parser estão marcados com † em 5.3.1 e serão medidos na linha de base.
- **Evidência:**
  - Comparações e `len()` sem verificação de tipo (`priority < 1`, `len(title)`), o que leva a `TypeError`.
  - `int()` na busca, o que leva a `ValueError`.
  - Corpo JSON não-objeto:
    - no POST, `data.get` gera `AttributeError`;
    - no PUT, um número ou booleano verdadeiro (`5`, `true`) passa por `if not data` e causa `TypeError` no operador `in` (`'title' in 5`);
    - uma lista ou string sem os nomes de campo (`[1]`, `"x"`) faz todos os `'campo' in data` serem falsos, e `PUT /tasks` responde 200 alterando apenas `updated_at` (215-218).
  - `update_category` não verifica corpo nulo.
  - Cor, `active` e IDs zero ou vazios são aceitos sem verificação.
  - Detalhe completo em 5.3.1.
- **Impacto:** erros 500 e dados inválidos gravados.
- **Justificativa da severidade:** base MEDIUM.
- **Recomendação:** contrato de validação explícito (5.3.1), com as restrições novas aprovadas em D-6a (T-10).

### F-12 — [MEDIUM] Regras e validações duplicadas e divergentes (AP-14)

- **Localização:**
  - Atraso: `routes/task_routes.py:30-39,71-80,283-287`; `routes/user_routes.py:171-180`; `routes/report_routes.py:33-43,132-135`; `models/task.py:50-60`
  - Status: `routes/task_routes.py:110,177`; `models/task.py:39`; `utils/helpers.py:75,110`
  - Roles: `routes/user_routes.py:71,120`; `utils/helpers.py:111`
  - Email: `routes/user_routes.py:61,106`; `utils/helpers.py:21`
  - Serialização de task: `routes/task_routes.py:17-28`; `routes/user_routes.py:162-169`
  - Validação de task: `utils/helpers.py:57-108`
- **Status:** Confirmado por leitura
- **Evidência:**
  - A regra de atraso aparece 6 vezes, além do model.
  - `helpers.process_task_data` faz `strip()` e aceita `dd/mm/YYYY`, ao contrário das rotas.
  - As mensagens de data inválida diferem entre POST e PUT.
- **Impacto:** cópias que já divergem entre si.
- **Justificativa da severidade:** base MEDIUM.
- **Recomendação:** fonte única nos models. O comportamento que vale é o das rotas; `helpers` não é usado. As diferenças intencionais entre POST e PUT e entre respostas são preservadas (5.3) (T-06, T-10).

### F-13 — [MEDIUM] `Model.query.get()` é API legada no SQLAlchemy 2.x (AP-15)

- **Localização:** `routes/task_routes.py:42,51,67,117,122,158,188,195,227`; `routes/user_routes.py:29,94,136,155`; `routes/report_routes.py:105,192,213`
- **Status:** Confirmado por leitura e pela documentação
- **Evidência:** 16 chamadas.
- **Impacto:** avisos de API legada e risco de remoção futura.
- **Justificativa da severidade:** base MEDIUM.
- **Recomendação:** `db.session.get(Model, id)` em `find_by_id` (T-11).
- **Fonte oficial:** https://docs.sqlalchemy.org/en/20/orm/queryguide/query.html — "Deprecated since version 2.0: The Query.get() method is considered legacy… now available as Session.get()". Flask-SQLAlchemy 3.1.x: "The query interface is considered legacy". Instalada: não verificado.

### F-14 — [MEDIUM] `datetime.utcnow()` está deprecated desde o Python 3.12 (AP-15)

- **Localização:** `models/task.py:15,16,52`; `models/user.py:14`; `models/category.py:11`; `routes/task_routes.py:31,72,215,285`; `routes/user_routes.py:172`; `routes/report_routes.py:35,42,45,71,133`; `services/notification_service.py:35`; `utils/helpers.py:38`; `seed.py:66,67,69,70,74`
- **Status:** Confirmado por leitura e pela documentação. O runtime do projeto não foi verificado.
- **Evidência:** o código usa datetimes ingênuos de `utcnow()`.
- **Impacto:** `DeprecationWarning` no Python ≥ 3.12.
- **Justificativa da severidade:** base MEDIUM.
- **Recomendação:** função única `utc_now()` que retorne `datetime.now(timezone.utc).replace(tzinfo=None)`. Ela mantém a compatibilidade com os valores gravados e serve de ponto único para controlar o tempo nos testes (T-11).
- **Fonte oficial:** https://docs.python.org/3.12/library/datetime.html — "Deprecated since version 3.12: Use datetime.now() with UTC instead."

### F-15 — [MEDIUM] Tratamento de erros disperso; rollback e conflito de unicidade inconsistentes (AP-16)

- **Localização:** `routes/task_routes.py:13,62-63,151-154,166-223,236-238`; `routes/user_routes.py:80-90,102-132,149-151`; `routes/report_routes.py:186-188,207-209,221-223`; `utils/helpers.py:46,49,88`; `app.py` (sem `errorhandler`)
- **Status:** Confirmado por leitura.
- **Evidência:**
  - `except:` sem tipo. `GET /tasks` mascara qualquer falha com 500 'Erro interno'.
  - Não há handler central, então as exceções de F-11 viram 500 em HTML.
  - Um `IntegrityError` de email no `commit` vira 500 'Erro ao criar usuário'/'Erro ao atualizar', em vez de 409.
  - `update_task`/`update_user` alteram atributos campo a campo e podem retornar 400/404 no meio do caminho sem `rollback` explícito (ex.: título alterado em 171 e prioridade inválida em 182-183). Consultas posteriores (`User.query.get`, 188) podem disparar autoflush, que envia as alterações pendentes ao banco **dentro da transação aberta**, sem confirmá-la.
  - **Correção em relação à revisão anterior:** o Flask-SQLAlchemy remove a sessão no fim do contexto da aplicação (`session.remove()` no teardown). Fechar a sessão faz rollback da transação pendente, então essas alterações não confirmadas são descartadas. Nenhum caminho do código original faz `commit` depois desses retornos antecipados, logo **não há persistência parcial demonstrada no original**. O comportamento será observado na linha de base (5.6.3 #6).
- **Impacto:**
  - Formato de erro inconsistente (JSON × HTML).
  - Status errado em conflito de unicidade.
  - A correção depende de um mecanismo implícito, o descarte no teardown. Código que fizer novo `commit` no mesmo contexto depois de uma validação falha, como controllers que encadeiam operações ou testes que reutilizam o contexto, confirmaria as alterações pendentes. É um risco de manutenção, não um defeito observado.
- **Justificativa da severidade:** base MEDIUM.
- **Recomendação:** especificação em 5.2.1 (T-12, T-08).

### F-16 — [LOW] Código morto (AP-19)

- **Localização:**
  - Imports: `app.py:7`; `models/task.py:3`; `routes/task_routes.py:7`; `routes/user_routes.py:6`; `routes/report_routes.py:7-8`; `utils/helpers.py:3-7`
  - Funções e módulos: `utils/helpers.py:9-116`; `services/notification_service.py:1-48`; `models/task.py:38-60`; `models/user.py:34-38`
  - Dependências: `requirements.txt:4-6`
- **Status:** Confirmado por leitura, `ast` e `grep`
- **Evidência:**
  - Imports sem uso listados na versão anterior: `os`, `sys`, `json`, `time`, `hashlib`, `math`, `format_date`, `calculate_percentage`.
  - `helpers.py` e `NotificationService` não têm consumidores.
  - Os métodos `validate_*`, `is_overdue` e `is_admin` não são chamados.
  - marshmallow, requests e python-dotenv não são importados.
  - Falso positivo descartado: as reexportações de `models/__init__.py`.
- **Impacto:** ruído.
- **Justificativa da severidade:** base LOW.
- **Recomendação:** remover o código morto, incluindo `services/` (D-4a), reaproveitar as regras úteis no model e manter `requirements.txt` sem mudanças (sugestão registrada) (T-13).

### F-17 — [LOW] Literais de regra sem nome (AP-17)

- **Localização:** `routes/task_routes.py:96-114,167-184`; `routes/user_routes.py:64,115`; `routes/report_routes.py:45,129`; `utils/helpers.py:110-116`
- **Status:** Confirmado por leitura
- **Evidência:** 3/200, 1–5/3, 4, 7 dias, `<= 2`, `'#000000'`. As constantes de helpers não são usadas.
- **Recomendação:** constantes nos models, com os mesmos valores e operadores (T-13).

### F-18 — [LOW] Logging com `print` (AP-20)

- **Localização:** `routes/task_routes.py:149,153,219,234`; `routes/user_routes.py:83,89,147`; `services/notification_service.py:21,24`; `utils/helpers.py:39-41`
- **Status:** Confirmado por leitura
- **Evidência:** sem níveis, com nome e email de usuários. Os `print` do seed são saída de CLI e foram desconsiderados. O caso do `str(e)` está em F-05.
- **Recomendação:** `logging` registrando apenas IDs (T-13).

### F-19 — [LOW] Nomes pouco descritivos (AP-18)

- **Localização:** `routes/task_routes.py:16,51,283`; `routes/user_routes.py:14`; `routes/report_routes.py:24-28,161`; `models/task.py:45`; `models/category.py:14`; `seed.py:16-78`
- **Status:** Confirmado por leitura
- **Recomendação:** renomear apenas identificadores internos (T-13).

**Falsos positivos descartados:**
- `like(f'%{query}%')`: é parametrizado.
- `db = SQLAlchemy()`: é a extensão do framework.
- `delete_user`: faz um único `commit`.
- `NotificationService.notifications`: é estado de instância, em código morto.

## 5. Plano de refatoração proposto

### 5.1 Estrutura-alvo

```
task-manager-api/
├── app.py              # create_app(overrides): valida config → init db → prepara schema → handlers → blueprints;
│                       # create_app() só sob __main__ (importar não tem efeitos); python app.py
├── config.py           # [novo] env: SECRET_KEY (obrigatória), DATABASE_URL, FLASK_DEBUG, HOST (padrão 127.0.0.1),
│                       #        PORT, CORS_ORIGINS, TOKEN_MAX_AGE; SQLALCHEMY_ENGINE_OPTIONS hide_parameters
├── database.py         # db + init_schema() (create_all + migração aditiva de users.auth_nonce) + commit_or_rollback()
├── errors.py           # [novo] ValidationError, NotFoundError, ConflictError, AuthError(401), ForbiddenError(403); handlers {'error': ...}
├── auth.py             # [novo] emissão/verificação do token assinado; decorators require_auth / optional_auth
├── models/             # [reaproveitado] task.py user.py category.py: constantes, validação, is_overdue, consultas, to_dict público
├── controllers/        # [novo] task, user, category, report
├── routes/             # [reaproveitado] task, user, report, category (novo arquivo; mesmos caminhos)
├── seed.py             # factory + transação única + senhas do ambiente (D-5a)
└── .env.example        # [novo] valores fictícios
```

`utils/helpers.py` e `services/` são removidos (sem consumidores; D-4a). Cada camada nova se justifica por um achado:
- `controllers/` e `errors.py`: F-07 e F-15.
- `config.py`: F-03 e F-09.
- `auth.py`: F-04 (D-1a).

#### 5.2.1 Erros, transações e logs

1. **Validar antes de alterar.** O controller valida o payload inteiro com uma função pura que devolve os dados normalizados e resolve as entidades referenciadas (usuário, categoria) **antes** de alterar qualquer objeto da sessão. Um 400/404 por validação nunca deixa alteração pendente, sem depender do descarte no teardown.
2. **Um commit por operação.** `commit_or_rollback()` envolve `flush` e `commit`:
   - `IntegrityError` da restrição `users.email`: `rollback()` e `ConflictError('Email já cadastrado')`, que gera 409 com a mesma mensagem da verificação prévia.
   - Outra `IntegrityError` ou `SQLAlchemyError`, incluindo falhas de autoflush e flush: `rollback()` e nova exceção. O handler responde 500 com a mensagem da operação (`'Erro ao criar task'`, `'Erro ao atualizar'`, etc.), preservando os textos atuais.
3. **Rede de segurança.** O handler de `Exception` chama `db.session.rollback()` antes de responder 500 com `{'error': 'Erro interno'}`. O descarte no fim do contexto continua existindo, mas o código não depende dele.
4. **Recuperação depois do conflito.** São duas propriedades distintas, testadas separadamente (5.6.4):
   - **Recuperação da aplicação:** a requisição seguinte responde normalmente. Isso não prova nada sobre a sessão anterior, porque cada requisição usa uma sessão nova depois do teardown.
   - **Recuperação da mesma sessão:** dentro de um único contexto, depois do `ConflictError`, a mesma sessão (mesmo objeto retornado por `db.session()`) aceita `add` + `commit` sem `PendingRollbackError`.
5. **Autoflush.** As consultas de verificação acontecem antes das alterações. Onde isso não for possível, usamos `with db.session.no_autoflush`.
6. **Logs.**
   - `logging` configurado na factory.
   - Mensagens registram a operação e os IDs.
   - Nunca são registrados corpos de requisição, o cabeçalho `Authorization`, senhas, hashes, tokens, o `auth_nonce`, a `SECRET_KEY` nem emails.
   - `SQLALCHEMY_ENGINE_OPTIONS={'hide_parameters': True}` e `SQLALCHEMY_ECHO=False`.
   - Erros inesperados com `logger.exception`: o traceback não traz parâmetros SQL, por causa do `hide_parameters`.
   - Tokens nunca trafegam na query string, então o access log do Werkzeug, que registra caminho e query, não os captura.

### 5.2 Transformações, em ordem de aplicação

| Ordem | Transformação | Achados | Arquivos |
|---:|---|---|---|
| 1 | T-02 Configuração por ambiente; validação de `SECRET_KEY`; host 127.0.0.1 (D-3b) | F-03, F-09 | config.py, app.py, .env.example |
| 2 | T-14 App factory, schema explícito e migração aditiva | F-08 | app.py, database.py |
| 3 | T-12 Erros centralizados, rollback, `hide_parameters`, logging | F-15, F-05, F-18 | errors.py, database.py, app.py, config.py |
| 4 | T-03 Representação pública sem senha | F-01 | models/user.py |
| 5 | T-04 Hash de senha com migração MD5 no login (D-2a) | F-02 | models/user.py |
| 6 | T-05/T-06 Models, controllers e rotas finas | F-07, F-12 | models/*, controllers/*, routes/* |
| 7 | T-10 Validação conforme 5.3.1, com R-01 a R-09 (D-6a) | F-11, F-12 | models/*, controllers/* |
| 8 | T-15 Token assinado vinculado à conta e matriz de permissões (D-1a) | F-04 | auth.py, models/user.py, routes/user_routes.py, controllers/user_controller.py |
| 9 | T-08 Seed transacional com senhas do ambiente (D-5a) | F-06, F-03 | seed.py |
| 10 | T-09 Eliminar N+1 | F-10 | models/* |
| 11 | T-11 Migrar APIs legadas | F-13, F-14 | models/*, controllers/*, seed.py |
| 12 | T-13 Limpeza, constantes e nomes; remoção de services/ (D-4a) | F-16, F-17, F-19 | todos, services/, utils/ |

### 5.3 Contratos preservados

- **Rotas:** os 22 caminhos e métodos, incluindo os conversores `<int:...>`.
- **Comando de início:** `python app.py`, porta 5000 e URI `sqlite:///tasks.db` por padrão. O host padrão muda para `127.0.0.1` (D-3b; 5.4 D).
- **Schema:** continua sendo criado ao iniciar; a tabela `users` ganha uma coluna (5.5.1).
- **Corpos de resposta**, com as diferenças atuais mantidas de propósito:
  - `GET /tasks`: `to_dict` + `overdue`, `user_name`, `category_name`.
  - `GET /tasks/<id>`: `to_dict` + `overdue`, sem nomes.
  - `POST`/`PUT /tasks` e `/tasks/search`: `to_dict` sem `overdue`.
  - `GET /users/<id>/tasks`: subconjunto sem `user_id`, `category_id`, `updated_at` e `tags`, com `overdue`.
  - `GET /users`: com `task_count`.
  - `GET /users/<id>`: com `tasks`.
  - Relatórios e categorias com as mesmas chaves.
  - O `auth_nonce` nunca aparece em respostas.
- **Formato de erro:** `{'error': <mensagem>}`, com os textos atuais, inclusive os que diferem entre POST e PUT:
  - título vazio: `'Título é obrigatório'` × `'Título muito curto'`;
  - senha curta: `'Senha deve ter no mínimo 4 caracteres'` × `'Senha muito curta'`;
  - data: `'Formato de data inválido. Use YYYY-MM-DD'` × `'Formato de data inválido'`.
- **Comportamentos de PUT:** `PUT /categories` com `{}` responde 200 sem alteração, enquanto `PUT /tasks` e `PUT /users` com `{}` respondem 400 `'Dados inválidos'`. Em `PUT /tasks`, `user_id`/`category_id` nulo desvincula e `due_date` falso limpa a data.
- **Exclusões:** `DELETE /users` apaga as tasks do usuário. O efeito de `DELETE /categories` sobre as tasks vinculadas é preservado **conforme observado na linha de base**. A hipótese é que o backref zere `category_id`; nenhuma mudança será proposta antes dessa verificação.

#### 5.3.1 Especificação de validação

Na coluna "hoje", o que não tem marca foi rastreado na leitura do código: o caminho de execução é determinístico, dado o objeto que `get_json()` devolve. Os itens com † dependem do parser JSON, da coerção do SQLAlchemy ou do driver SQLite e serão medidos na linha de base. Nenhum "200" ou "aceito" sem † foi suposto: cada um decorre de uma verificação que o valor atravessa sem exceção.

**Corpo JSON** (POST/PUT de tasks, users e categories; POST /login)

| Entrada | Hoje | Proposto |
|---|---|---|
| Content-Type não JSON | 415 HTML † | 415, `{'error': 'Dados inválidos'}` |
| JSON malformado | 400 HTML † | 400, `{'error': 'Dados inválidos'}` |
| Falsos: `null`, `{}`, `[]`, `""`, `0`, `false` | POST (todos) e PUT /tasks, PUT /users: 400 `'Dados inválidos'` (`if not data`). PUT /categories, que não tem essa verificação: `{}`, `[]` e `""` → 200 sem alteração (`'name' in ...` é falso); `null`, `0` e `false` → 500 (`TypeError` no operador `in`). | Igual nos POST e nos PUT de tasks e users. PUT /categories: `{}` continua 200; `null`, `0`, `false` → 400 `'Dados inválidos'` (C-01); `[]` e `""` → 400 (R-01). |
| Número ou booleano verdadeiro (`5`, `1.5`, `true`) | POST: 500 (`AttributeError` em `.get`). Todos os PUT: 500 (`TypeError: argument of type 'int' is not iterable` no primeiro `'campo' in data`). | 400 `'Dados inválidos'` (C-01) |
| Lista ou string verdadeira **sem** nome de campo (`[1]`, `"x"`) | POST: 500 (`.get`). PUT /tasks e PUT /users: 200, nenhum campo alterado (todos os `in` falsos); `PUT /tasks` grava `updated_at`. PUT /categories: 200 sem alteração. | 400 `'Dados inválidos'` (C-01 no POST; R-01 nos PUT) |
| String que **contém** um nome de campo (`"title"`, `"name"`) | POST: 500. PUT: 500 (`data['title']` numa str gera `TypeError`). | 400 `'Dados inválidos'` (C-01) |
| Campos desconhecidos, `id`, `created_at`, `auth_nonce` | Ignorados | Ignorados |

**Tasks**

| Campo | POST (hoje → proposto) | PUT (hoje → proposto) |
|---|---|---|
| `title` | Ausente, nulo ou falso → 400 `'Título é obrigatório'` (mantido). str com menos de 3 / mais de 200 → `'Título muito curto'`/`'Título muito longo'` (mantido, sem `strip`). Número ou `true` → 500 (`len`) → 400 `'Título inválido'` (C-02). Lista com menos de 3 itens → 400 `'Título muito curto'`; com 3 ou mais → falha no `commit` † → 500 `'Erro ao criar task'` † → 400 `'Título inválido'` (C-02). | Nulo, número ou `true` → 500 (`len`) → 400 `'Título inválido'` (C-02). `""`/`false` → `false` gera 500 (`len(False)`), `""` gera `'Título muito curto'` (mantido); `false` → 400 `'Título inválido'` (C-02). Lista → como no POST, com `'Erro ao atualizar'` † → 400 `'Título inválido'` (C-02). |
| `description` | Ausente → `''`. `null` → `null`. str → ok. Número/bool → aceito, gravado com afinidade de texto † → 400 `'Descrição inválida'` (R-02). Lista/objeto → falha no `commit` † → 500 → 400 (C-10). | Igual; ausente não altera. |
| `status` | Ausente → `'pending'`. Fora de {pending, in_progress, done, cancelled}, de qualquer tipo, ou nulo → 400 `'Status inválido'` (mantido). | Igual; ausente não altera. |
| `priority` | Ausente → 3. int 1–5 → ok. `false` → 400 `'Prioridade deve ser entre 1 e 5'` (`False < 1`) → 400 `'Prioridade inválida'` (M-04). `true` → passa a faixa (`True` = 1) e é aceito † → 400 `'Prioridade inválida'` (R-03). Float inteiro (`2.0`) → passa a faixa; gravação † → aceito como 2 (mantido). `2.5` → passa a faixa; gravação † → 400 (R-03). `NaN` (se o parser aceitar †) → passa a faixa; gravação † → 400 (R-03). `±Infinity` † → 400 com mensagem de faixa → 400 `'Prioridade inválida'` (M-01). Fora da faixa → `'Prioridade deve ser entre 1 e 5'` (mantido). String, nulo, lista, objeto → 500 (`TypeError` na comparação) → 400 `'Prioridade inválida'` (C-03). | Igual. |
| `user_id` / `category_id` | Ausente/nulo → sem vínculo. Falsos (`0`, `false`, `""`) → `if` falso, gravados sem verificação → 400 `'Usuário inválido'`/`'Categoria inválida'` (R-04). int positivo inexistente → 404 `'Usuário não encontrado'`/`'Categoria não encontrada'` (mantido). `"1"` e `true` → resultado de `Query.get` † → 400 (R-04). Negativo, float, string não numérica → provável 404 † → 400 (M-02). Lista/objeto → `Query.get` † (500 ou 404) → 400 (C-11 se 500; M-02 se 404). | Nulo → desvincula (mantido). Demais casos iguais ao POST. |
| `due_date` | Ausente ou falso → sem data. str no formato `%Y-%m-%d` (dígitos sem zero à esquerda aceitos) → ok. Inválida, ou não-str verdadeira (`strptime` lança `TypeError`, capturado pelo `except:`) → 400 `'Formato de data inválido. Use YYYY-MM-DD'` (mantido). | Falso → limpa a data. Inválida → `'Formato de data inválido'` (mantido). |
| `tags` | Ausente ou falso → sem tags (`[]`). Lista de str → junção com vírgula. str → gravada como veio. Lista com elemento não-str → 500 (`join`, fora do `try`) → 400 `'Tags inválidas'` (C-04). Elemento com vírgula → aceito e dividido na leitura → 400 (R-05). Número/`true` → gravado † → 400 (R-05). Objeto não vazio → falha no `commit` † → 500 → 400 (C-04). Elemento vazio e tamanho total acima de 500 → mantidos, aceitos †. | `null` → `[]`. `""` → `[]`. Demais casos iguais ao POST. |

**Filtros de `GET /tasks/search`**

| Filtro | Comportamento |
|---|---|
| `q` | Qualquer texto, mantido. `%` e `_` continuam agindo como curingas, comportamento atual documentado. Aspas são tratadas como literal. |
| `status` | Não validado; valor inválido retorna `[]` (mantido). |
| `priority`, `user_id` | Vazio → filtro ignorado. Valor aceito por `int()` (ex.: `" 2 "`, `"+2"`) → mantido. Não inteiro (`"abc"`, `"2.5"`) → 500 (`ValueError`) → 400 `'Prioridade inválida'`/`'Usuário inválido'` (C-05). |
| Parâmetro repetido | Vale o primeiro (mantido). |

**Users**

| Campo | POST | PUT |
|---|---|---|
| `name` | Falso → `'Nome é obrigatório'` (mantido). Número/`true` → aceito, gravado com afinidade de texto † → 400 `'Nome inválido'` (R-06). Lista/objeto → falha no `commit` † → 500 `'Erro ao criar usuário'` → 400 (C-10). | `null` → 500 no `commit` (NOT NULL, `'Erro ao atualizar'`) → 400 `'Nome inválido'` (C-06). `""` → aceito → 400 (R-06). Número/bool → aceito † → 400 (R-06). Lista/objeto → 500 † → 400 (C-10). |
| `email` | Falso → `'Email é obrigatório'`. Regex atual mantida, sensível a maiúsculas. Não-str verdadeiro → 500 (`re.match` lança `TypeError`) → 400 `'Email inválido'` (C-06). Duplicado → 409. | Não-str (inclusive `null`) → 500 (`re.match`) → 400 `'Email inválido'` (C-06). str inválida → `'Email inválido'`. Duplicado → 409. Conflito no commit → 409 em vez de 500 (C-07). |
| `password` | Falso → `'Senha é obrigatória'`. Menos de 4 → `'Senha deve ter no mínimo 4 caracteres'` (mantido). Número/`true` → 500 (`len`) → 400 `'Senha inválida'` (C-06). Lista com 4+ itens → 500 (`.encode`) → 400 (C-06). | `null`/não-str → 500 (`len` ou `.encode`) → 400 `'Senha inválida'` (C-06). Menos de 4 → `'Senha muito curta'` (mantido). |
| `role` | Ausente → `'user'`. Inválido ou nulo → `'Role inválido'` (mantido). Autorização conforme a matriz (5.5.1). | Igual + matriz. |
| `active` | Ignorado (mantido). | bool → ok. `0`/`1` → aceitos pelo tipo `Boolean` † → 400 `'Campo active inválido'` (R-07). `null` → aceito † → 400 (R-07). str → falha no `commit` † → 500 → 400 (C-06). |

A ordem das verificações do POST é mantida: presença (nome, email, senha) → formato do email → tamanho da senha → 409 → role → autorização da role (5.5.1). As verificações de tipo entram junto da verificação de presença de cada campo.

**Login**

| Entrada | Hoje | Proposto |
|---|---|---|
| Corpo falso | 400 `'Dados inválidos'` | Mantido |
| Corpo não-objeto verdadeiro | 500 (`.get`) | 400 `'Dados inválidos'` (C-01) |
| `email` ou `password` falsos | 400 `'Email e senha são obrigatórios'` | Mantido |
| `email` não-str verdadeiro: número ou `true` | Vai para `filter_by(email=...)`; resultado da comparação no SQLite † (provável 401 `'Credenciais inválidas'`) | 401 `'Credenciais inválidas'`, **sem consulta ao banco**: o tipo é verificado antes de `filter_by` (M-05 se a linha de base mostrar 401; C-08 se mostrar 500) |
| `email` lista ou objeto | Vai para `filter_by`; erro de binding do driver † (provável 500) | 401 `'Credenciais inválidas'`, sem consulta (C-08) |
| `password` não-str verdadeiro, email existente | 500 (`.encode` em `check_password`) | 401 `'Credenciais inválidas'` (C-08) |
| `password` não-str, email inexistente | 401 (a senha não chega a ser usada) | 401 (mantido) |
| Hash armazenado malformado | Comparação MD5 → 401 | 401, nunca 500 |

Escolhemos 401, e não 400, para email e senha de tipo inválido: assim a resposta não distingue "tipo errado" de "credencial errada", e o caso `false`/`0` continua com 400 de campo obrigatório, como hoje.

**Categories**

| Campo | POST | PUT |
|---|---|---|
| `name` | Falso → `'Nome é obrigatório'` (mantido). Número/`true` → aceito † → 400 `'Nome inválido'` (R-08). Lista/objeto → falha no `commit` † → 500 → 400 (C-10). | `null` → 500 no `commit` (NOT NULL) → 400 `'Nome é obrigatório'` (C-09). `""` → aceito → 400 (R-08). Número/bool → aceito † → 400 (R-08). |
| `description` | Ausente → `''`. Número/bool → aceito † → 400 `'Descrição inválida'` (R-08). Lista/objeto → 500 † → 400 (C-10). | Igual. |
| `color` | Ausente → `'#000000'`. Fora de `^#[0-9A-Fa-f]{6}$` ou `null` → aceito (str com mais de 7 caracteres: o SQLite não impõe `String(7)` †) → 400 `'Cor inválida'` (R-09). | Igual; ausente não altera. |

**IDs no caminho:** valores não numéricos ou negativos → 404, mantido pelo conversor `int`. O corpo passa a ser JSON (M-03).

### 5.4 Mudanças de contrato intencionais

**A. Correções: hoje 500 → 4xx controlado.** Não dependem de decisão.
- C-01: corpo JSON não-objeto em POST e login; corpo `null`, `0`, `false`, número, `true` ou string com nome de campo em qualquer PUT.
- C-02: título nulo, não-str ou `false`.
- C-03: prioridade string, nula, lista ou objeto.
- C-04: tags com elemento não-str ou objeto.
- C-05: filtros não numéricos na busca.
- C-06: campos de usuário com tipo inválido.
- C-07: conflito de email no commit passa a 409.
- C-08: login com email lista/objeto ou senha não-str (com email existente) passa a 401.
- C-09: nome nulo em PUT /categories.
- C-10: lista ou objeto em campos de texto (`description`, nomes), que hoje falham no `commit` † com 500.
- C-11: lista ou objeto em `user_id`/`category_id`, se a linha de base mostrar 500.
- Erros inesperados passam a 500 JSON `{'error': 'Erro interno'}`, em vez de página HTML.
- 404/405/415 do framework passam a vir em JSON.

**B. Restrições novas que rejeitam entradas antes aceitas.** Todas aprovadas (D-6a).

| ID | Restrição |
|---|---|
| R-01 | Corpo JSON lista ou string sem nome de campo em PUT /tasks, PUT /users e PUT /categories (inclusive `[]` e `""` em PUT /categories) |
| R-02 | `description` de task número ou booleano |
| R-03 | Prioridade `true`, float não inteiro ou NaN |
| R-04 | `user_id`/`category_id` igual a `0`, `false`, `""`, string numérica ou `true` |
| R-05 | Tag com vírgula; `tags` numérico ou booleano |
| R-06 | Nome de usuário número/bool; `""` no PUT |
| R-07 | `active` não booleano (`0`, `1`, `null`) |
| R-08 | Nome e descrição de categoria número/bool; nome `""` no PUT |
| R-09 | Cor fora do formato `#RRGGBB` ou nula |

**C. Mudanças só de status ou mensagem.**
- M-01: `±Infinity` em prioridade passa a `'Prioridade inválida'`.
- M-02: IDs negativos, float ou texto em `user_id`/`category_id` passam de 404 para 400.
- M-03: 404 de rota e de conversor passa a vir em JSON.
- M-04: `priority: false` continua 400, com a mensagem `'Prioridade inválida'` no lugar da mensagem de faixa.
- M-05: login com email número/`true` mantém 401, sem consulta ao banco (se a linha de base confirmar 401).

**D. Demais mudanças.**
- `password` some de todas as respostas (F-01).
- O hash passa ao formato werkzeug; hashes MD5 migram no primeiro login bem-sucedido (D-2a).
- `SECRET_KEY` passa a ser **obrigatória**: sem ela, ou com menos de 32 caracteres, a aplicação e o seed não iniciam e nenhum banco é criado (F-03).
- Debug desligado por padrão. Host padrão `127.0.0.1` (D-3b): clientes de outras máquinas precisam de `HOST=0.0.0.0` explícito.
- `token` de `/login` passa a ser um token assinado e verificado (D-1a); PUT/DELETE de usuários e POST com role elevada exigem autenticação (5.5.1).
- A tabela `users` ganha a coluna `auth_nonce`, com migração aditiva (5.5.1).
- `services/notification_service.py` é removido (D-4a).
- Seed com senhas do ambiente (D-5a).

### 5.5 Decisões do usuário (consolidadas)

| ID | Decisão | Escolha | Efeito |
|---|---|---|---|
| D-1 | Controle de acesso às contas (F-04) | **(a)** Token assinado com autorização por identidade | 5.5.1; T-15; auth.py, models/user.py, routes/controllers de user, config.py |
| D-2 | Hashes MD5 existentes (F-02) | **(a)** No login, aceitar MD5 legado (exatamente 32 caracteres hex minúsculos, comparação com `hmac.compare_digest`) e regravar no formato novo após sucesso | T-04; models/user.py. A regravação **não** troca o `auth_nonce` (não é troca de senha). |
| D-3 | Host padrão (F-09) | **(b)** `127.0.0.1`, configurável por `HOST` | T-02; config.py |
| D-4 | `services/notification_service.py` | **(a)** Remover | T-13; não há `SMTP_*` na configuração |
| D-5 | Senhas do seed (F-03, F-06) | **(a)** `SEED_ADMIN_PASSWORD`, `SEED_USER_PASSWORD` e `SEED_MANAGER_PASSWORD` do ambiente, sem fallback, **todas** validadas (presentes, str, com o mínimo vigente de 4 caracteres) antes de qualquer exclusão. Se faltar alguma, o seed sai com código ≠ 0, nomeia só as variáveis ausentes e não toca no banco. | T-08, T-02; seed.py, .env.example |
| D-6 | Restrições novas R-01 a R-09 | **(a)** Aplicar todas | T-10; models/*, controllers/* |

A opção D-1(b), token administrativo, foi descartada, assim como o detalhamento que constava em 5.5.2 na revisão anterior.

#### 5.5.1 Detalhamento de D-1 (a): token assinado vinculado à conta

**Problema da revisão anterior.** Um payload só com `uid` autentica qualquer conta que venha a ocupar aquele ID. No SQLite, uma chave `INTEGER PRIMARY KEY` sem `AUTOINCREMENT` recebe `max(rowid) + 1`, então:
- excluir o usuário de maior ID e criar outro reutiliza o ID;
- o seed apaga todos os usuários e reinsere, e os IDs voltam a começar em 1.

Nos dois casos, um token antigo autenticaria uma conta diferente, possivelmente admin.

**Solução: nonce de autenticação por conta.**
- Nova coluna `users.auth_nonce` (`String(64)`), preenchida com `secrets.token_urlsafe(32)` (43 caracteres, 256 bits aleatórios):
  - na criação da conta (POST /users e seed);
  - a cada troca de senha.
- Payload do token: `{"uid": <id>, "sid": <auth_nonce>}`. Não contém senha, hash nem nada derivado deles. O nonce é aleatório e não revela nada sobre a credencial; mesmo assim é tratado como sensível (nunca aparece em respostas nem em logs).
- Verificação: depois da assinatura e da expiração, carrega o usuário por `uid` e compara `hmac.compare_digest(user.auth_nonce, sid)`. Usuário inexistente, `auth_nonce` nulo ou diferente → 401 `'Token inválido'`. A mesma mensagem nos três casos evita enumeração.
- Uma conta nova no mesmo ID recebe um nonce novo, então tokens da conta anterior deixam de valer. O mesmo vale para um novo seed.

**Token:** `itsdangerous.URLSafeTimedSerializer(SECRET_KEY, salt="task-manager-auth")`. O itsdangerous já é dependência do Flask; a versão instalada será registrada.
- É assinado, **não** criptografado, e **não** é JWT. O payload é legível, por isso só leva o ID e o nonce.
- Continua no campo `token` da resposta de `/login`. O prefixo `fake-jwt-token-` deixa de existir.
- Uso: `Authorization: Bearer <token>`. O esquema é comparado sem diferenciar maiúsculas; exige exatamente um espaço e um token não vazio sem espaços. Tokens com mais de 4096 caracteres são rejeitados antes de qualquer decodificação.

**Validação dos tipos do payload** (depois de `loads`, antes de qualquer consulta). Qualquer falha → 401 `'Token inválido'`:
- o payload é um `dict` com exatamente as chaves `uid` e `sid`;
- `uid` é `int` (`type(uid) is int`, o que exclui `bool`) e é ≥ 1;
- `sid` é `str` e casa com `^[A-Za-z0-9_-]{43}$`.

Uma assinatura válida com payload de outro formato só seria possível com a `SECRET_KEY`, mas a validação evita que um token de outra versão do esquema, ou forjado com chave vazada, chegue à consulta ORM com tipos inesperados.

**Expiração:** `TOKEN_MAX_AGE` em segundos, vindo do ambiente, com padrão de 3600, verificado por `loads(max_age=...)`.

**`SECRET_KEY`:**
- Obrigatória e persistente por ambiente, para que os tokens sobrevivam a reinícios e valham entre processos.
- Sem fallback efêmero.
- Mínimo de 32 caracteres.
- Validada em `create_app` **antes** de `db.init_app` e de `init_schema`; se falhar, nenhum arquivo de banco é criado.
- Trocar a `SECRET_KEY` invalida todos os tokens (`BadSignature` → 401).

**Ciclo de vida do token:**

| Evento | Efeito nos tokens já emitidos |
|---|---|
| Troca de senha (PUT /users/<id> com `password`, pelo próprio usuário ou por admin) | `auth_nonce` regenerado no mesmo `commit` → **todos** os tokens daquela conta passam a 401 `'Token inválido'`, inclusive o usado na própria requisição. A resposta do PUT continua sendo o usuário (sem novo token); o cliente precisa fazer login de novo. Se o `commit` falhar, nem a senha nem o nonce mudam. |
| Migração de hash MD5 no login (D-2a) | Nonce mantido; tokens continuam válidos. |
| Troca de email, nome ou role | Nonce mantido. Role é lida do banco a cada requisição, então rebaixamento vale na hora. |
| Inativação (`active=false`) | Nonce mantido; enquanto inativo, toda requisição autenticada recebe 403 `'Usuário inativo'`. Se reativado antes da expiração, os tokens voltam a valer. |
| Exclusão da conta | Usuário inexistente → 401. Se outra conta ocupar o mesmo ID, o nonce difere → 401. |
| Novo seed | Contas recriadas com nonces novos → 401 para tokens antigos. |
| Expiração | 401 `'Token expirado'`. |

**Mudança de schema e compatibilidade.** `db.create_all()` só cria tabelas ausentes: não adiciona colunas a uma tabela `users` que já existe. Sem migração, um banco criado pela versão original faria a versão refatorada falhar com `no such column: users.auth_nonce` em qualquer consulta a usuários. Por isso `init_schema()` faz, na factory, depois da validação de configuração:
1. `db.create_all()`. Num banco novo, cria `users` já com a coluna.
2. Inspeciona as colunas de `users` (`sqlalchemy.inspect(engine).get_columns('users')`). Se `auth_nonce` faltar:
   - `ALTER TABLE users ADD COLUMN auth_nonce VARCHAR(64)`. No SQLite, `ADD COLUMN` aceita coluna anulável sem default; por isso a coluna fica anulável no banco.
   - Preenche cada usuário existente com um nonce aleatório próprio.
   - Tudo numa única transação; em falha, rollback e a aplicação não inicia (código ≠ 0, mensagem sem dados sensíveis).
3. Se a coluna já existir, não faz nada: a migração é idempotente.

Compatibilidade:
- Um banco migrado continua legível pela versão original, que só seleciona as colunas que declara. Contas criadas pela versão original depois disso ficam com `auth_nonce` nulo; na versão refatorada, o login dessas contas gera o nonce antes de emitir o token, e tokens com nonce nulo no banco nunca são aceitos.
- Não há Alembic nem nova dependência (`requirements.txt` fica como está). A migração cobre só esta coluna; mudanças futuras de schema exigiriam ferramenta própria (registrado como limitação).
- Os dados existentes (usuários, tasks, categorias e IDs) não mudam.

**Estados do token** (todos com `{'error': ...}`):

| Situação | Resposta |
|---|---|
| Cabeçalho ausente, em rota que exige autenticação | 401 `'Token ausente'` (+ `WWW-Authenticate: Bearer`) |
| Esquema diferente de Bearer, formato ruim, token longo demais, assinatura inválida, salt ou chave diferentes (`BadSignature`), payload com tipos ou chaves inválidos | 401 `'Token inválido'` |
| Expirado (`SignatureExpired`) | 401 `'Token expirado'` |
| Usuário do token excluído, ou `auth_nonce` diferente ou nulo | 401 `'Token inválido'` |
| Usuário inativo | 403 `'Usuário inativo'` (mesma mensagem do login) |
| Permissão insuficiente | 403 `'Permissão negada'` |

**Bearer em `POST /users` (cadastro público).** A rota usa autenticação **opcional**:
- Sem cabeçalho `Authorization`: tratada como anônima (cadastro com role `user`, como hoje).
- **Com** cabeçalho `Authorization` presente, válido ou não: o token passa pela verificação completa. Inválido, malformado, expirado ou de conta inexistente → 401 com a mensagem da tabela acima, **mesmo que o pedido fosse um cadastro anônimo válido**. Conta inativa → 403 `'Usuário inativo'`.
- Motivo: um admin cujo token expirou não pode ter o pedido silenciosamente rebaixado para um cadastro anônimo, que criaria a conta com outra autorização ou responderia 401/403 por motivo enganoso. Um cabeçalho enviado é sempre verificado.
- Nas rotas públicas que não usam identidade (todos os GET, `/login`, CRUD de tasks e categorias), o cabeçalho `Authorization` é ignorado, como hoje.

**Permissões:** `role` e `active` são lidos do banco a cada requisição, nunca do token. `manager` não recebe permissão extra, porque o código atual não define nenhuma.

**Ordem das verificações** em PUT/DELETE: autenticação (401) → usuário-alvo existe (404) → autorização (403) → validação (400) → unicidade (409).

**Matriz de permissões:**

| Operação / campo | Anônimo | Próprio usuário (user/manager) | Outro usuário (user/manager) | Admin |
|---|---|---|---|---|
| POST /users: name, email, password | ✔ | ✔ | — | ✔ |
| POST /users: role ausente ou `'user'` | ✔ | ✔ | — | ✔ |
| POST /users: role `manager`/`admin` | 401 | 403 | — | ✔ |
| POST /users: active | ignorado (como hoje) | ignorado | — | ignorado |
| PUT /users/<id>: name, email, password | 401 | ✔ | 403 | ✔ (qualquer id) |
| PUT /users/<id>: role | 401 | 403 se diferente do atual (igual = sem efeito) | 403 | ✔ |
| PUT /users/<id>: active | 401 | 403 se diferente do atual | 403 | ✔ |
| DELETE /users/<id> | 401 | 403 | 403 | ✔ |

Em POST, "próprio" e "outro" não se aplicam: um usuário autenticado sem admin é tratado como anônimo, exceto pelo 403 no lugar de 401.

A regra de "último administrador ativo", proposta na revisão anterior, foi **retirada**. Um admin pode rebaixar, inativar ou excluir qualquer conta, inclusive a própria e a última conta admin. Risco residual documentado: o sistema pode ficar sem administrador ativo, e a recuperação seria por novo seed ou por alteração direta no banco.

**Continuam públicos:** `GET /`, `GET /health`, `POST /login`, `POST /users` com role `user` (sem cabeçalho), todos os GET (inclusive `/users`, `/users/<id>` com email e os relatórios), e o CRUD de tasks e categorias. Isso é risco residual documentado, fora de F-04.

### 5.6 Validação planejada

Tudo roda em cópias dentro de `mktemp -d`, com venv temporário (`pip install -r requirements.txt`, que exige rede) e versões registradas por `pip show`. Nada roda no repositório e nenhum serviço externo é chamado.

#### 5.6.1 Isolamento e caminho do banco

- **Cópias:** `$BASE/original` e `$BASE/refatorado`.
- **Caminho do banco:** o caminho efetivo é registrado por `db.engine.url.database` em cada cenário. A expectativa, pela documentação, é `$BASE/<copia>/instance/tasks.db`. Os arquivos criados são listados.
- **Repositório limpo:** `git status` confirma que não surgiu `instance/` nem `*.db` no repositório.
- **Banco recriado por grupo:** cada grupo de cenários começa com o banco removido e recriado, em subprocesso com `cwd` na cópia.
- **Integrações:** nenhuma. `notification_service.py` não é importado no original e não existe no refatorado.

#### 5.6.2 Fixtures e controle de tempo

O código original chama `datetime.utcnow()` diretamente, então não há como congelar o relógio sem modificar o original. Por isso:

- As fixtures são datadas **relativamente ao momento do teste, com margens**:
  - prazos em −3 dias, −1 dia, +5 dias e +10 dias;
  - `created_at` e `updated_at` gravados direto no banco da cópia em −6 dias e −8 dias, para a janela de 7 dias, incluindo uma task `done` com `updated_at` em −6 dias e outra em −8 dias.
- A fronteira exata de 7 dias não é testável sem relógio controlado; isso fica como limitação. Na versão refatorada, `utc_now()` permite um teste adicional da fronteira.
- `days_overdue` é comparado exatamente (esperado 3 e 1).
- Os campos temporais (`created_at`, `updated_at`, `generated_at`, `/health.timestamp`) só são normalizados depois de verificar o formato com `^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?$` e de checar ordem plausível (`updated_at ≥ created_at`; atualização posterior altera `updated_at`).
- Os conjuntos de dados de teste são:
  - **seed**: 3 usuários, 4 categorias, 10 tasks;
  - **vazio**: banco sem registros;
  - **bordas**: task sem usuário e sem categoria, usuário sem tasks, categoria sem tasks, tasks atrasadas nos estados pending, in_progress, done e cancelled.

#### 5.6.3 Matriz por endpoint (casos e expectativas)

| # | Endpoint | Casos | Expectativa |
|---:|---|---|---|
| 1 | GET / | — | 200, corpo exato |
| 2 | GET /health | — | 200, `status: ok`, timestamp com formato válido |
| 3 | GET /tasks | seed; vazio; bordas | 10 itens com chaves exatas. `overdue` true só para atraso em pending/in_progress. `user_name`/`category_name` nulos sem vínculo. `[]` no vazio. Ordem igual à linha de base. Nº de consultas **medido** (contador de `before_cursor_execute`) antes e depois; antes, registrado contra o limite 1 + 2N; depois, constante em relação a N. |
| 4 | GET /tasks/<id> | existente atrasada, não atrasada, done atrasada; 999; `/tasks/abc` | `overdue` correto; 404 `'Task não encontrada'`; 404 do conversor |
| 5 | POST /tasks | mínimo (só title); completo; cada linha de 5.3.1; user/category inexistentes | 201 com padrões (`pending`, 3, `''`, `[]`); 400/404 com mensagens exatas; GET posterior confirma a gravação; nenhuma gravação nos 4xx (contagem) |
| 6 | PUT /tasks/<id> | cada campo isolado; desvincular com null; título válido + prioridade inválida; `{}`; `[1]`; `5`; `"title"`; 404 | Atualização parcial correta. **Caso combinado:** 400 e o GET mostra o título original nas **duas** versões (no original, pelo descarte no teardown; no refatorado, porque nada é alterado antes da validação). `{}` → 400. `[1]` → 200 no original / 400 no refatorado (R-01). `5` e `"title"` → 500 no original / 400 no refatorado (C-01). |
| 7 | DELETE /tasks/<id> | existente; repetido | 200 com mensagem; GET → 404; segundo DELETE → 404 |
| 8 | GET /tasks/search | q em título e descrição; `q=%`; `q=x' OR '1'='1`; status válido e inválido; priority `2`/`abc`; user_id `1`/`abc`; combinação; sem filtros | Conjuntos de IDs exatos; aspas tratadas como literal; `abc` → 500 no original / 400 no refatorado |
| 9 | GET /tasks/stats | seed; vazio; depois de criar e concluir uma task | Contagens e `completion_rate` exatos; zeros no vazio |
| 10 | GET /users | seed; usuário sem tasks | Sem `password` nem `auth_nonce`; `task_count` correto, inclusive 0; consultas medidas e constantes no refatorado |
| 11 | GET /users/<id> | existente; 999 | Sem `password` nem `auth_nonce`; `tasks` correta; 404 |
| 12 | POST /users | sucesso; duplicado; cada linha de 5.3.1; roles conforme a matriz; Bearer inválido/expirado/de conta excluída com corpo de cadastro anônimo válido; Bearer de conta inativa | 201 sem `password`; hash gravado com prefixo werkzeug e `auth_nonce` não nulo (consulta ao banco); 409; 400/401/403 conforme a matriz; **401 com Bearer inválido e nenhuma conta criada (contagem)**; 403 com conta inativa |
| 13 | PUT /users/<id> | cada campo; email duplicado; conflito forçado no commit; matriz; troca de senha | 200/400/409 exatos. Depois do conflito forçado: 409 e a **requisição seguinte** responde 200 (recuperação da aplicação). A recuperação da mesma sessão é testada à parte (5.6.4). Troca de senha: ver 5.6.4. |
| 14 | DELETE /users/<id> | usuário com 3 tasks; usuário sem tasks; 999; matriz | Usuário e as **suas** tasks removidos (contagem antes e depois), tasks de outros intactas; 404; 401/403 conforme a matriz |
| 15 | GET /users/<id>/tasks | com tasks; sem tasks; 999 | Subconjunto de chaves exato; `[]`; 404 |
| 16 | POST /login | correto; senha errada; email inexistente; inativo; campos ausentes; email número, `true`, lista, objeto; senha número com email existente; hashes (5.6.4) | 200 sem `password`, `token` assinado; 401; 401; 403; 400; email não-str → 401 **sem consulta ao banco** (contador de consultas = 0 para `users`); senha número → 500 no original / 401 no refatorado |
| 17 | GET /reports/summary | seed; vazio; bordas; janela de 7 dias | Contagens por status e prioridade exatas; `overdue.tasks` com `days_overdue`; `tasks_created_last_7_days`/`tasks_completed_last_7_days` conforme as fixtures de −6/−8 dias; `user_productivity` com usuário sem tasks (taxa 0); zeros e `[]` no vazio; mesmos valores antes e depois de otimizar |
| 18 | GET /reports/user/<id> | com tasks; sem tasks; 999 | `high_priority` (≤ 2) e `overdue` exatos; taxa 0; 404 |
| 19 | GET /categories | seed; categoria sem tasks | `task_count` exato, inclusive 0 |
| 20 | POST /categories | padrões; cor válida, inválida e nula; nome ausente | 201 com `'#000000'`; 400 (R-09) |
| 21 | PUT /categories/<id> | parcial; `{}`; `null`; `0`; `false`; `[]`; `""`; `5`; nome nulo; 999 | 200; `{}` → 200 sem alteração; `null`/`0`/`false`/`5` → 500 no original / 400 no refatorado (C-01); `[]`/`""` → 200 no original / 400 no refatorado (R-01); nome nulo → 400; 404 |
| 22 | DELETE /categories/<id> | sem tasks; **com tasks vinculadas**; 999 | 200; efeito real nas tasks registrado na linha de base (hipótese: `category_id` zerado pelo ORM) e reproduzido igual depois; 404 |

#### 5.6.4 Cenários transversais

- **Autorização (D-1a):**
  - Token ausente, malformado, adulterado, assinado com outra chave, longo demais e expirado (via `TOKEN_MAX_AGE` curto em `create_app(overrides)`) → 401 com mensagens exatas.
  - Payload com tipos inválidos, assinado com a chave de teste pelo harness: `uid` str, `uid` bool, `uid` 0 ou negativo, `sid` ausente, `sid` com tamanho ou caracteres errados, chaves extras, payload lista → 401 `'Token inválido'` sem exceção (nenhum 500).
  - Esquema `bearer` em minúsculas aceito; `Basic`, dois espaços, token vazio → 401.
  - Usuário inativado → 403; reativado antes da expiração → token volta a valer.
  - Rebaixamento de admin vale na requisição seguinte.
  - Cada célula da matriz é testada com um caso positivo e um negativo.
  - Admin rebaixando, inativando e excluindo a própria conta (inclusive como último admin) → 200, sem regra de bloqueio.
- **Reutilização de ID e novo seed** (o token antigo deve receber 401 em todos):
  - Exclusão + recriação: criar o usuário X com o maior ID, fazer login (token T), excluí-lo como admin, criar o usuário Y e **confirmar que Y recebeu o mesmo ID** (se não receber, o caso é registrado como não exercitado, e não como aprovado). Usar T em PUT /users/<id> → 401 `'Token inválido'`, e Y continua inalterado.
  - O mesmo cenário com Y criado como admin, para provar que T não herda privilégio.
  - Novo seed: login como admin do seed (token T), executar o seed de novo, confirmar que o admin tem o mesmo ID e outro `auth_nonce`, usar T → 401.
  - Controle positivo: um token emitido **depois** da recriação ou do novo seed funciona.
- **Troca de senha:**
  - Usuário com dois tokens (T1, T2) troca a própria senha usando T1 → 200; T1 e T2 → 401 depois; login com a senha nova → token novo funciona; login com a senha antiga → 401.
  - Admin troca a senha de outro usuário → os tokens daquele usuário → 401; o token do admin continua válido.
  - Troca de senha com `commit` forçado a falhar → 500, senha e nonce inalterados, T1 continua válido.
  - Migração de MD5 no login (D-2a) → nonce inalterado; tokens anteriores continuam válidos.
- **Migração de schema:**
  - Banco criado pela versão original (cópia da linha de base com seed e registros marcadores) aberto pela refatorada → coluna adicionada, todos os usuários com nonce distinto e não nulo, contagens e IDs de todas as tabelas idênticos ao snapshot, login funciona.
  - Segunda inicialização → nenhuma alteração (idempotência: schema e nonces iguais).
  - Banco migrado aberto de novo pela versão original → endpoints de leitura continuam respondendo como na linha de base.
  - Falha induzida durante o preenchimento → aplicação não inicia, banco igual ao snapshot (coluna ausente).
- **Hashes:**
  - Novo: prefixo werkzeug; login correto e incorreto.
  - Legado MD5 (D-2a): login aceito e hash regravado no banco no formato werkzeug; login seguinte usa o formato novo.
  - Malformado (`''`, `'abc'`, formato werkzeug truncado, MD5 com 31 caracteres, MD5 em maiúsculas): 401, nunca 500.
- **Rollback e sessão:**
  - Caso combinado do PUT (#6), nas duas versões.
  - Conflito forçado no commit (#13), substituindo a verificação prévia por um dublê **no harness**, sem alterar o código. Prova a recuperação **da aplicação** (requisição seguinte).
  - **Mesma sessão:** no harness, dentro de um único `with app.app_context():`, guardar `s = db.session()`, provocar o `IntegrityError` de email via `commit_or_rollback()`, capturar `ConflictError`, conferir que `db.session()` é o mesmo objeto `s`, que `s.is_active` é verdadeiro e que `s.add(...)` + `commit_or_rollback()` grava um registro válido (confirmado por consulta numa conexão separada). Só esse teste sustenta a afirmação de recuperação da mesma sessão.
  - Falha forçada de flush (`db.session.flush` instrumentado para lançar) → 500 com a mensagem da operação; o banco fica inalterado e a requisição seguinte funciona (recuperação da aplicação).
- **Inicialização e importação:**
  - Sem `SECRET_KEY` ou com chave curta → processo termina com código ≠ 0 e **nenhum** `instance/tasks.db` criado.
  - Com a chave, `python app.py` sobe em porta livre, em `127.0.0.1`, sem debugger no log.
  - **Efeitos da importação**, com o Python do venv temporário. `python -I` sozinho não serve: `-I` não põe o diretório atual nem o do script em `sys.path`, então `import app` falharia com `ModuleNotFoundError` e pareceria "sem efeitos". O harness:
    1. tira um snapshot da árvore de arquivos da cópia (caminhos e tamanhos), ignorando nada;
    2. executa, com `cwd` na cópia e `SECRET_KEY` ausente do ambiente:
       `"$VENV/bin/python" -I -B -c 'import sys, os; sys.path.insert(0, sys.argv[1]); import app; print(os.path.realpath(app.__file__))' "$COPIA"`
       (`-B` evita gravar `__pycache__`, que poluiria o snapshot);
    3. classifica o resultado:
       - código ≠ 0 → **falha de importação** (registra o stderr sanitizado); o teste é reprovado e não conta como "sem efeitos";
       - código 0, mas o caminho impresso diferente de `$COPIA/app.py` → **importou o módulo errado**; reprovado;
       - código 0 e caminho correto → compara o snapshot. Original: espera-se registrar a criação de `instance/tasks.db`. Refatorado: nenhum arquivo novo ou alterado.
- **Seed:**
  - Execução normal com as três variáveis → 3/4/10, com os mesmos dados da linha de base, exceto hashes, nonces e tempos.
  - Sem uma das variáveis (D-5a) → código ≠ 0, a mensagem nomeia só a variável ausente, e o snapshot do banco previamente populado (seed + registros marcadores criados via API) fica idêntico.
  - **Falha induzida** com banco previamente populado: o harness intercepta `db.session.add` e lança exceção na 5ª task. Isso vale igual para o original e o refatorado, sem modificar código.
    - Original: espera-se registrar a perda de dados.
    - Refatorado: código ≠ 0, e contagens, IDs, nonces e marcadores idênticos ao snapshot.

#### 5.6.5 Logs

- Durante todos os cenários, inclusive o conflito forçado e a falha de flush, stdout, stderr e os logs são capturados **brutos** no diretório temporário.
- Antes de qualquer sanitização, o log bruto é varrido em busca de:
  - senhas de teste;
  - hashes gerados (`scrypt:`, `pbkdf2:`, `[0-9a-f]{32}`);
  - tokens emitidos e `auth_nonce` gravados;
  - `SECRET_KEY`;
  - o texto `parameters:`.
- Expectativa no refatorado: zero ocorrências.
- O resultado do original (F-05) é registrado como achado confirmado ou refutado.
- Só trechos sanitizados (`<removido>`) vão para as evidências; os logs brutos não saem do diretório temporário.

#### 5.6.6 Comparador

- Cada caso tem uma **expectativa explícita escrita antes da execução**: status, corpo exato normalizado ou predicados (conjunto de chaves, ausência de `password` e `auth_nonce`, contagens, IDs). A comparação entre linha de base e refatorado complementa, mas não substitui, essas expectativas.
- Para os itens † de 5.3.1, a expectativa do original é registrada como "medir", e a classificação final (C-xx, R-xx ou M-xx) é ajustada pelo valor observado, com a mudança anotada nas evidências.
- Cada diferença é classificada como C-xx, R-xx, M-xx, mudança da seção 5.4 D, ou **regressão**.
- **Testes negativos do comparador**, executados antes do uso real: ele precisa **falhar** para:
  - status alterado;
  - chave removida;
  - chave `password` ou `auth_nonce` adicionada;
  - mensagem de erro alterada;
  - contagem alterada;
  - ordem de lista alterada;
  - campo temporal fora do formato;
  - cópia de resposta de outro endpoint.
- Proteção contra execução vazia: o número de casos executados é conferido contra o planejado, e o caminho do banco e as contagens iniciais são registrados por grupo.

### 5.7 Destino do relatório e das evidências

- Relatório oficial da Fase 3: `reports/audit-project-3.md`. **Estado verificado em 2026-10-31** (`ls reports/`): o arquivo **não existe**; o diretório contém apenas `audit-project-1.md`, `audit-project-2.md` e `evidence/`. Se existir quando a Fase 3 começar, o conteúdo será conferido e nada será sobrescrito sem perguntar.
- Este documento de revisão não é o relatório oficial. Foi gravado com autorização do usuário (seção 1, Registro) e não está em `reports/` no momento desta revisão.
- Evidências, com dados sensíveis removidos: `reports/evidence/task-manager-api/` (ainda não existe; `reports/evidence/` contém só as pastas dos projetos 1 e 2).

## 6. Limitações

- **Versões instaladas não verificadas:** Flask, Flask-SQLAlchemy, SQLAlchemy, itsdangerous, Werkzeug e o runtime Python.
- **Comportamentos confirmados só pela documentação:** o caminho efetivo do SQLite, `hide_parameters`, a remoção da sessão no teardown do contexto e a reutilização de rowid no SQLite sem `AUTOINCREMENT`.
- **Comportamentos sem confirmação**, a medir na linha de base (itens †):
  - o 415/400 do `get_json`;
  - se o parser aceita `NaN`/`Infinity`;
  - a coerção e a gravação de tipos não-str em colunas de texto e de `bool`/float em colunas inteiras;
  - o efeito do backref ao excluir uma categoria;
  - a coerção de `"1"`/`true`/lista/objeto em `Query.get`;
  - o resultado de `filter_by(email=<não-str>)` no login.
- **F-05:** é hipótese.
- **F-10:** os números são limites derivados do código, não medições.
- **Fronteira de 7 dias:** não é testável com precisão no código original.
- **Migração:** a migração manual cobre só `users.auth_nonce`; não há ferramenta de migração no projeto.
- **Risco residual de autorização:** sem regra de último admin, o sistema pode ficar sem administrador ativo; leitura e CRUD de tasks e categorias continuam públicos.
- **Leitura parcial da documentação:** as páginas oficiais foram consultadas por ferramenta que as lê parcialmente.
- **Artefatos do projeto 2:** não foram lidos (restrição de escopo).

## 7. Registro desta revisão

Revisão 3 gravada em 2026-10-31 sobre o arquivo `TaskManagerAPI-Fase02_Revisao.md`, com autorização explícita do usuário restrita a este arquivo. Não houve alteração de código, Skill ou dependências, execução da aplicação nem commit. A Fase 3 não foi iniciada.

================================
Total: 19 achados (CRITICAL: 4 | HIGH: 5 | MEDIUM: 6 | LOW: 4)
================================
