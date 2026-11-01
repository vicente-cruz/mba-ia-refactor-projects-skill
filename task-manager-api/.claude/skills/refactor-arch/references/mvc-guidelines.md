# Guidelines do MVC alvo

Regras de arquitetura para propor (Fase 2) e executar (Fase 3) a reorganização. O alvo é uma **API JSON**: não há telas HTML, e a "View" é a camada que expõe HTTP e serializa respostas.

## 1. Responsabilidades por camada

| Camada | Faz | Não faz |
|---|---|---|
| **Models** | Representa entidades e suas regras intrínsecas (invariantes, cálculos do próprio dado, transições de estado válidas); encapsula persistência da entidade (consultas, gravações, transações da operação). | Ler `request`/`req`, definir status HTTP, montar JSON de resposta. |
| **Controllers** | Coordenam um caso de uso: recebem dados já extraídos da requisição, validam a entrada, chamam Models (e serviços, se existirem), decidem o resultado e sinalizam erros de domínio. | Escrever SQL, conhecer detalhes do driver, formatar a resposta HTTP final, acumular regras de negócio que pertencem a Models. |
| **Views / Routes** | Mapeiam método + caminho para o controller; extraem parâmetros de path, query e corpo; serializam o resultado em JSON e definem códigos de status. | Regras de negócio, consultas ao banco, cálculos. |

### Onde ficam regras de negócio e persistência

- **Regra que pertence a uma entidade** (ex.: "item está atrasado", "status permitido", "total do pedido") → no Model, como método ou função do módulo do model. Reutilize-a em todos os lugares em vez de reimplementar.
- **Persistência** → no Model (ou em um módulo de acesso a dados por entidade, se o projeto já separa assim). SQL e ORM ficam fora de Controllers e Routes.
- **Regra que coordena várias entidades** (ex.: checkout que cria matrícula, pagamento e auditoria) → função de caso de uso chamada pelo controller. Mantenha-a no controller **apenas** se for curta e só orquestrar chamadas a Models. Se envolver cálculo, transação e várias entidades, extraia para um módulo `services/` — e só nesse caso.
- **Controllers finos não significam Models gigantes.** Divida Models por entidade/domínio; um módulo `models.py` com quatro domínios é tão problemático quanto um controller inchado.

### Adaptação de "View" para APIs JSON

- `routes/` (Flask Blueprints, Express Routers) cumpre o papel de View: é a fronteira HTTP.
- Serialização: métodos como `to_public_dict()`/`toPublic()` no Model ou funções de apresentação próximas às rotas. Campos sensíveis nunca entram na representação pública.
- O nome do diretório pode ser `views/` ou `routes/`; prefira o que o projeto já usa.

## 2. Estruturas de referência (adaptáveis)

Não são obrigatórias nem devem ser copiadas sem necessidade. Ajuste ao tamanho do projeto e reaproveite a organização existente quando ela já separa responsabilidades.

**Flask**

```
<projeto>/
├── app.py                 # ponto de entrada: create_app() + execução local
├── config.py              # leitura de variáveis de ambiente
├── database.py            # conexão/extensão e ciclo de vida (init_app)
├── models/                # entidades, regras intrínsecas e persistência
├── controllers/           # casos de uso
├── routes/                # Blueprints: HTTP ↔ controllers
├── errors.py              # exceções de domínio e handlers centralizados
└── services/              # somente se houver integração externa ou regra multi-entidade concreta
```

**Express**

```
<projeto>/
├── src/
│   ├── app.js             # ponto de entrada (preserve o comando de start existente)
│   ├── config.js          # process.env
│   ├── database.js        # conexão, schema e seed explícitos
│   ├── models/
│   ├── controllers/
│   ├── routes/
│   └── middlewares/errorHandler.js
└── package.json
```

Se o projeto já tem `src/` ou já tem `models/` e `routes/`, mantenha-os e corrija o conteúdo. Mudar a estrutura apenas por estética não é objetivo.

## 3. Configuração

- Segredos, credenciais, URIs de banco, portas, modo debug e chaves de integração vêm de **variáveis de ambiente**, lidas em um único módulo de configuração.
- Segredos **não têm fallback literal** no código. Para desenvolvimento, documente as variáveis em `.env.example` (com valores fictícios) e, se for necessário que a aplicação inicie sem a variável, gere um valor efêmero em tempo de execução com aviso no log, nunca um valor fixo.
- Valores não secretos podem ter padrão seguro (ex.: porta original, debug desligado, caminho de banco local).
- Use bibliotecas de `.env` apenas se já forem dependências do projeto; caso contrário, leia o ambiente diretamente e documente as variáveis.
- Preserve os padrões que o comportamento atual pressupõe (ex.: mesma porta e mesmo arquivo de banco), salvo mudança justificada.

## 4. Tratamento de erros centralizado

- Defina exceções de domínio (ex.: `NotFoundError`, `ValidationError`) ou um erro HTTP com status, lançadas por Controllers/Models.
- Registre um handler central: Flask `@app.errorhandler(...)`/`app.register_error_handler`; Express middleware `(err, req, res, next)` registrado **após** as rotas. No Express 4, erros em funções `async` precisam ser encaminhados com `next(err)` (wrapper); o Express 5 já encaminha promessas rejeitadas.
- O handler converte erro de domínio em 4xx com mensagem controlada e erro inesperado em 500 genérico, registrando o detalhe no log, não na resposta.
- **Preserve o formato de erro existente** (ex.: chave `erro` vs `error`, campos adicionais), pois ele faz parte do contrato.

## 5. Inicialização e ponto de entrada

- Um ponto de entrada claro cria o app, carrega configuração, inicializa o banco, registra rotas e handlers e inicia o servidor. Em Flask, prefira `create_app(config)`; em Express, separe a criação do app (`createApp`) de `listen`, se isso facilitar testes.
- Nenhum módulo deve criar banco, tabelas, seeds ou conexões externas **na importação**. Faça isso em funções chamadas explicitamente pelo ponto de entrada.
- Preserve o comando de inicialização documentado do projeto (ex.: `python app.py`, `npm start`). Se for preciso mudá-lo, atualize o manifesto correspondente e registre a mudança.
- Preserve o comportamento de inicialização relevante (ex.: criação de schema e seed automáticos), a menos que seja um problema apontado na auditoria e a mudança tenha sido aprovada.

## 6. Dependências entre camadas

```
routes → controllers → models (→ database)
            ↘ services (opcional) → models / integrações
config, errors: usados por todas
```

- Dependências apontam para dentro; Models não importam Routes nem Controllers.
- Passe dependências concretas (conexão, cliente de e-mail) por parâmetro, factory ou registro no app, para permitir dados isolados e dublês em testes.

## 7. Quando **não** adicionar camadas

- Não crie `services/`, `repositories/`, interfaces ou containers de injeção sem um problema concreto que eles resolvam (regra multi-entidade, integração externa, necessidade de substituição em testes).
- Não divida um arquivo pequeno e coeso apenas para cumprir uma árvore de diretórios.
- Dividir um God Class em vários arquivos **sem** separar responsabilidades não resolve o problema.
- Justifique no plano da Fase 2 cada camada nova.
