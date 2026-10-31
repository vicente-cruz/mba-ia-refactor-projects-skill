'use strict';
// Testes controlados do refatorado: rollback, intercalação controlada por "portões", liberação da fila,
// autorização, D-3(b), D-4(a), D-6 (seed) e semântica do relatório.
// Uso: REF_DIR=<dir-da-copia-refatorada> node --test concurrency_rollback.test.js
// Cada teste usa um banco :memory: próprio; models são substituídos por injeção (createApp(..., { models })).

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { secrets, startRefactored, http, counts, sleep } = require('./lib');

const dir = process.env.REF_DIR;
if (!dir) throw new Error('defina REF_DIR');
const model = (name) => require(path.join(dir, 'src', 'models', name));
const { openDatabase, createDataAccess, initSchema, closeDatabase } = require(path.join(dir, 'src', 'database.js'));
const { hashPassword } = require(path.join(dir, 'src', 'passwordHash.js'));

const admin = { 'X-Admin-Token': secrets.adminToken };
const body = (overrides = {}) => ({
  usr: 'Guilherme', eml: 'gui@fullcycle.com.br', pwd: secrets.userPassword, c_id: 2, card: secrets.approvedCard, ...overrides,
});
const report = (inst) => http(inst.baseUrl, 'GET', '/api/admin/financial-report', { headers: admin });
const checkout = (inst, b) => http(inst.baseUrl, 'POST', '/api/checkout', { body: b });
const del = (inst, id, headers = admin) => http(inst.baseUrl, 'DELETE', `/api/users/${id}`, { headers });

function deferred() {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
}
function track(promise) {
  const state = { settled: false, value: undefined };
  state.done = promise.then((v) => { state.settled = true; state.value = v; return v; });
  return state;
}
async function usersWithEmail(inst, email) {
  return (await inst.query('SELECT COUNT(*) AS n FROM users WHERE email = ?', [email]))[0].n;
}
async function orphanEnrollments(inst) {
  return (await inst.query('SELECT COUNT(*) AS n FROM enrollments e LEFT JOIN users u ON u.id = e.user_id WHERE u.id IS NULL'))[0].n;
}
async function withInstance(options, fn) {
  const inst = await startRefactored(dir, options);
  try { await fn(inst); } finally { await inst.close(); }
}

// ---------------- R-01 rollback por ponto de falha ----------------
for (const [table, message] of [
  ['users', 'Erro ao criar usuário'],
  ['enrollments', 'Erro Matrícula'],
  ['payments', 'Erro Pagamento'],
  ['audit_logs', 'Erro Auditoria'],
]) {
  test(`R-01 falha em ${table} desfaz todas as escritas do checkout`, () => withInstance({}, async (inst) => {
    await inst.exec(`CREATE TRIGGER f BEFORE INSERT ON ${table} BEGIN SELECT RAISE(ABORT, 'falha induzida'); END`);
    const before = await counts(inst);
    const res = await checkout(inst, body({ eml: `r01-${table}@teste.com` }));
    assert.equal(res.status, 500);
    assert.equal(res.body, message);
    assert.deepEqual(await counts(inst), before);
    assert.equal(await usersWithEmail(inst, `r01-${table}@teste.com`), 0);
    await inst.exec('DROP TRIGGER f');
    assert.equal((await checkout(inst, body({ eml: `r01-${table}-ok@teste.com` }))).status, 200, 'fila liberada');
  }));
}

test('R-01 falha no COMMIT desfaz as escritas e responde 500 Erro DB', async () => {
  let armed = false;
  const wrapDb = (db) => ({
    run(sql, params, cb) {
      if (armed && sql === 'COMMIT') {
        armed = false;
        setImmediate(() => cb.call({}, new Error('commit induzido')));
        return this;
      }
      return db.run(sql, params, cb);
    },
    get: (...args) => db.get(...args),
    all: (...args) => db.all(...args),
    close: (...args) => db.close(...args),
  });
  await withInstance({ wrapDb }, async (inst) => {
    const before = await counts(inst);
    armed = true;
    const res = await checkout(inst, body({ eml: 'commit@teste.com' }));
    assert.equal(res.status, 500);
    assert.equal(res.body, 'Erro DB');
    assert.deepEqual(await counts(inst), before);
    assert.equal(await usersWithEmail(inst, 'commit@teste.com'), 0);
  });
});

// ---------------- R-02 / R-03 relatório durante checkout ----------------
function gatedPayment({ fail }) {
  const real = model('paymentModel.js');
  const reached = deferred();
  const gate = deferred();
  const paymentModel = {
    ...real,
    async create(db, args) {
      const id = await real.create(db, args);
      reached.resolve();
      await gate.promise;
      if (fail) throw new Error('falha após inserir pagamento');
      return id;
    },
  };
  return { paymentModel, reached, gate };
}

test('R-02 relatório durante checkout que depois falha só vê dados confirmados', async () => {
  const g = gatedPayment({ fail: true });
  await withInstance({ models: { paymentModel: g.paymentModel } }, async (inst) => {
    const reportBefore = await report(inst);
    const before = await counts(inst);
    const pendingCheckout = track(checkout(inst, body({ eml: 'r02@teste.com' })));
    await g.reached.promise; // matrícula e pagamento inseridos, transação aberta
    const pendingReport = track(report(inst));
    await sleep(300);
    assert.equal(pendingReport.settled, false, 'relatório deve aguardar o fim da transação');
    g.gate.resolve();
    const co = await pendingCheckout.done;
    const rep = await pendingReport.done;
    assert.equal(co.status, 500);
    assert.equal(co.body, 'Erro Pagamento');
    assert.equal(rep.status, 200);
    assert.deepEqual(rep.body, reportBefore.body, 'relatório idêntico ao anterior (rollback)');
    assert.deepEqual(await counts(inst), before);
  });
});

test('R-03 relatório durante checkout que conclui vê o estado completo, nunca parcial', async () => {
  const g = gatedPayment({ fail: false });
  await withInstance({ models: { paymentModel: g.paymentModel } }, async (inst) => {
    const pendingCheckout = track(checkout(inst, body({ eml: 'r03@teste.com', usr: 'R03' })));
    await g.reached.promise;
    const pendingReport = track(report(inst));
    await sleep(300);
    assert.equal(pendingReport.settled, false);
    g.gate.resolve();
    assert.equal((await pendingCheckout.done).status, 200);
    const rep = await pendingReport.done;
    const docker = rep.body.find((c) => c.course === 'Docker');
    assert.deepEqual(docker, { course: 'Docker', revenue: 497, students: [{ student: 'R03', paid: 497 }] });
  });
});

// ---------------- R-04 checkouts simultâneos com mesmo e-mail ----------------
test('R-04 dois checkouts simultâneos com mesmo e-mail novo criam 1 usuário (intercalação forçada)', async () => {
  const real = model('userModel.js');
  const reached = deferred();
  const gate = deferred();
  let calls = 0;
  const userModel = {
    ...real,
    async findIdByEmail(db, email) {
      const row = await real.findIdByEmail(db, email);
      calls += 1;
      if (calls === 1) { reached.resolve(); await gate.promise; }
      return row;
    },
  };
  await withInstance({ models: { userModel } }, async (inst) => {
    const before = await counts(inst);
    const first = track(checkout(inst, body({ eml: 'r04@teste.com' })));
    await reached.promise; // primeira operação já decidiu "usuário novo"
    const second = track(checkout(inst, body({ eml: 'r04@teste.com', c_id: 1 })));
    await sleep(200);
    assert.equal(second.settled, false, 'segundo checkout aguarda a fila');
    gate.resolve();
    assert.equal((await first.done).status, 200);
    assert.equal((await second.done).status, 200);
    assert.equal(await usersWithEmail(inst, 'r04@teste.com'), 1);
    const after = await counts(inst);
    assert.equal(after.enrollments - before.enrollments, 2);
    assert.equal(after.payments - before.payments, 2);
  });
});

test('R-04 dois checkouts disparados juntos (sem portão) criam 1 usuário', () => withInstance({}, async (inst) => {
  for (let trial = 0; trial < 10; trial += 1) {
    const email = `r04b-${trial}@teste.com`;
    const results = await Promise.all([checkout(inst, body({ eml: email })), checkout(inst, body({ eml: email }))]);
    assert.deepEqual(results.map((r) => r.status), [200, 200]);
    assert.equal(await usersWithEmail(inst, email), 1);
  }
}));

// ---------------- R-05 checkout e DELETE simultâneos ----------------
test('R-05 checkout em andamento + DELETE do mesmo usuário: DELETE espera e recebe 409; sem órfãos', async () => {
  const real = model('enrollmentModel.js');
  const reached = deferred();
  const gate = deferred();
  const enrollmentModel = {
    ...real,
    async create(db, args) {
      const id = await real.create(db, args);
      reached.resolve();
      await gate.promise;
      return id;
    },
  };
  await withInstance({ models: { enrollmentModel } }, async (inst) => {
    await inst.exec("INSERT INTO users (name, email, pass) VALUES ('R05', 'r05@teste.com', NULL)");
    const [{ id }] = await inst.query("SELECT id FROM users WHERE email = 'r05@teste.com'");
    const co = track(checkout(inst, body({ eml: 'r05@teste.com' })));
    await reached.promise;
    const d = track(del(inst, id));
    await sleep(200);
    assert.equal(d.settled, false);
    gate.resolve();
    assert.equal((await co.done).status, 200);
    const delRes = await d.done;
    assert.equal(delRes.status, 409);
    assert.equal(delRes.body, 'Usuário possui matrículas');
    assert.equal(await orphanEnrollments(inst), 0);
  });
});

test('R-05 DELETE em andamento + checkout do mesmo e-mail: checkout cria novo usuário depois; sem órfãos', async () => {
  const real = model('userModel.js');
  const reached = deferred();
  const gate = deferred();
  const userModel = {
    ...real,
    async deleteById(db, userId) {
      await real.deleteById(db, userId);
      reached.resolve();
      await gate.promise;
    },
  };
  await withInstance({ models: { userModel } }, async (inst) => {
    await inst.exec("INSERT INTO users (name, email, pass) VALUES ('R05b', 'r05b@teste.com', NULL)");
    const [{ id }] = await inst.query("SELECT id FROM users WHERE email = 'r05b@teste.com'");
    const d = track(del(inst, id));
    await reached.promise;
    const co = track(checkout(inst, body({ eml: 'r05b@teste.com' })));
    await sleep(200);
    assert.equal(co.settled, false);
    gate.resolve();
    assert.equal((await d.done).status, 200);
    assert.equal((await co.done).status, 200);
    // INTEGER PRIMARY KEY sem AUTOINCREMENT (schema original) reaproveita o maior rowid excluído,
    // por isso o id pode coincidir; a recriação é provada pelo nome (vindo do checkout) e pela matrícula.
    const rows = await inst.query("SELECT id, name FROM users WHERE email = 'r05b@teste.com'");
    assert.equal(rows.length, 1);
    assert.equal(rows[0].name, 'Guilherme', 'usuário recriado pelo checkout');
    const enrollments = await inst.query('SELECT COUNT(*) AS n FROM enrollments WHERE user_id = ?', [rows[0].id]);
    assert.equal(enrollments[0].n, 1);
    assert.equal(await orphanEnrollments(inst), 0);
    assert.ok(Number.isInteger(id));
  });
});

// ---------------- R-07 liberação da fila após erros ----------------
test('R-07 fila liberada após erro de validação, de domínio e inesperado', async () => {
  const real = model('courseModel.js');
  let explode = false;
  const courseModel = {
    ...real,
    async findActiveById(db, id) {
      if (explode) { explode = false; throw new TypeError('erro inesperado induzido'); }
      return real.findActiveById(db, id);
    },
  };
  await withInstance({ models: { courseModel } }, async (inst) => {
    assert.equal((await checkout(inst, body({ card: 123 }))).status, 400);
    assert.equal((await checkout(inst, body({ c_id: 999 }))).status, 404);
    assert.equal((await checkout(inst, body({ card: secrets.deniedCard, eml: 'r07d@teste.com' }))).status, 400);
    explode = true;
    const unexpected = await checkout(inst, body({ eml: 'r07x@teste.com' }));
    assert.equal(unexpected.status, 500);
    assert.equal(unexpected.body, 'Erro DB');
    const ok = await Promise.race([checkout(inst, body({ eml: 'r07ok@teste.com' })), sleep(3000).then(() => 'timeout')]);
    assert.notEqual(ok, 'timeout', 'fila travada');
    assert.equal(ok.status, 200);
    assert.equal((await report(inst)).status, 200);
  });
});

// ---------------- R-08 handle expirado e operação aninhada ----------------
test('R-08 handle expirado e operação aninhada lançam erro sem travar a fila', async () => {
  const db = await openDatabase(':memory:');
  const dataAccess = createDataAccess(db);
  try {
    const leaked = await dataAccess.read(async (h) => h);
    await assert.rejects(() => leaked.get('SELECT 1'), /Handle de banco expirado/);
    await assert.rejects(() => dataAccess.read(() => dataAccess.read(async () => 1)), /aninhada/);
    await assert.rejects(() => dataAccess.transaction(() => dataAccess.transaction(async () => 1)), /aninhada/);
    const value = await Promise.race([dataAccess.read((h) => h.get('SELECT 42 AS v')), sleep(2000).then(() => 'timeout')]);
    assert.deepEqual(value, { v: 42 });
  } finally {
    await closeDatabase(db);
  }
});

// ---------------- R-09 autorização ----------------
test('R-09 sem ADMIN_TOKEN configurado: 403 e nenhum efeito', () => withInstance({ adminToken: null }, async (inst) => {
  const before = await counts(inst);
  for (const res of [await report(inst), await del(inst, 1), await del(inst, 1, {})]) {
    assert.equal(res.status, 403);
    assert.equal(res.body, 'Operação administrativa desabilitada');
  }
  assert.deepEqual(await counts(inst), before);
}));

test('R-09 com ADMIN_TOKEN: ausente/incorreto → 401 sem efeito; correto → contrato do endpoint', () => withInstance({}, async (inst) => {
  await inst.exec("INSERT INTO users (name, email, pass) VALUES ('R09', 'r09@teste.com', NULL)");
  const [{ id }] = await inst.query("SELECT id FROM users WHERE email = 'r09@teste.com'");
  const before = await counts(inst);
  const wrongSameLength = `${secrets.adminToken.slice(0, -1)}${secrets.adminToken.endsWith('0') ? '1' : '0'}`;
  for (const headers of [{}, { 'X-Admin-Token': wrongSameLength }, { 'X-Admin-Token': 'curto' }, { 'X-Admin-Token': '' }]) {
    for (const res of [await http(inst.baseUrl, 'GET', '/api/admin/financial-report', { headers }), await del(inst, id, headers)]) {
      assert.equal(res.status, 401);
      assert.equal(res.body, 'Não autorizado');
    }
  }
  assert.deepEqual(await counts(inst), before);
  assert.equal((await report(inst)).status, 200);
  const ok = await del(inst, id);
  assert.equal(ok.status, 200);
  assert.equal(ok.body, 'Usuário deletado');
}));

// ---------------- R-10 D-3(b) ----------------
test('R-10 DELETE: com matrículas 409 sem alterações; sem matrículas 200; inválido 400; inexistente 404', () => withInstance({}, async (inst) => {
  const before = await counts(inst);
  const conflict = await del(inst, 1);
  assert.equal(conflict.status, 409);
  assert.equal(conflict.body, 'Usuário possui matrículas');
  assert.deepEqual(await counts(inst), before);
  for (const bad of ['0', '-1', '1.5', '01', 'abc', '1e3']) {
    const res = await del(inst, bad);
    assert.equal(res.status, 400, bad);
    assert.equal(res.body, 'ID inválido');
  }
  const missing = await del(inst, 9999);
  assert.equal(missing.status, 404);
  assert.equal(missing.body, 'Usuário não encontrado');
  await inst.exec("INSERT INTO users (name, email, pass) VALUES ('R10', 'r10@teste.com', NULL)");
  const [{ id }] = await inst.query("SELECT id FROM users WHERE email = 'r10@teste.com'");
  const ok = await del(inst, id);
  assert.equal(ok.status, 200);
  assert.equal(ok.body, 'Usuário deletado');
  assert.equal(await usersWithEmail(inst, 'r10@teste.com'), 0);
}));

// ---------------- R-11 D-4(a) ----------------
test('R-11 senha exigida só para usuário novo; existente ignora pwd', () => withInstance({}, async (inst) => {
  const before = await counts(inst);
  for (const pwd of [undefined, null, '', secrets.numericPassword, true, {}, []]) {
    const res = await checkout(inst, body({ eml: 'r11-novo@teste.com', pwd }));
    assert.equal(res.status, 400, `pwd=${JSON.stringify(pwd)}`);
    assert.equal(res.body, 'Bad Request');
  }
  assert.deepEqual(await counts(inst), before, 'nenhuma escrita nos casos 400');
  const [{ pass: passBefore }] = await inst.query('SELECT pass FROM users WHERE id = 1');
  for (const pwd of [undefined, secrets.numericPassword, '', 'outra-senha']) {
    const res = await checkout(inst, body({ eml: 'leonan@fullcycle.com.br', pwd }));
    assert.equal(res.status, 200, `existente pwd=${typeof pwd}`);
  }
  const [{ pass: passAfter }] = await inst.query('SELECT pass FROM users WHERE id = 1');
  assert.equal(passAfter, passBefore, 'senha do existente intacta');
  const created = await checkout(inst, body({ eml: 'r11-ok@teste.com', pwd: ' ' }));
  assert.equal(created.status, 200, 'string com espaço é senha válida');
  const [{ pass }] = await inst.query("SELECT pass FROM users WHERE email = 'r11-ok@teste.com'");
  assert.match(pass, /^scrypt\$[0-9a-f]{32}\$[0-9a-f]{128}$/);
}));

test('R-11 usuário novo sem senha e com cartão recusado: prevalece 400 Bad Request', () => withInstance({}, async (inst) => {
  const res = await checkout(inst, body({ eml: 'r11-recusado@teste.com', pwd: undefined, card: secrets.deniedCard }));
  assert.equal(res.status, 400);
  assert.equal(res.body, 'Bad Request');
}));

// ---------------- R-12 D-6 seed ----------------
test('R-12 seed: usuário 1, matrícula 1 e pagamento 1 preservados; senha em scrypt', () => withInstance({}, async (inst) => {
  const [user] = await inst.query('SELECT id, name, email, pass FROM users');
  assert.equal(user.id, 1);
  assert.equal(user.name, 'Leonan');
  assert.equal(user.email, 'leonan@fullcycle.com.br');
  assert.match(user.pass, /^scrypt\$[0-9a-f]{32}\$[0-9a-f]{128}$/);
  assert.notEqual(user.pass, '123');
  assert.deepEqual(await inst.query('SELECT id, user_id, course_id FROM enrollments'), [{ id: 1, user_id: 1, course_id: 1 }]);
  assert.deepEqual(await inst.query('SELECT id, enrollment_id, amount, status FROM payments'), [{ id: 1, enrollment_id: 1, amount: 997, status: 'PAID' }]);
  assert.deepEqual(await inst.query('SELECT id, title, price, active FROM courses'), [
    { id: 1, title: 'Clean Architecture', price: 997, active: 1 }, { id: 2, title: 'Docker', price: 497, active: 1 }]);
}));

test('R-12 falha no meio do seed não deixa schema nem dados parciais', async () => {
  const db = await openDatabase(':memory:');
  const wrapped = {
    run(sql, params, cb) {
      if (sql.startsWith('INSERT INTO payments')) {
        setImmediate(() => cb.call({}, new Error('falha induzida no seed')));
        return this;
      }
      return db.run(sql, params, cb);
    },
    get: (...args) => db.get(...args),
    all: (...args) => db.all(...args),
  };
  try {
    await assert.rejects(() => initSchema(createDataAccess(wrapped), { seedPasswordHash: 'x' }), /falha induzida no seed/);
    const tables = await new Promise((resolve, reject) =>
      db.all("SELECT name FROM sqlite_master WHERE type = 'table'", (err, rows) => (err ? reject(err) : resolve(rows))));
    assert.deepEqual(tables, []);
  } finally {
    await closeDatabase(db);
  }
  assert.equal(typeof hashPassword, 'function');
});

// ---------------- R-13 semântica do relatório ----------------
test('R-13 revenue só soma PAID; paid mostra qualquer pagamento; sem pagamento → 0; curso vazio; Unknown; menor id', () => withInstance({}, async (inst) => {
  await inst.exec("INSERT INTO courses (title, price, active) VALUES ('Kubernetes', 1497.00, 1)");
  await inst.exec("INSERT INTO users (name, email, pass) VALUES ('Aluno Recusado', 'recusado@teste.com', NULL)");
  await inst.exec('INSERT INTO enrollments (user_id, course_id) VALUES (2, 2)');
  await inst.exec("INSERT INTO payments (enrollment_id, amount, status) VALUES (2, 497.00, 'DENIED')");
  await inst.exec('INSERT INTO enrollments (user_id, course_id) VALUES (1, 2)');
  await inst.exec('INSERT INTO enrollments (user_id, course_id) VALUES (999, 2)');
  await inst.exec("INSERT INTO payments (enrollment_id, amount, status) VALUES (4, 100.00, 'PENDING')");
  await inst.exec("INSERT INTO payments (enrollment_id, amount, status) VALUES (1, 10.00, 'PAID')");
  const res = await report(inst);
  assert.deepEqual(res.body, [
    { course: 'Clean Architecture', revenue: 997, students: [{ student: 'Leonan', paid: 997 }] },
    { course: 'Docker', revenue: 0, students: [
      { student: 'Aluno Recusado', paid: 497 }, { student: 'Leonan', paid: 0 }, { student: 'Unknown', paid: 100 }] },
    { course: 'Kubernetes', revenue: 0, students: [] },
  ]);
}));
