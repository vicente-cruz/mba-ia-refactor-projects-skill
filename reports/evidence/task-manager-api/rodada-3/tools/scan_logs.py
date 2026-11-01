"""Varre logs brutos (antes de qualquer sanitização) e, com --evidencias, os artefatos a publicar.

Uso: python -I -B scan_logs.py <tmp> <saida.txt> [--evidencias <dir>]
Segredos procurados: SECRET_KEY, senhas e tokens anotados pelo harness (segredos-*.txt) e
padrões (hash MD5 de 32 hex, hash werkzeug, 'parameters:' do SQLAlchemy, nonce de 43 caracteres).
Só contagens e nomes de arquivo são impressos. Código 1 se: refatorado/migração/CLI tiverem
qualquer ocorrência, ou as evidências contiverem qualquer segredo anotado.
"""
import glob
import hashlib
import os
import re
import sys

T, OUT = sys.argv[1], sys.argv[2]
EVID = sys.argv[sys.argv.index('--evidencias') + 1] if '--evidencias' in sys.argv else None
secrets_ = {os.environ['SECRET_KEY']}
for f in glob.glob(os.path.join(T, 'res', '*', 'segredos-*.txt')):
    secrets_ |= {line.strip() for line in open(f) if line.strip() and line.strip() != 'None'}
for k in ('SEED_ADMIN_PASSWORD', 'SEED_USER_PASSWORD', 'SEED_MANAGER_PASSWORD'):
    secrets_.add(os.environ[k])
# o hash MD5 de cada senha também é segredo (é o que F-05 expõe no original)
secrets_ |= {hashlib.md5(s.encode()).hexdigest() for s in list(secrets_)}
secret_rx = re.compile('|'.join(r'(?<![A-Za-z0-9_-])' + re.escape(s) + r'(?![A-Za-z0-9_-])'
                                for s in sorted(secrets_, key=len, reverse=True)))
patterns = {
    'segredo anotado (senha/token/chave)': secret_rx,
    'hash werkzeug': re.compile(r'(scrypt|pbkdf2):\d+[^\s\'"]*\$'),
    'hash md5 (32 hex)': re.compile(r'(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])'),
    "'parameters:' do SQLAlchemy": re.compile(r'parameters:'),
    'nonce/sid (43 urlsafe)': re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])'),
}
lines, fail = [], False
for mode in ('original', 'refatorado', 'migracao', 'cli', 'warn-original', 'warn-refatorado'):
    files = sorted(glob.glob(os.path.join(T, 'logs', mode, '*')))
    totals = {k: 0 for k in patterns}
    for f in files:
        text = open(f, errors='replace').read().replace(T, '<tmp>')
        for k, rx in patterns.items():
            totals[k] += sum(1 for _ in rx.finditer(text))
    lines.append(f'== logs {mode} ({len(files)} arquivos)')
    lines += [f'  {k}: {v}' for k, v in totals.items()]
    if not mode.endswith('original') and any(totals.values()):
        fail = True
        lines.append('  ** OCORRÊNCIA FORA DO ORIGINAL **')
if EVID:
    hits = []
    for root, _, files in os.walk(EVID):
        for name in files:
            p = os.path.join(root, name)
            text = open(p, errors='replace').read()
            if secret_rx.search(text) or patterns['hash werkzeug'].search(text):
                hits.append(os.path.relpath(p, EVID))
    lines.append(f'== evidências ({EVID}): arquivos com segredo anotado: {len(hits)} {hits}')
    fail = fail or bool(hits)
open(OUT, 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
sys.exit(1 if fail else 0)
