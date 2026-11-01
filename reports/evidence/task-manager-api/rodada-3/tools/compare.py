"""Comparador da rodada 3 (rodada 2 + exceção de C-07 fechada + inventário explícito): original × refatorado, com regras restritas por classificação.

Uso: python -I -B compare.py <resultados_dir> <matriz.md> <resumo.json>
Sai com código 1 se: testes negativos falharem, faltar/duplicar caso, execução vazia,
expectativa falhar (mesmo com respostas idênticas), campo sensível público ou diferença não aprovada.

Regras de diferença permitida (além de nenhuma diferença = "preservado"):
- Folhas globais aprovadas: remoção de `password` (F-01), formato do `token` (D-1a), tipo do hash
  gravado `hash_novo` (F-02). Qualquer outra folha diferente reprova o caso sem classificação.
- Classes de correção/rejeição (C-*, R-*, M-01/02/04, C-JSON, C-12, D-1a com status >= 400),
  com expectativa forte do refatorado e só nestes campos:
    resp: status, is_json, text, www_authenticate e o corpo — que, em erro, deve ser exatamente
          {'error': <mensagem>} (campo extra reprova); em 2xx (C-12), igual ao `has` exato da expectativa.
    post: só se o ORIGINAL gravou (2xx) e o refatorado provou banco e visão pública inalterados
          (`unchanged` + `pre_view`). Se o original não gravou (ex.: C-07 com 500), o estado posterior
          deve ser igual nas duas versões; nenhuma verificação isolada de post.* libera diferenças.
- Inventário: os nomes de casos por grupo e versão vêm de `inventario.json` (arquivo explícito,
  congelado), nunca dos resultados validados; ausentes, extras e duplicados reprovam.
- M-03 (erro do framework em JSON): só is_json/text/json podem diferir; `allow` deve ser igual.
- Fatos D-2a e F-06: só o valor do fato pode diferir, com expectativa por versão atendida.
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from expect import ABSENT, evaluate, global_checks, normalize  # noqa: E402

GROUPS = ['seed_leitura', 'vazio', 'bordas', 'tasks_escrita', 'users_escrita', 'categories_escrita', 'auth',
          'ciclo_token', 'rollback', 'seed_falha', 'bigint', 'http', 'fronteira7']
REJECTION_PREFIXES = ('C-', 'R-', 'M-01', 'M-02', 'M-04', 'D-1a')
WRITE = ('POST', 'PUT', 'DELETE', 'PATCH')
RESP_ALLOWED = ('.resp.status', '.resp.is_json', '.resp.text', '.resp.json', '.resp.www_authenticate')
INVENTORY = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'inventario.json')


def diff(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff(a.get(k, ABSENT), b.get(k, ABSENT), f'{path}.{k}')
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [(path + '[len]', len(a), len(b))]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f'{path}.{i}')
        return out
    if a != b or type(a) is not type(b):
        return [(path, a, b)]
    return []


def comparable(rec):
    return normalize({'resp': rec.get('resp'), 'post': rec.get('post'), 'fact': rec.get('fact')})


def strong(spec, rec):
    if not spec or 'status' not in spec:
        return False
    detail = 'error' in spec or spec.get('has') or spec.get('ids')
    if rec.get('method') in WRITE and not (spec.get('unchanged') or spec.get('changed') or spec.get('has')):
        return False
    post_checks = any(k.startswith('post.') for k in spec.get('has', {}))
    if rec.get('method') in WRITE and spec['status'] >= 400 and not (spec.get('unchanged') or post_checks):
        return False  # rejeição em escrita precisa provar o estado do banco
    return bool(detail)


def leaf_allowed(path, a, b):
    leaf = path.split('.')[-1]
    if leaf == 'password' and a == '<presente>' and b == ABSENT:
        return 'F-01'
    if leaf == 'token' and a == '<fake-token>' and b == '<token>':
        return 'D-1a(token)'
    if leaf == 'hash_novo' and a == 'md5' and b == 'werkzeug-scrypt':
        return 'F-02'
    return None


def check_record(rec, mode):
    """Falhas próprias do registro: expectativa reavaliada + verificações globais."""
    return evaluate(rec.get('exp'), rec) + global_checks(rec, mode)


def classify(o, r):
    """(classificação, falhas). Classificação começando com 'FALHA' reprova."""
    fails = [f'refatorado: {e}' for e in check_record(r, 'refatorado')]
    if o is not None:
        fails += [f'original: {e}' for e in check_record(o, 'original')]
    if r.get('exp') is None:
        fails.append('refatorado sem expectativa')
    if fails:
        return 'FALHA expectativa/verificação', fails
    if o is None:
        return 'só refatorado', []
    d = diff(comparable(o), comparable(r))
    if not d:
        return 'preservado', []
    cls = r.get('cls') or ''
    allowed, rest = set(), []
    for p, a, b in d:
        tag = leaf_allowed(p, a, b)
        if tag:
            allowed.add(tag)
        else:
            rest.append((p, a, b))
    if not rest:
        return 'intencional ' + ', '.join(sorted(allowed)), []
    spec = r.get('exp') or {}
    if cls == 'M-03':
        bad = [x for x in rest if not x[0].startswith(('.resp.is_json', '.resp.text', '.resp.json'))]
        if bad:
            return 'FALHA diferença fora de M-03', [str(x) for x in bad]
        return 'intencional M-03', []
    if cls in ('D-2a', 'F-06'):
        bad = [x for x in rest if not x[0].startswith('.fact')]
        if bad or o.get('exp') is None:
            return f'FALHA diferença fora de {cls}', [str(x) for x in bad] or ['fato sem expectativa no original']
        return f'intencional {cls}', []
    if cls.startswith(REJECTION_PREFIXES) or cls == 'C-JSON':
        if cls.startswith('D-1a') and spec.get('status', 0) < 400:
            return 'FALHA D-1a só aprova negação de acesso', [str(x) for x in rest[:3]]
        if not strong(spec, r):
            return f'FALHA expectativa fraca para {cls}', [json.dumps(spec)[:200]]
        o_status, r_status = o['resp']['status'], r['resp']['status']
        r_json = r['resp'].get('json')
        if r_status >= 400 and not (isinstance(r_json, dict) and sorted(r_json) == ['error']):
            return f'FALHA corpo de erro com campos além de "error" em {cls}', [json.dumps(r_json)[:200]]
        if r_status < 400 and 'resp.json' not in spec.get('has', {}):
            return f'FALHA {cls} em 2xx sem corpo exato na expectativa', []
        original_wrote = 200 <= o_status < 300
        proved_unchanged = bool(spec.get('unchanged')) and 'pre_view' in r
        bad = []
        for p, a, b in rest:
            if p.startswith(RESP_ALLOWED):
                continue
            if p.startswith('.post.') and original_wrote and proved_unchanged:
                continue
            bad.append(f'{p}: {a!r} → {b!r}'[:200])
        if bad:
            return f'FALHA diferença não autorizada em {cls}', bad[:5]
        return f'intencional {cls}', []
    return 'FALHA diferença não aprovada', [f'{p}: {a!r} → {b!r}'[:200] for p, a, b in rest[:5]]


# ------------------------------------------------------------------ testes negativos
def negative_tests(results):
    """Mutações sobre registros reais, inclusive com classificação intencional: todas devem reprovar."""
    def find(group, name, mode='refatorado'):
        for x in results[mode][group]:
            if x['name'] == name:
                return x
        raise KeyError(name)

    out = []  # (tipo, rótulo, classificação, ok)

    def expect_fail(label, o, r):
        c, f = classify(o, r)
        out.append(('mutação', label, c, c.startswith('FALHA')))

    # controles positivos: os registros reais, sem mutação, passam
    for g, n in [('users_escrita', 'POST /users sucesso'), ('tasks_escrita', 'PUT /tasks/1 tags 0'),
                 ('auth', 'auth PUT anonimo'), ('seed_leitura', 'GET /tasks seed'),
                 ('rollback', 'conflito forçado PUT /users/2'), ('rollback', 'conflito forçado POST /users')]:
        c, _ = classify(find(g, n, 'original'), find(g, n))
        out.append(('controle', f'sem mutação: {n}', c, not c.startswith('FALHA')))
    o, r = find('rollback', 'conflito forçado PUT /users/2', 'original'), find('rollback', 'conflito forçado PUT /users/2')
    for label, fn in [
        ('C-07 role do usuário-alvo alterada', lambda x: x['post']['get']['json'].__setitem__('role', 'admin')),
        ('C-07 contagem de tarefas zerada', lambda x: x['post']['counts'].__setitem__('tasks', 0)),
        ('C-07 tarefas removidas da listagem', lambda x: x['post'].__setitem__('tasks', [])),
        ('C-07 outro usuário alterado', lambda x: x['post']['users'][0].__setitem__('name', 'Outro')),
        ('C-07 categoria alterada', lambda x: x['post']['categories'][0].__setitem__('color', '#000000')),
        ('C-07 email do alvo alterado', lambda x: x['post']['get']['json'].__setitem__('email', 'corrida2@email.com')),
        ('C-07 linha concorrente ausente', lambda x: x['post'].__setitem__('corrida', [])),
        ('C-07 campo extra no corpo de erro', lambda x: x['resp']['json'].__setitem__('detalhe', 'x')),
        ('C-07 password exposto no estado posterior', lambda x: x['post']['users'][1].__setitem__('password', '<presente>')),
    ]:
        m = copy.deepcopy(r)
        fn(m)
        expect_fail(label, o, m)
    o, r = find('users_escrita', 'POST /users sucesso', 'original'), find('users_escrita', 'POST /users sucesso')
    for label, fn in [
        ('F-01 identidade errada (id)', lambda x: x['resp']['json'].__setitem__('id', 99)),
        ('F-01 nome incorreto', lambda x: x['resp']['json'].__setitem__('name', 'Outro')),
        ('F-01 password exposto', lambda x: x['resp']['json'].__setitem__('password', '<presente>')),
        ('F-01 auth_nonce exposto', lambda x: x['resp']['json'].__setitem__('auth_nonce', '<presente>')),
        ('F-01 campo removido (email)', lambda x: x['resp']['json'].pop('email')),
        ('F-01 contagem posterior errada', lambda x: x['post']['counts'].__setitem__('users', 5)),
        ('F-01 banco não alterado', lambda x: x.__setitem__('post_state', x['pre_state'])),
        ('F-01 hash fraco gravado', lambda x: x['post'].__setitem__('hash_novo', 'md5')),
        ('F-01 data incoerente', lambda x: x['resp']['json'].__setitem__('created_at', '2001-01-01 00:00:00')),
    ]:
        m = copy.deepcopy(r)
        fn(m)
        expect_fail(label, o, m)
    o, r = find('tasks_escrita', 'PUT /tasks/1 tags 0', 'original'), find('tasks_escrita', 'PUT /tasks/1 tags 0')
    for label, fn in [
        ('R-05 banco alterado', lambda x: x.__setitem__('post_state', 'outro')),
        ('R-05 tags alteradas no GET posterior', lambda x: x['post']['get']['json'].__setitem__('tags', [])),
        ('R-05 mensagem errada', lambda x: x['resp']['json'].__setitem__('error', 'Outra')),
        ('R-05 status 200', lambda x: x['resp'].__setitem__('status', 200)),
        ('R-05 password exposto no GET posterior', lambda x: x['post']['get']['json'].__setitem__('password', '<presente>')),
        ('R-05 expectativa enfraquecida', lambda x: x.__setitem__('exp', {'status': 400})),
        ('R-05 campo extra no corpo de erro', lambda x: x['resp']['json'].__setitem__('detalhe', 'x')),
        ('R-05 visão posterior alterada com digest igual', lambda x: x['post']['get']['json'].__setitem__('title', 'X')),
    ]:
        m = copy.deepcopy(r)
        fn(m)
        expect_fail(label, o, m)
    o, r = find('auth', 'auth PUT anonimo', 'original'), find('auth', 'auth PUT anonimo')
    for label, fn in [
        ('D-1a banco alterado', lambda x: x.__setitem__('post_state', 'outro')),
        ('D-1a status 200', lambda x: x['resp'].__setitem__('status', 200)),
        ('D-1a sem WWW-Authenticate', lambda x: x['resp'].pop('www_authenticate')),
        ('D-1a nome alterado', lambda x: x['post']['get']['json'].__setitem__('name', 'Alterado')),
    ]:
        m = copy.deepcopy(r)
        fn(m)
        expect_fail(label, o, m)
    o, r = find('seed_leitura', 'GET /tasks seed', 'original'), find('seed_leitura', 'GET /tasks seed')
    for label, fn in [
        ('sem classe: ordem alterada', lambda x: x['resp']['json'].reverse()),
        ('sem classe: valor errado (overdue)', lambda x: x['resp']['json'][0].__setitem__('overdue', False)),
        ('sem classe: prazo errado com formato válido', lambda x: x['resp']['json'][0].__setitem__('due_date', '2030-01-01 00:00:00')),
        ('sem classe: campo removido', lambda x: x['resp']['json'][1].pop('title')),
        ('sem classe: cópia de outro endpoint', lambda x: x.__setitem__('resp', find('seed_leitura', 'GET /categories')['resp'])),
        ('sem classe: classe inventada', lambda x: (x['resp']['json'][0].__setitem__('title', 'X'), x.__setitem__('cls', 'C-01'))),
    ]:
        m = copy.deepcopy(r)
        fn(m)
        expect_fail(label, o, m)
    # expectativa falha com respostas idênticas
    m_o, m_r = copy.deepcopy(o), copy.deepcopy(r)
    m_o['exp'] = m_r['exp'] = {'status': 201}
    expect_fail('expectativa falha com respostas idênticas', m_o, m_r)
    return out


def main():
    res_dir, matriz, resumo = sys.argv[1:4]
    problems = []
    results = {'original': {}, 'refatorado': {}}
    for mode in results:
        for g in GROUPS:
            path = os.path.join(res_dir, mode, g + '.json')
            if not os.path.exists(path):
                problems.append(f'{mode}/{g}: resultado ausente')
                results[mode][g] = []
                continue
            recs = json.load(open(path))['records']
            if not recs:
                problems.append(f'{mode}/{g}: execução vazia')
            names = [x['name'] for x in recs]
            dups = sorted({n for n in names if names.count(n) > 1})
            if dups:
                problems.append(f'{mode}/{g}: casos duplicados {dups}')
            results[mode][g] = recs
    # inventário explícito (independente dos resultados validados)
    inventory = json.load(open(INVENTORY))
    for mode in results:
        for g in GROUPS:
            planned = inventory[mode].get(g)
            if planned is None:
                problems.append(f'{mode}/{g}: grupo sem inventário')
                continue
            got = [x['name'] for x in results[mode][g]]
            for n in planned:
                if n not in got:
                    problems.append(f'{mode}/{g}: caso do inventário AUSENTE nos resultados: "{n}"')
            for n in got:
                if n not in planned:
                    problems.append(f'{mode}/{g}: caso FORA do inventário: "{n}"')
    neg = negative_tests(results) if not any('AUSENTE' in p or 'ausente' in p for p in problems) else []
    neg_fail = [n for n in neg if not n[3]]
    if neg_fail:
        problems += [f'teste do comparador não passou: {n[0]} {n[1]} → {n[2]}' for n in neg_fail]
    rows, summary = [], {}
    totals = {'registros_original': 0, 'registros_refatorado': 0, 'http_refatorado': 0, 'fatos_refatorado': 0,
              'comparados': 0, 'so_refatorado': 0}
    for g in GROUPS:
        oo = {x['name']: x for x in results['original'][g]}
        rr = {x['name']: x for x in results['refatorado'][g]}
        totals['registros_original'] += len(oo)
        totals['registros_refatorado'] += len(rr)
        for n in oo:
            if n not in rr:
                problems.append(f'{g}/{n}: caso da linha de base ausente no refatorado')
        for n, r in rr.items():
            if 'fact' in r:
                totals['fatos_refatorado'] += 1
            else:
                totals['http_refatorado'] += 1
            o = oo.get(n)
            if o is None and r.get('only') != 'refatorado':
                problems.append(f'{g}/{n}: caso ausente no original e não declarado exclusivo')
            if o is None:
                totals['so_refatorado'] += 1
            else:
                totals['comparados'] += 1
            cls, fails = classify(o, r)
            key = cls if not cls.startswith('intencional') else 'intencional'
            summary[key] = summary.get(key, 0) + 1
            if cls.startswith('FALHA'):
                problems.append(f'{g}/{n}: {cls}: {"; ".join(fails)[:300]}')

            def st(x):
                if x is None:
                    return '—'
                if 'resp' in x:
                    e = x['resp'].get('json', {}).get('error') if isinstance(x['resp'].get('json'), dict) else None
                    return str(x['resp']['status']) + ('' if x['resp'].get('is_json') else ' (HTML)') + (f' `{e}`' if e else '')
                return f'`{json.dumps(x.get("fact"), ensure_ascii=False)[:50]}`'
            rows.append(f'| {g} | {n.replace("|", "/")} | {st(o)} | {st(r)} | {r.get("cls") or ""} | {cls} |')
    by_cls = {}
    for line in rows:
        c = line.rsplit('|', 2)[-2].strip()
        if c.startswith('intencional'):
            by_cls[c] = by_cls.get(c, 0) + 1
    totals.update({'preservados': summary.get('preservado', 0), 'intencionais': summary.get('intencional', 0),
                   'falhas': sum(v for k, v in summary.items() if k.startswith('FALHA')), 'problemas': len(problems),
                   'controles': sum(1 for n in neg if n[0] == 'controle'),
                   'controles_aprovados': sum(1 for n in neg if n[0] == 'controle' and n[3]),
                   'mutacoes': sum(1 for n in neg if n[0] == 'mutação'),
                   'mutacoes_detectadas': sum(1 for n in neg if n[0] == 'mutação' and n[3]),
                   'inventario_casos': {m: sum(len(v) for v in inventory[m].values()) for m in ('original', 'refatorado')}})
    with open(resumo, 'w') as fh:
        json.dump({'totais': totals, 'por_classe': by_cls, 'problemas': problems}, fh, ensure_ascii=False, indent=1)
    head = ['# Matriz — rodada 3 (original × refatorado)', '', 'Gerada por `tools/compare.py`. Valores sensíveis não aparecem.', '',
            '## Totais', '', '```', json.dumps(totals, ensure_ascii=False, indent=1), '```', '',
            '## Diferenças intencionais por classe', '', '| Classe | Casos |', '|---|---:|']
    head += [f'| {k} | {v} |' for k, v in sorted(by_cls.items())]
    head += ['', '## Verificações do comparador (controles positivos e mutações negativas)', '',
             '| Tipo | Verificação | Resultado | OK |', '|---|---|---|---|']
    head += [f'| {t} | {n} | {c} | {"sim" if ok else "NÃO"} |' for t, n, c, ok in neg]
    head += ['', f'## Problemas: {len(problems)}', ''] + [f'- {p}' for p in problems]
    head += ['', '## Casos', '', '| Grupo | Caso | Original | Refatorado | cls | Resultado |', '|---|---|---|---|---|---|']
    with open(matriz, 'w') as fh:
        fh.write('\n'.join(head + rows) + '\n')
    print(json.dumps(totals, ensure_ascii=False))
    for p in problems[:40]:
        print('PROBLEMA:', p)
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
