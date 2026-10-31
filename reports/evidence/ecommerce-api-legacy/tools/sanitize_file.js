'use strict';
// Sanitiza um arquivo (logs brutos) e falha se restar padrão sensível. Uso: node sanitize_file.js <entrada> <saída> [max-linhas]
// Observação: segredos aleatórios de outra execução não são conhecidos aqui; a remoção se apoia nos padrões genéricos.
const fs = require('node:fs');
const { sanitize, findSensitive } = require('./lib');
const [input, output, maxLines] = process.argv.slice(2);
let text = sanitize(fs.readFileSync(input, 'utf8'));
if (maxLines) text = text.split('\n').slice(0, Number(maxLines)).join('\n');
const leaks = findSensitive(text);
if (leaks.length) { console.error(`sensível após sanitização: ${leaks}`); process.exit(1); }
fs.writeFileSync(output, text);
console.log(`${output}: ${text.split('\n').length} linhas`);
