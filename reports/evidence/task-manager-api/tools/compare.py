"""Comparador linha de base x refatorado, com testes negativos executados antes do uso.

Uso: python compare.py <out_dir> <matriz.md>
"""
import copy
import json
import os
import sys

GROUPS = ['seed_leitura', 'vazio', 'bordas', 'tasks_escrita', 'users_escrita', 'categories_escrita',
          'auth', 'ciclo_token', 'rollback', 'seed_falha']
# Mudanças globais documentadas na seção 5.4 D do relatório aprovado.
KNOWN = {
    'password': 'F-01 (password removido)',
    'token': 'D-1a (token assinado)',
    'hash_novo': 'F-02 (hash werkzeug)',
}


def diff(a, b, path=''):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f'{path}.{k}'
            if k not in a:
                out.append((p, '<ausente>', b[k]))
            elif k not in b:
                out.append((p, a[k], '<ausente>'))
            else:
                out += diff(a[k], b[k], p)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [(path + '[len]', len(a), len(b))]
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f'{path}[{i}]')
        return out
    if a != b or type(a) is not type(b):
        return [(path, a, b)]
    return []


def comparable(rec):
    return {'resp': rec.get('resp'), 'post': rec.get('post'), 'fact': rec.get('fact')}


def classify(o, r):
    """Retorna (classificação, diferenças)."""
    if o.get('flags') or r.get('flags'):
        return 'FALHA: formato temporal inválido', o.get('flags', []) + r.get('flags', [])
    d = diff(comparable(o), comparable(r))
    if not d:
        return 'preservado', []
    if r.get('exp_ok') is False:
        return 'REGRESSÃO (expectativa do refatorado falhou)', d
    if r.get('cls'):
        if r.get('exp_ok') is True:
            return f'intencional {r["cls"]}', d
        return f'REVISAR {r["cls"]} (sem expectativa verificada)', d
    known = set()
    def __b_absent(path, diffs):
        return any(pp == path and bb == '<ausente>' for pp, _a, bb in diffs)
    for p, _, _b in d:
        leaf = p.split('.')[-1].split('[')[0]
        if leaf == 'password' and _ == '<presente>' and __b_absent(p, d):
            known.add(KNOWN[leaf])
        elif leaf in ('token', 'hash_novo'):
            known.add(KNOWN[leaf])
        else:
            return 'REGRESSÃO', d
    return 'intencional ' + ', '.join(sorted(known)), d


def negative_tests():
    base = {'name': 'x', 'resp': {'status': 200, 'is_json': True,
                                  'json': {'id': 1, 'error': 'Erro', 'items': [1, 2], 'created_at': '<ts>'}},
            'post': {'counts': {'tasks': 10}}, 'flags': [], 'exp_ok': True, 'cls': None}
    other = {'resp': {'status': 200, 'is_json': True, 'json': {'message': 'Task Manager API'}}}
    muts = {}
    m = copy.deepcopy(base); m['resp']['status'] = 201; muts['status alterado'] = m
    m = copy.deepcopy(base); del m['resp']['json']['id']; muts['chave removida'] = m
    m = copy.deepcopy(base); m['resp']['json']['password'] = '<presente>'
    muts['chave password adicionada'] = m
    m = copy.deepcopy(base); m['resp']['json']['error'] = 'Outra'; muts['mensagem de erro alterada'] = m
    m = copy.deepcopy(base); m['post']['counts']['tasks'] = 11; muts['contagem alterada'] = m
    m = copy.deepcopy(base); m['resp']['json']['items'] = [2, 1]; muts['ordem de lista alterada'] = m
    m = copy.deepcopy(base); m['flags'] = ['formato-temporal-invalido:created_at']
    muts['campo temporal fora do formato'] = m
    m = copy.deepcopy(base); m['resp'] = other['resp']; muts['cópia de outro endpoint'] = m
    results = []
    ok_all = True
    same, _ = classify(base, copy.deepcopy(base))
    results.append(('controle: registros idênticos', same, same == 'preservado'))
    ok_all &= same == 'preservado'
    for name, mutated in muts.items():
        c, _ = classify(base, mutated)
        # password adicionada no refatorado não pode passar como F-01 (F-01 é remoção)
        detected = 'REGRESS' in c or 'FALHA' in c
        results.append((name, c, detected))
        ok_all &= detected
    return ok_all, results


def main():
    out_dir, matriz = sys.argv[1], sys.argv[2]
    ok, results = negative_tests()
    lines = ['## Testes negativos do comparador (executados antes da comparação)', '',
             '| Mutação | Classificação obtida | Detectada |', '|---|---|---|']
    for n, c, d in results:
        lines.append(f'| {n} | {c} | {"sim" if d else "NÃO"} |')
    if not ok:
        print('\n'.join(lines))
        print('COMPARADOR REPROVADO')
        sys.exit(1)
    lines += ['', '## Matriz de casos (original × refatorado)', '',
              '| Grupo | Caso | Original | Refatorado | Expect. orig. | Expect. ref. | Classificação |',
              '|---|---|---|---|---|---|---|']
    summary = {}
    problems = []
    for g in GROUPS:
        o = json.load(open(os.path.join(out_dir, 'original', g + '.json')))['records']
        r = json.load(open(os.path.join(out_dir, 'refatorado', g + '.json')))['records']
        if not o or not r:
            problems.append(f'{g}: execução vazia')
        ro = {x['name']: x for x in r}
        oo = {x['name']: x for x in o}
        missing = [n for n in oo if n not in ro]
        if missing:
            problems.append(f'{g}: casos da linha de base ausentes no refatorado: {missing}')
        for name in list(oo) + [n for n in ro if n not in oo]:
            a, b = oo.get(name), ro.get(name)
            if a is None:
                cls = 'só refatorado' + ('' if b.get('exp_ok') is not False else ' — FALHOU')
                if b.get('exp_ok') is False:
                    problems.append(f'{g}/{name}: expectativa falhou')
            else:
                cls, _ = classify(a, b)
                if 'REGRESS' in cls or 'FALHA' in cls or 'REVISAR' in cls:
                    problems.append(f'{g}/{name}: {cls}')

            def st(x):
                if x is None:
                    return '—'
                if 'resp' in x:
                    resp = x['resp']
                    e = resp.get('json', {}).get('error') if isinstance(resp.get('json'), dict) else None
                    s = str(resp['status']) + ('' if resp.get('is_json') else ' (HTML)')
                    return s + (f' `{e}`' if e else '')
                return f'`{json.dumps(x.get("fact"), ensure_ascii=False)[:60]}`'

            def ex(x):
                if x is None:
                    return '—'
                return {True: 'ok', False: 'FALHOU', None: 'medir/n.a.'}[x.get('exp_ok')]
            summary[cls.split(' (')[0] if cls.startswith('intencional') else cls] = \
                summary.get(cls.split(' (')[0] if cls.startswith('intencional') else cls, 0) + 1
            lines.append(f'| {g} | {name.replace("|", "/")} | {st(a)} | {st(b)} | {ex(a)} | {ex(b)} | {cls} |')
    head = ['# Matriz de endpoints e cenários — antes × depois', '',
            'Gerada por `harness/compare.py`. Corpos normalizados (timestamps → `<ts>`, tokens → `<token>`, '
            'presença de `password` → `<presente>`). Valores sensíveis não aparecem.', '',
            '## Resumo por classificação', '', '| Classificação | Casos |', '|---|---:|']
    for k in sorted(summary):
        head.append(f'| {k} | {summary[k]} |')
    head += ['', f'Problemas: {len(problems)}'] + [f'- {p}' for p in problems] + ['']
    with open(matriz, 'w') as fh:
        fh.write('\n'.join(head + lines) + '\n')
    print('negativos ok;', 'total', sum(summary.values()), summary)
    for p in problems:
        print('PROBLEMA:', p)


if __name__ == '__main__':
    main()
