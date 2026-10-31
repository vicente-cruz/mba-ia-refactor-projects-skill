'use strict';
// Utilitários compartilhados pelos scripts de validação.
// Cada instância usa um banco :memory: novo; nada é gravado em disco.
// Dados sensíveis de teste (cartões, senhas, tokens) são gerados em tempo de execução.

const path = require('node:path');
const crypto = require('node:crypto');

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function randomDigits(count) {
  let out = '';
  while (out.length < count) out += crypto.randomInt(0, 10).toString();
  return out;
}

// Segredos de teste gerados por execução (nunca gravados nos arquivos preservados).
const secrets = {
  adminToken: crypto.randomBytes(24).toString('hex'),
  seedPassword: crypto.randomBytes(12).toString('hex'),
  userPassword: crypto.randomBytes(12).toString('hex'),
  approvedCard: `4${randomDigits(15)}`,
  deniedCard: `5${randomDigits(15)}`,
  numericPassword: crypto.randomInt(100000, 1000000),
};

function requireFrom(dir, mod) {
  return require(require.resolve(mod, { paths: [dir] }));
}

function listen(app) {
  return new Promise((resolve) => {
    const server = app.listen(0, '127.0.0.1', () => resolve(server));
  });
}

// --- Original: AppManager instanciado diretamente (o construtor não executa initDb). ---
async function startOriginal(dir) {
  const express = requireFrom(dir, 'express');
  const AppManager = require(path.join(dir, 'src', 'AppManager.js'));
  const manager = new AppManager();
  manager.initDb();
  const { db } = manager;
  const query = (sql, params = []) =>
    new Promise((resolve, reject) => db.all(sql, params, (err, rows) => (err ? reject(err) : resolve(rows))));
  const exec = (sql, params = []) =>
    new Promise((resolve, reject) => db.run(sql, params, (err) => (err ? reject(err) : resolve())));
  for (let attempt = 0; attempt < 200; attempt += 1) {
    try {
      const rows = await query('SELECT COUNT(*) AS n FROM payments');
      if (rows[0].n === 1) break;
    } catch (err) {
      // tabela ainda não criada
    }
    await sleep(10);
  }
  const app = express();
  app.use(express.json());
  manager.setupRoutes(app);
  const server = await listen(app);
  return {
    kind: 'original',
    baseUrl: `http://127.0.0.1:${server.address().port}`,
    query,
    exec,
    close: () => new Promise((resolve) => server.close(() => db.close(() => resolve()))),
  };
}

// --- Refatorado: composition root com dependências injetáveis. ---
async function startRefactored(dir, options = {}) {
  const { openDatabase, createDataAccess, initSchema, closeDatabase } = require(path.join(dir, 'src', 'database.js'));
  const { createApp } = require(path.join(dir, 'src', 'app.js'));
  const { hashPassword } = require(path.join(dir, 'src', 'passwordHash.js'));
  const db = await openDatabase(':memory:');
  const dataAccess = createDataAccess(options.wrapDb ? options.wrapDb(db) : db);
  await initSchema(dataAccess, { seedPasswordHash: await hashPassword(secrets.seedPassword) });
  const adminToken = 'adminToken' in options ? options.adminToken : secrets.adminToken;
  const app = createApp(dataAccess, { adminToken, models: options.models });
  const server = await listen(app);
  return {
    kind: 'refatorado',
    baseUrl: `http://127.0.0.1:${server.address().port}`,
    dataAccess,
    query: (sql, params = []) => dataAccess.read((handle) => handle.all(sql, params)),
    exec: (sql, params = []) => dataAccess.read((handle) => handle.run(sql, params)),
    close: () => new Promise((resolve) => server.close(() => closeDatabase(db).then(resolve, resolve))),
  };
}

async function http(baseUrl, method, urlPath, { body, rawBody, headers = {} } = {}) {
  const init = { method, headers: { ...headers } };
  if (rawBody !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = rawBody;
  } else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const res = await fetch(baseUrl + urlPath, init);
  const text = await res.text();
  const contentType = (res.headers.get('content-type') || '').split(';')[0];
  let parsed = text;
  if (contentType === 'application/json') {
    try {
      parsed = JSON.parse(text);
    } catch (err) {
      parsed = text;
    }
  }
  return { status: res.status, contentType, body: parsed };
}

const TABLES = ['users', 'enrollments', 'payments', 'audit_logs'];

async function counts(instance) {
  const result = {};
  for (const table of TABLES) {
    const rows = await instance.query(`SELECT COUNT(*) AS n FROM ${table}`);
    result[table] = rows[0].n;
  }
  return result;
}

// Substitui valores sensíveis conhecidos e padrões genéricos por <removido>.
function sanitize(text) {
  let out = String(text);
  out = out.replace(/pk_(live|test)_[A-Za-z0-9]+/g, 'pk_<removido>');
  out = out.replace(/\b\d{12,19}\b/g, '<removido>');
  out = out.replace(/scrypt\$[0-9a-f]+\$[0-9a-f]+/g, 'scrypt$<removido>');
  out = out.replace(/("(?:pwd|pass|password|card)"\s*:\s*)("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?)/g, '$1"<removido>"');
  for (const value of Object.values(secrets)) out = out.split(String(value)).join('<removido>');
  out = out.replace(/(X-Admin-Token["']?\s*[:=]\s*["']?)[^"'\s,}]+/gi, '$1<removido>');
  // Credenciais literais do original, por prefixo (o valor completo não é reproduzido aqui).
  out = out.replace(/senha_su[A-Za-z0-9_]+/g, '<removido>');
  out = out.replace(/admin_m[a-z]+\b/g, '<removido>');
  return out;
}

// Padrões que não podem aparecer em evidências preservadas.
function findSensitive(text) {
  const hits = [];
  for (const [name, value] of Object.entries(secrets)) if (text.includes(String(value))) hits.push(name);
  const patterns = {
    gatewayKey: /pk_(live|test)_[A-Za-z0-9]{4,}/,
    cardLike: /\b\d{12,19}\b/,
    scryptHash: /scrypt\$[0-9a-f]{8,}/,
    dbPass: /senha_su[A-Za-z0-9_]{4,}/,
  };
  for (const [name, re] of Object.entries(patterns)) if (re.test(text)) hits.push(name);
  return hits;
}

module.exports = {
  sleep, secrets, startOriginal, startRefactored, http, counts, sanitize, findSensitive, randomDigits, requireFrom,
};
