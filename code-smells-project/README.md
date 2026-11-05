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

`GET /usuarios`, `GET /usuarios/<id>`, `GET /relatorios/vendas`, `POST /admin/reset-db` e `POST /admin/query` exigem o header `X-Admin-Token` com o valor de `ADMIN_TOKEN`. `POST /admin/query` aceita apenas consultas predefinidas: `{"consulta": "contagem_por_tabela" | "pedidos_por_status" | "produtos_estoque_baixo" | "usuarios_por_tipo", "parametros": {...}}`.

Senhas são armazenadas com hash. Bancos `loja.db` criados pela versão anterior (senhas em texto puro) não são migrados: essas contas não autenticam até terem a senha redefinida.

## Estrutura

- `app.py`: `create_app()` (composition root) e execução local
- `config.py`: leitura e validação de variáveis de ambiente
- `database.py`: fábrica de conexões por instância, schema e seed (separados)
- `errors.py`, `auth.py`: erros centralizados e token administrativo
- `models/`: entidades, regras e persistência
- `controllers/`: casos de uso (recebem a conexão por parâmetro, sem dependência de Flask)
- `routes/`: Blueprints HTTP
- `tests/`: `python -B -m unittest discover -s tests -v`
