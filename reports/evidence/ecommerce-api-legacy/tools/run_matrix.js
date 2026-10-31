'use strict';
// Matriz de endpoints executada contra o original ou o refatorado, com as mesmas entradas.
// Uso: node run_matrix.js <original|refatorado> <dir-da-copia> <saida.json>
// Inclui falhas induzidas por triggers RAISE(ABORT) instaladas após o seed (B-T1..B-T4),
// casos de dados para a semântica do relatório e observações de concorrência não determinísticas.

const fs = require('node:fs');
const { secrets, startOriginal, startRefactored, http, counts, sanitize, findSensitive } = require('./lib');

const [target, dir, outFile] = process.argv.slice(2);
if (!['original', 'refatorado'].includes(target) || !dir || !outFile) {
  console.error('uso: node run_matrix.js <original|refatorado> <dir> <saida.json>');
  process.exit(2);
}

const start = () => (target === 'original' ? startOriginal(dir) : startRefactored(dir));
const admin = () => ({ 'X-Admin-Token': secrets.adminToken });

const checkoutBody = (overrides = {}) => ({
  usr: 'Guilherme',
  eml: 'gui@fullcycle.com.br',
  pwd: secrets.userPassword,
  c_id: 2,
  card: secrets.approvedCard,
  ...overrides,
});

const results = [];

async function step(instance, id, description, method, urlPath, options = {}) {
  const before = await counts(instance);
  const response = await http(instance.baseUrl, method, urlPath, options);
  const after = await counts(instance);
  const request = { method, path: urlPath };
  if (options.body !== undefined) request.body = options.body;
  if (options.rawBody !== undefined) request.rawBody = options.rawBody;
  if (options.headers) request.headers = Object.keys(options.headers);
  results.push({ id, description, request, response, counts: { before, after } });
  return response;
}

async function scenario(name, fn) {
  const instance = await start();
  try {
    await fn(instance);
  } catch (err) {
    results.push({ id: `${name}-ERRO`, description: 'falha do script', error: String(err && err.stack) });
  } finally {
    await instance.close();
  }
}

async function triggerScenario(id, table, body) {
  await scenario(id, async (instance) => {
    await instance.exec(
      `CREATE TRIGGER falha_${table} BEFORE INSERT ON ${table} BEGIN SELECT RAISE(ABORT, 'falha induzida ${table}'); END`,
    );
    await step(instance, id, `checkout com trigger RAISE(ABORT) em ${table}`, 'POST', '/api/checkout', { body });
    const users = await instance.query('SELECT id, name FROM users WHERE email = ?', [body.eml]);
    results[results.length - 1].usersWithEmail = users.length;
  });
}

async function main() {
  // S1 — fluxo do api.http e variações, numa mesma instância (efeitos acumulados).
  await scenario('S1', async (instance) => {
    await step(instance, 'S1-01', 'relatório inicial', 'GET', '/api/admin/financial-report', { headers: admin() });
    await step(instance, 'S1-02', 'checkout usuário novo aprovado (api.http)', 'POST', '/api/checkout', { body: checkoutBody() });
    await step(instance, 'S1-03', 'checkout usuário novo recusado (api.http)', 'POST', '/api/checkout', {
      body: checkoutBody({ usr: 'João', eml: 'joao@teste.com', c_id: 1, card: secrets.deniedCard }),
    });
    const joao = await instance.query('SELECT COUNT(*) AS n FROM users WHERE email = ?', ['joao@teste.com']);
    results[results.length - 1].usersWithEmail = joao[0].n;
    await step(instance, 'S1-04', 'checkout usuário existente sem pwd', 'POST', '/api/checkout', {
      body: checkoutBody({ usr: 'Outro Nome', eml: 'leonan@fullcycle.com.br', pwd: undefined }),
    });
    await step(instance, 'S1-05', 'checkout usuário existente com pwd numérico', 'POST', '/api/checkout', {
      body: checkoutBody({ eml: 'gui@fullcycle.com.br', pwd: secrets.numericPassword, c_id: 1 }),
    });
    await step(instance, 'S1-06', 'relatório após checkouts', 'GET', '/api/admin/financial-report', { headers: admin() });
    await step(instance, 'S1-07', 'checkout sem card', 'POST', '/api/checkout', { body: checkoutBody({ card: undefined }) });
    await step(instance, 'S1-08', 'checkout curso inexistente', 'POST', '/api/checkout', { body: checkoutBody({ c_id: 999 }) });
    await step(instance, 'S1-09', 'checkout c_id como string numérica', 'POST', '/api/checkout', {
      body: checkoutBody({ eml: 'str@teste.com', c_id: '1' }),
    });
    await step(instance, 'S1-10', 'checkout usuário novo sem pwd', 'POST', '/api/checkout', {
      body: checkoutBody({ eml: 'semsenha@teste.com', pwd: undefined }),
    });
    await step(instance, 'S1-11', 'checkout usuário novo com pwd vazio', 'POST', '/api/checkout', {
      body: checkoutBody({ eml: 'vazia@teste.com', pwd: '' }),
    });
    await step(instance, 'S1-12', 'checkout com JSON inválido', 'POST', '/api/checkout', { rawBody: '{"usr": ' });
    await step(instance, 'S1-13', 'DELETE usuário 1 (com matrícula)', 'DELETE', '/api/users/1', { headers: admin() });
    await step(instance, 'S1-14', 'relatório após DELETE 1', 'GET', '/api/admin/financial-report', { headers: admin() });
    await step(instance, 'S1-15', 'DELETE id inexistente', 'DELETE', '/api/users/9999', { headers: admin() });
    await step(instance, 'S1-16', 'DELETE id não numérico', 'DELETE', '/api/users/abc', { headers: admin() });
  });

  // S2 — curso inativo.
  await scenario('S2', async (instance) => {
    await instance.exec('UPDATE courses SET active = 0 WHERE id = 2');
    await step(instance, 'S2-01', 'checkout curso inativo', 'POST', '/api/checkout', { body: checkoutBody() });
  });

  // S3 — exclusão de usuário sem matrículas.
  await scenario('S3', async (instance) => {
    await instance.exec("INSERT INTO users (name, email, pass) VALUES ('Sem Matricula', 'sem@teste.com', NULL)");
    const [{ id }] = await instance.query("SELECT id FROM users WHERE email = 'sem@teste.com'");
    await step(instance, 'S3-01', 'DELETE usuário sem matrículas', 'DELETE', `/api/users/${id}`, { headers: admin() });
  });

  // B-T1..B-T4 — falhas induzidas por triggers instalados após o seed, cada uma em instância própria.
  await triggerScenario('B-T1', 'payments', checkoutBody({ eml: 'bt1@teste.com' }));
  await triggerScenario('B-T2', 'audit_logs', checkoutBody({ eml: 'bt2@teste.com' }));
  await triggerScenario('B-T3', 'users', checkoutBody({ eml: 'bt3@teste.com' }));
  await triggerScenario('B-T4', 'enrollments', checkoutBody({ eml: 'bt4@teste.com' }));

  // S5 — semântica do relatório com dados montados diretamente (R-13).
  await scenario('S5', async (instance) => {
    await instance.exec("INSERT INTO courses (title, price, active) VALUES ('Kubernetes', 1497.00, 1)");
    await instance.exec("INSERT INTO users (name, email, pass) VALUES ('Aluno Recusado', 'recusado@teste.com', NULL)");
    const [{ id: userId }] = await instance.query("SELECT id FROM users WHERE email = 'recusado@teste.com'");
    await instance.exec('INSERT INTO enrollments (user_id, course_id) VALUES (?, 2)', [userId]);
    const [{ id: deniedEnr }] = await instance.query('SELECT MAX(id) AS id FROM enrollments');
    await instance.exec("INSERT INTO payments (enrollment_id, amount, status) VALUES (?, 497.00, 'DENIED')", [deniedEnr]);
    await instance.exec('INSERT INTO enrollments (user_id, course_id) VALUES (1, 2)');
    await instance.exec('INSERT INTO enrollments (user_id, course_id) VALUES (999, 2)');
    const [{ id: orphanEnr }] = await instance.query('SELECT MAX(id) AS id FROM enrollments');
    await instance.exec("INSERT INTO payments (enrollment_id, amount, status) VALUES (?, 100.00, 'PENDING')", [orphanEnr]);
    await instance.exec("INSERT INTO payments (enrollment_id, amount, status) VALUES (1, 10.00, 'PAID')");
    await step(instance, 'S5-01', 'relatório com DENIED, PENDING, sem pagamento, órfã, curso vazio, 2 pagamentos', 'GET',
      '/api/admin/financial-report', { headers: admin() });
  });

  // C-OBS — observações de concorrência não determinísticas (sem pausa controlada).
  await scenario('C-OBS1', async (instance) => {
    const trials = [];
    for (let trial = 0; trial < 10; trial += 1) {
      const email = `dup${trial}@teste.com`;
      await Promise.all([1, 2].map(() =>
        http(instance.baseUrl, 'POST', '/api/checkout', { body: checkoutBody({ eml: email }) })));
      const rows = await instance.query('SELECT COUNT(*) AS n FROM users WHERE email = ?', [email]);
      trials.push(rows[0].n);
    }
    results.push({ id: 'C-OBS1', description: '10 tentativas: 2 checkouts simultâneos com mesmo e-mail novo; usuários criados por tentativa', usersPerTrial: trials });
  });
  await scenario('C-OBS2', async (instance) => {
    const requests = [];
    for (let i = 0; i < 20; i += 1) {
      requests.push(http(instance.baseUrl, 'POST', '/api/checkout', { body: checkoutBody({ eml: `obs${i}@teste.com` }) }));
      requests.push(http(instance.baseUrl, 'GET', '/api/admin/financial-report', { headers: admin() }));
    }
    const responses = await Promise.all(requests);
    const reports = responses.filter((r) => Array.isArray(r.body));
    const partial = reports.filter((r) => r.body.some((c) => c.students.some((s) => s.paid === 0))).length;
    results.push({ id: 'C-OBS2', description: '20 checkouts + 20 relatórios simultâneos; relatórios com aluno paid=0 (estado intermediário)', reports: reports.length, reportsWithPartialState: partial });
  });

  const output = sanitize(JSON.stringify({ target, generatedAt: new Date().toISOString(), results }, null, 2));
  const leaks = findSensitive(output);
  if (leaks.length) throw new Error(`dados sensíveis após sanitização: ${leaks.join(', ')}`);
  fs.writeFileSync(outFile, output);
  console.log(`${results.length} registros gravados em ${outFile}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
