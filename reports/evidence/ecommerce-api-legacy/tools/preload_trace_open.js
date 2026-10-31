'use strict';
// Instrumentação de teste (node -r): registra em stderr toda abertura de sqlite3.Database.
// Usada para provar que a validação de configuração ocorre antes de abrir o banco.
const sqlite3 = require(require.resolve('sqlite3', { paths: [process.cwd()] }));
const Original = sqlite3.Database;
sqlite3.Database = class TracedDatabase extends Original {
  constructor(...args) {
    process.stderr.write('[trace] sqlite3.Database aberto\n');
    super(...args);
  }
};
