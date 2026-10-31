'use strict';
// Instrumentação de teste (node -r): faz falhar o primeiro INSERT em payments (simula falha no meio do seed).
const sqlite3 = require(require.resolve('sqlite3', { paths: [process.cwd()] }));
const originalRun = sqlite3.Database.prototype.run;
let fired = false;
sqlite3.Database.prototype.run = function run(sql, params, callback) {
  if (!fired && typeof sql === 'string' && sql.startsWith('INSERT INTO payments')) {
    fired = true;
    const cb = typeof params === 'function' ? params : callback;
    setImmediate(() => cb.call({}, new Error('falha induzida no seed')));
    return this;
  }
  return originalRun.apply(this, arguments);
};
