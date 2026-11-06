# code-smells-project

API de E-commerce em Python/Flask usada como entrada do desafio `refactor-arch`.

## Como rodar

```bash
pip install -r requirements.txt
export ADMIN_TOKEN=... SEED_SENHA_ADMIN=... SEED_SENHA_JOAO=... SEED_SENHA_MARIA=...
python app.py
```

A aplicação sobe em `http://127.0.0.1:5000` (configure `HOST`/`PORT` para alterar). O banco SQLite (`loja.db`, ou `DATABASE_PATH`) é criado no primeiro boot. As variáveis estão documentadas em `.env.example`.

### Inicialização e dados de demonstração

A inicialização sempre cria as tabelas (`init_schema`). A carga de demonstração (`seed_demo_if_empty`) é separada e controlada por `SEED_ON_STARTUP`:

| Valor | Efeito |
|---|---|
| ausente ou `1` | carga ligada (padrão): com `produtos` vazia, insere os 10 produtos e os usuários de demonstração cujas senhas foram configuradas; e-mails que já existem são pulados, sem alterar senha nem perfil |
| `0` | carga desligada: só as tabelas; nenhum produto ou usuário de demonstração, mesmo com `SEED_SENHA_*` definidas. Reiniciar após `POST /admin/reset-db` mantém o banco vazio |
| outro valor | a inicialização é recusada antes de abrir o banco |

Com a carga ligada, reiniciar sobre um banco populado não duplica dados; reiniciar após um reset repõe a demonstração.

Em testes, `create_app(overrides, connection_factory=...)` aceita `SEED_ON_STARTUP` apenas como `bool` e uma fábrica de conexões sqlite3 (com `row_factory = sqlite3.Row`) que substitui a abertura de `DATABASE_PATH` naquela instância.

### Rotas administrativas

Exigem o header `X-Admin-Token` com o valor de `ADMIN_TOKEN` (sem `ADMIN_TOKEN` configurado: 403; token ausente ou incorreto: 401):

- `GET /usuarios`, `GET /usuarios/<id>`, `GET /relatorios/vendas`, `POST /admin/reset-db`, `POST /admin/query`;
- `GET /pedidos`, `GET /pedidos/usuario/<id>` e `PUT /pedidos/<id>/status`;
- `POST /produtos`, `PUT /produtos/<id>` e `DELETE /produtos/<id>`.

Continuam públicas as rotas do cliente: `GET /produtos`, `GET /produtos/<id>`, `GET /produtos/busca`, `POST /usuarios`, `POST /login`, `POST /pedidos`, `GET /` e `GET /health`. `POST /admin/query` aceita apenas consultas predefinidas: `{"consulta": "contagem_por_tabela" | "pedidos_por_status" | "produtos_estoque_baixo" | "usuarios_por_tipo", "parametros": {...}}`.

### Senhas e bancos legados

Senhas são armazenadas com hash. Um banco criado pela versão anterior guarda senhas em texto puro. Enquanto houver alguma credencial legada (texto puro ou formato inválido) em `usuarios.senha`, a inicialização é **recusada** antes de qualquer escrita ou seed: `python app.py` termina com código 1 e indica o comando abaixo.

Procedimento do operador:

1. Pare a aplicação e feche qualquer outra conexão com o banco (shells `sqlite3`, ferramentas de leitura).
2. Simule: `python migrar_senhas.py caminho/do/loja.db`. A simulação não abre o banco pelo SQLite: lê os bytes do arquivo e do `-wal` (aplicando em memória o que já foi confirmado no WAL) e mostra as contagens (hashes válidos, sem credencial, legadas) sem criar nem alterar arquivos. Se o banco mudar durante a leitura ou houver um journal de rollback ativo, a simulação é recusada (código 1) sem tocar em nada.
3. Aplique: `python migrar_senhas.py caminho/do/loja.db --aplicar`.
   - Etapa 1, numa transação única: cada credencial legada passa a `NULL`. Hashes válidos, IDs, perfis e as demais tabelas não mudam. Qualquer falha antes do commit desfaz tudo (código de saída 1).
   - Etapa 2, depois do commit: `VACUUM`, que reescreve o arquivo sem as sobras das senhas antigas (inclusive páginas livres), e, se o banco usar WAL, checkpoints `TRUNCATE` com o resultado conferido (nenhuma conexão bloqueando e `-wal` com 0 bytes). A etapa 1 grava uma marca de "limpeza pendente" (`PRAGMA user_version`) que só é removida depois de comprovada a limpeza; enquanto ela existir, a inicialização também é recusada. Se a limpeza não puder ser comprovada (por exemplo, outra conexão lendo o banco), o script termina com código 1, as credenciais já estão invalidadas e a marca continua: feche as conexões e rode o mesmo comando de novo. O comando pode ser repetido com segurança.
4. Inicie a aplicação. As contas legadas existem, mas não autenticam: recrie as credenciais dessas pessoas (por exemplo, um novo cadastro via `POST /usuarios`).
5. Trate cópias e backups antigos do banco: eles ainda contêm as senhas em texto puro e devem ser destruídos ou migrados da mesma forma. O script também não apaga dados que o sistema de arquivos ou o disco mantenham fora do arquivo SQLite.

O caminho do banco é sempre informado explicitamente (o script não lê `DATABASE_PATH`) e precisa existir: nenhum arquivo é criado.

## Estrutura

- `app.py`: `create_app()` (composition root) e execução local
- `migrar_senhas.py`: invalidação de credenciais legadas (simulação por padrão; `--aplicar` grava)
- `config.py`: leitura e validação de variáveis de ambiente
- `database.py`: fábrica de conexões por instância, schema e seed (separados)
- `errors.py`, `auth.py`: erros centralizados e token administrativo
- `models/`: entidades, regras e persistência
- `controllers/`: casos de uso (recebem a conexão por parâmetro, sem dependência de Flask)
- `routes/`: Blueprints HTTP
- `tests/`: `python -B -m unittest discover -s tests -v`
