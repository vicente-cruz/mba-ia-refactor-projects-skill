'use strict';
// Testes do próprio comparador (compare.js): resultados válidos passam; adulterações reprovam;
// só a diferença de ordem de cursos e de alunos entre linha de base e refatorado é aceita (C-7);
// contra as expectativas explícitas, o refatorado continua obrigado à ordem determinística.
// Uso: node --test compare.test.js   (CMP_BASE/CMP_REF apontam para outros JSONs; padrão: evidências preservadas)

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { compare } = require('./compare');

const baseFile = process.env.CMP_BASE || path.join(__dirname, '..', 'baseline.json');
const refFile = process.env.CMP_REF || path.join(__dirname, '..', 'refatorado.json');
const load = (file) => JSON.parse(fs.readFileSync(file, 'utf8')).results;
const fresh = () => ({ base: load(baseFile), ref: load(refFile) });
const find = (list, id) => list.find((r) => r.id === id);
const reasons = (result) => result.failures.map((f) => `${f.id}: ${f.reason}`);

function assertRejects(result, id, pattern) {
  assert.equal(result.ok, false, 'deveria reprovar');
  assert.ok(result.failures.some((f) => f.id === id && pattern.test(f.reason)),
    `esperava reprovação de ${id} por ${pattern}; obtido: ${reasons(result).join(' | ')}`);
}

// ---------- resultados válidos ----------
test('resultados válidos passam sem reprovações nem avisos', () => {
  const { base, ref } = fresh();
  const result = compare(base, ref);
  assert.deepEqual(reasons(result), []);
  assert.equal(result.ok, true);
  assert.equal(result.rows.length, 25);
});

test('CLI: resultados válidos → exit 0; S1-01 com HTTP 500 → exit 1 (falso negativo relatado)', (t) => {
  const tmp = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'cmp-'));
  t.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
  const cli = (refPath) => spawnSync(process.execPath, [path.join(__dirname, 'compare.js'), baseFile, refPath, path.join(tmp, 'm.md')]);
  assert.equal(cli(refFile).status, 0);
  const data = JSON.parse(fs.readFileSync(refFile, 'utf8'));
  find(data.results, 'S1-01').response.status = 500;
  const bad = path.join(tmp, 'ref-500.json');
  fs.writeFileSync(bad, JSON.stringify(data));
  const run = cli(bad);
  assert.equal(run.status, 1);
  assert.match(run.stdout.toString(), /REPROVADO S1-01: status 500/);
});

// ---------- adulterações que devem reprovar ----------
test('HTTP 500 inesperado em caso com ID de correção intencional reprova', () => {
  const { base, ref } = fresh();
  find(ref, 'S1-01').response.status = 500;
  assertRejects(compare(base, ref), 'S1-01', /status 500/);
  const second = fresh();
  find(second.ref, 'S1-13').response = { status: 500, contentType: 'text/html', body: 'Internal Server Error' };
  assertRejects(compare(second.base, second.ref), 'S1-13', /status 500/);
});

test('receita incorreta no relatório reprova', () => {
  const { base, ref } = fresh();
  const docker = find(ref, 'S1-06').response.body.find((c) => c.course === 'Docker');
  docker.revenue += 1;
  assertRejects(compare(base, ref), 'S1-06', /corpo diferente/);
  const second = fresh();
  second.ref.find((r) => r.id === 'S5-01').response.body.find((c) => c.course === 'Docker').revenue = 497; // somaria DENIED
  assertRejects(compare(second.base, second.ref), 'S5-01', /corpo diferente/);
});

test('escrita mantida após rollback reprova (efeito e retorno ao comportamento antigo)', () => {
  const { base, ref } = fresh();
  const bt1 = find(ref, 'B-T1');
  bt1.counts.after.users += 1;
  bt1.counts.after.enrollments += 1;
  const result = compare(base, ref);
  assertRejects(result, 'B-T1', /efeito/);
  assertRejects(result, 'B-T1', /retorno ao comportamento antigo/);
  const second = fresh();
  find(second.ref, 'B-T2').counts.after.payments += 1;
  assertRejects(compare(second.base, second.ref), 'B-T2', /efeito/);
});

test('caso ausente reprova (no refatorado e na linha de base)', () => {
  const { base, ref } = fresh();
  assertRejects(compare(base, ref.filter((r) => r.id !== 'S1-02')), 'S1-02', /ausente no refatorado/);
  const second = fresh();
  assertRejects(compare(second.base.filter((r) => r.id !== 'B-T4'), second.ref), 'B-T4', /ausente na linha de base/);
});

test('erro de execução reprova (registro *-ERRO e campo error)', () => {
  const { base, ref } = fresh();
  ref.push({ id: 'S1-ERRO', description: 'falha do script', error: 'TypeError: boom' });
  assertRejects(compare(base, ref), 'S1-ERRO', /erro de execução/);
  const second = fresh();
  find(second.ref, 'S3-01').error = 'ECONNRESET';
  assertRejects(compare(second.base, second.ref), 'S3-01', /erro de execução no refatorado/);
});

test('retorno ao comportamento antigo reprova mesmo quando coincide com a linha de base', () => {
  for (const id of ['S1-03', 'S1-10', 'S1-12', 'S1-13', 'S1-15', 'S1-16', 'S3-01', 'B-T1', 'B-T2', 'B-T4']) {
    const { base, ref } = fresh();
    const index = ref.findIndex((r) => r.id === id);
    ref[index] = JSON.parse(JSON.stringify(find(base, id))); // refatorado idêntico ao original
    assertRejects(compare(base, ref), id, /retorno ao comportamento antigo/);
  }
  const { base, ref } = fresh();
  find(ref, 'C-OBS1').usersPerTrial[3] = 2;
  const result = compare(base, ref);
  assertRejects(result, 'C-OBS1', /usersPerTrial/);
  assertRejects(result, 'C-OBS1', /retorno ao comportamento antigo/);
});

test('mudança silenciosa de corpo ou content-type em caso preservado reprova', () => {
  const { base, ref } = fresh();
  find(ref, 'S1-02').response.body.enrollment_id = 99;
  assertRejects(compare(base, ref), 'S1-02', /corpo diferente/);
  const second = fresh();
  find(second.ref, 'S1-08').response.contentType = 'application/json';
  assertRejects(compare(second.base, second.ref), 'S1-08', /content-type/);
  const third = fresh();
  find(third.ref, 'S1-03').usersWithEmail = 1;
  assertRejects(compare(third.base, third.ref), 'S1-03', /usersWithEmail/);
});

test('caso sem expectativa definida reprova', () => {
  const { base, ref } = fresh();
  const extra = { id: 'S9-01', description: 'novo', request: {}, response: { status: 200, contentType: 'text/html', body: 'x' } };
  base.push(extra);
  ref.push(extra);
  assertRejects(compare(base, ref), 'S9-01', /sem expectativa/);
});

test('linha de base que não reproduz o comportamento antigo reprova (comparação perderia sentido)', () => {
  const { base, ref } = fresh();
  const index = base.findIndex((r) => r.id === 'S1-13');
  base[index] = JSON.parse(JSON.stringify(find(ref, 'S1-13')));
  assertRejects(compare(base, ref), 'S1-13', /linha de base não exibiu/);
});

// ---------- ordenação ----------
test('ordem dos cursos diferente na LINHA DE BASE é aceita (C-7)', () => {
  const { base, ref } = fresh();
  for (const id of ['S1-01', 'S1-06', 'S5-01']) find(base, id).response.body.reverse();
  assert.deepEqual(reasons(compare(base, ref)), []);
});

test('ordem dos cursos fora de id no REFATORADO reprova', () => {
  const { base, ref } = fresh();
  find(ref, 'S5-01').response.body.reverse();
  assertRejects(compare(base, ref), 'S5-01', /corpo diferente/);
});

test('ordem dos alunos diferente na LINHA DE BASE é aceita (C-7) — cenário real da revisão em S5-01', () => {
  const { base, ref } = fresh();
  const docker = find(base, 'S5-01').response.body.find((c) => c.course === 'Docker');
  const byName = Object.fromEntries(docker.students.map((s) => [s.student, s]));
  docker.students = [byName['Aluno Recusado'], byName.Unknown, byName.Leonan]; // ordem observada pela revisão
  for (const id of ['S1-06', 'S1-14']) {
    for (const c of find(base, id).response.body) c.students.reverse();
  }
  assert.deepEqual(reasons(compare(base, ref)), []);
});

test('ordem dos alunos fora de id no REFATORADO reprova', () => {
  const { base, ref } = fresh();
  find(ref, 'S1-06').response.body.find((c) => c.course === 'Docker').students.reverse();
  assertRejects(compare(base, ref), 'S1-06', /corpo diferente/);
  const second = fresh();
  find(second.ref, 'S5-01').response.body.find((c) => c.course === 'Docker').students.reverse();
  assertRejects(compare(second.base, second.ref), 'S5-01', /corpo diferente/);
});

test('linha de base com paid alterado, aluno removido ou duplicado reprova mesmo com a normalização de ordem', () => {
  const mutations = {
    'paid alterado': (students) => { students[0].paid += 1; },
    'aluno removido': (students) => { students.pop(); },
    'aluno duplicado': (students) => { students.push({ ...students[0] }); },
    'nome trocado': (students) => { students[1].student = 'Outro'; },
  };
  for (const [name, mutate] of Object.entries(mutations)) {
    const { base, ref } = fresh();
    mutate(find(base, 'S5-01').response.body.find((c) => c.course === 'Docker').students);
    const result = compare(base, ref);
    assert.ok(result.failures.some((f) => f.id === 'S5-01' && /diferença além da ordem de cursos e alunos/.test(f.reason)),
      `${name}: deveria reprovar; obtido ${reasons(result).join(' | ')}`);
  }
  // duplicação compensada por remoção (mesmo tamanho, multiplicidade diferente) também reprova
  const { base, ref } = fresh();
  const students = find(base, 'S1-06').response.body.find((c) => c.course === 'Clean Architecture').students;
  students[0] = { ...students[1] }; // [Guilherme, Guilherme] em vez de [Leonan, Guilherme]
  assertRejects(compare(base, ref), 'S1-06', /diferença além da ordem de cursos e alunos/);
});

test('a normalização de ordem não modifica os registros recebidos', () => {
  const { base, ref } = fresh();
  for (const c of find(base, 'S5-01').response.body) c.students.reverse();
  find(base, 'S5-01').response.body.reverse();
  const snapshotBase = JSON.stringify(base);
  const snapshotRef = JSON.stringify(ref);
  compare(base, ref);
  assert.equal(JSON.stringify(base), snapshotBase);
  assert.equal(JSON.stringify(ref), snapshotRef);
});

test('conteúdo diferente na linha de base em caso preservado reprova', () => {
  const { base, ref } = fresh();
  find(base, 'S1-01').response.body.find((c) => c.course === 'Docker').revenue = 5;
  assertRejects(compare(base, ref), 'S1-01', /diferença além da ordem de cursos e alunos/);
  const second = fresh();
  find(second.base, 'S1-04').counts.after.payments += 1;
  assertRejects(compare(second.base, second.ref), 'S1-04', /preservado/);
});
