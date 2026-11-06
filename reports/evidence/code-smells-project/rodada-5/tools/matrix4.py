"""Matriz de endpoints (linha de base x refatorado) — rodada 4: token também em D-10/D-11.

Uso: python matrix.py <base_url> <db_path> <saida.json> [--refatorado]
Senhas de login vêm de SEED_SENHA_ADMIN/JOAO/MARIA; token de ADMIN_TOKEN.
Toda senha, hash e token é mascarado na saída.
"""
import json
import os
import re
import secrets
import sqlite3
import sys
import urllib.error
import urllib.request

BASE, DB_PATH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
REFATORADO = "--refatorado" in sys.argv
TOKEN = os.environ.get("ADMIN_TOKEN", "")
SENHAS = {
    "admin": os.environ.get("SEED_SENHA_ADMIN", ""),
    "joao": os.environ.get("SEED_SENHA_JOAO", ""),
}
SENHA_TESTE = secrets.token_urlsafe(12)  # senha do usuário criado no teste, gerada a cada execução
SEGREDOS = [v for v in [TOKEN, *SENHAS.values(), SENHA_TESTE] if v]
HASH_RE = re.compile(r"(scrypt|pbkdf2)[:$][^\"\s]+")


def mascarar(texto):
    for segredo in SEGREDOS:
        texto = texto.replace(segredo, "<removido>")
    texto = HASH_RE.sub("<hash-removido>", texto)
    texto = re.sub(r'"senha":\s*"[^"]*"', '"senha": "<removido>"', texto)
    texto = re.sub(r'"secret_key":\s*"[^"]*"', '"secret_key": "<removido>"', texto)
    texto = re.sub(r'"criado_em":\s*"[^"]*"', '"criado_em": "<ts>"', texto)
    return texto


def contagens():
    con = sqlite3.connect(DB_PATH)
    try:
        return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("produtos", "usuarios", "pedidos", "itens_pedido")}
    finally:
        con.close()


def estoque(produto_id):
    con = sqlite3.connect(DB_PATH)
    try:
        row = con.execute("SELECT estoque FROM produtos WHERE id = ?", (produto_id,)).fetchone()
        return row[0] if row else None
    finally:
        con.close()


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
resultados = []


def chamar(nome, metodo, caminho, corpo=None, protegido=False, bruto=None, efeito=None):
    headers = {}
    data = None
    if bruto is not None:
        data = bruto.encode()
        headers["Content-Type"] = "text/plain"
    elif corpo is not None:
        data = json.dumps(corpo).encode()
        headers["Content-Type"] = "application/json"
    if protegido and REFATORADO and TOKEN:
        headers["X-Admin-Token"] = TOKEN
    req = urllib.request.Request(BASE + caminho, data=data, method=metodo, headers=headers)
    try:
        with OPENER.open(req, timeout=10) as resp:
            status, texto = resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        status, texto = err.code, err.read().decode()
    try:
        corpo_resp = json.loads(texto)
        texto_norm = json.dumps(corpo_resp, ensure_ascii=False, sort_keys=True)
    except ValueError:
        corpo_resp = None
        texto_norm = texto.strip()[:300]
    registro = {
        "caso": nome,
        "metodo": metodo,
        "caminho": caminho,
        "entrada": mascarar(json.dumps(corpo, ensure_ascii=False)) if corpo is not None else bruto,
        "auth": "X-Admin-Token: <removido>" if "X-Admin-Token" in headers else "-",
        "status": status,
        "corpo": mascarar(texto_norm),
    }
    if efeito:
        registro["efeito"] = efeito()
    resultados.append(registro)
    return status, corpo_resp


ADMIN_LOGIN = {"email": "admin@loja.com", "senha": SENHAS["admin"]}

# --- sistema / leitura
chamar("indice", "GET", "/")
chamar("health", "GET", "/health")
chamar("listar produtos", "GET", "/produtos")
chamar("produto existente", "GET", "/produtos/1")
chamar("produto inexistente", "GET", "/produtos/999")
chamar("busca por termo", "GET", "/produtos/busca?q=Mouse")
chamar("busca categoria+faixa", "GET", "/produtos/busca?categoria=moveis&preco_min=100&preco_max=2000")
chamar("busca com aspas (injecao)", "GET", "/produtos/busca?q=x%27%20OR%20%271%27%3D%271")
chamar("busca preco_min invalido", "GET", "/produtos/busca?preco_min=abc")

# --- produtos escrita
chamar("criar produto valido", "POST", "/produtos",
       {"nome": "Livro Python", "descricao": "Livro", "preco": 99.9, "estoque": 5, "categoria": "livros"},
       efeito=contagens, protegido=True)
chamar("criar produto sem nome", "POST", "/produtos", {"preco": 1, "estoque": 1}, protegido=True)
chamar("criar produto categoria invalida", "POST", "/produtos",
       {"nome": "X Y", "preco": 1, "estoque": 1, "categoria": "nada"}, protegido=True)
chamar("criar produto com aspas", "POST", "/produtos",
       {"nome": "Livro D'Avila", "descricao": "it's", "preco": 10, "estoque": 1, "categoria": "livros"},
       efeito=contagens, protegido=True)
chamar("criar produto preco string", "POST", "/produtos", {"nome": "Abc", "preco": "abc", "estoque": 1}, protegido=True)
chamar("criar produto sem corpo JSON", "POST", "/produtos", bruto="x", protegido=True)
chamar("atualizar produto 11", "PUT", "/produtos/11",
       {"nome": "Livro Python 2", "descricao": "Novo", "preco": 120.0, "estoque": 7, "categoria": "livros"}, protegido=True)
chamar("ler produto 11 apos update", "GET", "/produtos/11")
chamar("atualizar produto inexistente", "PUT", "/produtos/999", {"nome": "Ab", "preco": 1, "estoque": 1}, protegido=True)
chamar("atualizar produto categoria invalida", "PUT", "/produtos/11",
       {"nome": "Livro Python 2", "preco": 120.0, "estoque": 7, "categoria": "nada"}, protegido=True)
chamar("deletar produto 12", "DELETE", "/produtos/12", efeito=contagens, protegido=True)
chamar("ler produto 12 apos delete", "GET", "/produtos/12")
chamar("deletar produto inexistente", "DELETE", "/produtos/999", protegido=True)

# --- usuarios
chamar("listar usuarios", "GET", "/usuarios", protegido=True)
chamar("usuario existente", "GET", "/usuarios/1", protegido=True)
chamar("usuario inexistente", "GET", "/usuarios/999", protegido=True)
chamar("criar usuario valido", "POST", "/usuarios",
       {"nome": "Teste", "email": "teste@loja.com", "senha": SENHA_TESTE}, efeito=contagens)
chamar("criar usuario incompleto", "POST", "/usuarios", {"nome": "Teste"})
chamar("login admin valido", "POST", "/login", ADMIN_LOGIN)
chamar("login usuario criado", "POST", "/login", {"email": "teste@loja.com", "senha": SENHA_TESTE})
chamar("login senha errada", "POST", "/login", {"email": "admin@loja.com", "senha": "errada"})
chamar("login incompleto", "POST", "/login", {"email": "admin@loja.com"})
chamar("login sem corpo JSON", "POST", "/login", bruto="x")
chamar("login injecao", "POST", "/login", {"email": "admin@loja.com' --", "senha": "qualquer"})

# --- pedidos
antes = estoque(2)
chamar("criar pedido valido", "POST", "/pedidos",
       {"usuario_id": 2, "itens": [{"produto_id": 2, "quantidade": 2}, {"produto_id": 3, "quantidade": 1}]},
       efeito=lambda: {"estoque_produto_2_antes": antes, "estoque_produto_2_depois": estoque(2), **contagens()})
chamar("pedido produto inexistente", "POST", "/pedidos",
       {"usuario_id": 2, "itens": [{"produto_id": 999, "quantidade": 1}]})
chamar("pedido estoque insuficiente", "POST", "/pedidos",
       {"usuario_id": 2, "itens": [{"produto_id": 6, "quantidade": 1000}]})
chamar("pedido sem usuario", "POST", "/pedidos", {"itens": [{"produto_id": 1, "quantidade": 1}]})
chamar("pedido sem itens", "POST", "/pedidos", {"usuario_id": 2, "itens": []})
antes_neg = estoque(1)
chamar("pedido quantidade negativa", "POST", "/pedidos",
       {"usuario_id": 2, "itens": [{"produto_id": 1, "quantidade": -5}]},
       efeito=lambda: {"estoque_produto_1_antes": antes_neg, "estoque_produto_1_depois": estoque(1)})
chamar("pedido produto_id com injecao", "POST", "/pedidos",
       {"usuario_id": 2, "itens": [{"produto_id": "1 OR 1=1", "quantidade": 1}]}, efeito=contagens)
chamar("listar pedidos", "GET", "/pedidos", protegido=True)
chamar("pedidos do usuario 2", "GET", "/pedidos/usuario/2", protegido=True)
chamar("pedidos de usuario sem pedidos", "GET", "/pedidos/usuario/999", protegido=True)
chamar("status aprovado", "PUT", "/pedidos/1/status", {"status": "aprovado"}, protegido=True)
chamar("status invalido", "PUT", "/pedidos/1/status", {"status": "xyz"}, protegido=True)
chamar("status pedido inexistente", "PUT", "/pedidos/999/status", {"status": "enviado"}, protegido=True)
chamar("status sem corpo JSON", "PUT", "/pedidos/1/status", bruto="x", protegido=True)
chamar("relatorio vendas", "GET", "/relatorios/vendas", protegido=True)
chamar("health apos escritas", "GET", "/health")

# --- admin
if REFATORADO:
    chamar("admin query predefinida", "POST", "/admin/query", {"consulta": "contagem_por_tabela"}, protegido=True)
else:
    chamar("admin query select", "POST", "/admin/query", {"sql": "SELECT id, nome FROM produtos WHERE id <= 2"})
chamar("admin query sem consulta", "POST", "/admin/query", {}, protegido=True)
chamar("admin reset-db", "POST", "/admin/reset-db", protegido=True, efeito=contagens)
chamar("listar produtos apos reset", "GET", "/produtos")
chamar("health apos reset", "GET", "/health")

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(resultados, fh, ensure_ascii=False, indent=1)
print(f"{len(resultados)} casos gravados em {OUT}")
