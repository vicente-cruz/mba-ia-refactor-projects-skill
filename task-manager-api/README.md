# task-manager-api

API de Task Manager em Python/Flask usada como entrada do desafio `refactor-arch`, reorganizada em MVC: `models/` (entidades, regras e consultas), `controllers/` (casos de uso e validação), `routes/` (Blueprints HTTP), com `config.py`, `errors.py`, `auth.py` e `database.py`.

## Como rodar

```bash
pip install -r requirements.txt
export SECRET_KEY='<valor aleatório com 32+ caracteres>'
export SEED_ADMIN_PASSWORD='...' SEED_USER_PASSWORD='...' SEED_MANAGER_PASSWORD='...'
python seed.py
python app.py
```

As variáveis estão documentadas em `.env.example` (o projeto não carrega `.env` automaticamente). Sem `SECRET_KEY` (mínimo de 32 caracteres) a aplicação e o seed não iniciam e nenhum banco é criado.

A aplicação sobe em `http://127.0.0.1:5000` (use `HOST=0.0.0.0` para aceitar conexões de outras máquinas; debug só com `FLASK_DEBUG=1`). O banco SQLite fica em `instance/tasks.db`. O `seed.py` apaga e recria usuários, categorias e tasks de exemplo numa única transação.

## Autenticação

`POST /login` devolve um `token` assinado (não é JWT), enviado como `Authorization: Bearer <token>`. São exigidos:

- `PUT /users/<id>`: o próprio usuário altera nome, email e senha; `role` e `active` só por admin;
- `DELETE /users/<id>`: somente admin;
- `POST /users` com `role` diferente de `user`: somente admin.

Trocar a senha revoga todos os tokens da conta. Os demais endpoints continuam públicos.
