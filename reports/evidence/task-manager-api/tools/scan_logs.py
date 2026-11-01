"""Varre os logs brutos (antes de qualquer sanitização). Imprime só contagens e trechos mascarados."""
import glob, os, re, sys
S = sys.argv[1]
secret_key = open(os.path.join(S, 'out', 'secret_key')).read().strip()
tokens = set()
for f in glob.glob(os.path.join(S, 'out', '*', 'segredos-emitidos.txt')):
    tokens |= {l.strip() for l in open(f) if l.strip() and l.strip() != 'None'}
pw = ['<removido>', '<removido>', '<removido>', '<removido>', '<removido>', '<removido>', '<removido>', '<removido>', '<removido>']
patterns = {
    'senha de teste': re.compile(r"(?<![A-Za-z0-9])(" + '|'.join(map(re.escape, pw)) + r")(?![A-Za-z0-9])"),
    'hash werkzeug': re.compile(r'(scrypt|pbkdf2):[^\s\'"]+'),
    'hash md5 (32 hex)': re.compile(r'(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])'),
    'parameters:': re.compile(r'parameters:'),
    'nonce/sid (43 urlsafe)': re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])'),
}
for mode in ('original', 'refatorado', 'migracao', 'cli'):
    files = sorted(glob.glob(os.path.join(S, 'rawlogs', mode, '*')))
    total = {k: 0 for k in list(patterns) + ['token emitido', 'SECRET_KEY']}
    examples = {}
    for f in files:
        text = open(f, errors='replace').read()
        # caminhos de arquivo do ambiente temporário não são dados sensíveis
        text = text.replace(S, '<tmp>')
        for name, rx in patterns.items():
            for m in rx.finditer(text):
                line = text[max(0, text.rfind('\n', 0, m.start()) + 1): text.find('\n', m.end())]
                if name == 'senha de teste' and ('File "' in line or 'line ' in line and '.py' in line):
                    continue  # linhas de traceback/código-fonte, não valores
                total[name] += 1
                examples.setdefault(name, (os.path.basename(f), rx.sub('<removido>', line)[:160]))
        total['token emitido'] += sum(text.count(t) for t in tokens)
        total['SECRET_KEY'] += text.count(secret_key)
    print(f'== {mode} ({len(files)} arquivos)')
    for k, v in total.items():
        ex = f'  ex.: {examples[k][0]}: {examples[k][1]}' if k in examples else ''
        print(f'  {k}: {v}{ex}')
