# Validação da Fase 3 — code-smells-project — rodada 5

- **Data:** 2026-11-05
- **Ponto de partida:** commit `218ea6c` (HEAD), working tree limpo no início da rodada.
- **Plano e inventário:** `../rodada-4/auditoria.md` (relatório da Fase 2, não editado) e `../rodada-4/validation.md` §7 (inventário de 14 achados graves). As rodadas anteriores não foram alteradas.
- **Skill lida no início:** `code-smells-project/.claude/skills/refactor-arch/SKILL.md` (regra 6: conclusão só com zero CRITICAL/HIGH pendentes e evidência verificável). A Skill não foi alterada.
- **Dados sensíveis:** token, `SECRET_KEY` e senhas são sintéticos, gerados a cada execução, e aparecem como `<removido>`. As senhas legadas rastreáveis aparecem como `<marca-…>`, os hashes como `<hash-removido>` e os caminhos temporários como `<tmp>`/`<scratchpad>`. Todos os bancos usados são temporários e foram gerados nesta rodada.
- **Revisão independente (mesmo dia, antes do commit):** confirmou F-07, F-09, F-11, F-22 e a preservação do F-13 e **reabriu o F-04** (falso sucesso em WAL, simulação que cria/altera arquivos auxiliares e exceção com texto legado arbitrário). A correção foi restrita ao F-04, aos seus testes, à documentação e às evidências (§7.1); as evidências da revisão estão em `revisao-f04/`. Os arquivos da bateria anterior desta pasta foram mantidos como registro do código anterior à revisão.
- **Revisão independente 2 (antes do commit):** confirmou as correções anteriores e encontrou uma **regressão na preservação de hashes válidos** introduzida pela revisão 1 (§7.2). A correção foi restrita a `hash_preservavel`, aos testes, à documentação e às evidências, que estão em `revisao-f04-2/`. As evidências anteriores foram mantidas.
- **Sem commit nem push.**

## 1. Escopo e decisões aplicadas

A autorização desta rodada substitui a restrição da rodada 4, que limitava a implementação ao F-13.

| Decisão | Achado | Aplicação |
|---|---|---|
| D-4R (d) + (ii) | F-04 | `migrar_senhas.py`: simulação por padrão; `--aplicar` exige o banco por argumento e só grava num arquivo que já existe. Invalida todas as credenciais legadas (`senha = NULL`) e preserva hashes válidos, IDs, perfis e as demais tabelas. O boot recusa, antes de qualquer escrita ou seed, um banco com credencial legada ou com limpeza física pendente |
| D-9 (b) | F-07 | Campo `ambiente` removido de `GET /health`; demais campos e caminho de erro preservados |
| F-09 | F-09 | Teste concorrente executado primeiro contra 218ea6c. Passou, e nenhuma mudança de código foi necessária (§5) |
| D-10 (a) | F-11 | `X-Admin-Token` exigido em `GET /pedidos` e `GET /pedidos/usuario/<id>` |
| D-11 (a) | F-22 | `X-Admin-Token` exigido em `POST /produtos`, `PUT`/`DELETE /produtos/<id>` e `PUT /pedidos/<id>/status`, com o mesmo `require_admin_token` de `/admin/*` |
| D-7 (b), D-8 (b), D-12 (a) | F-13 | Mantidas da rodada 4, sem alteração, e revalidadas |

## 2. Alterações no working tree

| Arquivo | Mudança |
|---|---|
| `models/usuario.py` | `hash_preservavel` (versão final, após a revisão 2: mesmo formato aceito no login, com salt de qualquer tamanho; parâmetros numéricos só são convertidos com até 19 dígitos e precisam caber num long de 64 bits, que é o limite do `hashlib`; scrypt com `n` potência de 2 e hash de 128 hex; pbkdf2 com o tamanho do digest obtido de `hashlib.new(nome).digest_size`, que não processa dados; não executa KDF nem verifica senha e não lança exceção para texto arbitrário), `ids_com_credencial_legada`, `resumo_credenciais`, `invalidar_credenciais` e a marca de limpeza pendente (`PRAGMA user_version`). O login (`_senha_confere`) não mudou |
| `database.py` | `MigracaoPendenteError` e `verificar_credenciais_legadas`, chamada em `prepare()` **antes** de `init_schema` e do seed, somente leitura |
| `app.py` | Entrada `python app.py`: `MigracaoPendenteError` → log "Inicialização recusada" e código 1 |
| `migrar_senhas.py` (novo) | CLI. Simulação: lê os bytes de `.db`/`-wal` sem abrir o SQLite, aplica em memória os quadros confirmados do WAL (salts e checksums conferidos) e analisa a imagem com `deserialize`; recusa controlada se o banco mudar durante a leitura ou houver journal ativo. Etapa 1: transação única (`BEGIN IMMEDIATE`, `secure_delete = ON`, `UPDATE … SET senha = NULL`, marca de limpeza, verificação, `COMMIT`; qualquer falha → `ROLLBACK`). Etapa 2: `VACUUM` e, em WAL, checkpoints `TRUNCATE` com resultado conferido (`busy = 0` e `-wal` com 0 bytes), sem páginas livres nem journal; a marca só sai depois dessa comprovação (e volta se o checkpoint final falhar). É idempotente; nunca imprime o conteúdo da coluna `senha` |
| `config.py`, `controllers/sistema_controller.py` | Remoção de `AMBIENTE` e do campo `ambiente` |
| `routes/pedidos.py`, `routes/produtos.py` | `@require_admin_token` nas 6 rotas de D-10/D-11 |
| `tests/test_regressao.py`, `tests/test_inicializacao.py` | Token válido apenas nas chamadas a rotas agora protegidas; nenhuma asserção mudou |
| `tests/test_seguranca.py` (novo) | 26 testes (17 + 6 da revisão 1 + 3 da revisão 2 em `PreservacaoHashesValidosTest`, além de novos casos de classificação; revisão 1: texto legado arbitrário sem exceção nem KDF, texto gigante no boot/simulação/aplicação, WAL com leitor aberto e retomada, simulação de WAL fechado, simulação com dados confirmados no WAL, recusa com journal ativo): negações de D-10/D-11, `/health` (D-9), classificação, boot recusado, migração, rollback, falha na limpeza e retomada |
| `README.md`, `.env.example` | Rotas protegidas e procedimento do operador para bancos legados |

## 3. Ambiente

Venv temporário (`versoes.txt`): Python 3.14.0, SQLite 3.37.2, Flask 3.1.1, flask-cors 5.0.1, Werkzeug 3.1.9. Foram usadas três cópias isoladas, extraídas com `git archive`/`tar`:
- **original** (40d2986), para gerar bancos legados;
- **218ea6c**, a linha de base desta rodada;
- **final**, uma cópia nova do working tree. O `diff -r` contra o working tree não mostrou diferença.

Os segredos foram gerados num `secrets.env` temporário, já removido.

## 4. Validação funcional do código final

A tabela aponta para a evidência mais recente de cada execução. As execuções iniciais e os controles das revisões permanecem preservados nas respectivas pastas. Matriz, S1–S9 e F-09 têm a execução mais recente em `revisao-f04/`; a revisão 2 alterou somente a classificação de hashes e os testes correspondentes.

| # | Execução | Resultado | Arquivo |
|---|---|---|---|
| 1 | `python -B -m unittest tests.test_regressao -v` (os 18 testes originais; só receberam token nas escritas de produto) | **18 OK** | [Revisão 2](revisao-f04-2/unittest_regressao_18.txt) |
| 2 | `python -B -m unittest discover -s tests -v` (18 de regressão + 15 de inicialização + 26 de segurança) | **59 OK** | [Revisão 2](revisao-f04-2/unittest_todos.txt) |
| 3 | Matriz de 54 casos (`tools/matrix4.py`, contrato da rodada 3 com token nas rotas protegidas), sobre 218ea6c e sobre o código da revisão 1 | **51 idênticos; 3 mudaram (casos 2, 49 e 54, `/health`), todos por D-9 (b); 0 diferenças sem justificativa.** Contra o original: 32 idênticos e 22 diferenças classificadas. | [Comparação](matriz.md), [linha de base](revisao-f04/linha_base_218ea6c.json), [refatorado](revisao-f04/refatorado.json) |
| 4 | Testes específicos (`tools/specific5.py`) | **168 OK, 0 falhas** | [Revisão 2](revisao-f04-2/specific.txt) |
| 5 | F-13, S1–S9 por `python -B app.py` (`tools/f13_entrypoint5.py`) | **56 OK, 0 falhas** | [Revisão 1](revisao-f04/f13_entrypoint.txt) |
| 6 | F-09: concorrência e rollback (`tools/f09_concorrencia.py`) | **Aprovado, 0 falhas** | [Revisão 1](revisao-f04/f09_concorrencia.txt) |
| 7 | F-04: bancos gerados pelo código original (`tools/f04_migracao.py`) | **61 OK, 0 falhas** | [Revisão 2](revisao-f04-2/f04_migracao.txt) |
| 8 | Nova inspeção estática (`rodada-2/tools/inspecao.sh`) | Nenhuma ocorrência nova grave (§8) | [Revisão 2](revisao-f04-2/inspecao.txt) |
| 9 | F-04: WAL, simulação e texto gigante (`revisao-f04/tools/f04_wal.py`) | **20 OK, 0 falhas** | [Revisão 2](revisao-f04-2/f04_wal.txt) |
| 10 | F-04: preservação de hashes válidos (`revisao-f04-2/tools/f04_hashes.py`) | **20 OK, 0 falhas** | [Revisão 2](revisao-f04-2/f04_hashes_depois.txt) |

**Reexecução após a revisão do F-04** (cópia nova idêntica ao working tree corrigido; `revisao-f04/`): unittest **56 OK** (18 originais OK em separado); matriz com os mesmos 3 casos alterados (2, 49, 54, D-9 b), idêntica caso a caso à execução anterior desta rodada e com 0 regressões contra o original; `specific5.py` **168 OK**; S1–S9 **56 OK**; F-09 aprovado; `f04_migracao.py` **61 OK**; `f04_wal.py` **20 OK**; inspeção sem achado grave.

**Reexecução após a revisão 2 do F-04** (cópia nova idêntica ao working tree; `revisao-f04-2/`): unittest **59 OK** (18 originais OK em separado); `f04_hashes.py` **20 OK**; `f04_migracao.py` **61 OK**; `f04_wal.py` **20 OK**; `specific5.py` **168 OK**; inspeção sem achado grave. A matriz, S1–S9 e F-09 não foram reexecutados nesta etapa. A única mudança de código foi a classificação de hashes em `models/usuario.py`, exercitada novamente pelos testes de classificação, boot e migração. Para os demais fluxos, foram mantidas as evidências da revisão 1 indicadas na tabela, sem atribuir a elas uma nova execução.

Nenhum 500 inesperado apareceu. Os únicos 500 registrados vêm de falhas induzidas de propósito (triggers dos testes de rollback e `/health` com banco quebrado), e o corpo é o genérico esperado. Os logs dos servidores da matriz não têm traceback.

### 4.1 Resultados da matriz que mudaram pelas decisões aprovadas

| Caso | 218ea6c | Final | Decisão |
|---|---|---|---|
| 2 `GET /health` | 200, com `"ambiente": "producao"` | 200, sem `ambiente`; demais campos idênticos | D-9 (b) |
| 49 `GET /health` após escritas | idem | idem | D-9 (b) |
| 54 `GET /health` após reset | idem | idem | D-9 (b) |

D-10 (a) e D-11 (a) não mudam nenhum resultado da matriz: os casos 10–16, 18–20, 22, 41–47 levam token válido e respondem exatamente como antes. As negações estão em §6. D-4R não afeta a matriz, que usa banco novo.

## 5. F-09: concorrência e rollback

**Contra 218ea6c, antes de qualquer edição** (`f09_antes_218ea6c.txt`): aprovado. Por isso nenhuma correção foi necessária, e o código de pedidos não foi alterado nesta rodada.

Desenho do teste:
- **Servidor e banco:** um banco temporário novo por repetição, servido por `werkzeug.serving.make_server(threaded=True)` com HTTP real. Cada requisição abre a própria conexão ao **mesmo arquivo SQLite**.
- **Clientes:** N clientes disparam ao mesmo tempo (barreira) um pedido válido de 1 unidade sobre estoque K.
- **Sobreposição no servidor:** medida por middleware WSGI, que conta as requisições em andamento ao mesmo tempo.
- **Fábrica lenta:** pelo ponto de injeção `connection_factory`, abre o mesmo arquivo e espera 50 ms depois de ler o estoque, para alargar a janela entre checagem e baixa. Conta quantas leituras viram estoque disponível.

| Cenário | Repetições aprovadas | Simultâneas no servidor | Leituras com estoque disponível |
|---|---|---|---|
| N=20, K=5, conexão padrão | 20/20 | 20 | — |
| N=20, K=5, fábrica lenta | 20/20 | 20 | 20 por repetição (> K) |
| N=2, K=1, conexão padrão | 50/50 | 2 | — |
| N=2, K=1, fábrica lenta | 50/50 | 2 | 2 (> K) |
| N=50, K=10, fábrica lenta | 5/5 | 50 | 48–50 (> K) |

Critério de cada repetição:
- exatamente K respostas 201;
- as N−K demais são 400 `{"erro": "Estoque insuficiente para …", "sucesso": false}`;
- estoque final 0;
- pedidos e itens existem só para os IDs com 201 (total e preço corretos);
- nenhum 500 ou exceção;
- nenhum traceback, "locked" ou "Erro não tratado" no servidor.

Com a fábrica lenta, mais leituras que K viram estoque disponível. Isso mostra que a corrida aconteceu e que a baixa condicional (`estoque >= ?` + `rowcount`) recusou os excedentes.

**O teste detecta o defeito:** um mutante de 218ea6c sem a baixa condicional (`f09_mutante_sem_baixa_condicional.txt`) **reprova**, com 147 falhas e venda acima do estoque.

**Rollback por falha induzida** (trigger em `itens_pedido`):
- **sequencial:** 500 genérico; 0 pedidos e 0 itens; estoque intacto;
- **concorrente** (10 válidos + 10 com falha, natural e lenta): 10×201 e 10×500 induzidos; estoque 20; pedidos e itens só dos 10 válidos.

O resultado se repete no código final (`f09_concorrencia.txt`) e no grupo 5 de `specific.txt`.

## 6. F-07, F-11 e F-22

- **F-07 (D-9 b):**
  - `specific.txt` grupo 9 e `tests/test_seguranca.py::HealthTest`: o corpo de `/health` tem exatamente `status`, `database`, `counts`, `versao` e `debug`.
  - A resposta não contém token, `SECRET_KEY`, senha, hash, caminho do banco, `secret_key`, `db_path` nem `ambiente`.
  - Caminho de erro preservado: tabela removida ou fábrica de conexão que falha → 500 `{"status": "erro", "detalhes": "Banco de dados indisponível"}`, também sem segredos (unittest; `specific.txt` grupo 8).
- **F-11 / F-22 (D-10 a, D-11 a):** as 6 rotas novas foram testadas por HTTP real (`specific.txt` grupo 9) e pelo `test_client` (`AcessoAdministrativoTest`).
  - **`ADMIN_TOKEN` ausente:** 403 "Operação administrativa desabilitada", com ou sem header.
  - **Header ausente, token incorreto, vazio ou com prefixo correto:** 401 "Não autorizado".
  - **Dados:** o dump das 4 tabelas fica idêntico antes e depois de cada recusa.
  - **Token válido:** 200/201 com os efeitos conferidos no banco (status, preço 0, exclusão, criação).
  - **Ordem das verificações:** a autorização acontece antes da validação do corpo.
  - **Rotas do cliente** (`GET /produtos*`, `POST /usuarios`, `/login`, `POST /pedidos`): continuam públicas.

## 7. F-04: bancos legados (D-4R d + ii)

O roteiro `tools/f04_migracao.py` usa só bancos temporários gerados pelo **código original 40d2986**:
- 3 usuários do seed original (senhas públicas);
- a conta A, cuja senha foi trocada por uma mais longa;
- a conta B;
- 60 contas excluídas;
- 2 pedidos.

As alterações foram feitas com `secure_delete = OFF`, simulando um SQLite sem secure delete. O resultado deixa a senha antiga de A como sobra dentro da página e as senhas das contas excluídas em 5 páginas livres. O cenário **misto** acrescenta 2 hashes válidos (scrypt e pbkdf2), 1 conta sem credencial e 1 valor em formato inválido (`abc$def$ghi`).

| Prova | Legado | Misto |
|---|---|---|
| Contagens iniciais | 5 usuários (5 legados), 10 produtos, 2 pedidos, 3 itens | 9 usuários (6 legados, 2 hashes, 1 nulo), 10/2/3 |
| Busca nos bytes antes (prova que a busca é sensível) | todas as marcas encontradas: A antiga 2, B 2, contas excluídas 70, A nova 1, `admin123` 2, `senha123` 2 | idem, com 68 das excluídas e `abc$def$ghi` 1 |
| Boot (`python app.py`, seed padrão e `SEED_ON_STARTUP=0`) | código 1, "Inicialização recusada … 5 credencial(is) legada(s) … migrar_senhas.py"; sha256 e dump idênticos; sem arquivo auxiliar; sem senha no log | idem, com 6 |
| Simulação | `legadas=5`; sha256, mtime e lista de arquivos idênticos | `legadas=6`, `hashes_validos=2`, `sem_credencial=1`; idem |
| Falha antes do commit (trigger na 2ª credencial) | código 1, "Transação desfeita"; sha256 e dump idênticos; boot continua recusado | idem |
| Falha na limpeza (etapa 2) | código 1, mensagem de retomada; credenciais já `NULL`; sobras ainda no arquivo (A: 1, freelist: 70), o que mostra que a etapa 2 é necessária; **boot recusado por limpeza pendente**, sem alterar o banco; a simulação mostra `limpeza_pendente=sim` | idem (freelist: 68) |
| Retomada (`--aplicar` de novo) | código 0; **0 ocorrências** de qualquer senha legada em todos os arquivos; só `loja.db` na pasta | idem |
| Aplicação | código 0; **0 ocorrências** (inclusive sobras e senhas do seed original); sem journal/WAL/SHM; `produtos`, `pedidos`, `itens_pedido` e `sqlite_sequence` idênticos; `usuarios` com os mesmos IDs, nomes, e-mails, perfis e datas; senhas legadas `NULL`; hashes válidos idênticos; `integrity_check = ok`; `user_version = 0` | idem |
| Boot após a migração | aceito; `/health` 200 sem seed adicional; logins com cada credencial legada → 401 (6 casos, inclusive `admin123`, `123456`, `senha123`); `GET /pedidos` com token → 2 pedidos; log sem traceback nem senha; dump inalterado | idem, com 7 casos de 401; contas com hash → **200**, perfis `admin`/`cliente` preservados |
| Segunda execução | simulação `legadas=0`; `--aplicar` → código 0, "0 credencial(is) invalidada(s)", dados idênticos | idem |

O grupo 7 de `specific.txt` repete a prova com um banco legado criado pelo servidor original:
- recusa do boot com o dump intacto;
- migração de 4 credenciais;
- dados preservados;
- logins legados → 401, inclusive a senha `abc$def$ghi` (500 na rodada 1);
- dados legíveis.

Os unittests de `CredenciaisLegadasTest` cobrem também:
- `user_version` inesperado: nada é alterado;
- banco inexistente: código 2, sem criar arquivo;
- bancos novos ou só com hashes: iniciam normalmente.

### 7.1 Revisão independente: WAL, simulação somente leitura e texto legado arbitrário

A revisão reabriu o F-04 com quatro casos. O roteiro `revisao-f04/tools/f04_wal.py` usa só bancos temporários. As conexões concorrentes (leitor e escritor) rodam em **outro processo**: no POSIX, fechar qualquer descritor de um arquivo libera todos os locks `fcntl` do processo sobre ele, e uma primeira versão do roteiro, que lia os bytes no mesmo processo do leitor, desfazia o leitor sem querer (registro operacional; corrigido antes dos controles abaixo).

| Caso | Antes da correção (`f04_wal_antes.txt`) | Depois (`f04_wal_depois.txt`) |
|---|---|---|
| 1. WAL, outro processo com `BEGIN` + `SELECT` em `usuarios`, `--aplicar` | **Falso sucesso reproduzido:** código 0, `user_version` 0, boot aceito, marca sintética presente em `loja.db-wal` (1 ocorrência) | Código 1, "Limpeza física não comprovada (… busy=1 …)" com orientação ao operador, sem traceback; credencial já `NULL`, `user_version` = marca de limpeza pendente; **boot recusado** |
| 1. Retomada com o leitor fechado | — (o boot já tinha sido aceito) | Código 0; **0 ocorrências** da senha no `.db` e nos auxiliares presentes (só `loja.db` restou); hash válido idêntico; `user_version` 0; boot aceito e login com hash → 200 |
| 2. Simulação de banco WAL fechado, sem `-wal`/`-shm` | **Criou** `loja.db-wal` e `loja.db-shm` | Lista de arquivos e sha256 idênticos (só `loja.db`); `legadas=1`, `journal_mode=wal` |
| 3. Simulação com commit só no WAL (escritor aberto em outro processo) | Contagem correta e arquivos inalterados neste ambiente | Arquivos (`.db`, `-wal`, `-shm`) com sha256 idênticos; `usuarios=3`, `legadas=2` (inclui a credencial que está só no WAL) |
| 4. `"scrypt:" + "9"*4400 + ":8:1$s$" + "a"*128` | **`ValueError` não tratado** (limite de 4300 dígitos) no boot, em `python app.py`, na simulação e no `--aplicar` | Boot: `MigracaoPendenteError` controlada; `python app.py` código 1 "Inicialização recusada", sem traceback; banco intacto; simulação `legadas=1`; `--aplicar` código 0, credencial `NULL`, hash válido preservado, trecho do texto ausente do arquivo; boot aceito e login com hash → 200 |

Resultado: **antes 10 falhas** (todas reproduzindo os defeitos apontados); **depois 20 OK, 0 falhas**. Os novos unittests (`WalESimulacaoTest` e dois casos em `CredenciaisLegadasTest`) repetem os quatro casos, incluem a recusa da simulação com journal de rollback ativo e provam que a classificação não chama `hashlib.scrypt`, `hashlib.pbkdf2_hmac` nem `check_password_hash`. O roteiro `f04_migracao.py` (bancos legado e misto gerados pelo código original, tabela acima) foi reexecutado sobre o código corrigido: **61 OK, 0 falhas**.

### 7.2 Revisão independente 2: preservação de hashes válidos

A revisão 2 mostrou que a classificação da revisão 1 invalidava hashes válidos do Werkzeug. Os três casos eram `pbkdf2:sha512_256:600000`, `pbkdf2:sha512_224:600000` e `scrypt` com `salt_length=129`. As causas eram duas: a tabela fixa de digests não tinha `sha512_256`/`sha512_224`, e o salt estava limitado a 128 caracteres.
- `_senha_confere` aceita esses hashes, e a versão anterior da migração os preservava.
- O boot os recusava como legados e a simulação os contava.
- O `--aplicar` os trocava por `NULL` com código 0, e o login das contas caía para 401.

O roteiro `revisao-f04-2/tools/f04_hashes.py` usa bancos temporários e senhas sintéticas. Ele inclui os três casos e, como referência, `scrypt` e `pbkdf2` padrão.

| Prova | Antes (`f04_hashes_antes.txt`) | Depois (`f04_hashes_depois.txt`) |
|---|---|---|
| Classificação direta: os 3 casos | `_senha_confere=True`, `hash_preservavel=False` | Ambos `True` |
| Banco só com hashes válidos: boot | Recusado ("3 credencial(is) legada(s)") | Aceito; login das 5 contas → 200; dados inalterados |
| Banco só com hashes válidos: simulação | `legadas=3`, `hashes_validos=2` | `legadas=0`, `hashes_validos=5`; arquivos (sha256) intactos |
| Banco misto (5 hashes + texto puro + texto de 4400 dígitos + conta sem credencial): boot e simulação | Recusa por 5 credenciais; simulação `legadas=5` | Recusa por **2**; simulação `legadas=2`, `hashes_validos=5`; arquivos intactos |
| Misto: `--aplicar` | Código 0 com 5 invalidadas; os 3 hashes válidos substituídos por `NULL`; login dessas contas → 401 | Código 0 com **2** invalidadas; os 5 hashes **idênticos byte a byte**; IDs, nomes, e-mails, perfis e datas preservados; produtos, pedidos e itens idênticos; texto puro e texto gigante ausentes do arquivo; login das 5 contas → 200 e da conta legada → 401; segunda simulação `legadas=0` |

Resultado: **antes 13 falhas; depois 20 OK, 0 falhas.**

Outras verificações da revisão 2:
- **Login × migração:** 64 hashes gerados pelo Werkzeug com pbkdf2 para cada algoritmo disponível no `hashlib` e salts de 1, 16, 129 e 500 caracteres, além de scrypt com os mesmos salts, receberam a mesma classificação nas duas funções (0 divergências).
- **Texto arbitrário:** continua classificado como legado sem exceção e sem KDF. Os casos testados são o de 4400 dígitos, iterações com 5000 dígitos, `n` com 20 dígitos ou igual a 2^64, digest inexistente, hex com tamanho errado, BLOB e número.
- **Unittests:** `PreservacaoHashesValidosTest` repete os casos da tabela, incluindo o login com perfil preservado.

## 8. Nova inspeção

`inspecao.txt` sobre o código final:
- **SQL:** sem concatenação de entrada. As f-strings interpolam só constantes; a nova, `PRAGMA user_version`, usa o inteiro `LIMPEZA_PENDENTE`. Na API, SQL em `models/` e `database.py`; a CLI de manutenção `migrar_senhas.py` também executa consultas de diagnóstico e comandos transacionais e de limpeza.
- **Segredos e debug:** nenhum `SECRET_KEY` nem senha literal; nenhum debug fixo nem `0.0.0.0`; nenhum estado global de conexão; nenhum `str(e)`.
- **`except` novos:** são restritos (`sqlite3.Error`, `RuntimeError`, `ConfigError`/`MigracaoPendenteError`). O `except BaseException` de `migrar_senhas.invalidar` só desfaz a transação e relança a exceção.
- **`print`:** os novos estão em `migrar_senhas.py` e são a saída da CLI para o operador; não registram dados sensíveis.

Leitura do diff completo:
- o cadastro público continua sem aceitar `tipo` (sem escalada de perfil);
- as mensagens de recusa não incluem conteúdo de senha;
- o boot só lê o banco antes de recusar.

**Nenhum achado CRITICAL/HIGH novo.**

## 9. Reconciliação por ID: 14 achados graves

| ID | Sev. | Situação no código final | Prova nesta rodada |
|---|---|---|---|
| F-01 SQL injection | CRIT | **Corrigido** | Matriz: casos 8 (busca com aspas), 13 (produto com aspas → 201 literal), 33 (login com injeção → 401) e 40 (`produto_id` com injeção → 400) idênticos à linha de base; `inspecao.txt` |
| F-02 `/admin/query` | CRIT | **Corrigido** | `specific.txt` grupos 1–2: `sql` → 400 sem execução; catálogo igual à consulta direta; 403/401 |
| F-03 senha na resposta | CRIT | **Corrigido** | Matriz casos 23–24 sem `senha`; `specific.txt` grupo 1 sem senha nem hash |
| F-04 senha em texto puro | CRIT | **Corrigido** (reaberto nas revisões independentes 1 e 2 e corrigido de novo; §7.1 e §7.2) | §7: boot recusado; migração com 0 ocorrências nos bytes, preservação, rollback, retomada e reexecução; §7.1: WAL com leitor aberto (falha controlada, boot recusado, retomada limpa), simulação sem criar nem alterar arquivos e com dados confirmados no WAL, texto legado arbitrário com recusa controlada; §7.2: hashes válidos do Werkzeug preservados e autenticando; `revisao-f04-2/f04_hashes_depois.txt`, `revisao-f04-2/f04_wal.txt`, `revisao-f04-2/f04_migracao.txt`, `revisao-f04-2/specific.txt` grupo 7, `CredenciaisLegadasTest`, `WalESimulacaoTest`, `PreservacaoHashesValidosTest` |
| F-05 `/admin/reset-db` | CRIT | **Corrigido** | `specific.txt` grupo 3 (401/200, rollback por trigger); S2/S6 |
| F-06 SECRET_KEY no código | CRIT | **Corrigido** | `inspecao.txt` sem literal; grupo 4 (chave efêmera); chaves distintas por instância (`DuasInstanciasTest`) |
| F-07 `/health` expõe config | CRIT | **Corrigido** | §6 e §4.1: `ambiente` removido; sem segredos; caminho de erro preservado |
| F-08 debug/0.0.0.0 | HIGH | **Corrigido** | `logs/refatorado_matriz.log`: `Rodando em http://127.0.0.1:5000`, `Debug mode: off`. `PORT` respeitado nos boots de `f04_migracao.py` (porta livre por execução). As linhas de `HOST`/`FLASK_DEBUG` em `config.py` não mudaram desde a prova de `../rodada-4/f13_host_porta_debug.txt` |
| F-09 pedido sem rollback / concorrência | HIGH | **Corrigido e provado** | §5: concorrência por HTTP real com sobreposição medida, K sucessos exatos, recusas controladas, estoque 0, sem 500; mutante reprovado; rollback sequencial e concorrente |
| F-10 conexão global | HIGH | **Corrigido** | Conexão por contexto via fábrica da instância; `DuasInstanciasTest` (16 requisições simultâneas, sem cruzamento) |
| F-11 dados de negócio sem acesso | HIGH | **Corrigido** | §6: `GET /pedidos*` 403/401/200; matriz 41–43 com token, idênticos |
| F-12 camadas nominais | HIGH | **Corrigido** | `inspecao.txt`; `test_controllers_nao_dependem_de_flask_nem_de_get_db`; caso de uso sem contexto Flask |
| F-13 acoplamento/init | HIGH | **Corrigido (revalidado)** | S1–S9 (`f13_entrypoint.txt`, 56 OK, inclusive seed desligado após reset e reinício); `SubstituicaoConexaoTest` (fábrica injetada no fluxo HTTP real, `DATABASE_PATH` não criado); `DuasInstanciasTest` |
| F-22 escritas sem controle | HIGH (novo na rodada 4) | **Corrigido** | §6: POST/PUT/DELETE `/produtos` e PUT `/pedidos/<id>/status` 403/401/200, dados idênticos nas recusas |

A lista confere: os 13 IDs graves da auditoria original mais o F-22 = 14. A nova inspeção não encontrou achado grave novo.

**MEDIUM/LOW independentes** (não tratados, conforme a instrução, e sem bloquear a conclusão):
- **F-14 (MEDIUM):** e-mail sem validação de formato nem unicidade. Depois da migração, a forma documentada de recriar o acesso de uma conta legada é um novo cadastro com o mesmo e-mail; o login percorre os cadastros na ordem e o perfil do novo cadastro é `cliente`.
- **F-16 (MEDIUM):** uma consulta por item na criação do pedido.

Observações que não são achados:
- CORS aberto sem credenciais (R-3);
- servidor de desenvolvimento (R-6);
- cancelamento não devolve estoque (R-2);
- token único sem limitação de tentativas (R-5);
- `/health` público com contagens (contrato preservado).

## 10. Situação geral da Fase 3

| Severidade | Inventário | Corrigidos com evidência | Pendentes |
|---|---:|---:|---:|
| CRITICAL | 7 | 7 | **0** |
| HIGH | 7 | 7 | **0** |
| Total grave | 14 | 14 | **0** |

Histórico: na primeira apresentação desta rodada a contagem era a mesma, mas a revisão independente reprovou a prova do F-04, que passou a **1 CRITICAL pendente** (F-04). Depois da correção e da reexecução da bateria (§4, §7.1), a contagem voltou a 0. A revisão 2 reabriu o F-04 de novo (**1 CRITICAL pendente**: hashes válidos invalidados pela migração). Depois da correção da classificação e da reexecução (§4, §7.2), a contagem observada é **0 pendentes**.

O inventário está completo, a validação funcional foi aprovada (0 regressões; as 3 diferenças da matriz são justificadas por D-9 b) e restam **0** CRITICAL/HIGH pendentes. **Fase 3 concluída**, com as alterações sem commit, para revisão independente.

## 11. Limitações e registros operacionais

- **Fora do arquivo SQLite:** o script não alcança cópias e backups antigos do banco, nem blocos que o sistema de arquivos ou o disco mantenham depois de apagar um journal. O README orienta o operador a destruir ou migrar essas cópias. Dentro dos arquivos do banco, a prova é de 0 ocorrências.
- **Contas legadas:** passam a não ter credencial (decisão D-4R d), inclusive o admin legado. Recriar o acesso é um passo do operador, documentado no README.
- **Banco em WAL:** exercitado na revisão (§7.1). A simulação reproduz em Python a recuperação do WAL (salts, checksums e último commit) e recusa o caso de journal de rollback ativo em vez de reconstruí-lo. Se outra conexão mantiver o banco aberto, `--aplicar` termina com código 1 e a inicialização continua recusada até uma execução sem bloqueio.
- **HOST alternativo e `FLASK_DEBUG=1`:** não foram reexecutados nesta rodada. As linhas correspondentes de `config.py` e `app.py` não mudaram desde a prova da rodada 4. Um HOST diferente de 127.0.0.1 nunca foi exercitado, para não expor o servidor na rede.
- **Temporários da rodada 4:** `/tmp/f13_9kvnmck1` e `/tmp/f13_qs8a6cmg` (dados sintéticos) continuam lá, para remoção manual, como registrado em `../rodada-4/validation.md` §9. Esta rodada usou só diretórios temporários próprios, removidos ao final.
- **Ferramentas:** `tools/matrix4.py` e `tools/run_matrix.sh` são cópias sem alteração das ferramentas da rodada 4. `matrix.py`, `compare.py` e `inspecao.sh` foram usados a partir de `../rodada-2/tools/`, sem cópia.

## 12. Arquivos desta pasta

- `validation.md`: este documento.
- `unittest_regressao_18.txt`, `unittest_todos.txt`: saídas do unittest.
- `linha_base_218ea6c.json`, `refatorado.json`, `matriz.md`: matriz de 54 casos e comparações.
- `specific.txt`: testes específicos (168 OK).
- `f13_entrypoint.txt`: S1–S9 pelo ponto de entrada.
- `f09_antes_218ea6c.txt`, `f09_mutante_sem_baixa_condicional.txt`, `f09_concorrencia.txt`: F-09.
- `f04_migracao.txt`: F-04.
- `inspecao.txt`: nova inspeção. `versoes.txt`: versões instaladas.
- `logs/`: logs dos servidores da matriz e trechos do S1–S9, sem segredos.
- `tools/`: `f09_concorrencia.py`, `f04_migracao.py`, `specific5.py`, `f13_entrypoint5.py`, `matrix4.py`, `run_matrix.sh`.
- `revisao-f04/`: controles da revisão do F-04 (`f04_wal_antes.txt`, `f04_wal_depois.txt`, `tools/f04_wal.py`) e a bateria reexecutada sobre o código corrigido (unittest, matriz, `specific.txt`, S1–S9, F-09, `f04_migracao.txt`, inspeção, versões e logs). Os arquivos da raiz desta pasta são da bateria anterior à revisão.
- `revisao-f04-2/`: controles da revisão 2 (`f04_hashes_antes.txt`, `f04_hashes_depois.txt`, `tools/f04_hashes.py`) e a reexecução sobre o código corrigido (unittest, `f04_migracao.txt`, `f04_wal.txt`, `specific.txt`, inspeção e versões).
