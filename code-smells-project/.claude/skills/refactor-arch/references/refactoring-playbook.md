# Playbook de refatoração

Padrões de transformação aplicáveis na Fase 3, cada um ligado aos anti-patterns de [anti-patterns.md](anti-patterns.md) e à arquitetura de [mvc-guidelines.md](mvc-guidelines.md).

## Como usar os exemplos

- **Todos os exemplos são didáticos.** Usam um domínio fictício de biblioteca (`authors`, `books`, `members`, `loans`); tabelas, rotas, campos e mensagens são ilustrativos. Adapte aos nomes reais do projeto e **preserve os contratos existentes** (rotas, métodos, nomes de campos, formato de erro, códigos de status), salvo mudança de segurança aprovada.
- Os trechos são código real de Python 3.10+ / Flask 3 e Node.js 18+ / Express 4, mas são **fragmentos**: dependem de imports e funções definidos no próprio exemplo ou em transformações citadas (ex.: `get_db` de T-07, `HttpError` de T-12). Pressupostos específicos aparecem em cada transformação.
- Aplique uma transformação por vez e valide (ver "Validação" em cada uma e a seção final). Não acumule muitas mudanças antes de verificar.
- Nenhum exemplo ou validação deve acionar serviços externos reais (e-mail, pagamento, APIs de terceiros). Use configuração desabilitada ou dublês.

## Índice

| ID | Transformação | Anti-patterns |
|---|---|---|
| T-01 | Parametrizar consultas SQL | AP-01 |
| T-02 | Extrair configuração para variáveis de ambiente | AP-02, AP-11 |
| T-03 | Representação pública sem dados sensíveis | AP-03 |
| T-04 | Hash de senha adequado | AP-04 |
| T-05 | Decompor God Class em Model, Controller e Routes | AP-05, AP-07 |
| T-06 | Rota fina, controller coordenador e regra no Model | AP-07, AP-14 |
| T-07 | Ciclo de vida explícito da conexão e injeção de estado | AP-08, AP-10 |
| T-08 | Transação explícita para escritas relacionadas | AP-09 |
| T-09 | Eliminar consultas N+1 | AP-12 |
| T-10 | Validação centralizada de entrada | AP-13, AP-14 |
| T-11 | Migrar API obsoleta | AP-15 |
| T-12 | Tratamento de erros centralizado | AP-16 |
| T-13 | Constantes nomeadas, nomes descritivos e remoção de código morto | AP-17, AP-18, AP-19, AP-20 |
| T-14 | Composition root, app factory e dependências injetáveis | AP-10, AP-11 |
| T-15 | Proteger ou remover operações administrativas | AP-06 |

---

## T-01 — Parametrizar consultas SQL

**Trata:** AP-01. **Pressupostos:** driver `sqlite3` (Python stdlib ou pacote npm `sqlite3`); outros drivers usam outros marcadores (`%s`, `$1`).

**Python — antes**

```python
def find_member_by_email(email):
    cursor = get_db().cursor()
    cursor.execute("SELECT * FROM members WHERE email = '" + email + "'")
    return cursor.fetchone()


def search_books(term):
    cursor = get_db().cursor()
    cursor.execute(f"SELECT * FROM books WHERE title LIKE '%{term}%'")
    return cursor.fetchall()
```

**Python — depois**

```python
def find_member_by_email(db, email):
    return db.execute(
        "SELECT id, name, email FROM members WHERE email = ?", (email,)
    ).fetchone()


def search_books(db, term):
    return db.execute(
        "SELECT id, title, author_id FROM books WHERE title LIKE ?", (f"%{term}%",)
    ).fetchall()
```

**JavaScript — antes**

```js
db.get(`SELECT * FROM members WHERE email = '${req.body.email}'`, (err, row) => {
  if (err) return res.status(500).send(err.message);
  res.json(row);
});
```

**JavaScript — depois** (no Model; usa o helper `get` de T-05 — a rota e o controller apenas chamam esta função)

```js
const { get } = require('../database');

function findByEmail(db, email) {
  return get(db, 'SELECT id, name, email FROM members WHERE email = ?', [email]);
}

module.exports = { findByEmail };
```

**Cuidados:** nomes de tabela/coluna não podem ser parametrizados; se forem dinâmicos, escolha-os de uma lista fixa no código. Ao trocar `SELECT *` por colunas explícitas, confira se a resposta original dependia de alguma coluna omitida (exceto campos sensíveis, ver T-03).

**Validação:** as mesmas entradas válidas retornam os mesmos dados da linha de base; uma entrada com aspas (ex.: `x' OR '1'='1`) é tratada como texto literal (nenhuma correspondência indevida, sem erro 500); login com credenciais corretas e incorretas mantém os resultados esperados.

---

## T-02 — Extrair configuração para variáveis de ambiente

**Trata:** AP-02, AP-11. **Pressupostos:** sem biblioteca de `.env` adicional; se o projeto já depende de `python-dotenv`/`dotenv`, ela pode carregar o arquivo antes da leitura.

**Python — antes**

```python
app = Flask(__name__)
app.config["SECRET_KEY"] = "chave-fixa-123"
app.config["DEBUG"] = True
app.run(host="0.0.0.0", port=5000, debug=True)
```

**Python — depois (`config.py`)**

```python
import logging
import os
import secrets

logger = logging.getLogger(__name__)


def _secret_key():
    value = os.environ.get("SECRET_KEY")
    if value:
        return value
    logger.warning("SECRET_KEY não definida; usando chave efêmera de desenvolvimento.")
    return secrets.token_hex(32)


def load_config():
    return {
        "SECRET_KEY": _secret_key(),
        "DATABASE_PATH": os.environ.get("DATABASE_PATH", "library.db"),
        "DEBUG": os.environ.get("FLASK_DEBUG", "0") == "1",
        "HOST": os.environ.get("HOST", "127.0.0.1"),
        "PORT": int(os.environ.get("PORT", "5000")),
    }
```

Uso: `app.config.from_mapping(load_config())` e `app.run(host=app.config["HOST"], port=app.config["PORT"], debug=app.config["DEBUG"])`.

**JavaScript — antes**

```js
const config = {
  dbPass: 'senha-fixa',
  paymentGatewayKey: 'pk_live_fixa',
  port: 3000,
};
module.exports = { config };
```

**JavaScript — depois (`src/config.js`)**

```js
const config = {
  port: Number(process.env.PORT || 3000),
  databasePath: process.env.DATABASE_PATH || ':memory:',
  dbPassword: process.env.DB_PASSWORD || null,
  paymentGatewayKey: process.env.PAYMENT_GATEWAY_KEY || null,
};

module.exports = { config };
```

Documente as variáveis em `.env.example` com valores fictícios.

**Cuidados:** mantenha padrões não secretos iguais aos originais (porta, caminho do banco). Mudar o host padrão (ex.: de `0.0.0.0` para `127.0.0.1`) altera quem pode acessar o servidor; registre a decisão. Código que dependia de um segredo agora `null` deve falhar de forma controlada (ex.: integração desabilitada), não com exceção genérica.

**Validação:** `grep` não encontra mais os literais secretos no código; a aplicação inicia sem as variáveis (ou falha com mensagem clara, se essa for a decisão aprovada) e também com elas definidas; o debug fica desligado por padrão.

---

## T-03 — Representação pública sem dados sensíveis

**Trata:** AP-03. **Pressupostos:** Flask-SQLAlchemy no exemplo Python; linhas do `sqlite3` no exemplo Node.

**Python — antes**

```python
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    password = db.Column(db.String(255))

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "password": self.password}
```

**Python — depois**

```python
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    password = db.Column(db.String(255))

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email}
```

**JavaScript — antes**

```js
db.all('SELECT * FROM members', [], (err, rows) => res.json(rows));
```

**JavaScript — depois** (no Model `src/models/memberModel.js`; usa o helper `all` de T-05)

```js
const { all } = require('../database');

function toPublicMember(row) {
  return { id: row.id, name: row.name, email: row.email };
}

async function listPublic(db) {
  const rows = await all(db, 'SELECT id, name, email FROM members');
  return rows.map(toPublicMember);
}

module.exports = { listPublic, toPublicMember };
```

O controller chama `memberModel.listPublic(db)` e a rota faz `res.json(...)` com o resultado.

**Cuidados:** procure **todos** os pontos que serializam a entidade (listagem, detalhe, login, relatórios, logs). Remover o campo é uma mudança de contrato intencional: registre-a no relatório final.

**Validação:** nenhuma resposta da matriz de endpoints contém o campo sensível (`grep` no corpo das respostas registradas); os demais campos permanecem iguais à linha de base.

---

## T-04 — Hash de senha adequado

**Trata:** AP-04. **Pressupostos:** Python usa `werkzeug.security`, já instalado como dependência do Flask; Node usa `node:crypto` (sem dependência nova).

**Python — antes**

```python
import hashlib


def set_password(member, raw_password):
    member.password = hashlib.md5(raw_password.encode()).hexdigest()


def check_password(member, raw_password):
    return member.password == hashlib.md5(raw_password.encode()).hexdigest()
```

**Python — depois**

```python
from werkzeug.security import check_password_hash, generate_password_hash


def set_password(member, raw_password):
    member.password = generate_password_hash(raw_password)


def check_password(member, raw_password):
    return check_password_hash(member.password, raw_password)
```

**JavaScript — antes**

```js
function encodePassword(pwd) {
  return Buffer.from(pwd).toString('base64');
}
```

**JavaScript — depois (`src/passwordHash.js`)**

```js
const crypto = require('node:crypto');
const { promisify } = require('node:util');

const scrypt = promisify(crypto.scrypt);

const SCHEME = 'scrypt';
const SALT_BYTES = 16;
const KEY_BYTES = 64;
const SALT_HEX = new RegExp(`^[0-9a-f]{${SALT_BYTES * 2}}$`);
const KEY_HEX = new RegExp(`^[0-9a-f]{${KEY_BYTES * 2}}$`);

async function hashPassword(password) {
  if (typeof password !== 'string') throw new TypeError('password deve ser string');
  const salt = crypto.randomBytes(SALT_BYTES);
  const derived = await scrypt(password, salt, KEY_BYTES);
  return `${SCHEME}$${salt.toString('hex')}$${derived.toString('hex')}`;
}

function parseStoredHash(stored) {
  if (typeof stored !== 'string') return null;
  const parts = stored.split('$');
  if (parts.length !== 3) return null;
  const [scheme, saltHex, keyHex] = parts;
  if (scheme !== SCHEME || !SALT_HEX.test(saltHex) || !KEY_HEX.test(keyHex)) return null;
  return { salt: Buffer.from(saltHex, 'hex'), key: Buffer.from(keyHex, 'hex') };
}

async function verifyPassword(password, stored) {
  if (typeof password !== 'string') return false;
  const parsed = parseStoredHash(stored);
  if (parsed === null) return false;
  const derived = await scrypt(password, parsed.salt, KEY_BYTES);
  return crypto.timingSafeEqual(derived, parsed.key);
}

module.exports = { hashPassword, verifyPassword };
```

O formato armazenado é validado por completo **antes** de executar `scrypt`: exatamente três campos, algoritmo `scrypt`, salt com 16 bytes e chave com 64 bytes em hexadecimal minúsculo (o formato que `hashPassword` gera). O tamanho da chave é uma constante, nunca derivado do valor armazenado. Sem essa validação, um hash malformado como `scrypt$<salt>$zz` vira um buffer vazio, a chave derivada também tem tamanho 0 e a comparação de dois buffers vazios retorna `true` para qualquer senha.

**Teste do exemplo** (verifica o exemplo T-04, **não** as aplicações do desafio; requer Node.js 18+ e roda com `node --test passwordHash.test.js` num diretório temporário com o arquivo acima):

```js
// Teste do exemplo T-04 do playbook — não testa as aplicações do desafio.
const test = require('node:test');
const assert = require('node:assert/strict');
const { hashPassword, verifyPassword } = require('./passwordHash');

test('aceita a senha correta', async () => {
  const stored = await hashPassword('senha-correta');
  assert.equal(await verifyPassword('senha-correta', stored), true);
});

test('recusa senha incorreta', async () => {
  const stored = await hashPassword('senha-correta');
  assert.equal(await verifyPassword('senha-errada', stored), false);
});

test('recusa valor armazenado vazio ou ausente', async () => {
  for (const stored of ['', null, undefined]) {
    assert.equal(await verifyPassword('qualquer-senha', stored), false);
  }
});

test('recusa hexadecimal inválido', async () => {
  assert.equal(await verifyPassword('qualquer-senha', 'scrypt$00112233445566778899aabbccddeeff$zz'), false);
  const stored = await hashPassword('senha-correta');
  const [scheme, salt, key] = stored.split('$');
  assert.equal(await verifyPassword('senha-correta', `${scheme}$${salt}$${'g'.repeat(key.length)}`), false);
  assert.equal(await verifyPassword('senha-correta', `${scheme}$${salt}$${key.toUpperCase()}`), false);
});

test('recusa hash ou salt truncados', async () => {
  const stored = await hashPassword('senha-correta');
  const [scheme, salt, key] = stored.split('$');
  assert.equal(await verifyPassword('senha-correta', `${scheme}$${salt}$${key.slice(0, -2)}`), false);
  assert.equal(await verifyPassword('senha-correta', `${scheme}$${salt.slice(0, -2)}$${key}`), false);
});

test('recusa campos extras e algoritmo diferente', async () => {
  const stored = await hashPassword('senha-correta');
  assert.equal(await verifyPassword('senha-correta', `${stored}$extra`), false);
  assert.equal(await verifyPassword('senha-correta', stored.replace(/^scrypt/, 'md5')), false);
});
```

**Cuidados:** a coluna precisa comportar o hash maior. Senhas já gravadas no formato antigo não podem ser convertidas sem a senha original: decida com o usuário (redefinição, ou verificar no formato antigo e regravar no novo no próximo login, se o formato antigo for verificável). Seeds que gravam senhas devem usar a nova função. Não introduza senha padrão literal.

**Validação:** cadastro grava valor com prefixo do algoritmo (consulta direta ao banco de teste); login com senha correta é aceito e com senha incorreta é recusado, com os mesmos status da linha de base; o hash não aparece em respostas.

---

## T-05 — Decompor God Class em Model, Controller e Routes

**Trata:** AP-05, AP-07. **Pressupostos:** Express 4 e pacote `sqlite3`; usa `HttpError`/`asyncHandler` (T-12). Se a operação tiver várias escritas relacionadas, combine com T-08.

**JavaScript — antes (`src/LibraryApp.js`)**

```js
class LibraryApp {
  constructor() {
    this.db = new sqlite3.Database(':memory:');
  }

  initDb() {
    this.db.serialize(() => {
      this.db.run('CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, available INTEGER)');
      this.db.run('CREATE TABLE loans (id INTEGER PRIMARY KEY, book_id INTEGER, member_id INTEGER)');
      this.db.run("INSERT INTO books (title, available) VALUES ('Livro A', 1)");
    });
  }

  setupRoutes(app) {
    app.post('/api/loans', (req, res) => {
      const b = req.body.book_id;
      const m = req.body.member_id;
      this.db.get('SELECT * FROM books WHERE id = ?', [b], (err, book) => {
        if (err || !book) return res.status(404).send('Livro não encontrado');
        if (!book.available) return res.status(409).send('Indisponível');
        this.db.run('INSERT INTO loans (book_id, member_id) VALUES (?, ?)', [b, m], function () {
          res.status(201).json({ id: this.lastID, book_id: b, member_id: m });
        });
      });
    });
  }
}
```

**JavaScript — depois**

`src/database.js`

```js
const sqlite3 = require('sqlite3');

function openDatabase(path) {
  return new sqlite3.Database(path);
}

function run(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.run(sql, params, function onRun(err) {
      if (err) return reject(err);
      resolve({ lastID: this.lastID, changes: this.changes });
    });
  });
}

function get(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => (err ? reject(err) : resolve(row)));
  });
}

function all(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => (err ? reject(err) : resolve(rows)));
  });
}

async function initSchema(db) {
  await run(db, 'CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, available INTEGER)');
  await run(db, 'CREATE TABLE loans (id INTEGER PRIMARY KEY, book_id INTEGER, member_id INTEGER)');
  await run(db, "INSERT INTO books (title, available) VALUES ('Livro A', 1)");
}

module.exports = { openDatabase, run, get, all, initSchema };
```

`src/models/bookModel.js`

```js
const { get } = require('../database');

function findById(db, id) {
  return get(db, 'SELECT id, title, available FROM books WHERE id = ?', [id]);
}

module.exports = { findById };
```

`src/models/loanModel.js`

```js
const { run } = require('../database');

async function create(db, { bookId, memberId }) {
  const { lastID } = await run(db, 'INSERT INTO loans (book_id, member_id) VALUES (?, ?)', [bookId, memberId]);
  return { id: lastID, book_id: bookId, member_id: memberId };
}

module.exports = { create };
```

`src/controllers/loanController.js`

```js
const { HttpError } = require('../errors');
const bookModel = require('../models/bookModel');
const loanModel = require('../models/loanModel');

function createLoanController(db) {
  return {
    async borrow({ bookId, memberId }) {
      const book = await bookModel.findById(db, bookId);
      if (!book) throw new HttpError(404, 'Livro não encontrado');
      if (!book.available) throw new HttpError(409, 'Indisponível');
      return loanModel.create(db, { bookId, memberId });
    },
  };
}

module.exports = { createLoanController };
```

`src/routes/loanRoutes.js`

```js
const express = require('express');
const { asyncHandler } = require('../middlewares/asyncHandler');

function loanRoutes(loanController) {
  const router = express.Router();
  router.post('/api/loans', asyncHandler(async (req, res) => {
    const loan = await loanController.borrow({
      bookId: req.body.book_id,
      memberId: req.body.member_id,
    });
    res.status(201).json(loan);
  }));
  return router;
}

module.exports = { loanRoutes };
```

A composição (abrir banco, `initSchema`, criar controllers, montar routers e o handler de erros) fica no ponto de entrada — ver T-14.

**Cuidados:** o "depois" executa as mesmas operações do "antes", apenas redistribuídas; **não** acrescente regras novas durante a refatoração. O "antes" tratava erro de banco como 404; o "depois" o encaminha ao handler central como 500 — diferença intencional a registrar. Preserve mensagens e formatos de resposta originais (aqui, texto puro em erros 404/409, se esse era o contrato). Dividir a classe em arquivos sem separar responsabilidades não resolve AP-05.

**Validação:** o comando de start original continua funcionando; cada rota da classe original responde com o mesmo status e corpo da linha de base; as tabelas e dados iniciais são os mesmos (consulta de contagem por tabela).

---

## T-06 — Rota fina, controller coordenador e regra no Model

**Trata:** AP-07, AP-14. **Pressupostos:** Flask 3 + Flask-SQLAlchemy 3.1 (SQLAlchemy 2.x); `db` é a extensão; `NotFoundError` vem de T-12.

**Python — antes (`routes/book_routes.py`)**

```python
@book_bp.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    book = db.session.get(Book, book_id)
    if book is None:
        return jsonify({"error": "Livro não encontrado"}), 404
    data = book.to_dict()
    data["overdue"] = (
        book.due_date is not None
        and book.due_date < datetime.now()
        and book.status not in ("returned", "lost")
    )
    return jsonify(data), 200
```

**Python — depois**

`models/book.py`

```python
from datetime import datetime

from database import db

CLOSED_STATUSES = ("returned", "lost")


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default="available")
    due_date = db.Column(db.DateTime, nullable=True)

    @classmethod
    def find_by_id(cls, book_id):
        return db.session.get(cls, book_id)

    def is_overdue(self, now=None):
        now = now or datetime.now()
        return self.due_date is not None and self.due_date < now and self.status not in CLOSED_STATUSES

    def to_dict(self):
        return {"id": self.id, "title": self.title, "status": self.status,
                "due_date": self.due_date.isoformat() if self.due_date else None}
```

`controllers/book_controller.py`

```python
from errors import NotFoundError
from models.book import Book


def get_book_details(book_id):
    book = Book.find_by_id(book_id)
    if book is None:
        raise NotFoundError("Livro não encontrado")
    return {**book.to_dict(), "overdue": book.is_overdue()}
```

`routes/book_routes.py`

```python
from flask import Blueprint, jsonify

from controllers import book_controller

book_bp = Blueprint("books", __name__)


@book_bp.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    return jsonify(book_controller.get_book_details(book_id)), 200
```

Fluxo resultante: a rota extrai o parâmetro e serializa; o controller coordena e sinaliza o erro de domínio; o Model concentra a consulta (`find_by_id`) e a regra (`is_overdue`). Nem a rota nem o controller acessam `db.session`.

**Cuidados:** se o projeto já possui o método de regra no Model (ex.: `is_overdue`), reutilize-o em vez de criar outro; confirme que a regra copiada nas rotas é idêntica à do Model antes de unificar — se divergirem, mantenha o comportamento observável do endpoint e registre a divergência. Mantenha o corpo e o status do erro iguais aos da linha de base (aqui, depende do handler de T-12 reproduzir `{"error": ...}`).

**Validação:** para registros atrasados, não atrasados e com status encerrado, o campo calculado é igual ao da linha de base; o 404 mantém status e corpo.

---

## T-07 — Ciclo de vida explícito da conexão e injeção de estado

**Trata:** AP-08, AP-10. **Pressupostos:** Python `sqlite3` + Flask (padrão de `g` e `teardown_appcontext`); Node com a conexão criada no composition root.

**Python — antes (`database.py`)**

```python
import sqlite3

_connection = None


def get_db():
    global _connection
    if _connection is None:
        _connection = sqlite3.connect("library.db", check_same_thread=False)
        _connection.row_factory = sqlite3.Row
    return _connection
```

**Python — depois (`database.py`)**

```python
import sqlite3

from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
```

**JavaScript — antes**

```js
let cache = {};

function remember(key, value) {
  cache[key] = value;
}

module.exports = { remember, cache };
```

**JavaScript — depois**

```js
function createCache() {
  const entries = new Map();
  return {
    get: (key) => entries.get(key),
    set: (key, value) => entries.set(key, value),
  };
}

module.exports = { createCache };
```

O composition root cria `const cache = createCache()` e o passa aos controllers que precisam dele. Se o cache/contador global não tiver consumidor real, remova-o (T-13) em vez de encapsulá-lo.

**Cuidados:** banco SQLite `:memory:` existe apenas enquanto sua conexão está aberta; nesse caso, mantenha **uma** conexão criada no ponto de entrada e injetada, em vez de abrir uma por requisição. Código executado fora de requisições (seed, scripts) precisa de `with app.app_context():`. Não confunda a extensão `db = SQLAlchemy()` (sessão gerenciada pelo contexto da aplicação) com conexão global: ela não precisa desta transformação.

**Validação:** endpoints de leitura e escrita mantêm resultados da linha de base; várias requisições seguidas não deixam conexões abertas indevidamente (sem erros "database is locked" no log); scripts de seed continuam funcionando.

---

## T-08 — Transação explícita para escritas relacionadas

**Trata:** AP-09. **Pressupostos:** conexão obtida como em T-07; helpers `run` de T-05.

**Python — antes**

```python
def create_loan(db, book_id, member_id):
    cursor = db.execute("INSERT INTO loans (book_id, member_id) VALUES (?, ?)", (book_id, member_id))
    db.commit()
    db.execute("UPDATE books SET available = 0 WHERE id = ?", (book_id,))
    db.commit()
    return cursor.lastrowid
```

**Python — depois**

```python
def create_loan(db, book_id, member_id):
    with db:  # commit ao final; rollback automático se houver exceção
        cursor = db.execute(
            "INSERT INTO loans (book_id, member_id) VALUES (?, ?)", (book_id, member_id)
        )
        db.execute("UPDATE books SET available = 0 WHERE id = ?", (book_id,))
    return cursor.lastrowid
```

Com Flask-SQLAlchemy: faça todas as alterações na sessão, um único `db.session.commit()` ao final e `db.session.rollback()` no tratamento de exceção.

**JavaScript — antes**

```js
db.run('INSERT INTO loans (book_id, member_id) VALUES (?, ?)', [bookId, memberId], function (err) {
  if (err) return res.status(500).send('Erro');
  db.run('INSERT INTO payments (loan_id, amount) VALUES (?, ?)', [this.lastID, fee], (err2) => {
    if (err2) return res.status(500).send('Erro no pagamento');
    res.status(201).send('ok');
  });
});
```

**JavaScript — depois (`src/transaction.js`)**

```js
const { run } = require('./database');

const queues = new WeakMap();

function withTransaction(db, work) {
  const previous = queues.get(db) || Promise.resolve();
  const result = previous.then(async () => {
    await run(db, 'BEGIN');
    try {
      const value = await work();
      await run(db, 'COMMIT');
      return value;
    } catch (err) {
      await run(db, 'ROLLBACK').catch(() => {});
      throw err;
    }
  });
  queues.set(db, result.catch(() => {}));
  return result;
}

module.exports = { withTransaction };
```

Uso no controller, que define a fronteira da transação e delega as escritas aos Models (`loanModel.create` de T-05; `paymentModel.create` é análogo, com `INSERT INTO payments ... VALUES (?, ?)`):

```js
const loan = await withTransaction(db, async () => {
  const created = await loanModel.create(db, { bookId, memberId });
  await paymentModel.create(db, { loanId: created.id, amount: fee });
  return created;
});
```

**Pressupostos e limites:**

- O que o exemplo garante: as escritas feitas dentro de `work` são confirmadas juntas ou desfeitas juntas, e duas chamadas de `withTransaction` na mesma conexão não se sobrepõem.
- O que o exemplo **não** garante: isolamento. Uma transação SQLite pertence à **conexão**, não à requisição. Qualquer instrução de outra requisição executada na mesma conexão entre `BEGIN` e `COMMIT` participa da transação aberta:
  - uma **escrita** externa à fila entra na transação e é desfeita se houver `ROLLBACK`;
  - uma **leitura** externa à fila enxerga alterações ainda não confirmadas, que podem deixar de existir após um `ROLLBACK`.
- Por isso, serializar apenas as escritas não isola as transações. Alternativas, a decidir pelo fluxo real:
  - encaminhar **todo** acesso ao banco dessa conexão (leituras inclusive) pela mesma fila, aceitando a perda de concorrência;
  - em banco em arquivo, usar conexões separadas por requisição ou transação; o SQLite então isola as transações entre conexões (sem modo de cache compartilhado com leitura não confirmada), e é preciso tratar `SQLITE_BUSY`/timeouts de bloqueio;
  - em `:memory:` cada conexão abre um banco distinto, então conexões separadas não são opção sem mudar o armazenamento.
- Registre a escolha e a limitação restante no relatório da Fase 3. Defina explicitamente se gravações acessórias (ex.: auditoria) fazem parte da transação.

**Validação:** caminho de sucesso igual à linha de base; para a falha, use um teste no banco isolado que force erro na segunda escrita (ex.: violar uma restrição em dados de teste) e confirme, por consulta, que a primeira escrita foi desfeita.

---

## T-09 — Eliminar consultas N+1

**Trata:** AP-12. **Pressupostos:** `sqlite3` (Python), SQLAlchemy 2.x (`select`) com Flask-SQLAlchemy, `sqlite3` npm com helper `all` de T-05.

**Python — antes**

```python
def list_authors_with_books(db):
    authors = [dict(row) for row in db.execute("SELECT id, name FROM authors ORDER BY id")]
    for author in authors:
        rows = db.execute("SELECT id, title FROM books WHERE author_id = ? ORDER BY id", (author["id"],))
        author["books"] = [dict(row) for row in rows]
    return authors
```

**Python — depois (uma consulta)**

```python
def list_authors_with_books(db):
    rows = db.execute(
        """
        SELECT a.id AS author_id, a.name AS author_name, b.id AS book_id, b.title AS book_title
        FROM authors a
        LEFT JOIN books b ON b.author_id = a.id
        ORDER BY a.id, b.id
        """
    ).fetchall()
    authors = {}
    for row in rows:
        author = authors.setdefault(
            row["author_id"], {"id": row["author_id"], "name": row["author_name"], "books": []}
        )
        if row["book_id"] is not None:
            author["books"].append({"id": row["book_id"], "title": row["book_title"]})
    return list(authors.values())
```

**SQLAlchemy — antes**

```python
result = []
for author in Author.query.all():
    data = author.to_dict()
    data["book_count"] = Book.query.filter_by(author_id=author.id).count()
    result.append(data)
```

**SQLAlchemy — depois**

```python
from sqlalchemy import func, select

stmt = (
    select(Author, func.count(Book.id).label("book_count"))
    .outerjoin(Book, Book.author_id == Author.id)
    .group_by(Author.id)
    .order_by(Author.id)
)
result = [{**author.to_dict(), "book_count": count} for author, count in db.session.execute(stmt).all()]
```

**JavaScript — antes**

```js
db.all('SELECT id, name FROM authors', [], (err, authors) => {
  let pending = authors.length;
  authors.forEach((author) => {
    db.all('SELECT id, title FROM books WHERE author_id = ?', [author.id], (err2, books) => {
      author.books = books;
      if (--pending === 0) res.json(authors);
    });
  });
});
```

**JavaScript — depois**

```js
async function listAuthorsWithBooks(db) {
  const rows = await all(db, `
    SELECT a.id AS author_id, a.name AS author_name, b.id AS book_id, b.title AS book_title
    FROM authors a
    LEFT JOIN books b ON b.author_id = a.id
    ORDER BY a.id, b.id`);
  const authors = new Map();
  for (const row of rows) {
    if (!authors.has(row.author_id)) {
      authors.set(row.author_id, { id: row.author_id, name: row.author_name, books: [] });
    }
    if (row.book_id !== null) {
      authors.get(row.author_id).books.push({ id: row.book_id, title: row.book_title });
    }
  }
  return [...authors.values()];
}
```

**Cuidados:** preserve entidades sem filhos (por isso `LEFT/OUTER JOIN`), a ordem dos itens e os nomes dos campos. Se o original não definia `ORDER BY`, a ordem observada na linha de base é a referência; registre se ela mudar. Agregações (somas, contagens) devem produzir os mesmos valores, inclusive zero. No exemplo Node "antes", uma lista vazia nunca responde — se o original tinha esse defeito, registre a correção.

**Validação:** respostas idênticas à linha de base (comparação de JSON normalizado), incluindo casos com entidade sem filhos; contagem de consultas por inspeção do código (1 em vez de 1 + N).

---

## T-10 — Validação centralizada de entrada

**Trata:** AP-13, AP-14. **Pressupostos:** `ValidationError`/`HttpError` de T-12; regras e mensagens ilustrativas.

**Python — antes**

```python
def create_book():
    data = request.get_json()
    if "title" not in data or "copies" not in data:
        return jsonify({"error": "Campos obrigatórios"}), 400
    if len(data["title"]) < 2:
        return jsonify({"error": "Título curto"}), 400
    if data["copies"] < 0:
        return jsonify({"error": "Cópias inválidas"}), 400
    ...


def update_book(book_id):
    data = request.get_json()
    if "copies" in data and data["copies"] < 0:
        return jsonify({"error": "Cópias inválidas"}), 400
    ...
```

**Python — depois (`models/book_rules.py`)**

```python
from errors import ValidationError

TITLE_MIN_LENGTH = 2
REQUIRED_FIELDS = ("title", "copies")


def validate_book(data, *, partial=False):
    if not isinstance(data, dict):
        raise ValidationError("Corpo JSON inválido")
    if not partial:
        missing = [field for field in REQUIRED_FIELDS if field not in data]
        if missing:
            raise ValidationError("Campos obrigatórios")
    if "title" in data and (not isinstance(data["title"], str) or len(data["title"]) < TITLE_MIN_LENGTH):
        raise ValidationError("Título curto")
    if "copies" in data:
        copies = data["copies"]
        if isinstance(copies, bool) or not isinstance(copies, int) or copies < 0:
            raise ValidationError("Cópias inválidas")
    return data
```

Uso: a rota extrai o corpo com `request.get_json(silent=True)` e o repassa ao controller; o controller chama `validate_book(data)` na criação e `validate_book(data, partial=True)` na atualização, antes de acionar o Model.

**JavaScript — antes**

```js
if (!req.body.member_name || !req.body.card) return res.status(400).send('Bad Request');
if (req.body.card.startsWith('4')) { /* ... */ }
```

**JavaScript — depois**

```js
const { HttpError } = require('../errors');

function validateCheckout(body) {
  if (!body || typeof body !== 'object') throw new HttpError(400, 'Bad Request');
  const { member_name: memberName, card } = body;
  if (typeof memberName !== 'string' || memberName.trim() === '') throw new HttpError(400, 'Bad Request');
  if (typeof card !== 'string' || card.trim() === '') throw new HttpError(400, 'Bad Request');
  return { memberName, card };
}
```

**Cuidados:** as regras de validação do domínio ficam junto ao Model (aqui, `models/book_rules.py`); o controller as invoca na entrada do caso de uso; a rota só extrai o corpo. Preserve mensagens, status e tipos aceitos pelo contrato original (ex.: se clientes enviam IDs como texto, não passe a rejeitá-los sem aprovação). Unificar regras divergentes muda o comportamento da operação que era mais permissiva: liste isso como mudança de contrato no plano. `bool` é subclasse de `int` em Python, por isso a checagem explícita.

**Validação:** entradas válidas da linha de base continuam aceitas com a mesma resposta; entradas inválidas (campo ausente, tipo errado, valor fora da faixa, corpo vazio) retornam 4xx controlado em vez de 500.

---

## T-11 — Migrar API obsoleta

**Trata:** AP-15. **Pressupostos:** a obsolescência foi confirmada na documentação oficial da versão pertinente durante a Fase 2.

**SQLAlchemy 2.x / Flask-SQLAlchemy 3.x — antes** (método do Model)

```python
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    @classmethod
    def find_by_id(cls, book_id):
        return cls.query.get(book_id)
```

**Depois**

```python
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    @classmethod
    def find_by_id(cls, book_id):
        return db.session.get(cls, book_id)
```

Ambos retornam `None` quando o registro não existe; o controller continua sinalizando o 404 como antes. Se a chamada legada estiver em rotas ou controllers, mova-a para o Model durante a migração (T-06).

**Python 3.12+ `datetime.utcnow()` — antes**

```python
from datetime import datetime

created_at = datetime.utcnow()
```

**Depois (preservando datetimes ingênuos já armazenados)**

```python
from datetime import datetime, timezone

created_at = datetime.now(timezone.utc).replace(tzinfo=None)
```

Usar `datetime.now(timezone.utc)` sem `replace` produz datetime com fuso; compará-lo com valores ingênuos gravados no banco gera `TypeError`. Só adote valores com fuso se todo o fluxo for migrado.

**Express 4 — antes**

```js
res.send(404, 'Not found');
const id = req.param('id');
```

**Depois**

```js
res.status(404).send('Not found');
const id = req.params.id;
```

**Cuidados:** migre apenas o que a documentação confirma; não generalize para APIs vizinhas. Preserve o tratamento de `None`/`undefined` e os status de resposta.

**Validação:** os endpoints afetados retornam o mesmo da linha de base, incluindo o caso de registro inexistente; a busca por ocorrências da API antiga (`grep`) não retorna resultados no código do projeto.

---

## T-12 — Tratamento de erros centralizado

**Trata:** AP-16. **Pressupostos:** Flask 3; Express 4 (erros de funções `async` exigem `asyncHandler`).

**Python — antes**

```python
@book_bp.route("/books", methods=["POST"])
def create_book():
    try:
        ...
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

**Python — depois (`errors.py`)**

```python
from flask import jsonify
from werkzeug.exceptions import HTTPException


class DomainError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class ValidationError(DomainError):
    status_code = 400


class NotFoundError(DomainError):
    status_code = 404


def register_error_handlers(app):
    @app.errorhandler(DomainError)
    def handle_domain_error(error):
        return jsonify({"error": error.message}), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        return jsonify({"error": error.description}), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Erro não tratado")
        return jsonify({"error": "Erro interno do servidor"}), 500
```

**JavaScript — antes**

```js
app.get('/api/books/:id', (req, res) => {
  db.get('SELECT id, title FROM books WHERE id = ?', [req.params.id], (err, row) => {
    if (err) return res.status(500).send(err.message);
    if (!row) return res.status(404).send('Not found');
    res.json(row);
  });
});
```

**JavaScript — depois**

`src/errors.js`

```js
class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

module.exports = { HttpError };
```

`src/middlewares/asyncHandler.js`

```js
function asyncHandler(handler) {
  return (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next);
}

module.exports = { asyncHandler };
```

`src/middlewares/errorHandler.js`

```js
function errorHandler(err, req, res, next) {
  if (res.headersSent) return next(err);
  const status = Number.isInteger(err.status) ? err.status : 500;
  if (status >= 500) console.error(err);
  res.status(status).send(status >= 500 ? 'Internal Server Error' : err.message);
}

module.exports = { errorHandler };
```

Model (`src/models/bookModel.js`, usando o helper `get` de T-05; a consulta mantém as colunas da resposta original):

```js
const { get } = require('../database');

function findTitleById(db, id) {
  return get(db, 'SELECT id, title FROM books WHERE id = ?', [id]);
}

module.exports = { findTitleById };
```

Controller (`src/controllers/bookController.js`):

```js
const { HttpError } = require('../errors');
const bookModel = require('../models/bookModel');

function createBookController(db) {
  return {
    async getBook(id) {
      const book = await bookModel.findTitleById(db, id);
      if (!book) throw new HttpError(404, 'Not found');
      return book;
    },
  };
}

module.exports = { createBookController };
```

Rota (`src/routes/bookRoutes.js`):

```js
const express = require('express');
const { asyncHandler } = require('../middlewares/asyncHandler');

function bookRoutes(bookController) {
  const router = express.Router();
  router.get('/api/books/:id', asyncHandler(async (req, res) => {
    res.json(await bookController.getBook(req.params.id));
  }));
  return router;
}

module.exports = { bookRoutes };
```

A rota só extrai o parâmetro e serializa; o controller decide o 404; o Model executa a consulta. Resposta de sucesso (`{id, title}` em JSON) e 404 (`Not found` em texto) iguais ao "antes"; o 500 deixa de expor `err.message` (correção intencional). Registre `app.use(errorHandler)` **depois** de todas as rotas.

**Cuidados:** o formato do corpo de erro é contrato: adapte as chaves (`error`, `erro`, `message`) e o tipo (JSON ou texto) ao original. Registrar um handler para `HTTPException` muda o 404/405 de rotas inexistentes de HTML para JSON; registre como mudança ou restrinja o handler. Respostas 500 deixam de expor `str(e)`/`err.message`: é uma correção intencional — registre-a.

**Validação:** erros de domínio mantêm status e mensagem da linha de base; um erro inesperado provocado em teste isolado retorna 500 genérico e aparece no log; rotas inexistentes respondem conforme a decisão registrada.

---

## T-13 — Constantes nomeadas, nomes descritivos e remoção de código morto

**Trata:** AP-17, AP-18, AP-19, AP-20.

**Python — antes**

```python
import os
import json


def late_fee(days):
    if days > 30:
        return days * 2.5
    if days > 7:
        return days * 1.0
    return 0
```

**Python — depois**

```python
import logging

logger = logging.getLogger(__name__)

LONG_DELAY_DAYS = 30
SHORT_DELAY_DAYS = 7
LONG_DELAY_DAILY_FEE = 2.5
SHORT_DELAY_DAILY_FEE = 1.0


def late_fee(days_late):
    if days_late > LONG_DELAY_DAYS:
        return days_late * LONG_DELAY_DAILY_FEE
    if days_late > SHORT_DELAY_DAYS:
        return days_late * SHORT_DELAY_DAILY_FEE
    return 0
```

**JavaScript — antes**

```js
const { config, counter } = require('./utils');

function handle(req, res) {
  const u = req.body.usr;
  const e = req.body.eml;
  console.log('novo cadastro ' + e);
  // ...
}
```

**JavaScript — depois**

```js
const { config } = require('./config');

function handleSignup(req, res) {
  const userName = req.body.usr;
  const email = req.body.eml;
  // ...
}
```

**Cuidados:** preserve exatamente valores e operadores de comparação (`>` não vira `>=`). Renomeie apenas identificadores internos; chaves da API (`usr`, `eml` no exemplo) continuam iguais. Antes de remover um símbolo, busque usos no projeto inteiro, incluindo imports com efeito colateral. Se trocar `print`/`console.log` por logger, não registre dados sensíveis. Reutilize constantes já existentes em vez de criar duplicatas.

**Validação:** respostas idênticas à linha de base para entradas nos limites de cada faixa (ex.: 7, 8, 30, 31 dias no exemplo); a aplicação inicia sem `ImportError`/`ReferenceError`.

---

## T-14 — Composition root, app factory e dependências injetáveis

**Trata:** AP-10, AP-11. **Pressupostos:** Flask 3 com `config.py` (T-02), `database.py` (T-07), `errors.py` (T-12); Express 4 com os módulos de T-05/T-12.

**Python — antes (`app.py`)**

```python
from flask import Flask
import database  # cria tabelas e seed ao ser importado

app = Flask(__name__)
app.config["SECRET_KEY"] = "chave-fixa-123"

from routes import *  # registra rotas no app global

if __name__ == "__main__":
    app.run(debug=True)
```

**Python — depois (`app.py`)**

```python
from flask import Flask

import database
from config import load_config
from errors import register_error_handlers
from routes.book_routes import book_bp


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_mapping(load_config())
    if overrides:
        app.config.update(overrides)
    database.init_app(app)
    with app.app_context():
        database.init_schema()
    register_error_handlers(app)
    app.register_blueprint(book_bp)
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=app.config["HOST"], port=app.config["PORT"], debug=app.config["DEBUG"])
```

(`database.init_schema()` é a função que antes rodava na importação, agora chamada explicitamente.)

**Integração externa injetável — Python**

```python
import smtplib
from email.message import EmailMessage


class SmtpNotifier:
    def __init__(self, host, port, sender, timeout=10):
        self.host = host
        self.port = port
        self.sender = sender
        self.timeout = timeout

    def send(self, to, subject, body):
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
            server.send_message(message)


class DisabledNotifier:
    def send(self, to, subject, body):
        return None
```

O composition root escolhe `SmtpNotifier` apenas se a configuração de e-mail estiver presente; caso contrário, `DisabledNotifier`. Falhas de envio devem ser tratadas (timeout, credencial inválida) sem derrubar a operação principal, se esse era o comportamento original. Na validação, use `DisabledNotifier` ou um dublê que só registra chamadas — nunca o servidor real.

**JavaScript — depois (`src/app.js`, preservando `node src/app.js` como start)**

```js
const express = require('express');
const { config } = require('./config');
const { openDatabase, initSchema } = require('./database');
const { createLoanController } = require('./controllers/loanController');
const { loanRoutes } = require('./routes/loanRoutes');
const { errorHandler } = require('./middlewares/errorHandler');

function createApp(db) {
  const app = express();
  app.use(express.json());
  app.use(loanRoutes(createLoanController(db)));
  app.use(errorHandler);
  return app;
}

async function start() {
  const db = openDatabase(config.databasePath);
  await initSchema(db);
  const app = createApp(db);
  app.listen(config.port, () => console.log(`Servidor na porta ${config.port}`));
}

if (require.main === module) {
  start().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { createApp };
```

**Cuidados:** mantenha o comando de inicialização documentado; se o schema/seed era criado na inicialização, continue criando (agora de forma explícita). Não introduza containers de DI ou bibliotecas novas sem necessidade.

**Validação:** o comando original inicia a aplicação sem erros; importar o módulo (em ambiente isolado) não cria banco nem abre conexões externas; todos os endpoints respondem como na linha de base.

---

## T-15 — Proteger ou remover operações administrativas

**Trata:** AP-06. **Pressupostos:** a decisão (proteger, desabilitar por padrão ou remover) foi tomada pelo usuário na confirmação; token administrativo vem de variável de ambiente.

**Python — antes**

```python
@app.route("/admin/reset", methods=["POST"])
def reset_database():
    database.drop_and_recreate()
    return jsonify({"ok": True}), 200
```

**Python — depois**

```python
import hmac
from functools import wraps

from flask import current_app, request

from errors import DomainError


def require_admin_token(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("ADMIN_TOKEN")
        if not expected:
            raise DomainError("Operação administrativa desabilitada", 403)
        provided = request.headers.get("X-Admin-Token", "")
        if not hmac.compare_digest(provided, expected):
            raise DomainError("Não autorizado", 401)
        return view(*args, **kwargs)

    return wrapper


@admin_bp.route("/admin/reset", methods=["POST"])
@require_admin_token
def reset_database():
    admin_controller.reset_database()
    return jsonify({"ok": True}), 200
```

(Acrescente `"ADMIN_TOKEN": os.environ.get("ADMIN_TOKEN")` em `load_config()`.)

**JavaScript — depois**

```js
const crypto = require('node:crypto');
const { HttpError } = require('../errors');

function requireAdminToken(expectedToken) {
  return (req, res, next) => {
    if (!expectedToken) return next(new HttpError(403, 'Operação administrativa desabilitada'));
    const provided = Buffer.from(req.get('X-Admin-Token') || '');
    const expected = Buffer.from(expectedToken);
    if (provided.length !== expected.length || !crypto.timingSafeEqual(provided, expected)) {
      return next(new HttpError(401, 'Não autorizado'));
    }
    return next();
  };
}

module.exports = { requireAdminToken };
```

Uso: `router.delete('/api/members/:id', requireAdminToken(config.adminToken), asyncHandler(...))`.

**Cuidados:** um endpoint que executa SQL ou comandos arbitrários não fica seguro apenas com token; recomende removê-lo e só mantenha se o usuário decidir explicitamente. Toda proteção nova é mudança de contrato: documente-a, inclusive como chamar o endpoint na validação.

**Validação:** sem token configurado → 403; token incorreto → 401; token correto → mesmo efeito da linha de base (verificado no banco isolado).

---

## Validação do comportamento (Fase 3)

Procedimento geral, adaptável à stack. Registre todos os comandos executados e suas saídas resumidas.

### 1. Ambiente isolado

```bash
BASE="$(mktemp -d)"
cp -a <alvo> "$BASE/original"
rm -rf "$BASE/original/node_modules" "$BASE/original/.venv" "$BASE/original/venv"
find "$BASE/original" -name '*.db' -delete
```

- A linha de base roda **na cópia**, nunca no diretório do projeto; bancos e arquivos gerados ficam no diretório temporário.
- Dependências: Python → `python3 -m venv "$BASE/venv"` e `"$BASE/venv/bin/pip" install -r "$BASE/original/requirements.txt"`; Node → `npm ci` na cópia (ou `npm install` se não houver lockfile). Isso exige rede para os registros de pacotes; se não houver acesso, registre a limitação. Não instale no ambiente global.
- Registre as versões **instaladas** obtidas (`pip show`, `npm ls --depth=0`) e compare com as declaradas.
- Integrações externas: execute sem credenciais reais (variáveis vazias ou apontando para endereço inválido local) e não chame endpoints que disparem envio real; se for inevitável, registre o endpoint como "não verificado" ou use dublê.

### 2. Inicialização e porta

- Verifique se a porta está livre (`ss -ltn | grep :<porta>`); se o código fixa a porta, use-a apenas se livre. Se ler `PORT`, use uma porta alternativa.
- Inicie em segundo plano com o log redirecionado (`> "$BASE/original.log" 2>&1 &`), guarde o PID e aguarde a prontidão com tentativas limitadas (ex.: `curl` a cada 1 s por até 30 s).
- Falha de inicialização na linha de base é um **problema preexistente**: registre-o.

### 3. Matriz de endpoints

Para **cada** endpoint mapeado na Fase 1, registre ao menos:

| Método | Caminho | Entrada | Status | Corpo (normalizado) | Efeito nos dados |
|---|---|---|---|---|---|

- Casos: sucesso, recurso inexistente, entrada inválida (quando aplicável).
- Escritas: confirme o efeito com uma leitura posterior (GET ou consulta ao banco de teste).
- Destrutivos (reset, delete): execute por último ou recrie o ambiente.
- Normalize campos variáveis (timestamps, IDs gerados) antes de comparar.
- Use `curl -s -o body.json -w '%{http_code}'` ou o cliente de teste do framework (`app.test_client()` no Flask) **na cópia isolada**.

### 4. Execução após a refatoração

- Copie o projeto refatorado para `"$BASE/refatorado"` (mesmo procedimento) e repita a matriz com as mesmas entradas. Assim, a validação não cria bancos no repositório.
- Valide também após cada transformação relevante (ex.: rodar a matriz parcial dos endpoints afetados).

### 5. Comparação e classificação

Para cada diferença: **correção intencional documentada** (ex.: campo sensível removido, 500 virou 400 controlado, endpoint administrativo protegido) ou **regressão** (corrigir antes de concluir). Sem diferença → "preservado".

### 6. Preservar evidências (antes de qualquer limpeza)

Grave as evidências no destino acordado na Fase 2 (padrão: `reports/evidence/<nome-do-projeto>/`, relativo à raiz do repositório), **em arquivos separados** do relatório de auditoria — que permanece como foi aprovado. Conteúdo mínimo:

- `validation.md`: data, commit de referência, comandos executados (na ordem) com resultado resumido, versões de runtime e de dependências **instaladas** na linha de base e após a refatoração, matriz de endpoints antes × depois com a classificação de cada diferença, resultado da nova inspeção dos achados, limitações e problemas remanescentes.
- `logs/`: apenas trechos pertinentes dos logs de inicialização e de erro (não arquivos inteiros sem revisão), da linha de base e da versão refatorada.

Antes de gravar, **remova dados sensíveis** de comandos, corpos, cabeçalhos e logs: senhas (inclusive as de teste), hashes de senha, tokens, chaves (`SECRET_KEY`, chaves de gateway), cabeçalhos `Authorization`/`X-Admin-Token`, números de cartão e valores de variáveis de ambiente secretas. Substitua por `<removido>` mantendo a estrutura (ex.: `"password": "<removido>"`), para que a evidência continue legível. Releia os arquivos gravados procurando esses padrões antes de seguir.

### 7. Encerramento (somente após o passo 6)

- Encerre os processos iniciados (`kill <PID>`) e confirme que a porta foi liberada.
- Remova o diretório temporário, a menos que o usuário peça para mantê-lo.
- Verifique com `git status --porcelain` que só os arquivos esperados foram alterados no repositório (código refatorado, relatório e evidências) e que nenhum banco ou dependência foi criado nele.
- Não faça commit nem push.
