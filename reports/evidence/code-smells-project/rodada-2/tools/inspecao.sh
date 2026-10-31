#!/usr/bin/env bash
# Nova inspeção estática (somente leitura) do código refatorado. Executar na raiz do projeto.
g() { grep -rnE --include='*.py' --exclude-dir=.claude --exclude-dir=__pycache__ --exclude-dir=tests "$@" || echo "   (nenhuma ocorrência)"; }
echo "== AP-01: execute com concatenação ou f-string de valor externo"; g 'execute\((f"|f'"'"'|"[^"]*" *\+)' .
echo "== AP-01: f-strings em SQL (conferir que só interpolam constantes)"; g 'f"(SELECT|DELETE)|\{COLUNAS|\{tabela' models
echo "== AP-02: SECRET_KEY literal ou prefixo da chave antiga"; g -i 'minha-chave|SECRET_KEY"\] *= *"' .
echo "== AP-02/AP-04: senha literal em hash ou em tupla de seed (4 strings)"; g 'generate_password_hash\("|\("[^"]*", *"[^"]*@[^"]*", *"[^"]*", *"[^"]*"\)' .
echo "== AP-03: chave senha em código"; g '"senha"' .
echo "== AP-11: debug fixo / bind aberto"; g 'debug=True|0\.0\.0\.0' .
echo "== AP-08: estado global de conexão"; g 'global |check_same_thread' .
echo "== AP-16: str(e) / except Exception"; g 'str\(e\)|except Exception' .
echo "== AP-16: except amplos (conferir tipo capturado)"; g 'except ' .
echo "== AP-20: print( (exceto Blueprint)"; g '(^|[^A-Za-z])print\(' .
echo "== AP-07: SQL fora de models/database"; g 'execute\(' controllers routes app.py auth.py errors.py config.py
echo "== AP-07: request/jsonify fora de routes/errors/auth"; g '\brequest\b|jsonify' models controllers database.py config.py
echo "== AP-15: APIs obsoletas"; g 'utcnow|\.query\.get|before_first_request' .
