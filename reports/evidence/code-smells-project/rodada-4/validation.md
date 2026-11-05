# Validação da Fase 3 — code-smells-project — rodada 4

- **Data:** 2026-11-05
- **Commit de referência:** `c6a53b74482dea6aa8ce8d2daacad828dd64e70e`, com working tree limpo no início da rodada
- **Relatório da Fase 2:** `rodada-4/auditoria.md`, gravado antes de qualquer alteração de código e mantido sem edição de conteúdo. Ver também a nota da seção 9.
- **Rodadas anteriores:** `reports/audit-project-1.md`, `../validation.md`, `../rodada-2/` e `../rodada-3/`. Nenhuma foi alterada.
- **Dados sensíveis:** token, `SECRET_KEY` e senhas sintéticas foram gerados com `secrets` a cada execução e aparecem como `<removido>`. Os hashes aparecem como `<hash-removido>` e os caminhos temporários como `<scratchpad>/r4`.

## 1. Escopo e restrição posterior

| Momento | O que aconteceu |
|---|---|
| Aprovação inicial | Fase 3 aprovada com D-4R (d)+(ii), D-7 (b), D-8 (b), D-9 (a), D-10 (a), D-11 (a) e D-12 (a) |
| Pausa | O usuário pausou a Fase 3 e restringiu a autorização às correções pedidas pelo revisor. Foi apresentado um inventário do trabalho parcial, separado em Grupo 1 (F-13) e Grupo 2 (D-4R, D-9, D-10, D-11) |
| **Restrição de escopo** | A Fase 3 foi retomada **exclusivamente para o F-13**. A autorização de D-4R, D-9, D-10 e D-11 foi **retirada** e as alterações correspondentes foram removidas. Continuam valendo D-7 (b), D-8 (b) e D-12 (a), que fazem parte do F-13 |

### 1.1 Antes da pausa (registro histórico)

- **Executado:** a matriz de 54 casos sobre uma cópia de c6a53b7. Ela gerou a linha de base desta rodada (`linha_base_c6a53b7.json`, seção 4).
- **Executado e descartado:** os 18 testes antigos, sem adaptação, sobre uma cópia intermediária que já tinha as proteções de D-11. O resultado foi `FAILED (failures=25)`, todas por `401` nas escritas de produto. Essa saída e a adaptação temporária de `test_regressao.py` (token nas escritas de produto) pressupunham D-11 e foram descartadas. O arquivo foi restaurado ao conteúdo de c6a53b7.
- **Não executado:** `migrar_senhas.py` nunca rodou. Nenhum banco legado foi gerado ou migrado, e não houve teste de D-4R, D-9, D-10 ou D-11.

### 1.2 Remoção do Grupo 2, por trecho

- `migrar_senhas.py`, criado nesta rodada, foi removido.
- `models/usuario.py` e `tests/test_regressao.py` foram restaurados com `git restore --source=c6a53b7` para esses dois caminhos. O diff confirmou antes que todas as mudanças neles eram do Grupo 2.
- Nos arquivos mistos, a remoção foi feita trecho a trecho:
  - `database.py`: checagem de banco legado e `MigracaoPendenteError`;
  - `app.py`: `MigracaoPendenteError`;
  - `config.py`, `controllers/sistema_controller.py` e `routes/sistema.py`: o `AMBIENTE` configurável. Voltou a constante `"producao"`;
  - `routes/pedidos.py` e `routes/produtos.py`: os novos `@require_admin_token`;
  - `.env.example` e `README.md`: textos de D-4R, D-9 e D-11.
- As proteções que já existiam em c6a53b7 foram preservadas: `GET /usuarios`, `GET /usuarios/<id>`, `GET /relatorios/vendas`, `POST /admin/reset-db` e `POST /admin/query`.

## 2. Alterações do F-13 no working tree

| Arquivo | Mudança |
|---|---|
| `config.py` | `SEED_ON_STARTUP`: ausente ou `"1"` liga, `"0"` desliga e qualquer outro texto gera `ConfigError`. `validate_config` aceita apenas `bool` nos overrides da factory |
| `app.py` | `create_app(overrides=None, *, connection_factory=None)`. A configuração é lida e validada **antes** de criar o app e abrir o banco. `python app.py` encerra com código 1 e uma mensagem de log quando recebe `ConfigError` |
| `database.py` | Fábrica de conexão por instância (`init_app(app, connection_factory)`, guardada em `app.extensions`); `get_db()` passa pela fábrica; `init_schema()` só cria as tabelas; `seed_demo_if_empty()` roda numa transação única, só com `produtos` vazia, e pula e-mails de demonstração já existentes, preservando senha e perfil (D-7 b); `prepare()` sempre executa o schema e só executa o seed se a flag estiver ligada |
| `controllers/*.py` | Recebem `db` por parâmetro. Não importam `flask`, `database` nem `get_db` (D-8 b). `health_check(obter_db, debug)` mantém a abertura do banco dentro do `try`, preservando o caminho de erro |
| `routes/*.py` | Obtêm a conexão da instância com `get_db()` e a repassam aos controllers |
| `tests/test_inicializacao.py` | Arquivo novo, com 15 testes (seção 5) |
| `.env.example`, `README.md` | Documentação de `SEED_ON_STARTUP`, da separação schema/seed e de `connection_factory` |

Contratos HTTP: nenhuma rota, método, corpo ou status mudou (seção 4). O comando de inicialização (`python app.py`) e o padrão do seed (ligado) foram mantidos.

## 3. Ambiente

Venv temporário em `<scratchpad>/r4/venv`, criado com `pip install -r requirements.txt`.

| Componente | Declarado | Instalado |
|---|---|---|
| Python | — | 3.14.0 |
| Flask | 3.1.1 | 3.1.1 |
| flask-cors | 5.0.1 | 5.0.1 |
| Werkzeug (transitiva) | — | 3.1.9 |

Cópias isoladas usadas:
- `atual`: c6a53b7, via `git archive`;
- `original`: 40d2986, usada só pelos testes específicos, para gerar o banco legado e calcular o relatório original;
- `final`: cópia **nova** do working tree depois da limpeza. `diff -rq` confirmou que ela é idêntica ao repositório, sem contar `.claude`.

Todos os bancos foram criados dentro dessas cópias ou em diretórios temporários. Nenhum banco foi criado no repositório.

## 4. Testes executados no código final e resultados

| # | Execução | Resultado | Evidência |
|---:|---|---|---|
| 1 | Os 18 testes originais (`tests/test_regressao.py`, idêntico a c6a53b7): `python -B -m unittest tests.test_regressao -v` | `Ran 18 tests … OK` | `unittest_regressao_18.txt` |
| 2 | Os 15 testes novos do F-13: `python -B -m unittest tests.test_inicializacao -v` | `Ran 15 tests … OK` | `unittest_inicializacao.txt` |
| 3 | Matriz de 54 casos com o contrato da rodada 3 (`rodada-2/tools/matrix.py`, sem adaptações de D-10/D-11), via `python -B app.py` e banco novo | **54/54 idênticos** (status e corpo) à linha de base desta rodada, `linha_base_c6a53b7.json`, e a `rodada-3/refatorado.json`. Contra o código original (`../baseline.json`): 32 idênticos, 22 diferenças classificadas, **0 regressões**. Isso inclui os 3 casos de `/health` (`ambiente: "producao"`, `debug: false`) | `refatorado.json`, `matriz.md`, `logs/refatorado_matriz_trechos.log` |
| 4 | Testes específicos da rodada 3 (`rodada-2/tools/specific.py`), sem alteração | **122 OK, 0 falhas**. Inclui `/health` com banco quebrado → 500 `{"detalhes": "Banco de dados indisponível", "status": "erro"}`, idêntico ao anterior; reset + reinício repete o seed; banco legado com dump idêntico | `specific.txt` |
| 5 | S1–S9 pelo ponto de entrada real (`python -B app.py`), roteiro `tools/f13_entrypoint.py` | **56 OK, 0 falhas** | `f13_entrypoint.txt`, `logs/f13_entrypoint_trechos.log` |
| 6 | Controle: o mesmo roteiro S1–S9 sobre c6a53b7 | 32 OK, **24 falhas**. Mostra o defeito anterior: seed que não desliga, duplicação no S7 e boot que aceita valor inválido | `f13_entrypoint_controle_c6a53b7.txt` |
| 7 | Host, porta e debug pelo ambiente (`PORT=5057`, `FLASK_DEBUG=1`) | Padrão `127.0.0.1:5000` com `Debug mode: off`. `PORT=5057` faz o servidor escutar em 5057. `FLASK_DEBUG=1` gera `Debug mode: on` e `/health` responde com `debug: true`. Um HOST diferente de 127.0.0.1 **não** foi testado, para não expor o servidor na rede | `f13_host_porta_debug.txt` |
| 8 | Nova inspeção estática (`rodada-2/tools/inspecao.sh` + checagens do F-13 + AST) | Sem SQL com valor externo (as f-strings interpolam só constantes); controllers sem `flask`/`get_db`/`database`; `get_db()` só em `routes/` e `database.py`; nenhum import sem uso | `inspecao.txt` |

## 5. F-13: provas por cenário

Em todas as execuções de S1–S9, `SEED_SENHA_ADMIN`, `SEED_SENHA_JOAO`, `SEED_SENHA_MARIA` (valores sintéticos) e `ADMIN_TOKEN` estavam configurados. Com a flag em `"0"`, portanto, é a flag que impede a carga.

| Cenário | Ponto de entrada (`f13_entrypoint.txt`) | Teste unitário (`test_inicializacao.py`) |
|---|---|---|
| **S1** banco novo, `SEED_ON_STARTUP=0` | 4 tabelas criadas e vazias; `GET /produtos` → `{"dados": [], "sucesso": true}`; `/health` com contagens 0 e o mesmo corpo; `GET /usuarios` (token) → `[]`; login dos 3 e-mails com as senhas configuradas → 401; `POST /produtos` → 201 (id 1) e `GET /produtos/1` o devolve; `POST /usuarios` + login → 201/200; `POST /pedidos` → 201 e `GET /pedidos` mostra 1 pedido; no banco: 1/1/1/1, estoque 5 → 3; log com "carga de demonstração desligada" e sem aviso de senha de seed | `test_s1_…` |
| **S2** populado → reset → reinício com `0` | Antes: 10/3/1/1. Reset (token) → 200 e as 4 tabelas com 0. Dois reinícios com `0` → continuam 0, e `GET /produtos` → `[]` | `test_s2_…` |
| **S3** banco populado, boot com `0` | Dump completo idêntico | `test_s3_…` |
| **S4** banco novo, seed ligado (variável ausente e `"1"`) | 10 produtos e 3 usuários com hash; login dos 3 → 200 | `test_s4_…`, `test_variavel_de_ambiente_pela_factory` |
| **S5** reinício com seed ligado | 3 reinícios (ausente, `"1"`, ausente ou `"1"`): dump idêntico em ids, chaves e `criado_em`, sem duplicação | `test_s5_…` |
| **S6** seed ligado: reset + reinício | 0 → 10/3, o comportamento histórico preservado | `test_s6_…` |
| **S7** seed ligado: produtos apagados via API, usuários existentes (admin com perfil alterado), reinício com **outras** senhas | 10 produtos recarregados; as 3 linhas de usuário idênticas (sem duplicar; senha e perfil preservados); a senha antiga do João continua valendo e a nova é recusada (401). No controle c6a53b7, o mesmo cenário duplicava os usuários | `test_s7_…` |
| **S8** valor inválido (`true`, `""`, `2`, `" 1"`, `"0 "`, `false`) | O processo termina com código 1 e `ERROR … Inicialização recusada: SEED_ON_STARTUP inválido (…)`; o arquivo de banco **não é criado** e a porta não abre. Nos overrides da factory, `"0"`, `"1"`, `0`, `1`, `None` e `"False"` → `ConfigError`, sem criar o banco | `test_valor_invalido_…`, `test_override_da_factory_aceita_somente_bool` |
| **S9** importação | `python -I -B` a partir de um cwd vazio: exit 0, `app.__file__` correto, nenhum arquivo criado e projeto inalterado | `ImportacaoTest` (original), roteiro S9 |

### 5.1 R-10: substituição da conexão e duas instâncias

- **Conexão injetada no fluxo HTTP real** (`test_fabrica_injetada_e_usada_pelo_fluxo_http_real`):
  - a instância foi criada com `connection_factory`, uma fábrica espiã apontando para `injetado.db`, e `DATABASE_PATH=nao_usar.db`;
  - o servidor WSGI do Werkzeug foi iniciado numa porta livre e recebeu requisições HTTP reais: `GET /produtos` (10 itens), `POST /pedidos` (201), `PUT /pedidos/<id>/status` (200), `GET /health` e `GET /usuarios` com token;
  - resultado: o boot (schema + seed) passou pela fábrica; houve **exatamente 5 conexões injetadas, uma por requisição, e todas foram fechadas** no teardown; o status `aprovado` e o estoque 50 → 47 foram gravados em `injetado.db`; o arquivo `nao_usar.db` **não foi criado**.
- **Caso de uso sem contexto Flask** (`test_caso_de_uso_sem_contexto_flask`):
  - com `flask.has_app_context()` igual a `False`, os controllers rodaram com uma conexão `sqlite3` comum: `listar_produtos`, `criar_pedido`, `atualizar_status_pedido` e `listar_todos_pedidos`;
  - os efeitos foram conferidos no banco.
  - `test_controllers_nao_dependem_de_flask_nem_de_get_db` confirma por leitura dos arquivos que nenhum controller referencia `flask`, `get_db` ou `import database`.
- **Duas instâncias no mesmo processo** (`test_duas_instancias_no_mesmo_processo_com_bancos_isolados`):
  - A: seed ligado, `a.db`, token A. B: seed desligado, `b.db`, token B. Cada uma tem uma `SECRET_KEY` diferente.
  - As duas foram servidas por HTTP real ao mesmo tempo.
  - **Requisições intercaladas:** um produto gravado em A não aparece em B, e vice-versa; o token A em B → 401, e o token B em A → 401.
  - **Requisições simultâneas:** 16 threads, liberadas juntas por uma barreira, gravaram nas duas instâncias. Não houve erro. A ficou só com os seus produtos (19) e B só com os seus (9), sem nenhum dado cruzado.

Esses cenários também cobrem os impactos de F-10: troca de banco no mesmo processo e instâncias simultâneas.

## 6. Situação do F-13

| Impacto registrado (auditoria original e rodada 4) | Situação | Prova |
|---|---|---|
| Isolar testes dependia de caminhos frágeis | Corrigido | `create_app(overrides, connection_factory=…)`; todos os testes usam bancos próprios |
| Não havia como ter duas instâncias com configurações diferentes no mesmo processo | Corrigido | Seção 5.1 |
| Seed obrigatório, sem configuração para desligá-lo (R-9) | Corrigido | S1, S2, S3, S8 |
| Seed não idempotente para usuários (duplicação no reinício) | Corrigido | S5, S7 e o controle c6a53b7 |
| Host, porta e debug exigiam editar o código | Corrigido | `f13_host_porta_debug.txt` (HOST alternativo não exercitado; ver seção 4, item 7) |
| Controllers importavam `get_db` concreto, sem ponto de injeção (R-10) | Corrigido | Seção 5.1 e `inspecao.txt` |
| Schema e seed na mesma função / efeitos na importação | Corrigido | `init_schema` separado de `seed_demo_if_empty`; S9 |
| Regressões | Nenhuma | 54/54 idênticos à linha de base; 18 + 122 OK |

**F-13: corrigido, com evidência para cada impacto.**

## 7. Reconciliação por ID: 13 graves originais + F-22

| ID | Sev. | Situação | Evidência nesta rodada |
|---|---|---|---|
| F-01 | CRIT | Corrigido | Matriz: login com injeção → 401, produto com aspas → 201, `produto_id` com injeção → 400; inspeção sem SQL com valor externo |
| F-02 | CRIT | Corrigido | `specific.txt` grupos 1–2 (`sql` → 400 sem execução, catálogo igual à consulta direta, 403/401) |
| F-03 | CRIT | Corrigido | Matriz casos 23–24 sem `senha`; grupo 1 sem senha nem hash |
| **F-04** | CRIT | **Parcial / aberto**. Bancos legados mantêm senhas em texto puro (R-7). A correção (D-4R) foi retirada do escopo | `specific.txt` grupo 7 confirma o comportamento D-4 (a): o banco legado fica intacto, inclusive as senhas |
| F-05 | CRIT | Corrigido | Grupo 3 (401/200, reset transacional com rollback forçado); S2, S6 |
| F-06 | CRIT | Corrigido | Inspeção sem literal; grupo 4: sem `SECRET_KEY` → chave efêmera; chaves distintas por instância (seção 5.1) |
| **F-07** | CRIT | **Parcial / aberto**. `"ambiente": "producao"` continua fixo (R-4). A correção (D-9) foi retirada do escopo | Matriz e S1: o corpo de `/health` foi preservado, com `ambiente` fixo |
| F-08 | HIGH | Corrigido | `127.0.0.1` e `Debug mode: off` por padrão; `PORT` e `FLASK_DEBUG` pelo ambiente (seção 4, item 7) |
| **F-09** | HIGH | **Sem prova** do impacto concorrente. O rollback foi revalidado (grupo 5), mas o teste com requisições sobrepostas **não foi executado**, porque a restrição limitou a rodada ao F-13 | `specific.txt` grupo 5 (rollback) |
| F-10 | HIGH | Corrigido | Conexão por contexto via fábrica da instância; duas instâncias simultâneas isoladas (seção 5.1) |
| **F-11** | HIGH | **Parcial / aberto**. `GET /pedidos` e `GET /pedidos/usuario/<id>` continuam públicos. A correção (D-10) foi retirada do escopo | Matriz casos 41–43 (públicos, como na rodada 3) |
| F-12 | HIGH | Corrigido | Inspeção: SQL só em `models/`/`database.py`; controllers sem `request`/`jsonify`/`flask` |
| F-13 | HIGH | **Corrigido** | Seções 5 e 6 |
| **F-22** | HIGH (novo) | **Aberto**. POST/PUT/DELETE `/produtos` e PUT `/pedidos/<id>/status` continuam sem controle de acesso. A correção (D-11) foi retirada do escopo | Matriz casos 10–22 e 44–47 (públicos) |

Os MEDIUM remanescentes F-14 (R-1) e F-16 não foram tratados e não bloqueiam pela regra.

## 8. Situação geral da Fase 3

**Fase 3 bloqueada.**

| ID | Sev. | Motivo | O que falta |
|---|---|---|---|
| F-04 | CRITICAL | Senhas em texto puro permanecem em bancos legados | Autorização para uma correção (decisão D-4R) e sua validação |
| F-07 | CRITICAL | `ambiente` fixo em `/health` | Autorização para uma correção (D-9) |
| F-09 | HIGH | O impacto concorrente nunca foi provado | Permissão de escopo para executar o teste de requisições sobrepostas (não exige mudar código) |
| F-11 | HIGH | Dados de negócio continuam acessíveis via `GET /pedidos*` | Autorização para uma correção (D-10) |
| F-22 | HIGH | Escritas de catálogo e de pedidos sem controle de acesso | Autorização para uma correção (D-11) |

Pendências graves: **5** (2 CRITICAL, 3 HIGH). Corrigidos com evidência: **9** dos 14 IDs graves (F-01, F-02, F-03, F-05, F-06, F-08, F-10, F-12 e F-13). Validação funcional do código final: aprovada (0 regressões). Conforme a instrução, nenhuma correção independente foi implementada para obter aprovação global.

## 9. Limitações e registros operacionais

- **HOST alternativo:** a configuração de um HOST diferente de 127.0.0.1 não foi exercitada; foi verificada só por leitura (`config.py`). Fazer isso exporia o servidor na rede.
- **Concorrência:** fora o teste de duas instâncias, não houve teste de concorrência nem de carga (ver F-09).
- **Data de modificação de `auditoria.md`:** um `sed` de sanitização aplicado a `rodada-4/*.md`, para trocar o caminho do scratchpad por `<scratchpad>/r4`, regravou o arquivo. O conteúdo é o mesmo: o caminho substituído nunca aparecia nele, o tamanho continua 26903 bytes e o texto foi conferido. Só a data de modificação mudou.
- **Temporários fora do scratchpad:** duas execuções do roteiro de controle sobre c6a53b7 falharam no próprio script, antes de gravar a saída (o script tentou ler um `.db` como log), e deixaram `/tmp/f13_9kvnmck1` e `/tmp/f13_qs8a6cmg`, com bancos e logs só de dados sintéticos. A remoção automática foi negada pela política de permissões, então os diretórios continuam lá para remoção manual. As execuções seguintes usaram `TMPDIR` dentro do scratchpad.
- **Erro de digitação no relatório:** `auditoria.md` traz `SEED_SENHA_ON_STARTUP` na linha do D-12. O nome correto, implementado e validado, é `SEED_ON_STARTUP`. O relatório não foi corrigido, porque deve permanecer como foi apresentado.

## 10. Arquivos desta pasta

- `auditoria.md`: relatório da Fase 2 (sem resultados de validação).
- `validation.md`: este documento.
- `linha_base_c6a53b7.json`: matriz de 54 casos sobre c6a53b7, a linha de base.
- `refatorado.json`, `matriz.md`: matriz do código final e a comparação com `../baseline.json`.
- `specific.txt`: os 122 testes específicos da rodada 3.
- `unittest_regressao_18.txt`, `unittest_inicializacao.txt`: as saídas do unittest.
- `f13_entrypoint.txt`: S1–S9 no código final. `f13_entrypoint_controle_c6a53b7.txt`: o mesmo roteiro sobre c6a53b7.
- `f13_host_porta_debug.txt`: host, porta e debug pelo ambiente.
- `inspecao.txt`: a nova inspeção estática.
- `logs/`: trechos dos logs de inicialização, sem segredos.
- `tools/`:
  - `f13_entrypoint.py` e `run_matrix.sh`: o `run_matrix.sh` usa `MATRIZ` (padrão `matrix.py` da rodada 2);
  - `matrix4.py`: variante que manda o token também nas rotas de D-10/D-11. Foi usada **apenas** para gerar a linha de base, porque o código c6a53b7 ignora o header nessas rotas; a comparação de status e corpo não é afetada.
  - As demais ferramentas são as de `../rodada-2/tools/`, sem alteração.
