'use strict';
// Casos em nível de processo (`node src/app.js`): inicialização, quedas por tipo inválido e configuração (D-6).
// Uso: node process_cases.js <original|refatorado> <dir-da-copia> <saida.json> [porta]
// Cada caso inicia um processo novo. O refatorado recebe SEED_USER_PASSWORD/ADMIN_TOKEN gerados em tempo de execução.

const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { secrets, sleep, sanitize, findSensitive } = require('./lib');

const [target, dir, outFile, portArg] = process.argv.slice(2);
const port = Number(portArg || 3000);
const PRELOAD_FAIL_SEED = path.join(__dirname, 'preload_fail_seed.js');
const PRELOAD_TRACE_OPEN = path.join(__dirname, 'preload_trace_open.js');

function baseEnv(extra = {}) {
  const env = { ...process.env, PORT: String(port) };
  if (target === 'refatorado') {
    env.SEED_USER_PASSWORD = secrets.seedPassword;
    env.ADMIN_TOKEN = secrets.adminToken;
  }
  return { ...env, ...extra };
}

function portOpen() {
  return new Promise((resolve) => {
    const socket = net.connect(port, '127.0.0.1');
    socket.once('connect', () => { socket.destroy(); resolve(true); });
    socket.once('error', () => resolve(false));
  });
}

async function runProcess({ env, preload, action, waitReady = true }) {
  const args = [];
  if (preload) args.push('-r', preload);
  args.push('src/app.js');
  const child = spawn(process.execPath, args, { cwd: dir, env });
  let stdout = '';
  let stderr = '';
  child.stdout.on('data', (d) => { stdout += d; });
  child.stderr.on('data', (d) => { stderr += d; });
  const exited = new Promise((resolve) => child.on('exit', (code, signal) => resolve({ code, signal })));
  let exitInfo = null;
  exited.then((info) => { exitInfo = info; });

  let ready = false;
  for (let i = 0; i < 100 && !exitInfo; i += 1) {
    if (await portOpen()) { ready = true; break; }
    await sleep(50);
  }
  const record = { ready };
  if (ready && action) {
    try {
      record.response = await action();
    } catch (err) {
      record.requestError = String(err.cause ? err.cause.code || err.cause.message : err.message);
    }
    await Promise.race([exited, sleep(1000)]);
  } else if (!waitReady || !ready) {
    await Promise.race([exited, sleep(2000)]);
  }
  record.exitedBeforeKill = Boolean(exitInfo);
  record.exit = exitInfo;
  record.portOpenAfter = exitInfo ? await portOpen() : null;
  if (!exitInfo) {
    child.kill('SIGTERM');
    await exited;
  }
  record.stdout = stdout.split('\n').slice(0, 15).join('\n');
  record.stderr = stderr.split('\n').slice(0, 15).join('\n');
  return record;
}

async function post(body) {
  const res = await fetch(`http://127.0.0.1:${port}/api/checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: await res.text() };
}

async function main() {
  if (await portOpen()) {
    console.error(`porta ${port} ocupada; abortando`);
    process.exit(2);
  }
  const results = [];
  const body = (overrides) => ({ usr: 'Teste', eml: 'k@teste.com', pwd: secrets.userPassword, c_id: 1, card: secrets.approvedCard, ...overrides });

  results.push({ id: 'P-01', description: 'inicialização com configuração completa', ...(await runProcess({ env: baseEnv() })) });
  results.push({ id: 'P-02', description: 'checkout com card numérico e e-mail novo',
    ...(await runProcess({ env: baseEnv(), action: () => post(body({ card: Number(secrets.approvedCard.slice(0, 15)) })) })) });
  results.push({ id: 'P-03', description: 'checkout com pwd numérico e e-mail novo',
    ...(await runProcess({ env: baseEnv(), action: () => post(body({ pwd: secrets.numericPassword })) })) });

  if (target === 'refatorado') {
    const noSeed = baseEnv();
    delete noSeed.SEED_USER_PASSWORD;
    results.push({ id: 'P-04', description: 'sem SEED_USER_PASSWORD (D-6 b); preload registra se sqlite3.Database foi aberto',
      ...(await runProcess({ env: noSeed, preload: PRELOAD_TRACE_OPEN, waitReady: false })) });
    results.push({ id: 'P-05', description: 'SEED_USER_PASSWORD vazia (tratada como ausente)',
      ...(await runProcess({ env: baseEnv({ SEED_USER_PASSWORD: '' }), preload: PRELOAD_TRACE_OPEN, waitReady: false })) });
    results.push({ id: 'P-06', description: 'falha forçada no INSERT de payments durante o seed (preload de teste)',
      ...(await runProcess({ env: baseEnv(), preload: PRELOAD_FAIL_SEED, waitReady: false })) });
    results.push({ id: 'P-07', description: 'PORT inválida',
      ...(await runProcess({ env: baseEnv({ PORT: 'abc' }), preload: PRELOAD_TRACE_OPEN, waitReady: false })) });
  }

  const output = sanitize(JSON.stringify({ target, port, results }, null, 2));
  const leaks = findSensitive(output);
  if (leaks.length) throw new Error(`dados sensíveis após sanitização: ${leaks.join(', ')}`);
  fs.writeFileSync(outFile, output);
  for (const r of results) {
    console.log(r.id, 'ready=', r.ready, 'exit=', JSON.stringify(r.exit), 'resp=', r.response ? `${r.response.status} ${r.response.body}` : r.requestError || '-');
  }
}

main().catch((err) => { console.error(err); process.exit(1); });
