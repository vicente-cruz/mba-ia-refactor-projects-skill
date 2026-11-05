```
================================
RELATÓRIO DE AUDITORIA ARQUITETURAL — REEXECUÇÃO (RODADA 4)
================================
```

> Relatório gerado na Fase 2 em 2026-11-05 e aprovado pelo usuário em 2026-11-05. Linhas referem-se ao commit `c6a53b74482dea6aa8ce8d2daacad828dd64e70e`; o código pode ter sido alterado pela Fase 3.

## 1. Identificação

| Campo | Valor |
|---|---|
| Projeto | code-smells-project (`code-smells-project/`) |
| Data | 2026-11-05 |
| Versão de referência | commit `c6a53b74482dea6aa8ce8d2daacad828dd64e70e`, working tree limpo para o alvo |
| Referências históricas | `reports/audit-project-1.md` (commit `40d2986`), `reports/evidence/code-smells-project/validation.md` (rodadas 1–3) |
| Stack | Python + Flask (declarada: 3.1.1; instalada: não verificado) |
| Banco | SQLite, `DATABASE_PATH` (padrão `loja.db`) |
| Domínio | E-commerce |
| Ferramenta | refactor-arch (Claude Code) |

## 2. Escopo

- Arquivos de código: 24 | Linhas: 1317. Arquivos: `app.py` (38), `auth.py` (20), `config.py` (34), `database.py` (119), `errors.py` (39), `controllers/*` (227), `models/*` (425), `routes/*` (144) e `tests/test_regressao.py` (271). Todos foram lidos inteiros.
- Exclusões: `.claude/`, `README.md`, `.env.example` e `requirements.txt`. Esses arquivos foram lidos só como evidência.
- Natureza da análise: leitura estática. Não executei nada, não importei código nem abri bancos. As evidências das rodadas 1–3 foram lidas, não reexecutadas.

## 3. Resumo por severidade (achados com impacto remanescente no código atual)

| CRITICAL | HIGH | MEDIUM | LOW | Total |
|---:|---:|---:|---:|---:|
| 2 | 3 | 2 | 0 | 7 |

Todos os 7 foram confirmados por leitura. Um deles é novo (F-22). Os demais CRITICAL/HIGH da auditoria original estão na reconciliação da seção 4.1.

## 4. Achados

### 4.1 Reconciliação por ID: 7 CRITICAL + 6 HIGH da auditoria original

| ID | Sev. | Situação no código atual (confirmada por leitura) | Evidência existente | Impacto remanescente | O que a Fase 3 precisa demonstrar |
|---|---|---|---|---|---|
| F-01 SQL Injection | CRIT | Corrigido. Todo SQL usa `?`. As únicas f-strings interpolam constantes (`models/produto.py:15,72,76,104`, `models/usuario.py:10,32,36`, `models/admin.py:3-4,11,19`) | matriz casos 8, 13, 33, 40; `inspecao.txt` (r1–r3) | Nenhum | Repetir no código final: login `admin@loja.com' --` → 401; produto com aspas → 201 gravado literal; `produto_id: "1 OR 1=1"` → 400; inspeção estática sem concatenação de entrada |
| F-02 `/admin/query` | CRIT | Corrigido (D-1 c). Catálogo fechado (`models/admin.py:49-64`) e `sql` → 400 (`controllers/sistema_controller.py:60-61`) | `specific.txt` grupos 1–2; `rodada-2/` tipos de `consulta` | Nenhum | `{"sql": "DELETE…"}` com token → 400 e contagens iguais; 4 consultas = consulta direta; 403/401 sem configuração ou sem token |
| F-03 senha na resposta | CRIT | Corrigido. `COLUNAS_PUBLICAS` sem `senha` (`models/usuario.py:10,21-37`) | matriz 23–24; grupo 1 | Nenhum | Corpos de `/usuarios` e `/usuarios/<id>` sem `senha` nem prefixo de hash |
| F-04 senha em texto puro | CRIT | **Aberto (parcial).** O código grava e verifica hash (`models/usuario.py:40-76`) e o seed não tem senha no código (`database.py:91-104`). Porém **bancos legados continuam com as senhas em texto puro**, inclusive o admin com a senha pública do seed original, porque D-4 (a) mandou não alterar dados (R-7) | grupo 7 (dump idêntico, login legado → 401); rodadas 2–3 (hash malformado → 401) | "Quem lê o banco recupera todas as senhas" continua valendo para todo `loja.db` criado pela versão original. A Regra 6 da Skill diz que registrar a limitação não sana o impacto | Depende de **D-4R**. Num banco gerado pelo código original (40d2986): nenhum texto puro na coluna **nem nos bytes do arquivo** (busca binária antes e depois, considerando páginas livres e journal); demais colunas e tabelas idênticas; comportamento de login conforme a opção escolhida |
| F-05 `/admin/reset-db` | CRIT | Corrigido (D-2 b) com transação (`models/admin.py:8-11`) | grupo 3 (403/401/200, rollback por trigger) | Nenhum | Repetir 403/401/200 e o rollback forçado. Reset + reinício nos dois modos de seed (ver F-13) |
| F-06 SECRET_KEY no código | CRIT | Corrigido. Sem fallback literal; ausente → chave efêmera (`config.py:17-22`) | inspeção (literal ausente); grupo 4 (chave efêmera) | Nenhum | `grep` do literal antigo = 0; boot sem `SECRET_KEY` → aviso e chave diferente a cada instância |
| F-07 `/health` expõe config | CRIT | **Aberto (parcial).** `secret_key` e `db_path` foram removidos e `debug` é real (`controllers/sistema_controller.py:38-49`). Mas `"ambiente"` continua fixo em `"producao"` (`config.py:8`), mantido como contrato preservado (R-4) | matriz casos 2, 49, 54 | O impacto original diz que o endpoint "informa um estado de debug **e ambiente** que pode nem ser o verdadeiro". A parte do ambiente permanece | Depende de **D-9**. `/health` sem `secret_key`/`db_path`; `ambiente` igual ao configurado (ou ausente, conforme a opção) |
| F-08 debug/0.0.0.0 | HIGH | Corrigido (D-5 a) (`config.py:29-31`, `app.py:38`). CORS aberto é observação, não achado (R-3) | log `Debug mode: off`; `Rodando em http://127.0.0.1:5000` | Nenhum | Boot por `python app.py`: padrão 127.0.0.1/off; `FLASK_DEBUG=1`, `HOST` e `PORT` respeitados |
| F-09 pedido sem rollback | HIGH | Corrigido no código: `with db:` (`models/pedido.py:41-72`) e baixa condicional `estoque >= ?` (`:67-72`) | `rollback_baseline.txt` (original confirma a falha); grupo 5 (refatorado: 0 pedidos e 0 itens) | **Falta prova**: o trecho "checagem e baixa não atômicas entre requisições concorrentes" foi registrado como hipótese e nunca foi exercitado (R-8) | Rollback forçado repetido. **Teste concorrente**: N requisições simultâneas por HTTP real sobre estoque K → exatamente K sucessos, estoque final 0, nunca negativo, itens = pedidos. Qualquer 500 ou `database is locked` é registrado |
| F-10 conexão global | HIGH | Corrigido: `g` + `teardown_appcontext` (`database.py:79-88,118-119`) e caminho por config | testes com `create_app` por caso; inspeção sem `global`/`check_same_thread` | Nenhum no código. A troca de banco no mesmo processo ainda não foi provada com **instâncias simultâneas** | Coberto pela prova de duas instâncias do F-13 (R-10) |
| F-11 relatório/dados sem acesso | HIGH | **Aberto (parcial).** `/relatorios/vendas` e `/usuarios*` exigem token (`routes/relatorios.py:10`, `routes/usuarios.py:10,16`). Mas `GET /pedidos` e `GET /pedidos/usuario/<id>` são públicos (`routes/pedidos.py:14-21`) e devolvem `total`, itens e `preco_unitario` de **todos** os pedidos | grupo 1 | O "vazamento de dados de negócio" continua: o faturamento protegido pode ser recalculado somando `total` em `GET /pedidos`. A auditoria original não avaliou essa rota | Depende de **D-10**. Sem token → 401/403 nas rotas escolhidas; com token → corpo idêntico à linha de base |
| F-12 camadas nominais | HIGH | Corrigido: sem `request`/`jsonify` em controllers ou models; SQL só em `models/` e `database.py` | inspeção r1–r3 | Os controllers ainda dependem do contexto Flask (`get_db`, `current_app` em `sistema_controller.py:4,48`). Isso é tratado em F-13/R-10 | Inspeção estática repetida; com D-8 (b), casos de uso executados sem contexto Flask |
| F-13 acoplamento/init | HIGH | **Aberto (parcial):** ver detalhamento abaixo | `ImportacaoTest`; `rodada-2/importacao.txt` | R-9, R-10, duas instâncias sem prova e seed de usuários não idempotente | Seção 5.6.2 |

**Contagem:** 8 dos 13 graves estão corrigidos no código e têm evidência anterior: F-01, F-02, F-03, F-05, F-06, F-08, F-10 e F-12. Esses 8 só precisam ser revalidados no código final. O F-09 está corrigido no código, mas falta a prova de concorrência. F-04, F-07, F-11 e F-13 estão parciais. O novo grave confirmado é o F-22.

### 4.2 Achados com impacto remanescente

#### F-04: [CRITICAL] Senhas em texto puro permanecem em bancos legados (AP-04, reaberto)
- **Localização:** `models/usuario.py:55-65` (recusa formato legado sem alterar dados); `README.md:17`; decisão D-4 (a) em `validation.md` §1.
- **Status:** Confirmado por leitura. Não há bancos legados no alvo. Bancos fora do repositório não foram procurados.
- **Evidência:** a aplicação recusa o login legado (401), mas não altera a coluna `senha`. Um `loja.db` da versão original continua com `admin1…`/`1234…`/`senha1…` em claro, porque a decisão anterior era não recriar nem alterar dados.
- **Impacto:** quem tem o arquivo, uma cópia de backup ou acesso à máquina lê as senhas em claro. O admin legado tem senha publicada no histórico do git. Além disso, `UPDATE` no SQLite não apaga o valor antigo das páginas livres nem do journal, então uma migração ingênua deixaria o texto puro recuperável no arquivo.
- **Justificativa:** mantém a severidade do ID original. A Regra 6 não permite fechar o achado por limitação aceita.
- **Recomendação:** migração conforme D-4R (T-04), com `PRAGMA secure_delete=ON`, `VACUUM` e transação única.

#### F-07: [CRITICAL] `/health` informa ambiente fixo (AP-03, resíduo)
- **Localização:** `config.py:8`; `controllers/sistema_controller.py:47`.
- **Evidência:** `"ambiente": AMBIENTE` com `AMBIENTE = "producao"` constante.
- **Impacto:** é a parte remanescente do impacto original, um estado de ambiente possivelmente falso. Não é dado sensível: o risco é baixo, mas o achado não está integralmente corrigido.
- **Recomendação:** D-9 (T-02/T-03).

#### F-11: [HIGH] Dados de negócio acessíveis por `GET /pedidos` (AP-06, resíduo)
- **Localização:** `routes/pedidos.py:14-21`; `models/pedido.py:77-117`.
- **Evidência:** a listagem pública traz `usuario_id`, `status`, `total`, `itens[].preco_unitario` e `quantidade` de todos os pedidos.
- **Impacto:** a proteção do relatório pode ser contornada, já que faturamento, ticket médio e pedidos por status são deriváveis dessa listagem. A rota também expõe o histórico de compras por `usuario_id`.
- **Recomendação:** D-10 (T-15).

#### F-13: [HIGH] Seed obrigatório e dependência fixa de `get_db()` (AP-10, parcial)
- **Localização:** `database.py:107-115` (schema e seed na mesma função); `app.py:22-23`; `controllers/*_controller.py` (`from database import get_db` em todos); `controllers/sistema_controller.py:4,48` (`current_app`).
- **Evidência e impactos:**
  1. **R-9:** `init_db` sempre executa o seed quando `produtos` está vazia. Não existe configuração para desligá-lo. Após um reset seguido de reinício, os dados de demonstração voltam.
  2. **Seed de usuários não idempotente** (achado novo dentro de F-13, deduzido do código e não executado): a condição olha só `produtos` (`:113`), mas `_seed` também insere os 3 usuários (`:96-104`). Se todos os produtos forem apagados via `DELETE /produtos/<id>` e o app reiniciar, os usuários de demonstração são duplicados (não existe `UNIQUE` em `email`). O comportamento vem do código original.
  3. **R-10:** os controllers chamam `database.get_db()`, que abre `sqlite3.connect(DATABASE_PATH)` direto. Não há ponto de substituição na composição, e uma conexão de teste só entra pela troca de caminho.
  4. **Duas instâncias no mesmo processo:** parecem viáveis por leitura (`get_db` usa `current_app.config`), mas nunca foram provadas.
- **Recomendação:** T-14/T-07. Os detalhes estão em 5.6.2.

#### F-22: [HIGH, novo] Operações de escrita de catálogo e de pedidos sem controle de acesso (AP-06)
- **Localização:** `routes/produtos.py:29-44` (POST/PUT/DELETE `/produtos`); `routes/pedidos.py:24-27` (PUT `/pedidos/<id>/status`).
- **Status:** Confirmado por leitura.
- **Evidência:** qualquer cliente anônimo pode apagar produtos, alterar preços (por exemplo `preco: 0`) e aprovar ou cancelar pedidos de terceiros. Não há middleware global de autenticação.
- **Justificativa:** o AP-06 limita o achado a operações destrutivas ou sensíveis, e estas são: `DELETE` remove registros e a mudança de status é uma transição financeira. Fica em HIGH porque o efeito é por registro e não destrói o banco inteiro. **Conflito:** a auditoria original (F-11) não marcou "os demais CRUDs" ao aplicar a regra de falso positivo. Esta reexecução entende que DELETE, alteração de preço e mudança de status não se enquadram nessa exceção.
- **Recomendação:** D-11 (T-15). `POST /pedidos`, `POST /usuarios` e `/login` continuam públicos, porque são o fluxo do cliente.

#### F-14: [MEDIUM] E-mail sem validação de formato e sem unicidade (AP-13, resíduo R-1)
- `controllers/usuario_controller.py:25-35`; `database.py:23-30`. Cadastros duplicados continuam possíveis. Isso não bloqueia a conclusão, mas fica registrado.

#### F-16: [MEDIUM] Criação de pedido com N consultas de produto (AP-12, resíduo)
- `models/pedido.py:44-53`: uma consulta por item. As listagens já usam JOIN. O resíduo é menor e não bloqueia.

Observações que não são achados: CORS aberto sem credenciais (R-3); servidor de desenvolvimento (R-6); estoque não devolvido no cancelamento, que é regra ausente (R-2); token único sem limitação de tentativas (R-5).

## 5. Plano de refatoração proposto

### 5.1 Estrutura-alvo
A estrutura atual se mantém. As mudanças pontuais são:
- `config.py`: `SEED_ON_STARTUP` e, conforme D-9, `AMBIENTE`.
- `database.py`: `init_schema`, `seed_demo_if_empty` e uma fábrica de conexão injetável.
- `app.py`: `create_app(overrides=None, *, connection_factory=None)`.
- `controllers/*`: só mudam se D-8 = (b).
- `routes/produtos.py` e `routes/pedidos.py`: conforme D-10 e D-11.
- `migrar_senhas.py`: conforme D-4R.
- `tests/test_inicializacao.py`: arquivo novo. `tests/test_regressao.py` não é alterado.
- `README.md` e `.env.example`: documentação das variáveis.

Nenhuma camada nova será criada.

### 5.2 Transformações, em ordem

| Ordem | Transformação | Achados | Arquivos |
|---:|---|---|---|
| 1 | T-14: separar `init_schema()` de `seed_demo_if_empty()`; criar `SEED_ON_STARTUP` (padrão ligado, `0` desliga) | F-13 (R-9 e duplicação) | config.py, database.py, app.py |
| 2 | T-07/T-14: fábrica de conexão injetável e, conforme D-8, controllers recebendo `db` | F-13 (R-10), F-10, F-12 | database.py, app.py, controllers/* e routes/* (se D-8 b) |
| 3 | T-04: senhas legadas conforme D-4R | F-04 | migrar_senhas.py ou database.py, models/usuario.py |
| 4 | T-02/T-03: `ambiente` conforme D-9 | F-07 | config.py, sistema_controller.py |
| 5 | T-15: proteção conforme D-10 e D-11 | F-11, F-22 | routes/pedidos.py, routes/produtos.py |
| 6 | Testes de regressão novos e documentação | todos | tests/test_inicializacao.py, README.md, .env.example |

**Desenho do R-9.** `SEED_ON_STARTUP` aceita só `"1"` e `"0"`. Sem a variável, o seed fica ligado, o que preserva o comportamento atual. Um valor inválido segue D-12. Em overrides de `create_app`, o valor precisa ser `bool`, o que evita que a string `"0"` ligue o seed por ser verdadeira. `init_schema` executa só `CREATE TABLE IF NOT EXISTS`. `seed_demo_if_empty` roda numa transação única, insere produtos só se `produtos` estiver vazia e trata usuários conforme D-7. Com o seed desligado, `SEED_SENHA_*` é ignorado e nada é inserido.

**Menor ajuste para o R-10 (D-8 a).** `database.init_app(app, connection_factory=None)` registra em `app.extensions["loja.db_factory"]` a fábrica recebida ou o padrão `lambda: connect(app.config["DATABASE_PATH"])`, lido na hora da chamada. `get_db()` passa a chamar essa fábrica, mantendo o cache em `g` e o fechamento no teardown. `create_app(..., connection_factory=...)` repassa a fábrica. A mudança fica em cerca de 10 linhas de `database.py` e `app.py`, e o fluxo real (HTTP → controller → `get_db()` → fábrica injetada, inclusive o `init_schema` do boot) passa a aceitar substituição. **Limite desse ajuste:** os controllers continuam precisando de app context. A opção D-8 (b) remove também essa dependência: controllers recebem `db` (e `debug`) por parâmetro, as rotas obtêm `get_db()` e o repassam, e `sistema_controller` deixa de importar `flask`.

### 5.3 Contratos preservados
- As 19 rotas, os métodos, os envelopes e as mensagens.
- `python app.py`, porta 5000 e `loja.db`.
- **Com o seed no padrão, o comportamento de boot é idêntico ao atual**: produtos quando a tabela está vazia, usuários conforme `SEED_SENHA_*`, e reset seguido de reinício volta a popular o banco.
- A matriz de 54 casos tem de ficar idêntica à de `rodada-3/refatorado.json`, exceto pelas mudanças aprovadas em 5.4.

### 5.4 Mudanças de contrato intencionais (dependem das decisões)
1. `SEED_ON_STARTUP=0`: o banco fica com tabelas e sem dados de demonstração. É um modo novo; o padrão não muda.
2. D-7: o seed passa a não duplicar usuários de demonstração já existentes.
3. D-4R: altera dados de bancos legados (coluna `senha`) e/ou o comportamento de boot com dados legados.
4. D-9: valor ou presença de `ambiente` em `/health`.
5. D-10 e D-11: `X-Admin-Token` passa a ser exigido nas rotas escolhidas (403 sem configuração, 401 sem token ou com token errado).

### 5.5 Decisões pendentes do usuário

| ID | Decisão | Opções | Depende |
|---|---|---|---|
| D-4R | Senhas legadas (F-04). **Substitui D-4 (a)**, que deixa o F-04 aberto pela Regra 6 | (a) manter D-4 (a): F-04 continua aberto e **bloqueia a conclusão**; (b) script explícito `migrar_senhas.py` (dry-run por padrão, `--aplicar`) que converte cada senha legada em hash: os logins legados voltam a funcionar, mas o admin legado continua com a senha pública do seed original; (c) como (b), mas **invalida** as senhas dos 3 e-mails de demonstração e converte as demais em hash; (d) script explícito que **invalida todas** as senhas legadas: nenhum texto puro e nenhuma senha conhecida, e as contas legadas continuam sem login, como hoje; (e) aplicar (c) ou (d) **automaticamente no boot**, alterando dados sem ação do operador. Para (b)–(d), escolha também: (i) apenas aviso no boot com a contagem de legados, ou (ii) recusar o boot enquanto houver senha legada. Com (i), o impacto só termina nos bancos em que o operador rodar o script | T-04; migrar_senhas.py, database.py, app.py |
| D-7 | Idempotência do seed de usuários | (a) cada usuário de demonstração é inserido só se o e-mail não existir, independentemente de `produtos` (assim, configurar `SEED_SENHA_JOAO` depois cria João no próximo boot); (b) usuários continuam presos à condição "`produtos` vazia", mas pulando os e-mails que já existem | T-14; database.py |
| D-8 | Substituição de `get_db()` (R-10) | (a) menor ajuste: fábrica injetável em `create_app`, com os controllers inalterados; (b) (a) mais controllers recebendo `db` por parâmetro e sem import de Flask | T-07/T-14; database.py, app.py (+ controllers e routes em b) |
| D-9 | `ambiente` em `/health` (F-07) | (a) ler de variável de ambiente `AMBIENTE` com padrão `"producao"` (corpo igual por padrão, e o valor passa a ser declarado pelo operador); (b) remover o campo; (c) manter fixo: F-07 continua aberto | T-02; config.py, sistema_controller.py |
| D-10 | `GET /pedidos` e `GET /pedidos/usuario/<id>` (F-11) | (a) exigir `X-Admin-Token` nas duas; (b) exigir só em `GET /pedidos`: a rota por usuário continua pública e o resíduo permanece parcialmente; (c) manter públicas: F-11 continua aberto | T-15; routes/pedidos.py |
| D-11 | Escritas sem controle (F-22) | (a) exigir `X-Admin-Token` em POST/PUT/DELETE `/produtos` e em PUT `/pedidos/<id>/status`; (b) exigir só em DELETE `/produtos/<id>` e PUT `/pedidos/<id>/status`: PUT `/produtos` (preço) continua aberto; (c) manter públicas: F-22 continua aberto | T-15; routes/produtos.py, routes/pedidos.py |
| D-12 | Valor inválido em `SEED_SENHA_ON_STARTUP` (ex.: `true`, `""`, `2`) | (a) abortar o boot com erro que cita a variável e os valores aceitos; (b) registrar aviso e usar o padrão (ligado) | T-14; config.py |

#### Conflitos com decisões e conclusões anteriores
1. **D-4 (a) × Regra 6 (dados legados).** A rodada 1 aprovou "nenhum banco é recriado, apagado ou alterado" e aceitou a limitação R-7. A Skill atual não aceita limitação como correção. Qualquer opção que feche o F-04 **altera dados legados** e precisa da nova autorização em D-4R. Nada será alterado em bancos reais: os testes rodam só em cópias geradas pelo código original.
2. **F-07 × contrato preservado.** O `"ambiente": "producao"` foi mantido de propósito (R-4). Fechar o achado muda esse contrato ou a origem do valor (D-9).
3. **Escopo do AP-06 na auditoria original × F-11 e F-22.** A auditoria original não marcou "os demais CRUDs". Esta reexecução reabre o F-11 e cria o F-22. Os casos 10–22 e 41–47 da matriz passarão a ser chamados com token, se aprovado.
4. **`validation.md` declarou F-04, F-07 e F-11 "Corrigido" ou "Corrigido com limitação".** Esta reexecução os reclassifica como parciais. Os arquivos anteriores não serão editados.
5. **R-9 × §5.3 e §5.5.2 da auditoria original** ("seed na inicialização; reset + reinício repete o seed"): sem conflito no padrão ligado. D-7 muda só o caso de duplicação.
6. A decisão já dada nesta mensagem (seed ligado por padrão e desligável por configuração explícita) foi aplicada ao plano, e não a apresentei como pendente.

### 5.6 Validação planejada

#### 5.6.1 Ambiente
- Venv temporário no scratchpad, com `pip install -r requirements.txt` e as versões instaladas registradas.
- Três cópias isoladas: o código **original** `40d2986`, via `git show`, para gerar bancos legados e repetir a linha de base de 54 casos; o código **atual** `c6a53b7` ("antes" da rodada 4); e o código **refatorado**.
- As ferramentas de `rodada-2/tools/` serão copiadas para o temporário e não alteradas no repositório.
- Segredos, tokens e senhas serão sintéticos e mascarados.
- Não há integrações externas.

#### 5.6.2 F-13: provas exigidas

| # | Teste | Resultado esperado |
|---|---|---|
| S1 | Banco **novo**, `SEED_ON_STARTUP=0`, por `python app.py` | Boot sem erro; `sqlite_master` com as 4 tabelas; `COUNT(*)` = 0 em todas; `GET /produtos` → 200 `{"dados": [], "sucesso": true}`; `/health` com contagens 0; `POST /produtos` → 201 e `GET` o devolve; `POST /usuarios` + `/login` → 201/200; nenhum aviso de seed no log |
| S2 | Banco populado → `POST /admin/reset-db` com token → reinício com `SEED_ON_STARTUP=0` | Contagens 0 depois do reset e **0 depois do reinício**; `GET /produtos` vazio |
| S3 | Banco já populado com seed desligado | Dump completo idêntico antes e depois do boot |
| S4 | Banco novo, seed **ligado**, com a variável ausente e com `"1"`, e senhas sintéticas | 10 produtos, 3 usuários com hash, logins → 200 |
| S5 | Reinício com seed ligado sobre o S4 | Dump (ids, chaves, `criado_em`) idêntico, sem duplicação |
| S6 | Seed ligado: reset + reinício | Volta a 10/3 (comportamento atual preservado) |
| S7 | Seed ligado: apagar os 10 produtos via API + reinício | Produtos 10, usuários **3** (sem duplicar, conforme D-7) |
| S8 | Valores `"true"`, `""`, `"2"` | Conforme D-12; override `"0"` (string) em `create_app` é rejeitado |
| S9 | Importar `app.py` (`-I -B`, cwd vazio) | Nenhum banco nem arquivo criado (`ImportacaoTest`) |

**Substituição (R-10).** Uma fábrica de teste que conta as chamadas e aponta para um arquivo **diferente** de `DATABASE_PATH`. Pelo `test_client`:
- `GET /produtos`, `POST /pedidos` e `PUT /pedidos/<id>/status` usam o banco do dublê;
- o arquivo de `DATABASE_PATH` **não é criado**;
- o contador de chamadas é maior que 0 e cada conexão é fechada no teardown;
- o `init_schema` do boot também passa pela fábrica.

Com D-8 (b), o caso de uso também é executado sem contexto Flask, passando uma conexão `sqlite3` direta.

**Duas instâncias no mesmo processo.**
- A = seed ligado no banco `a.db` com token `tA`; B = seed desligado no banco `b.db` com token `tB`.
- Requisições intercaladas: `POST /produtos` em A → `GET /produtos` em B continua vazio; contagens independentes por consulta direta; `tA` em B → 401.
- Depois, as duas instâncias servidas por `werkzeug.serving.make_server` em threads, com requisições simultâneas: nenhum dado cruza, e a `SECRET_KEY` efêmera é diferente em cada uma.

#### 5.6.3 Demais graves
- F-01, F-02, F-03, F-05, F-06, F-08, F-10 e F-12 conforme a tabela 4.1.
- F-09 com o teste concorrente: por exemplo, 20 requisições simultâneas sobre estoque 5 repetidas 20 vezes, mais estoque 1 com 2 requisições repetidas 50 vezes.
- F-04 conforme D-4R, usando um banco gerado pelo código original:
  - dump antes;
  - script em dry-run, sem nenhuma mudança (hash do arquivo idêntico);
  - `--aplicar`;
  - busca binária das senhas legadas sintéticas no `.db` e no journal, com 0 ocorrências;
  - demais colunas e tabelas idênticas;
  - logins conforme a opção;
  - segunda execução sem alterações;
  - falha forçada sem nenhuma mudança.
- F-07, F-11 e F-22 com 403/401/200 e conferência dos efeitos no banco.

#### 5.6.4 Regressão
- Matriz de 54 casos igual à da rodada 3, exceto pelas mudanças de 5.4.
- `python -B -m unittest discover -s tests -v` com os 18 testes existentes mais os novos.
- `specific.py`: 122 OK.
- Nova inspeção estática.
- `validation.md` da rodada 4 com uma linha por ID (F-01…F-22) e contagem dos CRITICAL/HIGH pendentes.
- Se faltar decisão para algum ID, ele será registrado como **Fase 3 bloqueada**.

### 5.7 Destino do relatório e das evidências
- Relatório (este documento, sem alterações): `reports/evidence/code-smells-project/rodada-4/auditoria.md`.
- Evidências: `reports/evidence/code-smells-project/rodada-4/` (`validation.md`, matriz, logs, tools e saídas dos testes).
- **Preservados sem edição:** `reports/audit-project-1.md`, `reports/evidence/code-smells-project/validation.md` e as pastas da raiz, `rodada-2/` e `rodada-3/`.

## 6. Limitações
- As versões instaladas não foram verificadas, porque não há venv no alvo.
- As evidências das rodadas 1–3 foram lidas, não reexecutadas.
- A duplicação do seed e a viabilidade de duas instâncias foram deduzidas do código.
- Bancos legados fora do repositório não foram procurados.

```
================================
Total: 7 achados com impacto remanescente (CRITICAL: 2 | HIGH: 3 | MEDIUM: 2 | LOW: 0)
Reconciliação: 13 graves originais — 8 corrigidos com evidência, 1 corrigido sem prova
de concorrência (F-09), 4 parciais (F-04, F-07, F-11, F-13) + 1 novo grave (F-22)
================================
```
