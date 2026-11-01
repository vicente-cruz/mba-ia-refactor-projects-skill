"""Expectativas declarativas e verificações globais (usado pelo harness e pelo comparador).

Uma expectativa é um dict serializável avaliado sobre o registro de um caso:
  status, error, is_json         resposta HTTP
  has     {caminho: valor}       igualdade exata em todos os valores resolvidos
  lacks   [caminho]              caminho não pode existir
  keys    {caminho: [chaves]}    conjunto exato de chaves de cada dict resolvido
  ids     {caminho: [ids]}       lista de 'id' dos itens, em ordem
  len     {caminho: n}
  ts      {caminho: [offset_s, tolerância_s]}  datetime ≈ instante da requisição + offset
                                 (offset 'local' = relógio local, para /health)
  unchanged / changed            estado do banco (digest) depois × antes da requisição
Caminhos: pontos; '*' percorre itens de lista/valores de dict; números indexam listas.
"""
import json
from datetime import datetime, timedelta

ABSENT = '<ausente>'
TS_FORMATS = ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S')
TS_KEYS = ('created_at', 'updated_at', 'generated_at', 'timestamp', 'due_date')
FORBIDDEN_PUBLIC_KEYS = ('password', 'auth_nonce')
_NONE = object()


def resolve(obj, path):
    if path == '':
        return [obj]
    vals = [obj]
    for part in path.split('.'):
        nxt = []
        for v in vals:
            if part == '*':
                if isinstance(v, list):
                    nxt.extend(v)
                elif isinstance(v, dict):
                    nxt.extend(v.values())
            elif isinstance(v, list) and part.lstrip('-').isdigit():
                i = int(part)
                if -len(v) <= i < len(v):
                    nxt.append(v[i])
            elif isinstance(v, dict) and part in v:
                nxt.append(v[part])
        vals = nxt
    return vals


def same(v, e):
    """Igualdade estrita: True != 1; contêineres comparados pela serialização JSON."""
    if isinstance(v, (dict, list)) or isinstance(e, (dict, list)):
        return json.dumps(v, sort_keys=True) == json.dumps(e, sort_keys=True)
    if isinstance(v, bool) or isinstance(e, bool):
        return type(v) is type(e) and v == e
    if isinstance(v, (int, float)) and isinstance(e, (int, float)):
        return v == e
    return type(v) is type(e) and v == e


def parse_ts(value):
    if not isinstance(value, str):
        return None
    for fmt in TS_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def evaluate(spec, rec):
    """Lista de falhas (vazia = expectativa atendida). spec None = não avaliado."""
    if spec is None:
        return []
    errs = []
    resp = rec.get('resp') or {}
    if 'status' in spec and resp.get('status') != spec['status']:
        errs.append(f"status {resp.get('status')} != {spec['status']}")
    if 'error' in spec:
        js = resp.get('json')
        actual = js.get('error', None) if isinstance(js, dict) else None
        if actual != spec['error']:
            errs.append(f"error {actual!r} != {spec['error']!r}")
    if 'is_json' in spec and resp.get('is_json') != spec['is_json']:
        errs.append(f"is_json {resp.get('is_json')} != {spec['is_json']}")
    for path, expected in spec.get('has', {}).items():
        vals = resolve(rec, path)
        if not vals:
            errs.append(f'{path}: ausente (esperado {expected!r})')
        for v in vals:
            if not same(v, expected):
                errs.append(f'{path}: {v!r} != {expected!r}')
                break
    for path in spec.get('lacks', []):
        if resolve(rec, path):
            errs.append(f'{path}: presente, mas não deveria existir')
    for path, keys in spec.get('keys', {}).items():
        vals = resolve(rec, path)
        if not vals:
            errs.append(f'{path}: ausente (keys)')
        for v in vals:
            if not isinstance(v, dict) or sorted(v) != sorted(keys):
                errs.append(f'{path}: chaves {sorted(v) if isinstance(v, dict) else type(v).__name__} != {sorted(keys)}')
                break
    for path, ids in spec.get('ids', {}).items():
        vals = resolve(rec, path)
        got = [x.get('id') if isinstance(x, dict) else x for x in (vals[0] if vals and isinstance(vals[0], list) else [])]
        if not vals or got != ids:
            errs.append(f'{path}: ids {got} != {ids}')
    for path, n in spec.get('len', {}).items():
        vals = resolve(rec, path)
        if not vals or not isinstance(vals[0], list) or len(vals[0]) != n:
            errs.append(f'{path}: len != {n}')
    for path, (offset, tol) in spec.get('ts', {}).items():
        vals = resolve(rec, path)
        if not vals:
            errs.append(f'{path}: ausente (ts)')
        ref_key = 'at_local' if offset == 'local' else 'at_utc'
        ref = parse_ts(rec.get(ref_key))
        off = 0 if offset == 'local' else offset
        for v in vals:
            t = parse_ts(v)
            if t is None or ref is None or abs((t - (ref + timedelta(seconds=off))).total_seconds()) > tol:
                errs.append(f'{path}: {v!r} fora de {ref_key}{off:+}s ±{tol}s')
                break
    if 'max_queries' in spec and (rec.get('queries') is None or rec['queries'] > spec['max_queries']):
        errs.append(f"consultas {rec.get('queries')} > {spec['max_queries']}")
    if spec.get('unchanged') and rec.get('pre_state') != rec.get('post_state'):
        errs.append('banco alterado (esperado inalterado)')
    if spec.get('changed') and rec.get('pre_state') == rec.get('post_state'):
        errs.append('banco inalterado (esperada alteração)')
    if spec.get('unchanged') and not rec.get('pre_state'):
        errs.append('unchanged sem estado registrado')
    return errs


def global_checks(rec, mode):
    """Valem para todo registro: datas coerentes e, no refatorado, sem campos sensíveis."""
    errs = []
    at = parse_ts(rec.get('at_utc'))

    def walk(obj, where):
        if isinstance(obj, dict):
            if mode == 'refatorado':
                for k in FORBIDDEN_PUBLIC_KEYS:
                    if k in obj:
                        errs.append(f'{where}: campo público proibido {k!r}')
            c, u = parse_ts(obj.get('created_at')), parse_ts(obj.get('updated_at'))
            for k in TS_KEYS:
                v = obj.get(k)
                if v is None:
                    continue
                t = parse_ts(v)
                if t is None:
                    errs.append(f'{where}.{k}: formato inválido {v!r}')
                elif k in ('created_at', 'updated_at', 'generated_at') and at and not (
                        at - timedelta(days=40) <= t <= at + timedelta(seconds=120)):
                    errs.append(f'{where}.{k}: fora da janela plausível {v!r}')
            if c and u and u < c:
                errs.append(f'{where}: updated_at < created_at')
            for k, v in obj.items():
                walk(v, f'{where}.{k}')
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f'{where}[{i}]')
    walk((rec.get('resp') or {}).get('json'), 'resp.json')
    walk((rec.get('post') or {}).get('get', {}).get('json') if isinstance(rec.get('post'), dict) else None, 'post.get.json')
    return errs


def normalize(obj):
    """Para comparação entre versões: datas → '<ts>' (já verificadas antes)."""
    if isinstance(obj, dict):
        return {k: ('<ts>' if k in TS_KEYS and isinstance(v, str) and parse_ts(v) else normalize(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize(x) for x in obj]
    return obj
