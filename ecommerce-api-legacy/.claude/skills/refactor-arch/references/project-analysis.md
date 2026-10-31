# Análise de projeto (Fase 1)

Heurísticas para identificar o projeto-alvo, a stack, o banco, a arquitetura atual e os endpoints. Tudo nesta fase é **somente leitura**: não execute, não importe e não instale nada do projeto.

## 1. Identificar o projeto-alvo

1. Se `$ARGUMENTS` indicar um diretório, use-o (resolva caminhos relativos a partir do diretório atual e confirme que existe).
2. Senão, verifique se o diretório atual é a raiz de um projeto: contém manifesto (`requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile`, `package.json`, `go.mod`, `pom.xml`, `build.gradle`, `Gemfile`, `composer.json`, `*.csproj`) ou ponto de entrada reconhecível.
3. Se o diretório atual for a raiz de um repositório com **vários** projetos (vários manifestos em subpastas) e nada indicar o alvo, liste os candidatos e **pergunte**. Não escolha sozinho.
4. A partir daí, limite leitura, contagens e conclusões ao alvo. Arquivos da raiz do repositório ou de projetos vizinhos (ex.: um `requirements.txt` na raiz pertencente a outro contexto) **não** descrevem o alvo.

## 2. Inventário de arquivos

Liste os arquivos sob o alvo e separe código-fonte de todo o resto.

```bash
git -C <alvo> ls-files --cached --others --exclude-standard   # preferível em repositórios git
find <alvo> -type f -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/.claude/*' -not -path '*/__pycache__/*' -not -path '*/.venv/*' -not -path '*/venv/*'
wc -l <arquivos de código>   # linhas físicas, incluindo linhas em branco
```

**Exclua da contagem de código e informe a exclusão:** `.claude/` (a própria Skill — seus arquivos são lidos como instruções e referências, mas não são código do projeto nem objeto da auditoria), dependências instaladas (`node_modules/`, `venv/`, `.venv/`, `site-packages`), caches (`__pycache__/`, `*.pyc`), bancos e dados (`*.db`, `*.sqlite`, `instance/`), lockfiles (`package-lock.json`, `poetry.lock`), artefatos de build e arquivos de documentação ou requisições (`*.md`, `*.http`). Esses arquivos podem ser **lidos** como evidência (ex.: `api.http` para endpoints, lockfile para versões resolvidas), mas não entram como "arquivos de código analisados".

Informe: quantidade de arquivos de código analisados, total de linhas físicas e a lista de exclusões. Se algum arquivo de código não for lido integralmente, diga qual e por quê.

## 3. Linguagem e framework

| Sinal | Indica |
|---|---|
| `*.py` + `requirements.txt`/`pyproject.toml` | Python |
| `from flask import Flask`, `Flask(__name__)`, `Blueprint(` | Flask |
| `from fastapi import`, `from django` , `manage.py` | FastAPI / Django (adapte as heurísticas) |
| `*.js`/`*.ts` + `package.json` | Node.js (JavaScript/TypeScript) |
| `require('express')` / `import express`, `express()`, `express.Router()` | Express |
| `@nestjs/`, `fastify`, `koa` em `package.json` | Outros frameworks Node (adapte) |

Confirme o framework pelo **uso no código**, não só pela presença no manifesto: uma dependência declarada pode não ser usada, e um import pode faltar no manifesto.

Para outras tecnologias, aplique o mesmo processo: manifesto → ponto de entrada → registro de rotas → acesso a dados.

## 4. Versões declaradas × instaladas

Registre as duas separadamente; nunca apresente uma como a outra.

| Fonte | O que informa |
|---|---|
| `requirements.txt` (`flask==3.1.1`), `pyproject.toml` | Versão **declarada** (fixa ou faixa) |
| `package.json` (`"express": "^4.18.2"`) | **Faixa** declarada, não versão exata |
| `package-lock.json` (`"node_modules/express": {"version": ...}`) | Versão **resolvida** no lock; não prova instalação |
| `node_modules/<pacote>/package.json` | Versão **instalada** no projeto |
| `<venv-do-projeto>/bin/python -m pip show <pacote>` | Versão **instalada** no ambiente do projeto |

Cuidados:

- O interpretador ou `pip` global da máquina **não** representa o ambiente do projeto. Só use um ambiente virtual que pertença claramente ao alvo (ex.: `<alvo>/.venv`). Sem ele, registre "instalada: não verificado".
- `pip show`, `npm ls --depth=0`, `node --version` e `python3 --version` são leituras; `pip install`, `npm install`, `npm ci` e criação de venv **não** são permitidos nesta fase.
- Dependências transitivas relevantes (ex.: SQLAlchemy sob Flask-SQLAlchemy) podem ter versão mínima definida pela biblioteca que as exige; cite a fonte se usar essa inferência.

## 5. Banco de dados e persistência

Procure:

- **Python:** `sqlite3.connect`, `SQLAlchemy(`, `db.Model`, `create_engine`, `psycopg`, `pymongo`, `SQLALCHEMY_DATABASE_URI`.
- **Node:** `require('sqlite3')`, `new sqlite3.Database(`, `knex`, `sequelize`, `prisma`, `mongoose`, `pg`, `mysql2`.
- Caminho/URI do banco (arquivo, `:memory:`, servidor), criação de schema (`CREATE TABLE`, `db.create_all()`, migrations), dados iniciais (seeds) e **quando** isso acontece (na importação, na inicialização, por script separado).
- Tabelas/modelos: `CREATE TABLE <nome>`, classes `db.Model`, `__tablename__`.

Registre efeitos colaterais de inicialização (ex.: "importar o módulo X cria o arquivo de banco"). Isso orienta a Fase 3 a validar com dados isolados.

## 6. Pontos de entrada e endpoints

**Pontos de entrada:** `if __name__ == "__main__":`, `app.run(`, `create_app(`, `wsgi.py`; `"main"`/`"scripts.start"` em `package.json`, `app.listen(`, `server.listen(`. Registre host, porta e modo debug configurados.

**Endpoints — Flask:**

```bash
grep -rnE "@[A-Za-z_]+\.route\(|add_url_rule\(|Blueprint\(|register_blueprint\(" <alvo> --include='*.py'
```

- `@app.route("/x", methods=[...])`: sem `methods`, o padrão é `GET` (Flask também responde `HEAD` e `OPTIONS`).
- `app.add_url_rule("/x", "endpoint", view_func, methods=[...])`.
- Blueprints — prefixo efetivo (documentação oficial do Flask 3.1.x, `register_blueprint`: "Keyword arguments passed to this method will override the defaults set on the blueprint"):
  - sem `url_prefix` no registro → vale o `url_prefix` declarado em `Blueprint(...)`, se houver;
  - com `url_prefix` em `register_blueprint(...)` → ele **substitui** o declarado no `Blueprint(...)`; **não** some os dois;
  - Blueprints aninhados (`parent.register_blueprint(child)`) → as URLs do filho recebem o prefixo efetivo do pai antes do prefixo efetivo do filho (exemplo oficial: `/parent/child/create`);
  - o mesmo Blueprint pode ser registrado mais de uma vez com prefixos diferentes: liste cada registro.
  - Se a versão de Flask do projeto for diferente de 3.1.x, confirme a regra na documentação da versão pertinente. Por leitura estática, registre o caminho deduzido; a confirmação por `app.url_map` só pode ser feita na Fase 3, em cópia isolada, porque exige importar o app.
- Conversores de caminho (`<int:id>`) fazem parte do contrato (ex.: id não numérico → 404).

**Endpoints — Express:**

```bash
grep -rnE "(app|router|[A-Za-z_]+Router)\.(get|post|put|patch|delete|all|use|route)\(" <alvo> --include='*.js' --include='*.ts'
```

- `app.use('/prefixo', router)` prefixa todas as rotas do router.
- Rotas podem ser registradas dentro de funções/métodos chamados na inicialização; siga as chamadas a partir do ponto de entrada.
- Middlewares globais (`app.use(express.json())`, CORS, autenticação) e handlers de erro (`(err, req, res, next)`) fazem parte do comportamento.

Cruze com arquivos de exemplo (`*.http`, coleções, README do projeto), mas trate-os como documentação, não como prova: o código prevalece em caso de divergência, e a divergência deve ser registrada.

Para cada endpoint registre: método, caminho completo, função que o atende (`arquivo:linha`), entradas (path, query, corpo) e efeitos (leitura, escrita, exclusão, chamada externa).

## 7. Mapeamento de responsabilidades e arquitetura

Classifique cada arquivo pelo que ele **faz**, não pelo nome nem pela pasta:

- roteamento/HTTP (lê `request`/`req`, define status, serializa JSON);
- regras de negócio (cálculos, validações de domínio, transições de estado);
- persistência (SQL, ORM, conexão, transações);
- configuração (constantes, segredos, portas, URIs);
- inicialização (criação do app, registro de rotas, schema, seed);
- utilitários e integrações externas (e-mail, pagamento, HTTP).

Um arquivo chamado `models.py` que monta respostas HTTP, ou uma pasta `routes/` cujas funções executam consultas e cálculos, não demonstra separação de camadas. Descreva a arquitetura atual com base nessas observações (ex.: "monolítica, rotas acessam SQL diretamente", "camadas nominais, mas regras concentradas nas rotas").

## 8. Domínio

Infira o domínio por tabelas/modelos, rotas e nomes de entidades e operações (ex.: produtos/pedidos → e-commerce; cursos/matrículas → plataforma de cursos). Não se baseie apenas no nome da pasta ou do repositório; se o nome sugerir algo diferente do código, prevalece o código.

## 9. Formato do resumo da Fase 1

Imprima em bloco de texto, preenchendo apenas com dados observados (use "não verificado" quando for o caso):

```
================================
FASE 1: ANÁLISE DO PROJETO
================================
Projeto:        <nome> (<caminho relativo à raiz do repositório>)
Linguagem:      <linguagem e versão do runtime, se verificada>
Framework:      <framework> — declarada: <versão/faixa> | instalada: <versão ou "não verificado">
Dependências:   <lista com versões declaradas>
Banco:          <tecnologia, local/URI e tabelas/modelos>
Domínio:        <descrição baseada em entidades e rotas>
Arquitetura:    <descrição baseada no mapeamento de responsabilidades>
Entrada:        <arquivo:linha, comando de início, host/porta>
Endpoints:      <quantidade> (<lista resumida MÉTODO caminho>)
Arquivos:       <N> arquivos de código analisados | <L> linhas físicas
Exclusões:      <categorias/arquivos excluídos>
Efeitos de init:<ex.: cria banco na importação; seed automático>
================================
```

Em seguida, liste a tabela de endpoints e o mapeamento de responsabilidades por arquivo, de forma breve.
