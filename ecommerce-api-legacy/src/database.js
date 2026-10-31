const { AsyncLocalStorage } = require('node:async_hooks');
const sqlite3 = require('sqlite3');

function openDatabase(path) {
    return new Promise((resolve, reject) => {
        const db = new sqlite3.Database(path, (err) => (err ? reject(err) : resolve(db)));
    });
}

function closeDatabase(db) {
    return new Promise((resolve, reject) => db.close((err) => (err ? reject(err) : resolve())));
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

// Handle entregue aos models: só funciona enquanto a operação que o recebeu detém a conexão.
function createHandle(db) {
    let valid = true;
    const ensureValid = () => {
        if (!valid) throw new Error('Handle de banco expirado: use-o apenas dentro da operação que o recebeu');
    };
    return {
        run: async (sql, params) => { ensureValid(); return run(db, sql, params); },
        get: async (sql, params) => { ensureValid(); return get(db, sql, params); },
        all: async (sql, params) => { ensureValid(); return all(db, sql, params); },
        expire: () => { valid = false; },
    };
}

// Acesso exclusivo à conexão única: todas as operações (leituras e transações) passam pela mesma
// fila FIFO, de modo que nenhuma instrução de outra requisição se intercala entre BEGIN e COMMIT
// nem observa dados não confirmados. Trade-off: as operações de banco não rodam em paralelo.
function createDataAccess(db) {
    const operationContext = new AsyncLocalStorage();
    let queue = Promise.resolve();

    function exclusive(work) {
        if (operationContext.getStore()) {
            return Promise.reject(new Error('Operação de banco aninhada não é permitida'));
        }
        const result = queue.then(() => {
            const handle = createHandle(db);
            return operationContext.run(true, async () => {
                try {
                    return await work(handle);
                } finally {
                    handle.expire();
                }
            });
        });
        queue = result.catch(() => {});
        return result;
    }

    function read(work) {
        return exclusive(work);
    }

    function transaction(work) {
        return exclusive(async (handle) => {
            await handle.run('BEGIN');
            try {
                const value = await work(handle);
                await handle.run('COMMIT');
                return value;
            } catch (err) {
                await handle.run('ROLLBACK').catch(() => {});
                throw err;
            }
        });
    }

    return { read, transaction };
}

// Schema e seed explícitos, numa única transação: uma falha no meio não deixa seed parcial.
async function initSchema(dataAccess, { seedPasswordHash }) {
    await dataAccess.transaction(async (db) => {
        await db.run('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, pass TEXT)');
        await db.run('CREATE TABLE courses (id INTEGER PRIMARY KEY, title TEXT, price REAL, active INTEGER)');
        await db.run('CREATE TABLE enrollments (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER)');
        await db.run('CREATE TABLE payments (id INTEGER PRIMARY KEY, enrollment_id INTEGER, amount REAL, status TEXT)');
        await db.run('CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, action TEXT, created_at DATETIME)');

        await db.run('INSERT INTO users (name, email, pass) VALUES (?, ?, ?)', ['Leonan', 'leonan@fullcycle.com.br', seedPasswordHash]);
        await db.run("INSERT INTO courses (title, price, active) VALUES ('Clean Architecture', 997.00, 1), ('Docker', 497.00, 1)");
        await db.run('INSERT INTO enrollments (user_id, course_id) VALUES (1, 1)');
        await db.run("INSERT INTO payments (enrollment_id, amount, status) VALUES (1, 997.00, 'PAID')");
    });
}

module.exports = { openDatabase, closeDatabase, createDataAccess, initSchema };
