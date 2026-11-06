"""Invalida credenciais legadas (senha em texto puro ou formato inválido) de um banco SQLite da loja.

Uso:
    python migrar_senhas.py <banco>             # simulação (padrão): não abre o banco pelo SQLite
    python migrar_senhas.py <banco> --aplicar   # grava: invalida as legadas e limpa o arquivo

- O banco precisa ser indicado explicitamente e já existir; DATABASE_PATH não é lido e nenhum
  arquivo novo é criado.
- Simulação: lê os bytes de <banco> e <banco>-wal (sem abrir o banco pelo SQLite, que criaria ou
  alteraria -wal/-shm), aplica em memória os quadros já confirmados do WAL e analisa essa imagem.
  Se um arquivo mudar durante a leitura ou houver journal de rollback ativo, a simulação é recusada
  (código 1) sem tocar em nada.
- Hashes válidos do Werkzeug, IDs, perfis e as demais colunas e tabelas não são alterados. Cada
  credencial legada passa a NULL: a conta continua existindo, mas não autentica.
- Etapa 1 (transação única): UPDATE com secure_delete ligado, marca de limpeza pendente
  (PRAGMA user_version) e COMMIT. Qualquer falha antes do COMMIT desfaz tudo.
- Etapa 2 (limpeza física, depois do COMMIT): VACUUM e, em WAL, checkpoints TRUNCATE com o resultado
  conferido (nenhum bloqueio e -wal com 0 bytes); sem páginas livres nem journal remanescente. Só
  depois dessa comprovação a marca volta a 0. Enquanto a marca existir, a aplicação recusa a
  inicialização. Se a limpeza não puder ser comprovada (por exemplo, outra conexão lendo o banco),
  a CLI devolve código 1 e mantém a marca: feche as conexões e execute de novo com --aplicar.
- Nenhum conteúdo da coluna senha é impresso.
Pare a aplicação antes de aplicar. Cópias e backups antigos do banco continuam com as senhas legadas
e precisam ser tratados à parte (ver README).
"""
import argparse
import os
import sqlite3
import struct
import sys
from urllib.parse import quote

from models import usuario

SAIDA_OK, SAIDA_FALHA, SAIDA_USO = 0, 1, 2
MAGIC_JOURNAL = bytes.fromhex("d9d505f920a163d7")
MAGIC_WAL = (0x377F0682, 0x377F0683)
VERSAO_WAL = 3007000


class SimulacaoIndisponivel(Exception):
    """A simulação não pode garantir uma leitura somente leitura e consistente."""


class LimpezaNaoComprovada(Exception):
    """A etapa 2 não conseguiu comprovar a remoção física do conteúdo antigo."""


def abrir(caminho):
    """Conexão de escrita para --aplicar ("rw" não cria o arquivo)."""
    con = sqlite3.connect(f"file:{quote(os.path.abspath(caminho))}?mode=rw", uri=True, isolation_level=None)
    con.row_factory = sqlite3.Row
    return con


# ------------------------------------------------------------------ simulação (somente leitura)
def _ler_estavel(caminho):
    """Lê <banco>, -wal e -journal sem abrir o SQLite; recusa se algum arquivo mudar durante a leitura."""
    nomes = {"db": caminho, "wal": caminho + "-wal", "journal": caminho + "-journal"}

    def assinatura():
        resultado = {}
        for chave, nome in nomes.items():
            try:
                st = os.stat(nome)
            except FileNotFoundError:
                continue
            resultado[chave] = (st.st_size, st.st_mtime_ns, st.st_ino)
        return resultado

    for _ in range(3):
        antes = assinatura()
        dados = {}
        for chave in antes:
            with open(nomes[chave], "rb") as fh:
                dados[chave] = fh.read()
        if assinatura() == antes:
            return dados
    raise SimulacaoIndisponivel("o banco mudou durante a leitura; pare a aplicação e repita a simulação")


def _checksum(dados, s0, s1, big_endian):
    valores = struct.unpack((">" if big_endian else "<") + f"{len(dados) // 4}I", dados)
    for i in range(0, len(valores), 2):
        s0 = (s0 + valores[i] + s1) & 0xFFFFFFFF
        s1 = (s1 + valores[i + 1] + s0) & 0xFFFFFFFF
    return s0, s1


def _aplicar_wal(imagem, wal):
    """Aplica à imagem do banco os quadros do WAL até o último commit válido (salts e checksums
    conferidos, como na recuperação do SQLite). Quadros sem commit ou inválidos são ignorados."""
    if len(wal) < 32:
        return imagem
    magic, versao, tamanho_pagina, _seq, salt1, salt2, c1, c2 = struct.unpack(">8I", wal[:32])
    if (magic not in MAGIC_WAL or versao != VERSAO_WAL or not 512 <= tamanho_pagina <= 65536
            or tamanho_pagina & (tamanho_pagina - 1)):
        return imagem
    big_endian = magic & 1
    soma = _checksum(wal[:24], 0, 0, big_endian)
    if soma != (c1, c2):
        return imagem
    confirmadas, pendentes, paginas_no_commit, pos = {}, {}, None, 32
    while pos + 24 + tamanho_pagina <= len(wal):
        pagina, commit, s1, s2, k1, k2 = struct.unpack(">6I", wal[pos:pos + 24])
        if pagina == 0 or (s1, s2) != (salt1, salt2):
            break
        conteudo = wal[pos + 24:pos + 24 + tamanho_pagina]
        soma = _checksum(conteudo, *_checksum(wal[pos:pos + 8], *soma, big_endian), big_endian)
        if soma != (k1, k2):
            break
        pendentes[pagina] = conteudo
        if commit:
            confirmadas.update(pendentes)
            pendentes, paginas_no_commit = {}, commit
        pos += 24 + tamanho_pagina
    if paginas_no_commit is None:
        return imagem
    if len(imagem) >= 18:
        tamanho_banco = struct.unpack(">H", imagem[16:18])[0]
        if (65536 if tamanho_banco == 1 else tamanho_banco) != tamanho_pagina:
            raise SimulacaoIndisponivel("tamanho de página do WAL diferente do banco")
    total = paginas_no_commit * tamanho_pagina
    resultado = bytearray(imagem[:total])
    resultado.extend(bytes(total - len(resultado)))
    for pagina, conteudo in confirmadas.items():
        if pagina <= paginas_no_commit:
            resultado[(pagina - 1) * tamanho_pagina:pagina * tamanho_pagina] = conteudo
    return bytes(resultado)


def abrir_instantaneo(caminho):
    """Imagem em memória do estado confirmado mais recente, sem abrir os arquivos pelo SQLite."""
    dados = _ler_estavel(caminho)
    if dados.get("journal", b"")[:8] == MAGIC_JOURNAL:
        raise SimulacaoIndisponivel("há um journal de rollback ativo (transação em andamento ou interrompida); "
                                    "pare a aplicação e repita a simulação")
    imagem = bytearray(_aplicar_wal(dados["db"], dados.get("wal", b"")))
    modo = "wal" if len(imagem) >= 20 and imagem[18] == 2 else "rollback"
    if modo == "wal":
        imagem[18] = imagem[19] = 1  # a cópia em memória não usa WAL
    con = sqlite3.connect(":memory:", isolation_level=None)
    con.row_factory = sqlite3.Row
    if imagem:
        con.deserialize(bytes(imagem))
    if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        con.close()
        raise SimulacaoIndisponivel("a imagem lida não está íntegra; pare a aplicação e repita a simulação")
    return con, modo


# ------------------------------------------------------------------ situação e etapas
def situacao(con, modo=None):
    tabela = con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'usuarios'").fetchone()
    if tabela is None:
        return None
    resumo = usuario.resumo_credenciais(con)
    resumo["paginas_livres"] = con.execute("PRAGMA freelist_count").fetchone()[0]
    resumo["journal_mode"] = modo or con.execute("PRAGMA journal_mode").fetchone()[0]
    resumo["user_version"] = usuario.versao_do_banco(con)
    resumo["limpeza_pendente"] = "sim" if resumo["user_version"] == usuario.LIMPEZA_PENDENTE else "não"
    return resumo


def imprimir(rotulo, resumo):
    print(f"{rotulo}: usuarios={resumo['usuarios']} hashes_validos={resumo['hashes_validos']} "
          f"sem_credencial={resumo['sem_credencial']} legadas={resumo['legadas']} "
          f"paginas_livres={resumo['paginas_livres']} journal_mode={resumo['journal_mode']} "
          f"limpeza_pendente={resumo['limpeza_pendente']}")


def invalidar(con):
    """Etapa 1: tudo ou nada. Retorna a quantidade de credenciais invalidadas."""
    con.execute("PRAGMA secure_delete = ON")
    if con.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
        con.execute("PRAGMA journal_mode = DELETE")
    con.execute("BEGIN IMMEDIATE")
    try:
        ids = usuario.ids_com_credencial_legada(con)
        alteradas = usuario.invalidar_credenciais(con, ids)
        if alteradas != len(ids) or usuario.ids_com_credencial_legada(con):
            raise RuntimeError("verificação antes do commit não confere")
        usuario.marcar_limpeza_pendente(con)
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    return alteradas


def _arquivo(con):
    return con.execute("PRAGMA database_list").fetchone()[2]


def _checkpoint_truncate(con):
    """Checkpoint TRUNCATE com o resultado conferido: nenhum bloqueio e -wal com 0 bytes."""
    bloqueado, quadros, copiados = con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    wal = _arquivo(con) + "-wal"
    tamanho = os.path.getsize(wal) if os.path.exists(wal) else 0
    if bloqueado or tamanho:
        raise LimpezaNaoComprovada(
            f"checkpoint do WAL não concluído (busy={bloqueado}, quadros={quadros}, copiados={copiados}, "
            f"-wal com {tamanho} bytes): outra conexão está usando o banco")


def limpar(con):
    """Etapa 2: remove do arquivo o conteúdo antigo e só libera o boot depois de comprovar a limpeza."""
    wal = con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    if wal:
        _checkpoint_truncate(con)
    else:
        # Nesta conexão o journal é apagado ao final (PERSIST/TRUNCATE manteriam páginas antigas nele).
        con.execute("PRAGMA journal_mode = DELETE")
    con.execute("VACUUM")
    if wal:
        _checkpoint_truncate(con)
    livres = con.execute("PRAGMA freelist_count").fetchone()[0]
    if livres:
        raise LimpezaNaoComprovada(f"{livres} página(s) livre(s) após o VACUUM")
    journal = _arquivo(con) + "-journal"
    if not wal and os.path.exists(journal) and os.path.getsize(journal):
        raise LimpezaNaoComprovada("journal de rollback remanescente após o VACUUM")
    usuario.concluir_limpeza(con)
    if wal:
        try:
            _checkpoint_truncate(con)
        except LimpezaNaoComprovada:
            usuario.marcar_limpeza_pendente(con)  # mantém o boot recusado
            raise


# ------------------------------------------------------------------ CLI
def simular(caminho):
    try:
        con, modo = abrir_instantaneo(caminho)
    except (SimulacaoIndisponivel, sqlite3.DatabaseError) as erro:
        print(f"Simulação recusada: {erro}. Nenhum arquivo foi aberto pelo SQLite nem alterado.", file=sys.stderr)
        return SAIDA_FALHA
    try:
        resumo = situacao(con, modo)
    finally:
        con.close()
    if resumo is None:
        print("Simulação: o banco não tem a tabela usuarios. Nada a fazer.")
        return SAIDA_OK
    imprimir("Simulação", resumo)
    if resumo["limpeza_pendente"] == "sim":
        print("Simulação: a limpeza física de uma execução anterior não terminou; use --aplicar para concluí-la.")
    if resumo["legadas"]:
        print(f"Simulação: {resumo['legadas']} credencial(is) seriam invalidadas. Nenhuma alteração foi gravada; "
              "use --aplicar para gravar.")
    else:
        print("Simulação: nenhuma credencial legada. Nenhuma alteração foi gravada.")
    return SAIDA_OK


def aplicar(caminho):
    con = abrir(caminho)
    try:
        resumo = situacao(con)
        if resumo is None:
            print("O banco não tem a tabela usuarios. Nada foi alterado.")
            return SAIDA_OK
        imprimir("Antes", resumo)
        if resumo["user_version"] not in (0, usuario.LIMPEZA_PENDENTE):
            print(f"PRAGMA user_version inesperado ({resumo['user_version']}); este não parece um banco da loja. "
                  "Nada foi alterado.", file=sys.stderr)
            return SAIDA_FALHA
        try:
            alteradas = invalidar(con)
        except (sqlite3.Error, RuntimeError) as erro:
            print(f"Falha antes do commit ({type(erro).__name__}: {erro}). Transação desfeita; nada foi alterado.",
                  file=sys.stderr)
            return SAIDA_FALHA
        print(f"Etapa 1 confirmada: {alteradas} credencial(is) invalidada(s).")
        try:
            limpar(con)
        except (sqlite3.Error, LimpezaNaoComprovada) as erro:
            print(f"Limpeza física não comprovada ({type(erro).__name__}: {erro}). As credenciais legadas já estão "
                  "invalidadas e a inicialização continua recusada (limpeza pendente). Feche todas as conexões "
                  "com o banco (pare a aplicação e outros leitores) e execute novamente com --aplicar.",
                  file=sys.stderr)
            return SAIDA_FALHA
        print("Etapa 2 concluída e comprovada: arquivo reescrito (VACUUM), sem páginas livres nem WAL/journal "
              "remanescente.")
        imprimir("Depois", situacao(con))
    finally:
        con.close()
    return SAIDA_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="Invalida credenciais legadas de um banco da loja.")
    parser.add_argument("banco", help="caminho do arquivo SQLite (obrigatório; precisa existir)")
    parser.add_argument("--aplicar", action="store_true", help="grava as alterações (sem ela: simulação)")
    args = parser.parse_args(argv)
    if not os.path.isfile(args.banco):
        print(f"Banco não encontrado: {args.banco}. Nada foi criado.", file=sys.stderr)
        return SAIDA_USO
    return aplicar(args.banco) if args.aplicar else simular(args.banco)


if __name__ == "__main__":
    sys.exit(main())
