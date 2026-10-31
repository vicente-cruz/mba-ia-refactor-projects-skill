# code-smells-project

API de E-commerce em Python/Flask usada como entrada do desafio `refactor-arch`.

## Como rodar

```bash
pip install -r requirements.txt
export ADMIN_TOKEN=... SEED_SENHA_ADMIN=... SEED_SENHA_JOAO=... SEED_SENHA_MARIA=...
python app.py
```

A aplicação sobe em `http://127.0.0.1:5000` (configure `HOST`/`PORT` para alterar). O banco SQLite (`loja.db`, ou `DATABASE_PATH`) é criado no primeiro boot, já com produtos de exemplo e com os usuários de demonstração cujas senhas foram configuradas. As variáveis estão documentadas em `.env.example`.

`GET /usuarios`, `GET /usuarios/<id>`, `GET /relatorios/vendas`, `POST /admin/reset-db` e `POST /admin/query` exigem o header `X-Admin-Token` com o valor de `ADMIN_TOKEN`. `POST /admin/query` aceita apenas consultas predefinidas: `{"consulta": "contagem_por_tabela" | "pedidos_por_status" | "produtos_estoque_baixo" | "usuarios_por_tipo", "parametros": {...}}`.

Senhas são armazenadas com hash. Bancos `loja.db` criados pela versão anterior (senhas em texto puro) não são migrados: essas contas não autenticam até terem a senha redefinida.

## Estrutura

- `app.py`: `create_app()` e execução local
- `config.py`: leitura de variáveis de ambiente
- `database.py`: conexão por requisição, schema e seed
- `errors.py`, `auth.py`: erros centralizados e token administrativo
- `models/`: entidades, regras e persistência
- `controllers/`: casos de uso
- `routes/`: Blueprints HTTP
