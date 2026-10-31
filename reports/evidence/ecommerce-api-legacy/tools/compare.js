'use strict';
// Compara baseline.json (original) e refatorado.json caso a caso contra EXPECTATIVAS EXPLÍCITAS do contrato refatorado.
// Uso (CLI): node compare.js <baseline.json> <refatorado.json> <saida.md>   → exit 1 se houver qualquer reprovação.
//
// Para cada caso, o refatorado precisa atender: status, content-type, corpo exato, efeito em TODAS as tabelas
// (depois − antes) e campos observados extras. Além disso:
//  - relation 'same'           → o registro do refatorado deve ser idêntico ao da linha de base;
//  - relation 'same-unordered' → idêntico à linha de base ignorando SOMENTE a ordem dos cursos e a ordem dos alunos
//                                dentro de cada curso (C-7: o original ordenava pela conclusão dos callbacks). A
//                                normalização é feita sobre cópias e preserva conteúdo e multiplicidade: alterar paid,
//                                remover ou duplicar aluno continua reprovando. Essa folga vale só na relação com o
//                                original; contra EXPECTATIONS o refatorado segue obrigado à ordem determinística
//                                (curso por id, aluno por id da matrícula), fixada no corpo esperado;
//  - relation 'differs'        → correção intencional: a linha de base deve exibir a assinatura do comportamento
//                                antigo (old) e o refatorado NÃO pode exibi-la (detecta retorno ao comportamento antigo
//                                mesmo que ele coincida com a linha de base);
//  - relation 'observation'    → caso não determinístico: só a expectativa explícita do refatorado é exigida;
//                                a assinatura antiga na linha de base gera aviso, não reprovação.
// Também reprovam: caso ausente em qualquer lado, registro de erro de execução (*-ERRO ou campo error),
// caso sem expectativa definida e caso esperado que não foi executado.

const fs = require('node:fs');

const D = (users, enrollments, payments, auditLogs) => ({ users, enrollments, payments, audit_logs: auditLogs });
const NONE = D(0, 0, 0, 0);
const JSON_TYPE = 'application/json';
const TEXT_TYPE = 'text/html';

const course = (name, revenue, students) => ({ course: name, revenue, students: students.map(([student, paid]) => ({ student, paid })) });
const bodyIncludes = (r, text) => JSON.stringify(r.response && r.response.body).includes(text);
const status = (r) => r.response && r.response.status;

const EXPECTATIONS = {
  'S1-01': { relation: 'same-unordered', status: 200, contentType: JSON_TYPE, delta: NONE,
    body: [course('Clean Architecture', 997, [['Leonan', 997]]), course('Docker', 0, [])] },
  'S1-02': { relation: 'same', status: 200, contentType: JSON_TYPE, delta: D(1, 1, 1, 1), body: { msg: 'Sucesso', enrollment_id: 2 } },
  'S1-03': { relation: 'differs', status: 400, contentType: TEXT_TYPE, delta: NONE, body: 'Pagamento recusado', extras: { usersWithEmail: 0 },
    old: { description: 'C-3: recusa mantinha o usuário novo gravado', test: (r) => r.usersWithEmail === 1 } },
  'S1-04': { relation: 'same', status: 200, contentType: JSON_TYPE, delta: D(0, 1, 1, 1), body: { msg: 'Sucesso', enrollment_id: 3 } },
  'S1-05': { relation: 'same', status: 200, contentType: JSON_TYPE, delta: D(0, 1, 1, 1), body: { msg: 'Sucesso', enrollment_id: 4 } },
  'S1-06': { relation: 'same-unordered', status: 200, contentType: JSON_TYPE, delta: NONE,
    body: [course('Clean Architecture', 1994, [['Leonan', 997], ['Guilherme', 997]]), course('Docker', 994, [['Guilherme', 497], ['Leonan', 497]])] },
  'S1-07': { relation: 'same', status: 400, contentType: TEXT_TYPE, delta: NONE, body: 'Bad Request' },
  'S1-08': { relation: 'same', status: 404, contentType: TEXT_TYPE, delta: NONE, body: 'Curso não encontrado' },
  'S1-09': { relation: 'same', status: 200, contentType: JSON_TYPE, delta: D(1, 1, 1, 1), body: { msg: 'Sucesso', enrollment_id: 5 } },
  'S1-10': { relation: 'differs', status: 400, contentType: TEXT_TYPE, delta: NONE, body: 'Bad Request',
    old: { description: 'D-4(a): usuário novo sem pwd era aceito com senha padrão', test: (r) => status(r) === 200 } },
  'S1-11': { relation: 'differs', status: 400, contentType: TEXT_TYPE, delta: NONE, body: 'Bad Request',
    old: { description: 'D-4(a): usuário novo com pwd vazio era aceito com senha padrão', test: (r) => status(r) === 200 } },
  'S1-12': { relation: 'differs', status: 400, contentType: TEXT_TYPE, delta: NONE, body: 'Bad Request',
    old: { description: 'C-5: JSON inválido devolvia HTML com stack trace', test: (r) => bodyIncludes(r, '<!DOCTYPE html>') || bodyIncludes(r, 'SyntaxError') } },
  'S1-13': { relation: 'differs', status: 409, contentType: TEXT_TYPE, delta: NONE, body: 'Usuário possui matrículas',
    old: { description: 'D-3(b): excluía usuário com matrículas, deixando órfãos', test: (r) => status(r) === 200 || (r.counts && r.counts.after.users < r.counts.before.users) } },
  'S1-14': { relation: 'differs', status: 200, contentType: JSON_TYPE, delta: NONE,
    body: [course('Clean Architecture', 2991, [['Leonan', 997], ['Guilherme', 997], ['Guilherme', 997]]), course('Docker', 994, [['Guilherme', 497], ['Leonan', 497]])],
    old: { description: 'consequência de F-07: relatório com aluno "Unknown" após exclusão', test: (r) => bodyIncludes(r, 'Unknown') } },
  'S1-15': { relation: 'differs', status: 404, contentType: TEXT_TYPE, delta: NONE, body: 'Usuário não encontrado',
    old: { description: 'C-6: id inexistente respondia 200 com mensagem de sucesso', test: (r) => status(r) === 200 } },
  'S1-16': { relation: 'differs', status: 400, contentType: TEXT_TYPE, delta: NONE, body: 'ID inválido',
    old: { description: 'C-6: id não numérico respondia 200 com mensagem de sucesso', test: (r) => status(r) === 200 } },
  'S2-01': { relation: 'same', status: 404, contentType: TEXT_TYPE, delta: NONE, body: 'Curso não encontrado' },
  'S3-01': { relation: 'differs', status: 200, contentType: TEXT_TYPE, delta: D(-1, 0, 0, 0), body: 'Usuário deletado',
    old: { description: 'D-3(b): mensagem afirmava dados sujos no banco', test: (r) => bodyIncludes(r, 'sujos') } },
  'B-T1': { relation: 'differs', status: 500, contentType: TEXT_TYPE, delta: NONE, body: 'Erro Pagamento', extras: { usersWithEmail: 0 },
    old: { description: 'D-5(a)/C-3: falha em payments mantinha usuário e matrícula', test: (r) => Boolean(r.counts) && (r.counts.after.users > r.counts.before.users || r.counts.after.enrollments > r.counts.before.enrollments) } },
  'B-T2': { relation: 'differs', status: 500, contentType: TEXT_TYPE, delta: NONE, body: 'Erro Auditoria', extras: { usersWithEmail: 0 },
    old: { description: 'D-5(a): falha na auditoria respondia 200 e mantinha as escritas', test: (r) => status(r) === 200 } },
  'B-T3': { relation: 'same', status: 500, contentType: TEXT_TYPE, delta: NONE, body: 'Erro ao criar usuário', extras: { usersWithEmail: 0 } },
  'B-T4': { relation: 'differs', status: 500, contentType: TEXT_TYPE, delta: NONE, body: 'Erro Matrícula', extras: { usersWithEmail: 0 },
    old: { description: 'D-5(a): falha em enrollments mantinha o usuário criado', test: (r) => Boolean(r.counts) && r.counts.after.users > r.counts.before.users } },
  'S5-01': { relation: 'same-unordered', status: 200, contentType: JSON_TYPE, delta: NONE,
    body: [
      course('Clean Architecture', 997, [['Leonan', 997]]),
      course('Docker', 0, [['Aluno Recusado', 497], ['Leonan', 0], ['Unknown', 100]]),
      course('Kubernetes', 0, []),
    ] },
  'C-OBS1': { relation: 'observation', extras: { usersPerTrial: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1] },
    old: { description: 'F-06: checkouts simultâneos criavam usuário duplicado', test: (r) => Array.isArray(r.usersPerTrial) && r.usersPerTrial.some((n) => n > 1) } },
  'C-OBS2': { relation: 'observation', extras: { reports: 20, reportsWithPartialState: 0 } },
};

const isDeepEqual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const delta = (r) => (r.counts
  ? Object.fromEntries(Object.keys(r.counts.after).map((t) => [t, r.counts.after[t] - r.counts.before[t]]))
  : undefined);
// Normaliza a ordem de cursos e alunos de um relatório, sobre uma cópia profunda (o registro recebido não é alterado).
// Ordena por chave completa (JSON do item), então itens iguais permanecem repetidos e itens diferentes não se fundem.
const byJson = (a, b) => {
  const ka = JSON.stringify(a);
  const kb = JSON.stringify(b);
  return ka < kb ? -1 : ka > kb ? 1 : 0;
};
const normalizeReportOrder = (body) => {
  if (!Array.isArray(body)) return body;
  const copy = JSON.parse(JSON.stringify(body));
  for (const item of copy) {
    if (item && Array.isArray(item.students)) item.students.sort(byJson);
  }
  return copy.sort(byJson);
};
const EXTRA_KEYS = ['usersWithEmail', 'usersPerTrial', 'reports', 'reportsWithPartialState'];
const observed = (r) => ({
  status: status(r),
  contentType: r.response && r.response.contentType,
  body: r.response && r.response.body,
  delta: delta(r),
  extras: Object.fromEntries(EXTRA_KEYS.filter((k) => k in r).map((k) => [k, r[k]])),
});
const hasError = (r) => r.id.endsWith('-ERRO') || 'error' in r;

// Verifica o registro do refatorado contra a expectativa explícita; devolve a lista de falhas.
function checkExpectation(exp, r) {
  const fails = [];
  const o = observed(r);
  if ('status' in exp && o.status !== exp.status) fails.push(`status ${o.status} ≠ esperado ${exp.status}`);
  if ('contentType' in exp && o.contentType !== exp.contentType) fails.push(`content-type ${o.contentType} ≠ esperado ${exp.contentType}`);
  if ('body' in exp && !isDeepEqual(o.body, exp.body)) fails.push('corpo diferente do esperado');
  if ('delta' in exp && !isDeepEqual(o.delta, exp.delta)) fails.push(`efeito ${JSON.stringify(o.delta)} ≠ esperado ${JSON.stringify(exp.delta)}`);
  for (const [key, value] of Object.entries(exp.extras || {})) {
    if (!isDeepEqual(r[key], value)) fails.push(`${key}=${JSON.stringify(r[key])} ≠ esperado ${JSON.stringify(value)}`);
  }
  return fails;
}

function compare(baseResults, refResults) {
  const failures = [];
  const warnings = [];
  const rows = [];
  const index = (list, side) => {
    const map = new Map();
    for (const r of list) {
      if (hasError(r)) failures.push({ id: r.id, reason: `${side}: registro de erro de execução` });
      if (map.has(r.id)) failures.push({ id: r.id, reason: `${side}: caso duplicado` });
      map.set(r.id, r);
    }
    return map;
  };
  const base = index(baseResults, 'linha de base');
  const ref = index(refResults, 'refatorado');

  for (const id of new Set([...base.keys(), ...ref.keys()])) {
    if (id.endsWith('-ERRO')) continue;
    if (!EXPECTATIONS[id]) failures.push({ id, reason: 'caso sem expectativa definida' });
  }

  for (const [id, exp] of Object.entries(EXPECTATIONS)) {
    const b = base.get(id);
    const r = ref.get(id);
    const caseFails = [];
    if (!b) caseFails.push('ausente na linha de base');
    if (!r) caseFails.push('ausente no refatorado');
    if (b && hasError(b)) caseFails.push('erro de execução na linha de base');
    if (r && hasError(r)) caseFails.push('erro de execução no refatorado');
    if (b && r && !hasError(b) && !hasError(r)) {
      caseFails.push(...checkExpectation(exp, r));
      const ob = observed(b);
      const or = observed(r);
      if (exp.relation === 'same' && !isDeepEqual(ob, or)) caseFails.push('diferença em caso que deve ser preservado');
      if (exp.relation === 'same-unordered') {
        const normalize = (o) => ({ ...o, body: normalizeReportOrder(o.body) });
        if (!isDeepEqual(normalize(ob), normalize(or))) caseFails.push('diferença além da ordem de cursos e alunos');
      }
      if (exp.old) {
        if (exp.old.test(r)) caseFails.push(`retorno ao comportamento antigo — ${exp.old.description}`);
        if (!exp.old.test(b)) {
          const msg = `linha de base não exibiu o comportamento antigo esperado — ${exp.old.description}`;
          if (exp.relation === 'observation') warnings.push({ id, reason: msg });
          else caseFails.push(msg);
        }
      }
    }
    for (const reason of caseFails) failures.push({ id, reason });
    const label = {
      same: 'preservado', 'same-unordered': 'preservado (ordem de cursos e alunos por id — C-7)',
      differs: `correção intencional — ${exp.old ? exp.old.description : ''}`, observation: 'observação',
    }[exp.relation];
    rows.push({ id, b, r, exp, ok: caseFails.length === 0, label, caseFails });
  }
  return { ok: failures.length === 0, failures, warnings, rows };
}

function toMarkdown(result) {
  const cell = (s) => String(s).replace(/\|/g, '\\|').replace(/\n/g, ' ');
  const short = (body) => {
    if (body === undefined) return '-';
    const text = typeof body === 'string' ? body : JSON.stringify(body);
    return text.length > 120 ? `${text.slice(0, 120)}…` : text;
  };
  const fmtDelta = (d) => (d ? Object.entries(d).filter(([, v]) => v !== 0).map(([t, v]) => `${t} ${v > 0 ? '+' : ''}${v}`).join(', ') || 'nenhum' : '-');
  const extras = (r) => (r ? EXTRA_KEYS.filter((k) => k in r).map((k) => `${k}=${JSON.stringify(r[k])}`).join(' ') : '');
  const lines = [
    '# Matriz de endpoints — original × refatorado',
    '',
    'Gerada por `tools/compare.js`. O refatorado é verificado contra expectativas explícitas (status, content-type, corpo exato,',
    'efeito em todas as tabelas e campos observados); casos de correção também verificam a ausência do comportamento antigo.',
    'Efeito = variação de linhas por tabela causada pela requisição (depois − antes).',
    '',
    '| Caso | Descrição | Status antes | Status depois | Corpo/observação antes | Corpo/observação depois | Efeito antes | Efeito depois | Classificação | Verificação |',
    '|---|---|---|---|---|---|---|---|---|---|',
  ];
  for (const row of result.rows) {
    const { b, r } = row;
    const desc = (r && r.description) || (b && b.description) || '';
    lines.push(`| ${row.id} | ${cell(desc)} | ${b && b.response ? b.response.status : '-'} | ${r && r.response ? r.response.status : '-'} | ${cell(b && b.response ? short(b.response.body) : extras(b))} | ${cell(r && r.response ? short(r.response.body) : extras(r))} | ${b ? fmtDelta(delta(b)) : '-'} | ${r ? fmtDelta(delta(r)) : '-'} | ${cell(row.label)} | ${row.ok ? 'aprovado' : `REPROVADO: ${cell(row.caseFails.join('; '))}`} |`);
  }
  lines.push('', `Casos: ${result.rows.length} | Reprovações: ${result.failures.length} | Avisos: ${result.warnings.length}`);
  for (const f of result.failures) lines.push(`- REPROVADO ${f.id}: ${f.reason}`);
  for (const w of result.warnings) lines.push(`- AVISO ${w.id}: ${w.reason}`);
  lines.push('');
  return lines.join('\n');
}

function loadResults(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8')).results;
}

if (require.main === module) {
  const [baseFile, refFile, outFile] = process.argv.slice(2);
  if (!baseFile || !refFile || !outFile) {
    console.error('uso: node compare.js <baseline.json> <refatorado.json> <saida.md>');
    process.exit(2);
  }
  const result = compare(loadResults(baseFile), loadResults(refFile));
  fs.writeFileSync(outFile, toMarkdown(result));
  console.log(`casos: ${result.rows.length} | reprovações: ${result.failures.length} | avisos: ${result.warnings.length}`);
  for (const f of result.failures) console.log(`REPROVADO ${f.id}: ${f.reason}`);
  for (const w of result.warnings) console.log(`AVISO ${w.id}: ${w.reason}`);
  process.exit(result.ok ? 0 : 1);
}

module.exports = { compare, toMarkdown, EXPECTATIONS };
