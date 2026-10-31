# Validação da Fase 3 — code-smells-project

- **Data:** 2026-10-30
- **Commit de referência (auditoria):** `40d29863fed86442a86df1e37567cd2ec3d46ede`
- **Relatório de auditoria aprovado:** `reports/audit-project-1.md` (gravado antes de qualquer alteração de código, sem resultados de validação)
- **Dados sensíveis:** token administrativo, `SECRET_KEY`, senhas de teste e de seed, hashes de senha e o literal de `SECRET_KEY` do código original aparecem como `<removido>`/`<hash-removido>`. Os caminhos temporários aparecem como `<scratchpad>/fase3`.

> **Rodada 2 (2026-10-31).** Uma revisão independente reproduziu três falhas da implementação validada na rodada 1 (números não finitos aceitos em produtos, 500 em `/admin/query` com `consulta` não textual e 500 no login de contas com senha legada/hash malformado) e apontou que o registro da verificação de importação estava incorreto. As seções 1–11 descrevem a **rodada 1** e foram mantidas como registro histórico, com correções pontuais marcadas como "Rodada 2". A correção e a revalidação estão na **seção 12**. As evidências da rodada 1 estão na raiz desta pasta e as da rodada 2 em `rodada-2/`.

> **Rodada 3 (2026-10-31).** A revisão confirmou a rodada 2, mas encontrou três formatos de hash malformado que ainda provocavam 500 no login. A correção e a revalidação estão na **seção 13**; as evidências, em `rodada-3/`. As seções 1–12 continuam como registro das rodadas 1 e 2.

## 1. Decisões do usuário aplicadas

| ID | Escolha | Como foi aplicada |
|---|---|---|
| D-1 | (c) | `POST /admin/query` mantido com `X-Admin-Token`/`ADMIN_TOKEN` e catálogo fechado de 4 consultas somente leitura (`models/admin.py`); `{"sql": ...}` → 400 sem execução |
| D-2 | (b) | `POST /admin/reset-db` mantido com `X-Admin-Token`; mesmo corpo de sucesso e mesmo efeito (DELETE nas 4 tabelas), agora em transação única |
| D-3 | (d) | Usuários de demonstração (mesmos nome/e-mail/tipo) criados só com `SEED_SENHA_ADMIN`/`_JOAO`/`_MARIA`, gravados com hash; sem variável → usuário não criado + aviso |
| D-4 | (a) | Sem compatibilidade com senhas legadas e sem `migrar_senhas.py`; nenhum banco foi apagado ou recriado; limitação documentada (README e seção 7) |
| D-5 | (a) | Host padrão `127.0.0.1`, configurável por `HOST` |
| D-6 | (b) | `GET /relatorios/vendas`, `GET /usuarios` e `GET /usuarios/<id>` exigem `X-Admin-Token` |

Mecanismo comum: `auth.require_admin_token` — sem `ADMIN_TOKEN` configurado → 403 `{"erro": "Operação administrativa desabilitada"}`; header ausente/incorreto → 401 `{"erro": "Não autorizado"}`; comparação com `hmac.compare_digest`, antes da leitura do corpo.

## 2. Ambiente e versões instaladas

Ambiente temporário fora do repositório (`<scratchpad>/fase3/venv`), criado com `python3 -m venv` e `pip install -r requirements.txt`. O mesmo ambiente foi usado para a linha de base e para o refatorado (`requirements.txt` não mudou).

| Componente | Declarado | Instalado |
|---|---|---|
| Python | — | 3.14.0 |
| Flask | 3.1.1 | 3.1.1 |
| flask-cors | 5.0.1 | 5.0.1 |
| Werkzeug (transitiva) | — | 3.1.9 |
| Jinja2 / itsdangerous / click / blinker / MarkupSafe | — | 3.1.6 / 2.2.0 / 8.5.0 / 1.9.0 / 3.0.4 |

## 3. Comandos executados (ordem) e resultado resumido

1. `git status --porcelain` (raiz) → somente `?? requirements.txt` preexistente; nenhuma gravação anterior à interrupção.
2. Gravação de `reports/audit-project-1.md` (relatório da Fase 2 tal como apresentado + linha de aprovação).
3. `rsync` do alvo (sem `.git`/`.claude`) para `<scratchpad>/fase3/original`; `python3 -m venv venv`; `venv/bin/pip install -r original/requirements.txt` → versões da seção 2; `ss -ltn` → portas 5000–5009 livres.
4. Linha de base: `tools/run_original.py` — reproduz o `__main__` de `app.py` (`get_db()` + `app.run(debug=True)`), mas com `host="127.0.0.1"` e `use_reloader=False` para não expor o depurador do Werkzeug na rede e controlar o PID.
   - 1ª execução da matriz **descartada**: o cliente HTTP usou o proxy de `http_proxy`, todas as respostas foram 503 do proxy e nenhuma requisição chegou à aplicação (banco inalterado: 10/3/0/0). O script passou a ignorar o proxy (`ProxyHandler({})`) e a matriz foi refeita sobre banco novo.
   - `tools/matrix.py http://127.0.0.1:5000 original/loja.db baseline.json` → 54 casos.
   - `tools/rollback_test.sh` no original → `rollback_baseline.txt` (F-09 confirmado em execução, seção 6).
5. Refatoração no diretório do projeto (seção 8).
6. Cópia do refatorado para `<scratchpad>/fase3/refatorado`; verificação de importação; segredos de teste gerados com `secrets.token_urlsafe` em `secrets.env` (scratchpad, não preservado).
   - **Correção do registro (rodada 2):** a versão anterior deste item dizia `python -I -c "import app"`, o que é impreciso. Com `-I`, o diretório atual não entra no `sys.path`, e esse comando falha com `ModuleNotFoundError` (exit 1) num cwd sem `app.py`, como mostra o controle em `rodada-2/importacao.txt`. O comando executado de fato foi `cd <scratchpad>/fase3/refatorado && venv/bin/python -I -c "import sys; sys.path.insert(0,'.'); import app; print('import ok, create_app:', callable(app.create_app))" && ls *.db 2>/dev/null || echo "importar app.py nao criou banco"`. A saída foi `import ok, create_app: True`, um erro do zsh (`no matches found: *.db`) e a mensagem final. Esse registro tinha quatro limitações:
     - não guardou `app.__file__`;
     - não usou `-B`, então pode ter criado `__pycache__` na cópia;
     - só procurou banco no cwd, que era o próprio diretório da cópia;
     - não foi repetido depois dos ajustes do item 11, ao contrário do que esse item dava a entender.
     
     A verificação foi **refeita** na rodada 2 com caminho explícito, cópia nova sem banco, cwd temporário vazio, `-I -B`, `app.__file__`, código de saída e checagem de `*.db` no projeto e no cwd (seção 12.4).
7. `python app.py` (comando original de inicialização) com `DATABASE_PATH` na cópia → `Rodando em http://127.0.0.1:5000`, `Debug mode: off`, sem erros.
8. `url_map` via `create_app()` → 19 combinações método+rota (`url_map.txt`).
9. `tools/matrix.py ... --refatorado` → 54 casos (`refatorado.json`); `tools/compare.py` → `matriz.md` (seção 4).
10. `tools/specific.py` → 117 OK, 0 falhas (`specific.txt`, seção 5).
11. `tools/inspecao.sh` no código refatorado → `inspecao.txt` (seção 7). Achados de resíduo (SQL `SELECT 1` no controller; parâmetro `id` nas rotas) corrigidos e os passos 6–11 **repetidos** em cópia nova: resultados finais são os registrados aqui.
12. Incidentes de harness (não afetam o código): `pkill -f` encerrou o próprio shell de teste uma vez; conflito de nome de módulo `models` no script de teste corrigido carregando o relatório refatorado por caminho. Ambos refeitos.

## 4. Matriz de endpoints — antes × depois

Mesmas entradas, na mesma ordem, em bancos novos e isolados. Campos `criado_em` normalizados; senhas e hashes mascarados. No refatorado, os endpoints protegidos foram chamados **com** `X-Admin-Token` válido (a rejeição sem autorização está na seção 5). Corpos completos em `baseline.json` e `refatorado.json`.

| # | Caso | Método e caminho | Original | Refatorado | Resultado |
|---:|---|---|---|---|---|
| 1 | indice | `GET /` | 200 | 200 | Preservado (status e corpo idênticos) |
| 2 | health | `GET /health` | 200 | 200 | Correção intencional (5.4 item 2, F-07/F-08): sem secret_key e db_path; debug reflete a configuração (false) |
| 3 | listar produtos | `GET /produtos` | 200 | 200 | Preservado (status e corpo idênticos) |
| 4 | produto existente | `GET /produtos/1` | 200 | 200 | Preservado (status e corpo idênticos) |
| 5 | produto inexistente | `GET /produtos/999` | 404 | 404 | Preservado (status e corpo idênticos) |
| 6 | busca por termo | `GET /produtos/busca?q=Mouse` | 200 | 200 | Preservado (status e corpo idênticos) |
| 7 | busca categoria+faixa | `GET /produtos/busca?categoria=moveis&preco_min=100&preco_max=2000` | 200 | 200 | Preservado (status e corpo idênticos) |
| 8 | busca com aspas (injecao) | `GET /produtos/busca?q=x%27%20OR%20%271%27%3D%271` | 200 | 200 | Preservado (status e corpo idênticos) |
| 9 | busca preco_min invalido | `GET /produtos/busca?preco_min=abc` | 500 | 400 | Correção intencional (5.4 item 4, F-14): 500 com str(e) → 400 controlado |
| 10 | criar produto valido | `POST /produtos` | 201 | 201 | Preservado (status e corpo idênticos) |
| 11 | criar produto sem nome | `POST /produtos` | 400 | 400 | Preservado (status e corpo idênticos) |
| 12 | criar produto categoria invalida | `POST /produtos` | 400 | 400 | Preservado (status e corpo idênticos) |
| 13 | criar produto com aspas | `POST /produtos` | 500 | 201 | Correção intencional (5.4 item 8, F-01): aspas tratadas como texto; o original falhava com erro de sintaxe SQL |
| 14 | criar produto preco string | `POST /produtos` | 500 | 400 | Correção intencional (5.4 item 4, F-14) |
| 15 | criar produto sem corpo JSON | `POST /produtos` | 500 | 400 | Correção intencional (5.4 item 4, F-14): o original devolvia 415 embrulhado em 500 |
| 16 | atualizar produto 11 | `PUT /produtos/11` | 200 | 200 | Preservado (status e corpo idênticos) |
| 17 | ler produto 11 apos update | `GET /produtos/11` | 200 | 200 | Preservado (status e corpo idênticos) |
| 18 | atualizar produto inexistente | `PUT /produtos/999` | 404 | 404 | Preservado (status e corpo idênticos) |
| 19 | atualizar produto categoria invalida | `PUT /produtos/11` | 200 | 400 | Correção intencional (5.4 item 7, F-17): PUT aplica as regras do POST |
| 20 | deletar produto 12 | `DELETE /produtos/12` | 404 | 200 | Consequência do caso 'criar produto com aspas': o produto 12 agora existe e é excluído (efeito conferido) |
| 21 | ler produto 12 apos delete | `GET /produtos/12` | 404 | 404 | Preservado (status e corpo idênticos) |
| 22 | deletar produto inexistente | `DELETE /produtos/999` | 404 | 404 | Preservado (status e corpo idênticos) |
| 23 | listar usuarios | `GET /usuarios` | 200 | 200 | Correção intencional (5.4 item 1, F-03): sem o campo senha; os demais campos são idênticos; exige X-Admin-Token (D-6 b) |
| 24 | usuario existente | `GET /usuarios/1` | 200 | 200 | Correção intencional (5.4 item 1, F-03); exige X-Admin-Token (D-6 b) |
| 25 | usuario inexistente | `GET /usuarios/999` | 404 | 404 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 26 | criar usuario valido | `POST /usuarios` | 201 | 201 | Preservado (status e corpo idênticos) |
| 27 | criar usuario incompleto | `POST /usuarios` | 400 | 400 | Preservado (status e corpo idênticos) |
| 28 | login admin valido | `POST /login` | 200 | 200 | Preservado (status e corpo idênticos) |
| 29 | login usuario criado | `POST /login` | 200 | 200 | Preservado (status e corpo idênticos) |
| 30 | login senha errada | `POST /login` | 401 | 401 | Preservado (status e corpo idênticos) |
| 31 | login incompleto | `POST /login` | 400 | 400 | Preservado (status e corpo idênticos) |
| 32 | login sem corpo JSON | `POST /login` | 500 | 400 | Correção intencional (5.4 item 4, F-14) |
| 33 | login injecao | `POST /login` | 200 | 401 | Correção intencional (5.4 item 8, F-01): o original autenticava o admin sem senha |
| 34 | criar pedido valido | `POST /pedidos` | 201 | 201 | Preservado (status e corpo idênticos) |
| 35 | pedido produto inexistente | `POST /pedidos` | 400 | 400 | Preservado (status e corpo idênticos) |
| 36 | pedido estoque insuficiente | `POST /pedidos` | 400 | 400 | Preservado (status e corpo idênticos) |
| 37 | pedido sem usuario | `POST /pedidos` | 400 | 400 | Preservado (status e corpo idênticos) |
| 38 | pedido sem itens | `POST /pedidos` | 400 | 400 | Preservado (status e corpo idênticos) |
| 39 | pedido quantidade negativa | `POST /pedidos` | 201 | 400 | Correção intencional (5.4 item 5, F-14): o original aceitava e AUMENTAVA o estoque (10→15) |
| 40 | pedido produto_id com injecao | `POST /pedidos` | 201 | 400 | Correção intencional (5.4 item 5, F-01/F-14): o original criava o pedido com id injetado |
| 41 | listar pedidos | `GET /pedidos` | 200 | 200 | Consequência dos dois casos acima: o original listava 3 pedidos (2 inválidos); o pedido 1 é idêntico (verificado) |
| 42 | pedidos do usuario 2 | `GET /pedidos/usuario/2` | 200 | 200 | Idem: o pedido 1 é idêntico; os pedidos 2 e 3 do original eram inválidos |
| 43 | pedidos de usuario sem pedidos | `GET /pedidos/usuario/999` | 200 | 200 | Preservado (status e corpo idênticos) |
| 44 | status aprovado | `PUT /pedidos/1/status` | 200 | 200 | Preservado (status e corpo idênticos) |
| 45 | status invalido | `PUT /pedidos/1/status` | 400 | 400 | Preservado (status e corpo idênticos) |
| 46 | status pedido inexistente | `PUT /pedidos/999/status` | 200 | 404 | Correção intencional (5.4 item 6, F-14): 200 sem efeito → 404 |
| 47 | status sem corpo JSON | `PUT /pedidos/1/status` | 500 | 400 | Correção intencional (5.4 item 4, F-14) |
| 48 | relatorio vendas | `GET /relatorios/vendas` | 200 | 200 | Consequência dos pedidos inválidos rejeitados (o faturamento do original ficava negativo); regra de desconto idêntica em 9 faixas (testes, seção 6); exige X-Admin-Token (D-6 b) |
| 49 | health apos escritas | `GET /health` | 200 | 200 | Correção intencional (5.4 item 2); contagens diferem pelos pedidos inválidos que o original aceitava |
| 50 | admin query predefinida | `POST /admin/query` | 200 | 200 | Mudança de contrato aprovada (D-1 c): corpo {consulta}; o caso original {sql} é rejeitado com 400 (testes, seção 2) |
| 51 | admin query sem consulta | `POST /admin/query` | 400 | 400 | Mudança de contrato aprovada (D-1 c): mensagem 'Consulta não informada' (adaptação de 'Query não informada') |
| 52 | admin reset-db | `POST /admin/reset-db` | 200 | 200 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 53 | listar produtos apos reset | `GET /produtos` | 200 | 200 | Preservado (status e corpo idênticos) |
| 54 | health apos reset | `GET /health` | 200 | 200 | Correção intencional (5.4 item 2) |

Casos: 54 | idênticos: 32 | diferenças classificadas: 22 | regressões: 0

Cobertura: as 19 combinações método+rota do `url_map` foram exercitadas (`DELETE /produtos/<id>`, `GET /`, `GET /health`, `GET /pedidos`, `GET /pedidos/usuario/<id>`, `GET /produtos`, `GET /produtos/<id>`, `GET /produtos/busca`, `GET /relatorios/vendas`, `GET /usuarios`, `GET /usuarios/<id>`, `POST /admin/query`, `POST /admin/reset-db`, `POST /login`, `POST /pedidos`, `POST /produtos`, `POST /usuarios`, `PUT /pedidos/<id>/status`, `PUT /produtos/<id>`).

Verificações adicionais sobre as diferenças: o pedido 1 (único válido) é idêntico nas duas versões em `GET /pedidos` e `GET /pedidos/usuario/2`; `GET /usuarios` e `GET /usuarios/1` são idênticos à linha de base com exceção do campo `senha`; o efeito de `POST /pedidos` válido no estoque é idêntico (produto 2: 50 → 48; 1 pedido, 2 itens).

## 5. Testes específicos das decisões, rollback e erros (`specific.txt`)

Resultado: **117 OK, 0 falhas**. Cada grupo rodou em instância e banco isolados próprios.

| Grupo | O que demonstra |
|---|---|
| 1. Autorização (D-1 c, D-2 b, D-6 b) | Nos 5 endpoints protegidos: sem `ADMIN_TOKEN` configurado → 403 (com e sem header); configurado, sem header / token incorreto / token truncado → 401; contagens do banco inalteradas; token correto → 200, sem `senha` nem hash na resposta; `GET /usuarios/999` autorizado → 404; endpoints públicos seguem sem token |
| 2. `/admin/query` (D-1 c) | As 4 consultas → 200 e iguais à mesma consulta feita direto no arquivo isolado; `limite` 0/3/5/1000 e padrão 5; `{"sql": DELETE…}`, `{"sql": SELECT * FROM usuarios}` e `sql`+`consulta` → 400 sem execução e contagens inalteradas; nome desconhecido, `limite` malicioso/negativo/bool/texto, parâmetro extra e `parametros` não-objeto → 400; corpo não-JSON → 400; token ausente do log |
| 3. `/admin/reset-db` (D-2 b) | Sem header/incorreto → 401 com contagens iguais; correto → 200 com o corpo da linha de base e as 4 tabelas zeradas (consulta direta), `GET /produtos` vazio, `/health` zerado, WARNING no log; reinício repete o seed (10/3); falha forçada (trigger) no DELETE de `usuarios` → 500 genérico e **nenhuma tabela esvaziada** (rollback) |
| 4. Seed (D-3 d) | Login dos 3 usuários com senha configurada → 200 com os mesmos `dados` da linha de base; senha errada → 401; coluna `senha` com prefixo de hash e diferente do valor configurado; `POST /usuarios` grava hash; login com injeção → 401; sem variáveis → nenhum usuário, produtos criados, login 401, aviso para os 3 e-mails; só `SEED_SENHA_JOAO` → apenas João; log sem senhas; sem `SECRET_KEY` → inicia com aviso de chave efêmera |
| 5. Rollback do pedido (F-09) | Mesmo cenário da linha de base (trigger falha no item do produto 3): 500 genérico e, após escrita independente, **0 pedidos e 0 itens parciais, estoque intacto**; itens repetidos que somados excedem o estoque → 400 e estoque intacto; quantidade 0/1.5/ausente, `usuario_id` texto, `itens` objeto → 400 |
| 6. Relatório | `relatorio.vendas` refatorado == `models.relatorio_vendas` original nos limites 0, 999.99, 1000, 1000.01, 5000, 5000.01, 10000, 10000.01, 25000 |
| 7. Banco legado (D-4 a) | Banco gerado pelo código original: login com a senha legada → 401 (limitação aprovada); dados continuam legíveis; dump completo das 4 tabelas **idêntico** antes e depois de iniciar e usar o refatorado (nada recriado/alterado) |
| 8. Erros gerais | Rota inexistente → 404 HTML do Flask e método não permitido → 405 (preservados); `/produtos/abc` → 404; erro de banco inesperado → 500 `{"erro": "Erro interno do servidor"}` sem SQL na resposta, detalhe só no log; `/health` com banco quebrado → 500 `{"status": "erro", "detalhes": "Banco de dados indisponível"}` |

## 6. Rollback na linha de base (`rollback_baseline.txt`)

No código **original**, com o mesmo trigger: `POST /pedidos` → 500 `{"erro": "falha forcada"}` e banco aparentemente intacto (0/0, estoque 50); após um `POST /produtos` independente, o banco passou a ter **1 pedido, 1 item e estoque 48** — as escritas parciais foram confirmadas pelo `commit` de outra requisição. Isso confirma em execução o efeito que a Fase 2 registrou como deduzido do código. No refatorado (seção 5, grupo 5) o mesmo roteiro termina com 0 pedidos, 0 itens e estoque 50.

## 7. Nova inspeção — situação de cada achado

Inspeção estática (`inspecao.txt`, AST de imports sem uso) + evidência de execução das seções 4–6.

| Achado | Situação | Evidência |
|---|---|---|
| F-01 SQL Injection | **Corrigido** | Todas as consultas usam `?`; as únicas f-strings em SQL interpolam constantes do código (`COLUNAS`, `COLUNAS_PUBLICAS`, tupla fixa `TABELAS`/`ORDEM_RESET`). Execução: produto com aspas → 201; login `admin@loja.com' --` → 401 (original: 200); `produto_id: "1 OR 1=1"` → 400 (original: 201) |
| F-02 `/admin/query` SQL arbitrário | **Corrigido** (D-1 c) | Catálogo fechado em `models/admin.py`; `sql` → 400 sem execução; token obrigatório (seção 5, grupos 1–2). **Rodada 2:** com token correto, `consulta` como lista ou objeto causava 500 (`TypeError` na busca no dicionário); o tipo agora é validado antes da busca → 400 (seção 12) |
| F-03 Senha nas respostas | **Corrigido** | `models/usuario.py` não seleciona `senha` para respostas; matriz e grupo 1 sem `senha`/hash |
| F-04 Senha em texto puro | **Corrigido no código, com limitação** | `generate_password_hash`/`check_password_hash`; seed sem senhas no código (D-3 d). Bancos criados pela versão original continuam com senhas em texto puro no arquivo e essas contas não autenticam (D-4 a, aprovado). **Rodada 2:** contas legadas cuja senha em texto puro contém `$` (ex.: `abc$def$ghi`) ou hashes malformados causavam 500 no login (`ValueError` do Werkzeug/hashlib); agora → 401 sem modificar o banco (seção 12) |
| F-05 `/admin/reset-db` sem controle | **Corrigido** (D-2 b) | Token obrigatório; efeito transacional (grupo 3) |
| F-06 SECRET_KEY no código | **Corrigido** | `config.py` lê `SECRET_KEY` do ambiente, sem fallback literal; ausente → chave efêmera com aviso; `grep` não encontra o literal antigo |
| F-07 `/health` expõe segredo | **Corrigido** | Sem `secret_key`/`db_path`; `debug` real (`false`). Resta o literal `"ambiente": "producao"` (não sensível, ver R-4) |
| F-08 Debug fixo / 0.0.0.0 | **Corrigido** | `FLASK_DEBUG` (padrão off), `HOST` padrão `127.0.0.1`, `PORT` 5000; log "Debug mode: off". CORS aberto permanece como observação (R-3) |
| F-09 Pedido sem rollback | **Corrigido** | `with db:` + conexão por requisição + baixa condicional `estoque >= ?`; demonstrado em execução (seções 5 e 6). Concorrência real não testada sob carga (R-8) |
| F-10 Conexão global | **Corrigido** | `get_db()` por requisição em `g` + `teardown_appcontext`; caminho via `DATABASE_PATH`; sem `global`/`check_same_thread` |
| F-11 Relatório/usuários sem acesso | **Corrigido** (D-6 b) | Token obrigatório (grupo 1) |
| F-12 Camadas nominais | **Corrigido** | `routes/` (HTTP), `controllers/` (casos de uso, sem `request`/`jsonify`/SQL), `models/` por entidade (SQL e regras). Inspeção: nenhum `execute(` fora de `models/`/`database.py`; nenhum `request`/`jsonify` em models/controllers. Observação: controllers obtêm a conexão por `database.get_db()` (contexto Flask), ver R-10 |
| F-13 Acoplamento / init implícito | **Parcialmente corrigido** | `create_app(overrides)`, `init_db()` explícito, configuração por ambiente, importar não cria banco. Permanecem: seed automático sempre que `produtos` está vazia (contrato preservado, R-9) e dependência direta de `get_db()` nos controllers (R-10) |
| F-14 Validação insuficiente | **Parcialmente corrigido** | Corpo ausente/não-JSON, tipos, quantidade ≤ 0, `preco_min` inválido e pedido inexistente agora → 4xx (matriz). Permanece sem validação de formato e unicidade de e-mail (R-1). **Rodada 2:** `preco`/`estoque` não finitos (`1e309`, `NaN`, `Infinity`) eram aceitos e gravados como infinito/NULL, e `preco_min`/`preco_max` aceitavam `inf`/`nan`; agora → 400 antes da persistência (seção 12) |
| F-15 Erros dispersos | **Corrigido** | `errors.py` com handler central; nenhum `str(e)`/`except Exception` em rotas; 500 genérico com traceback só no log (grupo 8) |
| F-16 N+1 | **Parcialmente corrigido** | Listagens de pedidos: 1 consulta com `LEFT JOIN` (antes 1 + N + N×M). Criação de pedido: de 2N para N consultas de produto (uma por item) — remanescente menor |
| F-17 Duplicação/divergência | **Corrigido** | `produto.validar` único para POST e PUT; serializadores únicos; listagens com uma implementação (`_listar`) |
| F-18 Magic numbers | **Corrigido** | `FAIXAS_DESCONTO`, `NOME_MIN/MAX_LENGTH`, `CATEGORIAS_VALIDAS`, `STATUS_VALIDOS`, `API_VERSION`, `LIMITE_ESTOQUE_PADRAO`; resultados idênticos nos limites (grupo 6) |
| F-19 Logging com print | **Corrigido** | `logging` com níveis; login sem e-mail no log; `print` só no banner de inicialização (permitido) |
| F-20 Imports sem uso | **Corrigido** | AST sem imports sem uso; `SELECT 1` mantido (movido para `models/admin.verificar_conexao`) |
| F-21 Nomes | **Corrigido** | Sem variável `id`; parâmetros de URL `produto_id`/`usuario_id` (caminhos inalterados) |

### Problemas remanescentes e novos

| ID | Descrição | Origem |
|---|---|---|
| R-1 | E-mail sem validação de formato e sem `UNIQUE` no schema; cadastros duplicados continuam possíveis (o login verifica cada cadastro com o e-mail) | F-14 / limitação da Fase 2 |
| R-2 | Mudança de status para `cancelado` não devolve estoque (só registra "Devolver estoque" no log) — regra ausente, fora do escopo | Limitação da Fase 2 |
| R-3 | `CORS(app)` libera qualquer origem (sem credenciais) | Observação de F-08 |
| R-4 | `/health` mantém `"ambiente": "producao"` fixo, que pode não refletir o ambiente real | F-07 (contrato preservado) |
| R-5 | Não há autenticação de usuários finais (o `/login` não emite sessão/token); proteção administrativa usa um único token compartilhado, sem limitação de tentativas | Fora do escopo |
| R-6 | `python app.py` usa o servidor de desenvolvimento do Werkzeug | Ponto de entrada preservado |
| R-7 | Bancos legados mantêm senhas em texto puro no arquivo; essas contas não autenticam até redefinição (não há rota de redefinição) | D-4 (a) |
| R-8 | Contenção de escrita no SQLite (`database is locked`) não tem tratamento específico (vira 500 genérico após o timeout padrão); concorrência não foi testada sob carga | F-09 |
| R-9 | Seed executado sempre que `produtos` está vazia (inclusive após reset + reinício), sem opção para desligar | Contrato preservado |
| R-10 | Controllers chamam `database.get_db()` (contexto Flask) em vez de receber a conexão por parâmetro; models recebem `db` e são testáveis isoladamente | Simplicidade |

## 8. Mudanças de contrato efetivadas

Todas previstas na seção 5.4 do relatório aprovado:

1. `GET /usuarios`, `GET /usuarios/<id>`: sem `senha`.
2. `GET /health`: sem `secret_key`/`db_path`; `debug` real; falha → `{"status": "erro", "detalhes": "Banco de dados indisponível"}`.
3. 500 → `{"erro": "Erro interno do servidor"}`.
4. Entradas inválidas → 400 com mensagens controladas, inclusive novas mensagens para tipos inválidos: "Dados inválidos", "Nome inválido", "Descrição inválida", "Preço inválido", "Estoque inválido", "Parâmetro preco_min inválido", "Usuario ID inválido", "Itens inválidos", "Item inválido: …".
5. `POST /pedidos`: quantidade ≤ 0/não inteira e ids não inteiros → 400. Consequência da baixa condicional de F-09: itens repetidos do mesmo produto cuja soma excede o estoque → 400 `Estoque insuficiente para <nome>` (por leitura do código original, `models.py:139-146` validava cada item contra o estoque inicial e podia deixar o estoque negativo; não executado na linha de base).
6. `PUT /pedidos/<id>/status` inexistente → 404 `{"erro": "Pedido não encontrado"}`.
7. `PUT /produtos/<id>`: mesmas regras de nome/categoria do POST.
8. Aspas tratadas como texto literal.
9. Senhas com hash; seed conforme D-3 (d); legado conforme D-4 (a).
10. Debug off por padrão; host `127.0.0.1`.
11. D-1 (c), D-2 (b), D-6 (b) conforme seção 1.

Arquivos do projeto alterados: `app.py`, `database.py`, `README.md` (modificados); `controllers.py`, `models.py` (removidos, substituídos pelos pacotes); `config.py`, `errors.py`, `auth.py`, `.env.example`, `models/`, `controllers/`, `routes/` (novos).

## 9. Limitações da validação

- A linha de base não foi iniciada exatamente por `python app.py`: usou um wrapper equivalente ao `__main__` com bind `127.0.0.1` e sem reloader, para não expor o depurador interativo na rede. O refatorado foi iniciado por `python app.py`.
- Validação com o servidor de desenvolvimento e requisições sequenciais; sem teste de concorrência ou carga.
- Falhas de transação foram provocadas com triggers SQLite em bancos isolados de teste.
- Não há integrações externas reais no projeto (notificações são apenas log); nada externo foi acionado.
- Bancos fora do repositório não foram procurados nem tocados.

## 10. Arquivos desta pasta

- `validation.md` — este documento.
- `matriz.md` — matriz antes × depois (mesma tabela da seção 4).
- `baseline.json`, `refatorado.json` — corpos completos (mascarados) dos 54 casos.
- `specific.txt` — saída dos 117 testes específicos.
- `rollback_baseline.txt` — rollback no código original.
- `inspecao.txt` — nova inspeção estática.
- `url_map.txt` — rotas registradas no refatorado.
- `delete_complemento.txt` — complemento da seção 11.
- `logs/original.log`, `logs/refatorado.log`, `logs/testes-especificos.log` — trechos pertinentes.
- `rodada-2/` — evidências da rodada 2 (seção 12). Os arquivos acima, na raiz da pasta, são da rodada 1.
- `rodada-3/` — evidências da rodada 3 (seção 13).

## 11. Complemento: `DELETE /produtos/<id>` com sucesso na linha de base

Na matriz principal, o caso "deletar produto 12" não exercitou o caminho de sucesso no original: o produto 12 deveria ter sido criado pelo caso "criar produto com aspas", que no original falha (erro de sintaxe SQL, F-01). Para cobrir o caminho de sucesso, os arquivos do commit `40d2986` foram extraídos com `git show` para um diretório temporário novo, com um venv novo (mesmas versões da seção 2), e o mesmo roteiro rodou nas duas versões (`delete_complemento.txt`):

| Passo | Original | Refatorado |
|---|---|---|
| `POST /produtos` | 201 `{"dados": {"id": 11}, …}` | 201 idêntico |
| `COUNT(*) produtos` antes | 11 | 11 |
| `DELETE /produtos/11` | 200 `{"mensagem": "Produto deletado", "sucesso": true}` | 200 idêntico |
| `COUNT(*) produtos` depois | 10 | 10 |
| `GET /produtos/11` | 404 `{"erro": "Produto não encontrado", "sucesso": false}` | 404 idêntico |
| `DELETE /produtos/11` de novo | 404 `{"erro": "Produto não encontrado"}` | 404 idêntico |

Resultado: **preservado**. A única diferença é a indentação do JSON, porque o Flask formata a resposta quando o debug está ligado (original); o conteúdo é igual.

## 12. Rodada 2 (2026-10-31): correção das falhas apontadas pela revisão independente

Escopo: só as quatro falhas apontadas pela revisão. As decisões D-1 (c), D-2 (b), D-3 (d), D-4 (a), D-5 (a) e D-6 (b) não mudaram, e o relatório `reports/audit-project-1.md` e a Skill não foram alterados. Ambiente: venv temporário novo (`<scratchpad>/rodada2/venv`) com as mesmas versões da seção 2 (Python 3.14.0, Flask 3.1.1, flask-cors 5.0.1, Werkzeug 3.1.9).

### 12.1 Reprodução antes da correção (`rodada-2/reproducao_antes.txt`)

Executada por HTTP real (`python app.py`, banco isolado) sobre uma cópia da implementação da rodada 1, **antes** de qualquer alteração (ferramenta: `rodada-2/tools/reproducao.py`):

| Falha | Resultado observado antes |
|---|---|
| Números não finitos | `POST /produtos` com `preco` `1e309`/`Infinity` → 201 e `inf` gravado; `NaN` → 201 e `NULL` gravado; o mesmo vale para `estoque`; `PUT /produtos/1` idem, com 200. `-Infinity` já era rejeitado ("Preço não pode ser negativo"). `preco_min=inf`/`nan` e `preco_max=1e309`/`-inf` → 200, com respostas contendo `Infinity`, que não é JSON padrão |
| Tipo de `consulta` | Com token correto, `["contagem_por_tabela"]` e `{"nome": …}` → 500 (`TypeError: cannot use 'list'/'dict' as a dict key`); `1` e `true` já davam 400; sem token, 401 |
| Senhas legadas/hash malformado | `abc$def$ghi`, `pbkdf2:sha256:abc$salt$hash`, `pbkdf2:nada:10$salt$hash` e `scrypt:x:8:1$salt$hash` → 500 (`ValueError: Invalid hash method 'abc'`, `invalid literal for int()`, `UnsupportedDigestmodError`, `'scrypt' takes 3 arguments`); `texto-puro` (sem `$`) já dava 401; banco não alterado |

Os casos não citados pela revisão (`Infinity`, `estoque` não finito, filtros e os outros três formatos de hash) têm a mesma causa e foram incluídos na correção sem ampliar o escopo.

### 12.2 Correções aplicadas

| Arquivo | Mudança |
|---|---|
| `models/produto.py` | `_is_number` exige `math.isfinite(value)`: `preco`/`estoque` não finitos → 400 `"Preço inválido"`/`"Estoque inválido"` (mesmas mensagens já usadas para tipo inválido), antes da persistência |
| `controllers/produto_controller.py` | `_preco_opcional` rejeita valores convertidos que não são finitos → 400 `"Parâmetro preco_min inválido"`/`"Parâmetro preco_max inválido"` (mesma mensagem já usada para texto não numérico) |
| `models/admin.py` (`executar_consulta`) | `isinstance(nome, str)` verificado **antes** de `nome in CONSULTAS` → 400 `"Consulta inválida. Válidas: [...]"`; catálogo e autorização inalterados. Valores vazios (`[]`, `{}`, `""`, `null`) continuam caindo em "Consulta não informada" |
| `models/usuario.py` | `_senha_confere`: valor armazenado que não é texto ou está vazio → falha; `check_password_hash` envolvido apenas em `except ValueError` (o que inclui `hashlib.UnsupportedDigestmodError`, subclasse de `ValueError`), que registra um aviso sem o conteúdo armazenado e recusa a autenticação → 401. Não há comparação com texto puro, migração nem escrita no banco. Erros de banco (`sqlite3.Error`) **não** são capturados e continuam virando 500 |

Mudança de contrato: só rejeições novas, com status 400/401 e mensagens já existentes, para entradas que antes eram aceitas indevidamente ou geravam 500. Nenhum valor finito válido mudou de comportamento.

### 12.3 Testes de regressão reutilizáveis (`code-smells-project/tests/test_regressao.py`)

Usam só `unittest` da biblioteca padrão e o `test_client` do Flask, sem dependências novas. Para executar, a partir da raiz do projeto: `python -B -m unittest discover -s tests -v`.

| Classe | Cobre |
|---|---|
| `NumerosNaoFinitosTest` | POST e PUT com `1e309`, `-1e309`, `NaN`, `Infinity`, `-Infinity` em `preco` e `estoque` → 400 e tabela `produtos` idêntica; valores finitos (`0`, `12.5`, `1e6`, `2.0`, `5999.99`) aceitos e gravados; filtros `inf`/`-inf`/`nan`/`NaN`/`Infinity`/`1e309` → 400; filtro finito continua funcionando |
| `TipoConsultaAdministrativaTest` | `consulta` lista/objeto/número/booleano/decimal → 400; vazios → "Consulta não informada"; sem token → 401 e sem configuração → 403 (autorização antes da validação); consulta válida → 200 |
| `SenhasLegadasTest` | 6 formatos legados ou malformados e `NULL` → 401 com a senha armazenada e com outra senha, com a tabela `usuarios` idêntica; hashes válidos `scrypt`, `pbkdf2:sha256` e `pbkdf2:sha256:1000` e o admin do seed autenticam (senha errada → 401); cadastro duplicado com hash válido depois de um legado autentica; tabela `usuarios` ausente → 500 (erro de infraestrutura não mascarado) |
| `ImportacaoTest` | Importa `app.py` em subprocesso `-I -B` com caminho explícito, a partir de um cwd temporário vazio: `app.__file__` correto, nenhum arquivo no cwd e listagem do projeto inalterada |

Resultados (cópias isoladas):
- **Implementação corrigida:** `Ran 15 tests … OK` (`rodada-2/unittest_pos.txt`). A linha `OperationalError: no such table: usuarios` na saída é o traceback registrado pelo teste de infraestrutura, que é esperado.
- **Controle sobre a implementação anterior à correção:** `FAILED (failures=42)` nos subtestes de não finitos, tipo de consulta e senhas legadas; os testes de comportamento válido e de importação passam (`rodada-2/unittest_antes_da_correcao.txt`). Isso confirma que os testes detectam as falhas.

### 12.4 Verificação de importação refeita (`rodada-2/importacao.txt`, ferramenta `rodada-2/tools/importacao.sh`)

- Cópia nova do projeto, sem `*.db`, sem `tests/` e sem `__pycache__`; cwd temporário vazio dentro do scratchpad.
- Comando completo: `cd <cwd> && env -u DATABASE_PATH <venv>/bin/python -I -B -c "import sys; sys.path.insert(0, '<projeto>'); import app; print('app.__file__ =', app.__file__); print('create_app callable:', callable(app.create_app))"`.
- Resultado: `app.__file__ = <projeto>/app.py`, `create_app callable: True`, **exit code 0**; arquivos no cwd depois da importação: nenhum; `*.db` antes e depois, no projeto e no cwd: 0; listagem do projeto idêntica antes e depois.
- Controle: `python -I -c "import app"` no mesmo cwd → `ModuleNotFoundError: No module named 'app'`, **exit code 1**. Isso confirma que o registro anterior estava incorreto (seção 3, item 6).

### 12.5 Reprodução depois da correção (`rodada-2/reproducao_depois.txt`)

Mesmo roteiro da 12.1, sobre a implementação corrigida:
- os 9 casos de produto com não finitos → 400 e "dados alterados: não";
- valores válidos → 201/200 gravados;
- os 4 filtros não finitos → 400; o filtro finito → 200;
- `consulta` lista/objeto → 400; sem token → 401; consulta válida → 200;
- os 5 logins legados ou malformados → 401 com `usuarios` inalterada; admin com hash válido → 200; senha errada → 401;
- **0 tracebacks** no log do servidor e nenhuma resposta 500.

### 12.6 Repetição da inicialização, da cobertura e das verificações afetadas

As ferramentas da rodada 1 foram apagadas junto com os temporários. Foram recriadas a partir do conteúdo registrado na sessão e **preservadas** em `rodada-2/tools/`. Na recriação, a senha do usuário criado nos testes passou a ser gerada a cada execução, e a checagem AP-02 da inspeção passou a procurar o padrão (senha literal em `generate_password_hash(` ou em tupla de seed), sem listar as senhas antigas. Essa checagem foi conferida contra o código original, onde detecta as três tuplas do seed.

| Verificação | Resultado |
|---|---|
| `url_map` via `create_app()` (`rodada-2/url_map.txt`) | 19 combinações método+rota, iguais às da rodada 1 |
| Inicialização: `python -B app.py` com `DATABASE_PATH` isolado | `Rodando em http://127.0.0.1:5000`, `Debug mode: off`, 0 tracebacks (`rodada-2/logs/refatorado.log`) |
| Matriz (`rodada-2/refatorado.json`, `rodada-2/matriz.md`), comparada com `baseline.json` da rodada 1 | 54 casos, as **19 combinações exercitadas**; 32 idênticos, 22 diferenças classificadas, **0 regressões**; resultado idêntico ao `refatorado.json` da rodada 1 em todos os 54 casos |
| Testes específicos (`rodada-2/specific.txt`) | **122 OK, 0 falhas**: os 117 da rodada 1, mais `consulta` lista/objeto → 400, ausência de traceback na instância de autorização, conta criada pelo código **original** com senha `abc$def$ghi` → 401, e ausência de traceback no login legado |
| Inspeção (`rodada-2/inspecao.txt`) | Sem SQL concatenado, segredos literais, `str(e)` ou `except Exception`; os únicos `except` são `sqlite3.Error` (health), `ValueError` (filtro de preço) e `ValueError` (verificação de hash) |

### 12.7 Situação após a rodada 2

- Achados F-02, F-04 e F-14: as falhas da revisão foram corrigidas; a situação de cada um na seção 7 não muda (F-04 "corrigido no código, com limitação"; F-14 "parcialmente corrigido", por R-1).
- Pendências da seção 7 (R-1 a R-10): **continuam**; não fizeram parte do escopo desta rodada.
- Sem commit nem push.

## 13. Rodada 3 (2026-10-31): hashes malformados que ainda provocavam 500

Escopo: só `models/usuario.py::_senha_confere` e os testes de regressão. Decisões D-1 (c) a D-6 (b), as pendências R-1 a R-10, o relatório `reports/audit-project-1.md` e a Skill não foram alterados. Ambiente: venv temporário novo (`<scratchpad>/rodada3/venv`), com Python 3.14.0, Flask 3.1.1, flask-cors 5.0.1 e Werkzeug 3.1.9.

### 13.1 Reprodução antes da correção (`rodada-3/reproducao_antes.txt`)

Por HTTP real (`python -B app.py`, banco isolado) sobre a implementação da rodada 2, com as contas inseridas direto na coluna `senha` (ferramenta `rodada-3/tools/reproducao_hashes.py`):

| Valor armazenado | Antes | Exceção no log |
|---|---|---|
| `pbkdf2:sha256:1000$salt$á` (revisão 1) | **500** | `TypeError: comparing strings with non-ASCII characters is not supported` |
| `pbkdf2:sha256:999999999999999999999$salt$hash` (revisão 2) | **500** | `OverflowError: Python int too large to convert to C long` |
| `scrypt:32768:8:-1$salt$hash` (revisão 3) | 401 **neste ambiente** | Aqui o `hashlib.scrypt` lança `ValueError: Cannot convert negative int`, que já era capturado. A revisão observou `TypeError: p is required and must be an unsigned int`, ou seja, o tipo da exceção depende do ambiente (versão do Python/OpenSSL) |
| `scrypt:9999999999:9999999999:9999999999$salt$00` (extra) | **500** | `OverflowError` |
| `pbkdf2:sha256:1000$salt$ÿ` (extra) | **500** | `TypeError` (não ASCII) |
| `scrypt:3:8:1$salt$00`, `pbkdf2:sha256:0$salt$00` (extras) | 401 | `ValueError` já capturado |

Em todos os casos o banco não foi alterado. O hash válido do admin autenticava (200), e a senha errada dava 401.

### 13.2 Correção (`models/usuario.py`)

1. **Validação de formato antes da verificação.** A constante `FORMATO_HASH` (expressão regular aplicada com `fullmatch`) aceita só a estrutura gravada pelo `generate_password_hash` do Werkzeug 3: `scrypt:<n>:<r>:<p>$<salt>$<hex>` ou `pbkdf2:<digest>:<iterações>$<salt>$<hex>`, com parâmetros inteiros positivos em dígitos ASCII (sem sinal nem zero à esquerda), salt alfanumérico ASCII e hash hexadecimal minúsculo. Valores fora desse formato (não ASCII, parâmetros negativos ou não numéricos, texto puro, vazio, `NULL`, quebra de linha final) retornam falha **sem chamar** `check_password_hash`. Isso cobre os casos 1 e 3 sem depender do tipo de exceção de cada ambiente.
2. **Exceções específicas, restritas à verificação.** `check_password_hash` fica envolvido apenas em `except (ValueError, OverflowError)`, para formatos estruturalmente válidos cujos valores o `hashlib` recusa: digest não suportado (`UnsupportedDigestmodError` é subclasse de `ValueError`), `n` do scrypt que não é potência de 2, iterações zero e valores grandes demais para o C (`OverflowError`, caso 2). Não há `except Exception` nem captura de `TypeError`: um `TypeError` inesperado com formato válido continua propagando (há teste para isso).
3. Nos dois casos: aviso no log sem o conteúdo armazenado, autenticação recusada (o login responde 401 `{"erro": "Email ou senha inválidos", "sucesso": false}`), nenhuma escrita no banco, nenhuma comparação com texto puro e nenhuma migração. Erros de banco não passam por esse trecho e continuam virando 500.

### 13.3 Testes de regressão (`code-smells-project/tests/test_regressao.py`, agora 18 testes)

- `SenhasLegadasTest.LEGADOS` ganhou os 3 casos da revisão e os 2 extras que davam 500. `test_legados_e_malformados_retornam_401_sem_modificar_banco` verifica 401 para cada um, com a senha armazenada e com outra senha, e compara a tabela `usuarios` inteira antes e depois.
- Nova classe `FormatoHashTest`:
  - hashes gerados pelo Werkzeug (`scrypt`, `pbkdf2`, `pbkdf2:sha256`, `pbkdf2:sha256:1000`, `pbkdf2:sha512:600000`) passam na validação de formato;
  - com `check_password_hash` substituído por um dublê que lança `TypeError("p is required and must be an unsigned int")` (o comportamento do ambiente da revisão), nenhum valor estruturalmente inválido chega a ele (`assert_not_called`) e todos retornam falha;
  - um `TypeError` inesperado com formato válido **propaga**, o que mostra que a captura não é ampla.
- Mantidos e aprovados: hashes válidos `scrypt`, `pbkdf2:sha256` e `pbkdf2:sha256:1000` e o admin do seed autenticam (senha errada → 401); tabela `usuarios` ausente → 500.

| Execução | Resultado |
|---|---|
| Implementação corrigida (`rodada-3/unittest_pos.txt`) | `Ran 18 tests … OK` |
| Controle: mesmos testes contra a implementação da rodada 2 (`rodada-3/unittest_antes_da_correcao.txt`) | `FAILED (failures=9, errors=14)`, só nos casos novos: 8 subtestes de login (`legado7`, `legado8`, `legado10`, `legado11`; `legado9` passa neste ambiente, pela razão da 13.1), 13 erros + 1 falha no teste do dublê (a validação de formato não existia) e 1 erro por `FORMATO_HASH` inexistente |

### 13.4 Reprodução depois da correção (`rodada-3/reproducao_depois.txt`)

Os 7 formatos → **401**, banco não alterado em nenhum caso, **0 tracebacks** e 7 avisos de formato inválido no log. Admin com hash válido → 200; senha errada → 401.

### 13.5 Suíte e matriz repetidas (ferramentas preservadas em `rodada-2/tools/`)

| Verificação | Resultado |
|---|---|
| `url_map` (`rodada-3/url_map.txt`) | 19 combinações método+rota, idênticas às da rodada 2 |
| Inicialização `python -B app.py` | `Rodando em http://127.0.0.1:5000`, `Debug mode: off`, 0 tracebacks (`rodada-3/logs/refatorado.log`) |
| Matriz (`rodada-3/refatorado.json`, `rodada-3/matriz.md`) vs `baseline.json` | 54 casos, as **19 combinações exercitadas**; 32 idênticos, 22 diferenças classificadas, **0 regressões**; **idêntica** ao `rodada-2/refatorado.json` em todos os 54 casos |
| Testes específicos (`rodada-3/specific.txt`) | **122 OK, 0 falhas** (inclui seed, banco legado criado pelo código original, autorização e erros gerais) |
| Inspeção (`rodada-3/inspecao.txt`) | Nenhum `str(e)`/`except Exception`; `except` restantes: `sqlite3.Error` (health), `ValueError` (filtro de preço), `(ValueError, OverflowError)` (verificação de hash) |

### 13.6 Situação

- A falha apontada foi corrigida: os formatos malformados conhecidos respondem 401 sem alterar dados, e os hashes válidos continuam autenticando.
- Limitação conhecida, fora do escopo: um hash com estrutura válida e parâmetros de custo legítimos mas muito altos (por exemplo, bilhões de iterações pbkdf2 que ainda cabem num C long) seria processado e poderia tornar o login lento. A validação não impõe teto de custo; isso exigiria uma decisão de política. Não houve teste de desempenho.
- Pendências R-1 a R-10: **continuam**. Sem commit nem push.
