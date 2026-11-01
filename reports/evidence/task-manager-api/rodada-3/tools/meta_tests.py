"""Meta-testes de ponta a ponta do comparador: alteram CÓPIAS dos arquivos de resultado e
executam compare.py como processo, exigindo código de saída e mensagem esperados.

Uso: python -I -B meta_tests.py <resultados_dir> <tmp_dir> <saida.txt>
Código 1 se qualquer meta-teste não se comportar como esperado.
"""
import json
import os
import shutil
import subprocess
import sys

RES, TMP, OUT = sys.argv[1:4]
TOOLS = os.path.dirname(os.path.realpath(__file__))


def load(d, mode, g):
    return json.load(open(os.path.join(d, mode, g + '.json')))


def save(d, mode, g, data):
    json.dump(data, open(os.path.join(d, mode, g + '.json'), 'w'), ensure_ascii=False)


def drop_case(name, group, modes):
    def f(d):
        for m in modes:
            data = load(d, m, group)
            before = len(data['records'])
            data['records'] = [r for r in data['records'] if r['name'] != name]
            assert len(data['records']) == before - 1, f'{name} não encontrado em {m}'
            save(d, m, group, data)
    return f


def duplicate_case(name, group):
    def f(d):
        data = load(d, 'refatorado', group)
        data['records'].append([r for r in data['records'] if r['name'] == name][0])
        save(d, 'refatorado', group, data)
    return f


def remove_group(group):
    return lambda d: os.remove(os.path.join(d, 'refatorado', group + '.json'))


def empty_group(group):
    def f(d):
        for m in ('original', 'refatorado'):
            data = load(d, m, group)
            data['records'] = []
            save(d, m, group, data)
    return f


def mutate(group, name, fn, mode='refatorado'):
    def f(d):
        data = load(d, mode, group)
        rec = [r for r in data['records'] if r['name'] == name][0]
        fn(rec)
        save(d, mode, group, data)
    return f


C07 = 'conflito forçado PUT /users/2'
CASES = [  # (descrição, alteração, código esperado, trecho obrigatório na saída)
    ('controle: resultados sem alteração', lambda d: None, 0, None),
    ('"POST /tasks minimo" removido das DUAS versões', drop_case('POST /tasks minimo', 'tasks_escrita', ('original', 'refatorado')),
     1, 'caso do inventário AUSENTE nos resultados: "POST /tasks minimo"'),
    ('"POST /tasks minimo" removido só do refatorado', drop_case('POST /tasks minimo', 'tasks_escrita', ('refatorado',)),
     1, 'AUSENTE nos resultados: "POST /tasks minimo"'),
    ('caso duplicado', duplicate_case('GET /tasks seed', 'seed_leitura'), 1, 'casos duplicados'),
    ('grupo ausente', remove_group('bigint'), 1, 'refatorado/bigint: resultado ausente'),
    ('execução vazia', empty_group('vazio'), 1, 'execução vazia'),
    ('caso fora do inventário', mutate('vazio', 'vazio GET /tasks', lambda r: r.__setitem__('name', 'caso inventado')),
     1, 'caso FORA do inventário: "caso inventado"'),
    ('C-07: role do alvo → admin (arquivo)', mutate('rollback', C07, lambda r: r['post']['get']['json'].__setitem__('role', 'admin')),
     1, f'rollback/{C07}: FALHA'),
    ('C-07: post.counts.tasks → 0 (arquivo)', mutate('rollback', C07, lambda r: r['post']['counts'].__setitem__('tasks', 0)),
     1, f'rollback/{C07}: FALHA'),
    ('C-07: campo extra no corpo de erro (arquivo)', mutate('rollback', C07, lambda r: r['resp']['json'].__setitem__('detalhe', 'x')),
     1, f'rollback/{C07}: FALHA corpo de erro com campos além de "error"'),
]
lines, fail = [], False
for i, (desc, change, exp_code, exp_msg) in enumerate(CASES):
    d = os.path.join(TMP, f'meta-{i}')
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(RES, d, ignore=shutil.ignore_patterns('segredos-*.txt'))
    change(d)
    p = subprocess.run([sys.executable, '-I', '-B', os.path.join(TOOLS, 'compare.py'), d, os.path.join(d, 'm.md'),
                        os.path.join(d, 'r.json')], capture_output=True, text=True)
    out = p.stdout + p.stderr
    ok = p.returncode == exp_code and (exp_msg is None or exp_msg in out)
    fail |= not ok
    probs = [l for l in out.splitlines() if l.startswith('PROBLEMA')]
    msg = next((l for l in probs if exp_msg and exp_msg in l), probs[0] if probs else '') if exp_code else ''
    lines.append(f'{"OK " if ok else "ERRO"} | {desc} | exit={p.returncode} (esperado {exp_code})'
                 + (f' | {msg[:220]}' if msg else ''))
    shutil.rmtree(d, ignore_errors=True)
open(OUT, 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
sys.exit(1 if fail else 0)
