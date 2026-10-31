# ecommerce-api-legacy

LMS API (com fluxo de checkout) em Node.js/Express usada como entrada do desafio `refactor-arch`.

## Como rodar

```bash
npm install
export SEED_USER_PASSWORD='<senha do usuário inicial>'   # obrigatória
export ADMIN_TOKEN='<token administrativo>'              # necessário para os endpoints administrativos
npm start
```

A aplicação sobe em `http://localhost:3000` (ou na porta definida em `PORT`). O banco SQLite é em memória e já carrega seeds automaticamente no boot. Sem `SEED_USER_PASSWORD`, a aplicação encerra com mensagem de erro antes de abrir o banco ou a porta.

Variáveis de ambiente estão documentadas em `.env.example`.

`GET /api/admin/financial-report` e `DELETE /api/users/:id` exigem o cabeçalho `X-Admin-Token` igual a `ADMIN_TOKEN`
(sem `ADMIN_TOKEN` configurado: 403; cabeçalho ausente ou incorreto: 401).

Exemplos de requisições estão em `api.http`.
