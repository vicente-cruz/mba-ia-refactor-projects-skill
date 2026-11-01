# Desafio refactor-arch — Refatoração Arquitetural Automatizada

MBA em Engenharia de Software com IA — módulo Desenvolvimento de Software e Aplicações com IA.

Ferramenta escolhida: **Claude Code**, utilizado no VS Code em ambiente WSL.

**Estado técnico:** Skill criada e aplicada aos três projetos; auditorias, refatorações e validações concluídas no escopo aprovado, com revisão independente e correções posteriores. As limitações remanescentes estão documentadas em [Resultados](#resultados) e nos registros de validação. A aprovação refere-se aos cenários exercitados, não à ausência de toda vulnerabilidade ou à prontidão para produção.

| Projeto | Skill | Auditoria da Fase 2 | Validação final |
|---|---|---|---|
| E-commerce Flask | [refactor-arch](code-smells-project/.claude/skills/refactor-arch/SKILL.md) | [Projeto 1](reports/audit-project-1.md) | [Rodada 3, seção 13](reports/evidence/code-smells-project/validation.md#13-rodada-3-2026-10-31-hashes-malformados-que-ainda-provocavam-500) |
| LMS Express | [refactor-arch](ecommerce-api-legacy/.claude/skills/refactor-arch/SKILL.md) | [Projeto 2](reports/audit-project-2.md) | [Validação e revisões do comparador](reports/evidence/ecommerce-api-legacy/validation.md) |
| Task Manager Flask | [refactor-arch](task-manager-api/.claude/skills/refactor-arch/SKILL.md) | [Projeto 3](reports/audit-project-3.md) | [Rodada 3](reports/evidence/task-manager-api/rodada-3/validation.md) |

Navegação: [Análise Manual](#análise-manual) · [Construção da Skill](#construção-da-skill) · [Resultados](#resultados) · [Como Executar](#como-executar) · [Enunciado original](#enunciado-original).

## Análise Manual

### Método, escopo e versão de referência

- Data do registro: **30/10/2026**.
- Método: leitura estática do código assistida por IA, seguida de conferência humana dos trechos discutidos. Não houve execução da Skill, das aplicações, de testes funcionais ou de exploração de vulnerabilidades nesta etapa.
- Os achados são uma seleção inicial para orientar a construção da Skill. Não constituem uma auditoria exaustiva e não devem limitar a futura detecção automática.
- As severidades seguem a escala do enunciado. A seleção de cada projeto contém pelo menos um CRITICAL ou HIGH, dois MEDIUM e dois LOW.
- As quantidades de linhas incluem linhas em branco. Os totais de código consideram arquivos .py ou .js do projeto; no Task Manager incluem seed.py e __init__.py. Não incluem dependências instaladas.
- Versão de referência: commit [`6d1ce6248c3e956801010a89d8bdaab48029bf30`](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/commit/6d1ce6248c3e956801010a89d8bdaab48029bf30), presente no pacote enviado. O código extraído correspondia ao commit antes da edição deste README.
- Os links de localização abaixo apontam para esse commit, preservando a possibilidade de conferência quando os arquivos forem movidos ou alterados pela refatoração.
- Os IDs P1-xx, P2-xx e P3-xx identificam achados manuais. As auditorias posteriores têm seus próprios IDs F-xx; a correspondência está registrada em Resultados. Esta seção preserva a análise inicial, anterior à execução da Skill.
- As explicações de arquitetura, segurança e bibliotecas são interpretações técnicas aplicadas ao código. Não são transcrições nem afirmações atribuídas a aulas específicas do MBA. As referências externas estão identificadas ao final desta seção.

### Resumo dos achados manuais

| Projeto | CRITICAL | HIGH | MEDIUM | LOW | Total |
|---|---:|---:|---:|---:|---:|
| `code-smells-project` | 2 | 1 | 2 | 2 | 7 |
| `ecommerce-api-legacy` | 2 | 1 | 2 | 2 | 7 |
| `task-manager-api` | 1 | 1 | 3 | 2 | 7 |
| **Total** | **5** | **3** | **7** | **6** | **21** |

### Projeto 1 — code-smells-project

- **Domínio:** API de E-commerce.
- **Tecnologias declaradas/identificadas:** Python, Flask 3.1.1 e SQLite.
- **Código inspecionado:** 4 arquivos, 780 linhas físicas.

O projeto possui arquivos chamados models e controllers, mas ainda mistura responsabilidades: app.py executa SQL nas rotas administrativas; controllers.py contém validações, montagem de respostas e consultas diretas no health check; models.py concentra acesso a dados, cálculos e formatação de diferentes domínios.

#### P1-01 — [CRITICAL] SQL Injection por concatenação de entradas

**Localização no código original:** [models.py:105–111](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/models.py#L105-L111); [models.py:285–299](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/models.py#L285-L299); [controllers.py:167–176](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/controllers.py#L167-L176); [controllers.py:111–123](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/controllers.py#L111-L123).

**Evidência:** O login concatena email e senha ao SQL; a busca concatena termo e categoria à consulta. Esses valores vêm de requisições HTTP e são incorporados ao texto da instrução.

**Impacto e justificativa:** Entradas podem alterar a lógica da consulta, comprometendo autenticação ou acesso aos dados. A classificação segue o exemplo explícito de SQL Injection da escala do desafio. Não foi executada uma exploração.

**Direção de correção:** Separar instruções SQL dos valores recebidos usando parâmetros. A classificação se apoia nos fluxos de texto identificados; não presume que toda concatenação envolvendo IDs já convertidos em inteiros seja igualmente explorável.

#### P1-02 — [CRITICAL] Exposição de senhas armazenadas em texto puro

**Localização no código original:** [models.py:72–103](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/models.py#L72-L103); [models.py:122–129](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/models.py#L122-L129); [controllers.py:128–144](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/controllers.py#L128-L144).

**Evidência:** O cadastro insere diretamente a senha recebida. As funções de consulta de usuários incluem o campo senha nos dicionários que os controllers devolvem em JSON.

**Impacto e justificativa:** Respostas da API expõem credenciais em texto puro. Trata-se de exposição de dados sensíveis, prevista como CRITICAL no enunciado.

**Direção de correção:** Remover senha das representações públicas e adotar armazenamento e verificação apropriados de senhas. A correção deve ser registrada como alteração de segurança intencional, sem preservar o vazamento como se fosse um contrato válido.

#### P1-03 — [HIGH] Conexão global mutável compartilhada

**Localização no código original:** [database.py:4–10](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/database.py#L4-L10); [database.py:86](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/database.py#L86).

**Evidência:** get_db() mantém e devolve uma única conexão global, criada com check_same_thread=False. Os chamadores compartilham o mesmo objeto de conexão.

**Impacto e justificativa:** O estado compartilhado dificulta o isolamento entre testes e o controle das transações de requisições diferentes. A opção de acesso por diferentes threads não estabelece, sozinha, coordenação das escritas. Não foi reproduzida uma falha de concorrência.

**Direção de correção:** Definir um ciclo de vida explícito para conexões e transações, com isolamento adequado às requisições e aos testes. Evitar compartilhar uma conexão mutável indiscriminadamente.

#### P1-04 — [MEDIUM] Consultas N+1 na listagem de pedidos

**Localização no código original:** [models.py:203–233](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/models.py#L203-L233).

**Evidência:** get_todos_pedidos() consulta pedidos, consulta itens dentro do laço de pedidos e consulta o nome do produto dentro do laço de itens.

**Impacto e justificativa:** O número de consultas cresce com pedidos e itens: nesse trecho, 10 pedidos com 3 itens cada demandariam 1 + 10 + 30 = 41 consultas. É um gargalo de desempenho previsto como MEDIUM na escala.

**Direção de correção:** Buscar dados relacionados em conjunto, por joins ou consultas em lote, preservando a estrutura de resposta esperada. A contagem acima é derivada do código, não medida em execução.

#### P1-05 — [MEDIUM] Validações duplicadas e divergentes de produtos

**Localização no código original:** [controllers.py:28–54](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/controllers.py#L28-L54); [controllers.py:72–90](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/controllers.py#L72-L90).

**Evidência:** Criar e atualizar produto repetem verificações de presença de campos e valores negativos. A criação também verifica tamanho do nome e categoria permitida; a atualização não aplica essas mesmas regras.

**Impacto e justificativa:** O mesmo produto pode passar por critérios diferentes conforme a operação. A duplicação já apresenta divergência observável no código.

**Direção de correção:** Centralizar as regras comuns de produto e aplicá-las coerentemente nas operações, mantendo explícitas eventuais diferenças legítimas entre criação e atualização.

#### P1-06 — [LOW] Limites e percentuais de desconto sem nomes explicativos

**Localização no código original:** [models.py:256–262](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/models.py#L256-L262).

**Evidência:** A regra de desconto utiliza diretamente 10000, 5000, 1000 e os percentuais 0.1, 0.05 e 0.02.

**Impacto e justificativa:** Esses números representam uma política de negócio, mas não possuem nomes que expliquem suas faixas e finalidades. A dificuldade principal é de leitura e manutenção, sem prova de erro no cálculo.

**Direção de correção:** Representar as faixas com constantes ou uma estrutura nomeada, preservando valores e limites de comparação até que uma mudança de regra seja explicitamente definida.

#### P1-07 — [LOW] Importações sem uso

**Localização no código original:** [database.py:2](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/database.py#L2); [models.py:2](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/code-smells-project/models.py#L2).

**Evidência:** database.py importa os sem utilizá-lo; models.py importa sqlite3 sem referenciar o módulo.

**Impacto e justificativa:** As importações acrescentam ruído e sugerem dependências que não são utilizadas nesses arquivos. O impacto é de legibilidade.

**Direção de correção:** Remover as importações não utilizadas após conferir os usos no arquivo inteiro.

### Projeto 2 — ecommerce-api-legacy

- **Domínio:** LMS API com fluxo de checkout de cursos.
- **Tecnologias declaradas/identificadas:** Node.js, Express declarado como ^4.18.2 e SQLite em memória.
- **Código inspecionado:** 3 arquivos, 180 linhas físicas.

src/app.js inicializa o servidor, enquanto AppManager reúne quase todo o funcionamento: criação e preenchimento do banco, rotas, compra, matrícula, pagamento e relatórios. utils.js agrega configurações, cache, logs e uma transformação insegura de senhas. O domínio foi identificado pelo código, não apenas pelo nome da pasta.

#### P2-01 — [CRITICAL] God Class com banco, regras e roteamento

**Localização no código original:** [src/AppManager.js:4–138](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/AppManager.js#L4-L138).

**Evidência:** AppManager cria a conexão, define tabelas e dados iniciais, registra rotas, processa checkout e gera relatórios financeiros.

**Impacto e justificativa:** A classe reúne as responsabilidades de persistência, fluxo de negócio e atendimento HTTP, dificultando mudanças e testes isolados. A severidade segue o exemplo explícito de God Class com banco, lógica complexa e roteamento do enunciado; não decorre apenas do tamanho do arquivo.

**Direção de correção:** Separar inicialização, acesso aos dados, regras de negócio, coordenação e registro de rotas, seguindo o MVC alvo. Dividir o arquivo sem separar responsabilidades não basta.

#### P2-02 — [CRITICAL] Transformação insegura de senhas

**Localização no código original:** [src/utils.js:17–22](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/utils.js#L17-L22); [src/AppManager.js:68–69](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/AppManager.js#L68-L69).

**Evidência:** badCrypto() codifica a senha em Base64, conserva apenas os dois primeiros caracteres, repete esse fragmento 10000 vezes e devolve os primeiros dez caracteres. O checkout usa esse resultado no cadastro.

**Impacto e justificativa:** Senhas distintas que compartilham o mesmo fragmento geram o mesmo valor armazenado. Repetir e truncar uma codificação não constitui proteção adequada de credenciais. A leitura demonstra a construção insegura; não há alegação de exploração de um login neste projeto.

**Direção de correção:** Substituir a função por um mecanismo próprio para armazenamento seguro de senhas e rever a senha padrão usada quando pwd está ausente. Considerar os dados existentes ao planejar a mudança.

#### P2-03 — [HIGH] Checkout com gravações sem transação conjunta

**Localização no código original:** [src/AppManager.js:50–60](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/AppManager.js#L50-L60).

**Evidência:** O código insere uma matrícula, depois um pagamento e depois um registro de auditoria. Se a inserção de pagamento falhar, responde com erro, sem desfazer a matrícula criada anteriormente.

**Impacto e justificativa:** Uma operação de negócio pode ficar parcialmente registrada. A ausência de uma fronteira transacional prejudica a consistência do fluxo de compra.

**Direção de correção:** Definir quais gravações devem ser atômicas e executá-las em transação com confirmação ou reversão. Tratar a falha da auditoria de modo explícito. Não foi induzida uma falha em execução.

#### P2-04 — [MEDIUM] Consultas N+1 no relatório financeiro

**Localização no código original:** [src/AppManager.js:83–106](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/AppManager.js#L83-L106).

**Evidência:** Após listar cursos, o código busca matrículas de cada curso e executa consultas separadas de usuário e pagamento para cada matrícula.

**Impacto e justificativa:** A quantidade de consultas cresce com cursos e matrículas, elevando o custo de geração do relatório.

**Direção de correção:** Buscar as informações relacionadas em conjunto e agregar os resultados, preservando as regras e campos da resposta. Não há medição de desempenho nesta análise estática.

#### P2-05 — [MEDIUM] Validação insuficiente dos tipos de entrada

**Localização no código original:** [src/AppManager.js:29–46](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/AppManager.js#L29-L46).

**Evidência:** A verificação inicial testa a presença de alguns valores. Em seguida, cc.startsWith("4") pressupõe que card seja texto. Um número diferente de zero passa na verificação de presença, mas não oferece esse método.

**Impacto e justificativa:** Uma entrada com tipo incorreto pode provocar exceção em vez de uma resposta de validação controlada. Trata-se de validação incompleta nas rotas.

**Direção de correção:** Validar tipos e campos necessários antes de acessar o banco e executar a lógica de checkout. Preservar os nomes públicos usr, eml, pwd, c_id e card quando apenas variáveis internas forem renomeadas.

#### P2-06 — [LOW] Nomes locais pouco descritivos

**Localização no código original:** [src/AppManager.js:29–33](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/AppManager.js#L29-L33); [src/AppManager.js:52](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/AppManager.js#L52).

**Evidência:** O fluxo usa variáveis locais u, e, p, cid, cc e enrId para informações de usuário, curso, cartão e matrícula.

**Impacto e justificativa:** As abreviações obrigam o leitor a retornar às atribuições para entender cada valor, aumentando o esforço de manutenção.

**Direção de correção:** Adotar nomes internos descritivos. Renomear uma variável local não exige alterar as chaves recebidas na API.

#### P2-07 — [LOW] Variável exportada e importada sem uso

**Localização no código original:** [src/utils.js:10](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/utils.js#L10); [src/utils.js:25](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/utils.js#L25); [src/AppManager.js:2](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/ecommerce-api-legacy/src/AppManager.js#L2).

**Evidência:** totalRevenue é inicializada com zero, exportada e importada, mas não é usada no cálculo do relatório ou em outra operação do projeto.

**Impacto e justificativa:** O nome sugere um controle de faturamento que não existe nesse fluxo. O problema identificado é código sem uso, não um cálculo incorreto comprovado.

**Direção de correção:** Remover a declaração, a exportação e a importação se a conferência de referências confirmar que não há consumidor.

### Projeto 3 — task-manager-api

- **Domínio:** API de gerenciamento de tarefas, usuários, categorias e relatórios.
- **Tecnologias declaradas/identificadas:** Python, Flask 3.0.0, Flask-SQLAlchemy 3.1.1 e SQLite.
- **Código inspecionado:** 15 arquivos, 1158 linhas físicas.

O projeto possui models, routes, services e utils. Entretanto, as rotas concentram validações, consultas, gravações e cálculos, inclusive duplicando regras que já existem nos modelos. A existência das pastas não demonstra, por si só, separação efetiva das responsabilidades.

#### P3-01 — [CRITICAL] Exposição do hash de senha nas respostas

**Localização no código original:** [models/user.py:16–25](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/models/user.py#L16-L25); [models/user.py:27–32](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/models/user.py#L27-L32); [routes/user_routes.py:33–40](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/user_routes.py#L33-L40); [routes/user_routes.py:207–211](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/user_routes.py#L207-L211).

**Evidência:** User.to_dict() inclui password. O método é utilizado na consulta individual de usuário e na resposta de login. set_password() mostra que esse campo armazena um hash MD5.

**Impacto e justificativa:** As respostas expõem material de credencial que deve permanecer interno. A descrição é precisa: é exposição de hash MD5, não de senha em texto puro.

**Direção de correção:** Remover password das representações públicas e revisar o mecanismo de armazenamento de senhas. Documentar a remoção desse campo como correção de segurança intencional.

#### P3-02 — [HIGH] Rotas concentram regras e persistência

**Localização no código original:** [routes/task_routes.py:85–154](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/task_routes.py#L85-L154); [routes/report_routes.py:12–101](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/report_routes.py#L12-L101).

**Evidência:** create_task() recebe dados HTTP, aplica validações, consulta entidades, interpreta datas, grava a tarefa e monta a resposta. summary_report() realiza consultas e cálculos de negócio dentro da função de rota.

**Impacto e justificativa:** O acoplamento dificulta reutilizar e testar as regras sem envolver o atendimento HTTP, caracterizando forte violação da separação de responsabilidades.

**Direção de correção:** Manter o registro de rotas enxuto e distribuir coordenação, regras e persistência conforme as responsabilidades MVC definidas. Aproveitar os modelos existentes e evitar reescrita desnecessária.

#### P3-03 — [MEDIUM] Consultas N+1 na listagem de categorias

**Localização no código original:** [routes/report_routes.py:157–165](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/report_routes.py#L157-L165).

**Evidência:** get_categories() lista categorias e executa Task.query.filter_by(category_id=c.id).count() dentro do laço para cada categoria.

**Impacto e justificativa:** O trecho realiza uma consulta de listagem mais uma contagem por categoria. O custo cresce com a quantidade de categorias, embora os dados possam ser agregados em conjunto.

**Direção de correção:** Obter as contagens por categoria em uma consulta agregada, preservando inclusive categorias sem tarefas e o campo task_count.

#### P3-04 — [MEDIUM] Regra de tarefa atrasada duplicada

**Localização no código original:** [routes/task_routes.py:30–39](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/task_routes.py#L30-L39); [routes/task_routes.py:71–80](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/task_routes.py#L71-L80); [models/task.py:50–60](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/models/task.py#L50-L60).

**Evidência:** As rotas repetem a comparação do prazo com a data atual e a exclusão dos estados done e cancelled, embora Task.is_overdue() já implemente essa regra.

**Impacto e justificativa:** Alterações futuras podem ser feitas em apenas uma cópia, produzindo resultados divergentes entre endpoints.

**Direção de correção:** Definir um único lugar para a regra de atraso e reutilizá-la nas rotas e relatórios, preservando a regra atual até que uma alteração funcional seja definida.

#### P3-05 — [MEDIUM] Uso da API legada Query.get()

**Localização no código original:** [routes/task_routes.py:67](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/task_routes.py#L67); [routes/task_routes.py:158](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/task_routes.py#L158); [routes/task_routes.py:227](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/task_routes.py#L227); [routes/user_routes.py:29](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/user_routes.py#L29); [requirements.txt:2](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/requirements.txt#L2).

**Evidência:** O projeto usa Task.query.get(...) e User.query.get(...). A documentação oficial marca Query.get() como deprecated/legado desde SQLAlchemy 2.0 e indica Session.get(). Flask-SQLAlchemy 3.1.1 pertence à série cujo mínimo de SQLAlchemy é 2.0.16.

**Impacto e justificativa:** Há uso recorrente de uma interface oficialmente legada, exigindo manutenção de compatibilidade. A classificação MEDIUM considera padronização e manutenção; não afirma que o método foi removido ou que a aplicação falha hoje. A versão efetivamente instalada ainda não foi verificada.

**Direção de correção:** Migrar, por exemplo, Task.query.get(task_id) para db.session.get(Task, task_id), preservando o tratamento de None e a resposta 404. Conferir versões e comportamento na validação. Ver referências externas ao final da análise.

#### P3-06 — [LOW] Limites de título repetidos sem uso das constantes existentes

**Localização no código original:** [routes/task_routes.py:96–100](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/task_routes.py#L96-L100); [routes/task_routes.py:167–170](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/task_routes.py#L167-L170); [utils/helpers.py:112–113](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/utils/helpers.py#L112-L113).

**Evidência:** As rotas usam diretamente 3 e 200 para validar títulos, embora MIN_TITLE_LENGTH e MAX_TITLE_LENGTH já estejam declaradas nos utilitários.

**Impacto e justificativa:** A relação entre os números e a regra fica implícita, e uma alteração dos limites exige localizar várias ocorrências. O achado trata especificamente da representação desses limites, não repete o achado da regra de atraso.

**Direção de correção:** Utilizar uma definição nomeada e única dos limites, mantendo os valores atuais e organizando-a junto à regra correspondente.

#### P3-07 — [LOW] Importações sem uso

**Localização no código original:** [app.py:7](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/app.py#L7); [routes/task_routes.py:7](https://github.com/vicente-cruz/mba-ia-refactor-projects-skill/blob/6d1ce6248c3e956801010a89d8bdaab48029bf30/task-manager-api/routes/task_routes.py#L7).

**Evidência:** Em app.py, os, sys e json não são utilizados, enquanto datetime é utilizado. Em routes/task_routes.py, json, os, sys e time não são utilizados.

**Impacto e justificativa:** As importações desnecessárias adicionam ruído e confundem a identificação das dependências reais de cada módulo.

**Direção de correção:** Remover apenas os nomes não utilizados, preservando as importações necessárias.

### Observações para a futura construção da Skill

Registro histórico das orientações formuladas na análise manual e utilizadas na construção posterior da Skill:

- Detectar responsabilidades pelo conteúdo e pelos fluxos, não apenas pelos nomes de arquivos ou pela presença de pastas models, routes e services.
- Usar padrões gerais de detecção e correção. Os nomes dos projetos e os números de linha desta análise são evidências locais, não regras a serem embutidas na Skill.
- Não reproduzir diagnósticos automaticamente entre stacks. Por exemplo, as consultas parametrizadas observadas no checkout Node.js não têm a concatenação de texto identificada no login do primeiro projeto.
- Não confundir o objeto de extensão db = SQLAlchemy() do Task Manager com a conexão sqlite3 global do primeiro projeto. No Flask-SQLAlchemy, a sessão tem escopo vinculado ao contexto da aplicação, segundo a documentação oficial.
- Consultar a documentação da versão pertinente antes de declarar uma API obsoleta. Não pressupor que todo método da interface Query tenha exatamente o mesmo status de Query.get().
- Preservar rotas, métodos HTTP, campos públicos e regras válidas durante a refatoração. Correções de segurança, como remover senha/hash de respostas, devem ser explicitamente justificadas e validadas, em vez de manter vulnerabilidades por compatibilidade.
- Verificar inicialização e endpoints por execução nas etapas apropriadas. Esta análise não permite marcar o checklist funcional como aprovado.
- Antes de qualquer alteração realizada pela Skill, apresentar a auditoria e aguardar a confirmação humana exigida pelo desafio.

### Referências externas utilizadas na análise

**Atenção! Conhecimento externo (referência de mercado, fora do MBA).** As fontes abaixo fundamentam detalhes técnicos e complementam a leitura do código e os critérios do enunciado.

- [Python 3.11 — sqlite3](https://docs.python.org/3.11/library/sqlite3.html): parâmetros SQL e cuidados com check_same_thread. Apoia P1-01 e P1-03; não declara a versão instalada no ambiente do aluno.
- [SQLAlchemy 2.0 — Query.get()](https://docs.sqlalchemy.org/en/20/orm/queryguide/query.html#sqlalchemy.orm.Query.get): status legado/deprecated e substituição por Session.get(). Apoia P3-05.
- [Flask-SQLAlchemy — histórico de versões](https://flask-sqlalchemy.palletsprojects.com/en/stable/changes/): requisito mínimo de SQLAlchemy na série 3.1 e escopo da sessão no contexto da aplicação. Apoia P3-05 e a distinção entre extensão e conexão global.

## Construção da Skill

### Organização e decisões de design

A Skill `refactor-arch` foi construída primeiro para `code-smells-project` e reutilizada nos outros dois projetos. Cada cópia contém seis arquivos: um orquestrador e cinco referências. Os links abaixo apontam para a cópia do projeto 1.

| Arquivo | Responsabilidade |
|---|---|
| [SKILL.md](code-smells-project/.claude/skills/refactor-arch/SKILL.md) | Define alvo, escopo, ordem das fases, pausa para aprovação, registro das evidências e encerramento sem commit ou push. |
| [project-analysis.md](code-smells-project/.claude/skills/refactor-arch/references/project-analysis.md) | Detecta stack, domínio, versões, persistência, endpoints e responsabilidades; diferencia versões declaradas das instaladas. |
| [anti-patterns.md](code-smells-project/.claude/skills/refactor-arch/references/anti-patterns.md) | Catálogo de 20 padrões com sinais de detecção, severidade e cuidados contra falsos positivos. |
| [audit-template.md](code-smells-project/.claude/skills/refactor-arch/references/audit-template.md) | Padroniza achados, localizações, plano, mudanças de contrato, decisões pendentes e destinos dos registros. |
| [mvc-guidelines.md](code-smells-project/.claude/skills/refactor-arch/references/mvc-guidelines.md) | Define responsabilidades de Models, Controllers e Views/Routes, configuração, erros e inicialização. |
| [refactoring-playbook.md](code-smells-project/.claude/skills/refactor-arch/references/refactoring-playbook.md) | Reúne 15 transformações com exemplos antes/depois e procedimentos de validação e preservação das evidências. |

As referências são lidas na etapa correspondente. O `SKILL.md` mantém o fluxo: **Fase 1 — análise → Fase 2 — auditoria → aprovação humana e decisões → Fase 3 — refatoração e validação**. A invocação é explícita (`disable-model-invocation: true`); chamar a Skill não aprova a refatoração.

As fases 1 e 2 não executam a aplicação nem alteram código. A auditoria distingue leitura estática de hipóteses que dependem de execução e exige confirmação documental de APIs obsoletas. Na fase 3, o relatório aprovado é salvo antes das alterações; os resultados posteriores ficam em arquivos de validação separados. Mudanças de contrato exigem decisões explícitas e são conferidas contra a linha de base.

### Catálogo e playbook

Os 20 anti-patterns cobrem arquitetura, segurança, consistência, desempenho e manutenção:

| Severidade base | IDs | Padrões incluídos |
|---|---|---|
| CRITICAL — 6 | AP-01 a AP-06 | SQL Injection/SQL arbitrário; segredos no código; exposição de dados sensíveis; armazenamento inseguro de senhas; God Class/Module; operações administrativas sem controle de acesso. |
| HIGH — 5 | AP-07 a AP-11 | Regras e persistência na camada HTTP; estado global mutável; escritas sem transação; acoplamento e efeitos na inicialização; configuração de execução insegura. |
| MEDIUM — 5 | AP-12 a AP-16 | N+1; validação insuficiente; regras duplicadas; APIs obsoletas; tratamento de erros disperso ou com vazamento. |
| LOW — 4 | AP-17 a AP-20 | Literais sem nome; nomenclatura; código morto; logging ad hoc. |

A severidade pode mudar mediante justificativa contextual. O catálogo ultrapassa os oito padrões exigidos e inclui APIs deprecated, sem presumir que todo uso de uma interface legada seja equivalente.

O playbook também supera o mínimo de oito transformações:

| IDs | Transformações com exemplos antes/depois |
|---|---|
| T-01 a T-04 | Parametrizar SQL; extrair configuração; remover dados sensíveis das representações públicas; armazenar senhas com hash adequado. |
| T-05 a T-08 | Decompor God Class; separar rota/controller/model; explicitar o ciclo de vida da conexão; reunir escritas relacionadas em transação. |
| T-09 a T-12 | Eliminar N+1; centralizar validação; substituir APIs obsoletas; centralizar tratamento de erros. |
| T-13 a T-15 | Nomear constantes e remover código morto; organizar a inicialização e injeção de dependências; proteger ou remover operações administrativas. |

### Independência de tecnologia

As regras descrevem responsabilidades e comportamentos, sem embutir os nomes dos três projetos ou seus números de linha. Os exemplos usam um domínio fictício de biblioteca e mostram Python/Flask e Node.js/Express; são referências adaptáveis, não substitutos da leitura do alvo.

Para APIs JSON, Views/Routes cuidam de HTTP e serialização; Controllers coordenam casos de uso; Models concentram regras e persistência. A aplicação concreta respeita diferenças como a sessão do Flask-SQLAlchemy, conexões SQLite por requisição e callbacks/fila na aplicação Express. A execução demonstrou reutilização nos três projetos fornecidos; outras stacks não foram validadas neste desafio.

### Desafios e revisões

- **Construção da Skill:** a revisão corrigiu o YAML da descrição, a validação completa do formato de hash no exemplo Node.js, exemplos que ainda misturavam persistência e HTTP, as regras de escopo e decisões pendentes, a preservação de evidências e explicações sobre transações e Blueprints. Testar exemplos da Skill não foi tratado como validação das aplicações.
- **Projeto 1:** rodadas posteriores corrigiram números não finitos, entrada não textual na consulta administrativa e formatos de hash malformados que provocavam 500. A evidência de importação também foi refeita com controle explícito.
- **Projeto 2:** testes controlados exercitaram rollback e isolamento. O comparador foi corrigido para rejeitar alterações indevidas mesmo em casos com mudanças intencionais e para tratar apenas a ordem não garantida no original, mantendo a ordem exigida no refatorado.
- **Projeto 3:** a revisão corrigiu validações de tags, cores e inteiros, a preservação do cabeçalho `Allow` e a precedência do 404. A última rodada reforçou a comparação do estado completo após conflitos e criou um inventário fixo para detectar casos ausentes até quando removidos das duas versões.
- **Interrupções da API:** a continuidade foi conferida pelos arquivos gravados e pelo estado do Git. Mensagens incompletas não foram tomadas como prova de execução ou conclusão.

As correções das aplicações e das suítes foram delimitadas por rodada; a Skill permaneceu inalterada durante as execuções de refatoração. Houve revisão humana das decisões e revisão independente do código e das evidências.

## Resultados

### Auditorias dos três projetos

Os **21 achados manuais** são a seleção inicial. As auditorias da Skill identificaram **56 achados**, antes das correções; estas contagens não representam problemas remanescentes no código final.

| Projeto / relatório | CRITICAL | HIGH | MEDIUM | LOW | Total |
|---|---:|---:|---:|---:|---:|
| [1 — code-smells-project](reports/audit-project-1.md) | 7 | 6 | 4 | 4 | 21 |
| [2 — ecommerce-api-legacy](reports/audit-project-2.md) | 5 | 4 | 3 | 4 | 16 |
| [3 — task-manager-api](reports/audit-project-3.md) | 4 | 5 | 6 | 4 | 19 |
| **Total** | **16** | **15** | **13** | **12** | **56** |

Os relatórios preservam os achados e o plano da Fase 2, inclusive hipóteses e decisões daquele momento. A situação após implementação está nos registros de validação. No projeto 3, por exemplo, F-05 era uma hipótese de vazamento em logs e foi confirmado por execução no original.

Correspondência temática entre análise manual e auditoria (os IDs F-xx pertencem ao relatório de cada projeto):

| Projeto | Correspondência |
|---|---|
| 1 | P1-01 → F-01; P1-02 → F-03/F-04; P1-03 → F-10; P1-04 → F-16; P1-05 → F-17; P1-06 → F-18; P1-07 → F-20. |
| 2 | P2-01 → F-05; P2-02 → F-03; P2-03 → F-06; P2-04 → F-10; P2-05 → F-11; P2-06 → F-14; P2-07 → F-15. |
| 3 | P3-01 → F-01; P3-02 → F-07; P3-03 → F-10; P3-04 → F-12; P3-05 → F-13; P3-06 → F-12/F-17; P3-07 → F-16. |

### Estrutura antes e depois

| Projeto | Antes | Depois |
|---|---|---|
| 1 — Flask + sqlite3 | Quatro arquivos Python; `app.py`, `controllers.py` e `models.py` misturavam HTTP, regras e SQL; conexão global em `database.py`. | `app.py` com factory; `config.py`, `database.py`, `errors.py`, `auth.py`; pacotes `models/`, `controllers/` e `routes/` por domínio; `tests/test_regressao.py`. Os dois módulos monolíticos foram substituídos por pacotes. |
| 2 — Express + sqlite3 | Três arquivos JavaScript; `AppManager.js` reunia schema, seed, rotas, checkout e relatório; `utils.js` misturava configuração, cache e senhas. | Em `src/`: `app.js`, `config.js`, `database.js`, `errors.js`, `passwordHash.js`, `models/`, `controllers/`, `routes/` e `middlewares/`. `AppManager.js` e `utils.js` removidos. |
| 3 — Flask + SQLAlchemy | Quinze arquivos Python; pastas `models/` e `routes/` já existiam, mas as rotas continham regras, consultas e relatórios; `services/` e `utils/` continham código sem uso. | Factory e configuração explícita; `auth.py` e `errors.py`; `controllers/`; Models com consultas e regras, incluindo `clock.py`; rotas próprias de categorias e sistema; seed atômico. `services/` e `utils/` removidos. |

### Validação final e evidências

| Projeto | Resultado final registrado | Evidências |
|---|---|---|
| 1 | 54 casos nas 19 combinações de método/rota: 32 preservados e 22 diferenças classificadas, sem regressão detectada; 18 testes de regressão aprovados; 122 verificações específicas aprovadas. | [Validação, seção 13](reports/evidence/code-smells-project/validation.md#13-rodada-3-2026-10-31-hashes-malformados-que-ainda-provocavam-500), [matriz final](reports/evidence/code-smells-project/rodada-3/matriz.md), [testes](reports/evidence/code-smells-project/rodada-3/unittest_pos.txt), [log da aplicação](reports/evidence/code-smells-project/rodada-3/logs/refatorado.log). |
| 2 | 25 casos na matriz, sem reprovações ou avisos; 21 testes controlados aprovados; 18 testes do comparador aprovados; casos de inicialização e falhas de processo documentados. | [Validação](reports/evidence/ecommerce-api-legacy/validation.md), [matriz](reports/evidence/ecommerce-api-legacy/matriz.md), [testes controlados](reports/evidence/ecommerce-api-legacy/logs/testes-controlados.log), [comparador](reports/evidence/ecommerce-api-legacy/logs/testes-comparador.log), [log de processo](reports/evidence/ecommerce-api-legacy/logs/refatorado-process.log). |
| 3 | 377 registros originais e 400 refatorados; 377 comparações: 166 preservadas e 211 diferenças intencionais; 23 registros exclusivos declarados. Zero falhas; 43 verificações do comparador (37 mutações + 6 controles) e 10 meta-testes com resultados esperados. | [Validação final](reports/evidence/task-manager-api/rodada-3/validation.md), [matriz](reports/evidence/task-manager-api/rodada-3/resultados/matriz.md), [resumo estruturado](reports/evidence/task-manager-api/rodada-3/resultados/resumo.json), [meta-testes](reports/evidence/task-manager-api/rodada-3/resultados/meta-testes.txt), [inicialização e CLI](reports/evidence/task-manager-api/rodada-3/resultados/cli.txt). |

As unidades de contagem diferem: registros, testes e verificações não devem ser somados como uma única cobertura. No projeto 3, os 377 registros originais incluem 367 HTTP + 10 fatos; os 400 refatorados incluem 383 HTTP + 17 fatos. As diferenças intencionais são mudanças de contrato ou correções documentadas, não equivalência literal de todas as respostas.

As pastas preservam rodadas anteriores para rastreabilidade. Para avaliar o estado final, use os links acima: a validação do projeto 1 consolida a rodada 3 na seção 13; a do projeto 2 contém as revisões do comparador; a do projeto 3 tem um arquivo específico para a rodada 3.

### Checklist por projeto

`Concluído` indica evidência de atendimento no escopo da etapa. `N/A` indica que a auditoria não confirmou ocorrência aplicável. Os relatórios e as validações vinculados acima sustentam os itens; limitações de implementação e de cobertura continuam explicitadas abaixo.

| Fase / critério do enunciado | Projeto 1 | Projeto 2 | Projeto 3 |
|---|---|---|---|
| F1 — Linguagem detectada corretamente | Concluído: Python | Concluído: JavaScript | Concluído: Python |
| F1 — Framework detectado corretamente | Concluído: Flask | Concluído: Express | Concluído: Flask |
| F1 — Domínio descrito corretamente | Concluído: E-commerce | Concluído: LMS/checkout | Concluído: Task Manager |
| F1 — Contagem de arquivos compatível com o alvo original | Concluído: 4 | Concluído: 3 | Concluído: 15 |
| F2 — Relatório segue o template | Concluído | Concluído | Concluído |
| F2 — Achados com arquivos e linhas da versão auditada | Concluído | Concluído | Concluído |
| F2 — Ordenação CRITICAL → LOW | Concluído | Concluído | Concluído |
| F2 — Pelo menos cinco achados, incluindo CRITICAL ou HIGH | Concluído: 21 | Concluído: 16 | Concluído: 19 |
| F2 — Detecção de APIs obsoletas, quando aplicável | N/A: sem ocorrência confirmada | N/A: sem ocorrência confirmada | Concluído: `Query.get()` e `datetime.utcnow()` |
| F2 — Pausa e confirmação antes da refatoração | Concluído | Concluído | Concluído |
| F3 — Estrutura MVC | Concluído | Concluído | Concluído |
| F3 — Configuração em módulo próprio e segredos fora do código | Concluído | Concluído | Concluído |
| F3 — Models abstraem dados | Concluído | Concluído | Concluído |
| F3 — Views/Routes separadas | Concluído | Concluído | Concluído |
| F3 — Controllers coordenam fluxo | Concluído | Concluído | Concluído |
| F3 — Tratamento de erros centralizado | Concluído | Concluído | Concluído |
| F3 — Ponto de entrada claro | Concluído | Concluído | Concluído |
| F3 — Aplicação inicia com configuração válida | Concluído | Concluído | Concluído |
| F3 — Endpoints originais exercitados conforme contratos aprovados | Concluído | Concluído | Concluído |

### Diferenças entre stacks e mudanças aprovadas

- **Projeto 1:** SQL parametrizado, conexão por requisição, transações de pedido, hash de senha e token administrativo. `/admin/query` foi mantido como catálogo fechado de consultas, sem aceitar SQL arbitrário. As contas legadas com senha em texto puro não migram automaticamente, conforme decisão aprovada.
- **Projeto 2:** a fila exclusiva abrange leituras e escritas do banco em memória; checkout, pagamento e auditoria são atômicos. Exclusão de usuário com matrículas retorna 409. Relatório financeiro e exclusão exigem token administrativo; o cadastro implícito de usuário novo no checkout exige senha.
- **Projeto 3:** autenticação por token assinado vinculado à instância da conta, sem JWT; migração de MD5 no login bem-sucedido; restrições nas operações de conta; seed atômico; agrupamento de consultas. A presença prévia de Models e Routes não impediu a identificação e correção da mistura de responsabilidades.

### Limitações e problemas remanescentes

| Projeto | Principais limites documentados |
|---|---|
| 1 | F-13, F-14 e F-16 ficaram parcialmente corrigidos: seed automático e acesso ao contexto Flask pelos controllers; email sem validação de formato/unicidade; consulta de produto por item na criação do pedido. Bancos legados mantêm senhas em texto puro e não há rota de redefinição. Cancelamento não devolve estoque. Não há autenticação de usuário final nem teste de carga. Ver R-1 a R-10 na validação. |
| 2 | A fila serializa as operações, sem medição de vazão/latência sob carga. O schema preservado não impõe unicidade de email. O checkout com email existente não verifica senha. A revisão de vulnerabilidades das dependências não integrou o escopo. |
| 3 | Leituras e CRUD de tarefas/categorias continuam públicos; CORS aberto e ausência de limitação de tentativas de login permanecem. `Model.query` ainda é usado em consultas, embora `Query.get()` tenha sido removido. Email com quebra de linha final mantém o comportamento original; `ResourceWarning` não foi investigado; migração fora do SQLite não foi validada; o original não autentica hashes já migrados. |

Os registros completos têm detalhes adicionais. A validação usou ambientes isolados e servidores de desenvolvimento/clientes de teste; não constitui homologação de produção. As decisões de compatibilidade e os limites de escopo não são classificados como correções concluídas de problemas que permaneceram.

### Registro no Git

| Marco | Commit |
|---|---|
| Referência da análise manual | `6d1ce6248c3e956801010a89d8bdaab48029bf30` |
| Refatoração do projeto 1 | `209d251268b702c9dbb76e5d32139d861ed48889` |
| Refatoração do projeto 2 | `f6eaae357672157858e16e4b58b49d0e6839a506` |
| Refatoração do projeto 3 | `2104c2e` |
| Formatação das evidências e permissão do relatório do projeto 3 | `c6098de` |

Os commits de referência específicos de cada auditoria estão nos respectivos relatórios. O ajuste `c6098de` removeu espaços finais, uma linha vazia excedente e a permissão de execução do Markdown, sem mudança funcional.

## Como Executar

### Pré-requisitos

- Git e Bash em Linux/WSL; clone com histórico disponível para reproduzir comparações com commits anteriores.
- Claude Code instalado e configurado para executar a Skill; acesso ao modelo usado pela ferramenta.
- Python com `venv`/`pip` para os projetos 1 e 3; Node.js/npm para o projeto 2. As execuções registradas pelo Claude usaram Python 3.14.0 e Node.js 20.20.0; versões das bibliotecas estão nas evidências de cada projeto.
- Dependências instaladas separadamente: os projetos Flask usam versões diferentes e não compartilham um `requirements.txt` na raiz.

### Invocar a Skill

Partindo da raiz do repositório, execute **um** dos comandos abaixo, conforme o alvo:

```bash
(cd code-smells-project && claude "/refactor-arch")
(cd ecommerce-api-legacy && claude "/refactor-arch")
(cd task-manager-api && claude "/refactor-arch")
```

Na conversa, indique o destino correspondente: `reports/audit-project-1.md`, `reports/audit-project-2.md` ou `reports/audit-project-3.md`, e `reports/evidence/<nome-do-projeto>/` para as evidências. Os caminhos são relativos à raiz do repositório.

A Skill apresenta análise e auditoria, solicita confirmação e aguarda as decisões pendentes. Só depois inicia a refatoração. Os relatórios desta entrega já existem: para uma nova execução, use outros destinos e uma cópia de trabalho separada, preservando as evidências atuais. Invocar a Skill no código final audita o refatorado; para reproduzir a auditoria original, use a versão de referência indicada em cada relatório e disponibilize nela uma cópia da Skill.

### Inicializar as aplicações

Os comandos abaixo partem da raiz do repositório, em terminais separados. Os ambientes Python ficam em `.venv/` na raiz, separados por projeto e fora dos diretórios copiados pelos runners de comparação. Configure as variáveis indicadas por cada `.env.example`; copiar esse arquivo para `.env` não substitui a exportação das variáveis nos comandos de execução direta. Use valores próprios para senhas e segredos, sem versioná-los.

| Projeto | Configuração e comportamento |
|---|---|
| [1 — README](code-smells-project/README.md) / [.env.example](code-smells-project/.env.example) | `ADMIN_TOKEN` protege operações administrativas. `SEED_SENHA_ADMIN`, `SEED_SENHA_JOAO` e `SEED_SENHA_MARIA` definem as senhas dos usuários de demonstração. Configure `SECRET_KEY` para evitar a chave efêmera de desenvolvimento. Banco padrão `loja.db`; porta 5000. |
| [2 — README](ecommerce-api-legacy/README.md) / [.env.example](ecommerce-api-legacy/.env.example) | `SEED_USER_PASSWORD` é obrigatória; `ADMIN_TOKEN` habilita operações administrativas. Banco em memória, reinicializado em cada execução; porta 3000. |
| [3 — README](task-manager-api/README.md) / [.env.example](task-manager-api/.env.example) | `SECRET_KEY` obrigatória com pelo menos 32 caracteres. O seed exige `SEED_ADMIN_PASSWORD`, `SEED_USER_PASSWORD` e `SEED_MANAGER_PASSWORD`. Banco padrão `instance/tasks.db`; porta 5000. |

Projeto 1, depois de exportar suas variáveis:

```bash
python3 -m venv .venv/projeto-1
.venv/projeto-1/bin/python -m pip install -r code-smells-project/requirements.txt
(cd code-smells-project && ../.venv/projeto-1/bin/python app.py)
```

Projeto 2, depois de exportar suas variáveis:

```bash
(cd ecommerce-api-legacy && npm ci && npm start)
```

Projeto 3, depois de exportar suas variáveis:

```bash
python3 -m venv .venv/projeto-3
.venv/projeto-3/bin/python -m pip install -r task-manager-api/requirements.txt
(cd task-manager-api && ../.venv/projeto-3/bin/python app.py)
```

Para carregar dados de demonstração no projeto 3, execute `(cd task-manager-api && ../.venv/projeto-3/bin/python seed.py)` **somente em banco de teste**: o comando apaga e recria usuários, categorias e tarefas em uma transação. Execute-o antes de iniciar a aplicação. Os dois projetos Flask usam a porta 5000 por padrão; execute um por vez ou configure outra `PORT`.

### Reproduzir validações

Os exemplos seguintes partem da raiz do repositório, com as dependências já instaladas. Não é necessário iniciar manualmente servidores para essas suítes.

Projeto 1 — regressões automatizadas:

```bash
(cd code-smells-project && ../.venv/projeto-1/bin/python -B -m unittest discover -s tests -v)
```

Resultado registrado: 18 testes aprovados. A matriz HTTP e as verificações específicas estão descritas nas seções 12 e 13 de [validation.md](reports/evidence/code-smells-project/validation.md), com ferramentas preservadas em `rodada-2/tools/` e a reprodução adicional em `rodada-3/tools/`.

Projeto 2 — testes controlados e testes do comparador:

```bash
REF_DIR="$PWD/ecommerce-api-legacy" node --test \
  reports/evidence/ecommerce-api-legacy/tools/concurrency_rollback.test.js

node --test reports/evidence/ecommerce-api-legacy/tools/compare.test.js
```

Resultados registrados: 21 e 18 testes aprovados, respectivamente. Os testes do comparador usam os registros preservados; não substituem nova execução da matriz da aplicação. A reprodução completa está em [commands.md](reports/evidence/ecommerce-api-legacy/commands.md), com as correções posteriores identificadas ao final.

Projeto 3 — comparação completa em cópias isoladas, escrevendo fora das evidências versionadas:

```bash
resultado_p3="$(mktemp -d)"
VENV="$PWD/.venv/projeto-3" \
  bash reports/evidence/task-manager-api/rodada-3/tools/run_all.sh "$resultado_p3"
```

O runner usa o commit original indicado em `BASE_REF`, gera segredos de teste, exercita os 13 grupos e as verificações transversais, compara o inventário e executa os meta-testes. Sem `VENV`, cria um ambiente temporário e instala dependências. A saída zero indica aprovação das etapas; os detalhes ficam em `$resultado_p3`. O inventário de 377/400 casos é versionado e não deve ser regenerado automaticamente a partir da execução avaliada.

Para conferir as aplicações em execução, use as matrizes e os exemplos de requisições documentados nos projetos. Os logs de inicialização vinculados em Resultados atendem ao registro de execução solicitado no enunciado.

## Enunciado original

O texto original do repositório foi preservado integralmente abaixo para consulta. Seus exemplos, comandos e mensagens de sucesso descrevem o desafio; não são evidências de execução desta entrega.

<details>
<summary>Expandir enunciado original completo</summary>

# Criação de Skills — Refatoração Arquitetural Automatizada

Ao longo do curso você aprendeu o que são Skills e como elas permitem que um agente de IA atue como um especialista em tarefas específicas. Agora imagine o seguinte cenário: você herdou 3 projetos legados com problemas de arquitetura, segurança e qualidade de código. Revisar e corrigir tudo manualmente levaria dias.

Neste desafio, você vai criar uma Skill que automatiza esse processo — analisando, auditando e refatorando qualquer projeto para o padrão MVC, independente da tecnologia.

## Objetivo

Você deve entregar uma Skill capaz de:

- Analisar uma codebase detectando linguagem, framework e arquitetura atual
- Identificar anti-patterns e code smells, classificando por severidade com arquivo e linha exatos
- Gerar um relatório de auditoria estruturado com todos os achados
- Refatorar o projeto para o padrão MVC (Model-View-Controller), eliminando os problemas encontrados
- Validar o resultado garantindo que a aplicação continua funcionando após as mudanças

A skill deve ser agnóstica de tecnologia, funcionando com diferentes linguagens e frameworks.

## Contexto

### Definição de Severidades

Para padronizar a sua auditoria e os relatórios gerados pela IA, utilize a seguinte escala de classificação baseada em problemas de MVC e SOLID:

- **CRITICAL:** Falhas graves de arquitetura ou segurança que impedem o funcionamento correto, expõem dados sensíveis (ex: credenciais hardcoded, SQL Injection) ou violam completamente a separação de responsabilidades (ex: "God Class" contendo banco de dados, lógicas complexas e roteamento no mesmo arquivo).
- **HIGH:** Fortes violações do padrão MVC ou princípios SOLID que dificultam muito a manutenção e testes (ex: lógicas de negócio pesadas presas dentro de Controllers, forte acoplamento sem Injeção de Dependência, ou uso de estado global mutável em toda a aplicação).
- **MEDIUM:** Problemas de padronização, duplicação de código ou gargalos de performance moderada (ex: Queries N+1 no banco de dados, uso inadequado de middlewares, validações ausentes nas rotas).
- **LOW:** Melhorias de legibilidade, nomenclatura de variáveis ruins, ou "magic numbers" soltos pelo código.

### Exemplo de Uso no CLI

```bash
# Executar a skill no projeto com problemas
cd code-smells-project
claude "/refactor-arch"
```

```
================================
PHASE 1: PROJECT ANALYSIS
================================
Language:      Python
Framework:      Flask 3.1.1
Dependencies:  flask-cors
Domain:        E-commerce API (produtos, pedidos, usuários)
Architecture:  Monolítica — tudo em 4 arquivos, sem separação de camadas
Source files:  4 files analyzed
DB tables:     produtos, usuarios, pedidos, itens_pedido
================================
```

```
================================
ARCHITECTURE AUDIT REPORT
================================
Project: code-smells-project
Stack:   Python + Flask
Files:   4 analyzed | ~800 lines of code

## Summary
CRITICAL: 4 | HIGH: 5 | MEDIUM: 2 | LOW: 3

## Findings

### [CRITICAL] God Class / God Method
File: models.py:1-350
Description: Arquivo único contém toda lógica de negócio, queries SQL, validação e formatação para 4 domínios diferentes.
Impact: Impossível testar em isolamento, qualquer mudança afeta tudo.
Recommendation: Separar em models e controllers por domínio.

### [CRITICAL] Hardcoded Credentials
File: app.py:8
Description: SECRET_KEY hardcoded como 'minha-chave-super-secreta-123'
...

================================
Total: 14 findings
================================

Phase 2 complete. Proceed with refactoring (Phase 3)? [y/n]
> y
```

```
[... refatoração executada ...]

================================
PHASE 3: REFACTORING COMPLETE
================================
## New Project Structure
src/
├── config/settings.py
├── models/
│   ├── produto_model.py
│   └── usuario_model.py
├── views/
│   └── routes.py
├── controllers/
│   ├── produto_controller.py
│   └── pedido_controller.py
├── middlewares/error_handler.py
└── app.py (composition root)

## Validation
  ✓ Application boots without errors
  ✓ All endpoints respond correctly
  ✓ Zero anti-patterns remaining
================================
```

## Tecnologias obrigatórias

- **Ferramenta:** uma das três opções abaixo (não são aceitas outras ferramentas):
  - Claude Code
  - Gemini CLI
  - OpenAI Codex
- **Recurso:** Custom Skills (ou o equivalente na ferramenta escolhida)
- **Formato dos arquivos de referência:** Markdown
- **Projetos-alvo:** Python/Flask (2 projetos) e Node.js/Express (1 projeto) (fornecidos no repositório base)

> **Nota sobre a ferramenta:** Os exemplos deste documento usam o Claude Code (`.claude/skills/`) como referência, pois é a ferramenta utilizada no curso. Se você optar por Gemini CLI ou Codex, adapte o nome da pasta e o comando de invocação conforme a convenção dela — o conceito de skill e a estrutura interna (SKILL.md + arquivos de referência) permanecem os mesmos.

## Requisitos

### 1. Análise Manual dos Projetos

Antes de criar a skill, você deve entender os problemas que ela vai resolver.

**Tarefas:**

- Analisar o projeto `code-smells-project/` (Python/Flask — API de E-commerce)
- Analisar o projeto `ecommerce-api-legacy/` (Node.js/Express — LMS API com fluxo de checkout)
- Analisar o projeto `task-manager-api/` (Python/Flask — API de Task Manager)

Para cada projeto, identificar e documentar no mínimo 5 problemas, incluindo pelo menos:

- 1 de severidade CRITICAL ou HIGH
- 2 de severidade MEDIUM
- 2 de severidade LOW

Documentar os achados na seção "Análise Manual" do seu `README.md`

> **Dica:** Não precisa encontrar todos os problemas — foque nos que têm maior impacto arquitetural. Use os projetos como insumo para entender quais padrões sua skill precisa detectar.

> **Por que 3 projetos?** Dois são Python/Flask (com níveis de organização diferentes) e um é Node.js/Express. Sua skill precisa funcionar nos 3 para provar que é verdadeiramente agnóstica de tecnologia — lidando tanto com código completamente desestruturado quanto com projetos que já possuem alguma separação de camadas.

### 2. Criação da Skill

Agora que você conhece os problemas, crie uma skill que os detecte, gere um relatório de auditoria e corrija automaticamente.

**Tarefas:**

Criar a skill dentro do projeto `code-smells-project/` e implementar o SKILL.md com 3 fases sequenciais:

- **Fase 1 — Análise:** Detectar stack, mapear arquitetura atual, imprimir resumo
- **Fase 2 — Auditoria:** Cruzar código contra catálogo de anti-patterns, gerar relatório, pedir confirmação
- **Fase 3 — Refatoração:** Reestruturar para o padrão MVC, validar que funciona

Criar arquivos de referência em Markdown que forneçam à skill o conhecimento necessário para executar as 3 fases. Os arquivos devem cobrir **obrigatoriamente** as seguintes áreas de conhecimento:

| Área de conhecimento | O que deve conter |
|---|---|
| Análise de projeto | Heurísticas para detecção de linguagem, framework, banco de dados e mapeamento de arquitetura |
| Catálogo de anti-patterns | Anti-patterns com sinais de detecção e classificação de severidade |
| Template de relatório | Formato padronizado do relatório de auditoria (Fase 2) |
| Guidelines de arquitetura | Regras do padrão MVC alvo (camadas Models, Views/Routes e Controllers, responsabilidades de cada uma) |
| Playbook de refatoração | Padrões concretos de transformação para cada anti-pattern (com exemplos de código) |

> **Nota:** Você tem liberdade para organizar os arquivos de referência como preferir — pode usar os nomes e a quantidade de arquivos que fizer sentido para sua skill. O importante é que todas as 5 áreas de conhecimento estejam cobertas. O nome da skill (`refactor-arch`) e o arquivo `SKILL.md` são obrigatórios e não devem ser alterados. O path da skill segue a convenção da ferramenta escolhida (no Claude Code, por exemplo, é `.claude/skills/refactor-arch/`).

**Requisitos da skill:**

- Deve ser agnóstica de tecnologia — deve funcionar corretamente nos 3 projetos fornecidos, independente da stack ou nível de organização
- O catálogo de anti-patterns deve conter no mínimo 8 anti-patterns com severidade distribuída (CRITICAL, HIGH, MEDIUM, LOW)
- O catálogo deve incluir detecção de APIs deprecated — identificar uso de APIs obsoletas e recomendar o equivalente moderno
- O playbook deve ter no mínimo 8 padrões de transformação com exemplos de código antes/depois
- A Fase 2 deve pausar e pedir confirmação antes de modificar qualquer arquivo
- A Fase 3 deve validar o resultado (boot da aplicação + endpoints funcionando)

### 3. Execução da Skill

Execute sua skill nos 3 projetos e valide que ela funciona em todas as stacks.

#### Projeto 1 — code-smells-project (Python/Flask)

Invocar a skill no Claude Code:

```bash
claude "/refactor-arch"
```

> **Nota:** O comando acima é o exemplo com Claude Code. Se você estiver usando Gemini CLI ou Codex, utilize o comando equivalente para invocar uma skill na sua ferramenta.

- Verificar que a Fase 1 detecta corretamente a stack e imprime o resumo
- Verificar que a Fase 2 encontra no mínimo 5 dos problemas documentados na sua análise manual
- Confirmar a execução da Fase 3
- Verificar que a Fase 3:
  - Cria a estrutura de diretórios baseada em MVC
  - A aplicação inicia sem erros
  - Os endpoints originais continuam respondendo
- Salvar o relatório de auditoria (output da Fase 2) em `reports/audit-project-1.md`
- Commitar o código refatorado do projeto no repositório

#### Projeto 2 — ecommerce-api-legacy (Node.js/Express)

Prove que sua skill é reutilizável em outro projeto de backend, mas com stack diferente.

- Copiar a pasta `.claude/skills/refactor-arch/` para dentro de `ecommerce-api-legacy/`
- Invocar a skill:

```bash
cd ../ecommerce-api-legacy
claude "/refactor-arch"
```

- Verificar que as 3 fases executam corretamente neste projeto
- Salvar o relatório em `reports/audit-project-2.md`
- Commitar o código refatorado do projeto no repositório

#### Projeto 3 — task-manager-api (Python/Flask)

Agora o teste com um projeto Python/Flask que já possui alguma organização de camadas (models, routes, services, utils).

- Copiar a pasta `.claude/skills/refactor-arch/` para dentro de `task-manager-api/`
- Invocar a skill:

```bash
cd ../task-manager-api
claude "/refactor-arch"
```

- Verificar que:
  - A Fase 1 detecta corretamente Python/Flask como stack e identifica o domínio de Task Manager
  - A Fase 2 identifica problemas mesmo em um projeto parcialmente organizado
  - A Fase 3 melhora a estrutura sem quebrar a aplicação (todos os endpoints devem continuar respondendo)
- Salvar o relatório em `reports/audit-project-3.md`
- Commitar o código refatorado do projeto no repositório

> **Nota:** Este projeto já possui alguma separação de camadas, mas isso não significa que a arquitetura está adequada. A skill deve identificar tanto problemas de código (segurança, performance, qualidade) quanto oportunidades de melhoria arquitetural. Se houver mudanças estruturais necessárias, a skill deve propô-las e executá-las.

#### Validação

Para cada projeto refatorado, valide o seguinte checklist:

```markdown
## Checklist de Validação

### Fase 1 — Análise
- [ ] Linguagem detectada corretamente
- [ ] Framework detectado corretamente
- [ ] Domínio da aplicação descrito corretamente
- [ ] Número de arquivos analisados condiz com a realidade

### Fase 2 — Auditoria
- [ ] Relatório segue o template definido nos arquivos de referência
- [ ] Cada finding tem arquivo e linhas exatos
- [ ] Findings ordenados por severidade (CRITICAL → LOW)
- [ ] Mínimo de 5 findings identificados
- [ ] Detecção de APIs deprecated incluída (se aplicável)
- [ ] Skill pausa e pede confirmação antes da Fase 3

### Fase 3 — Refatoração
- [ ] Estrutura de diretórios segue padrão MVC
- [ ] Configuração extraída para módulo de config (sem hardcoded)
- [ ] Models criados para abstrair dados
- [ ] Views/Routes separadas para visualização ou roteamento
- [ ] Controllers concentram o fluxo da aplicação
- [ ] Error handling centralizado
- [ ] Entry point claro
- [ ] Aplicação inicia sem erros
- [ ] Endpoints originais respondem corretamente
```

> **Dica:** Se a skill não detectou problemas suficientes ou a refatoração falhou, ajuste os arquivos de referência e execute novamente. É normal precisar de 2-4 iterações.

## Entregável

Repositório público no GitHub (fork do repositório base) contendo:

- Skill completa em `.claude/skills/refactor-arch/` (dentro dos 3 projetos)
- Código refatorado dos 3 projetos (resultado da execução da Fase 3, commitado no repositório)
- Relatórios de auditoria em `reports/` (3 arquivos)
- `README.md` atualizado

### Estrutura do repositório

Faça um fork do repositório base contendo os três projetos com code smells.

> **Nota:** A estrutura abaixo usa Claude Code como exemplo (`.claude/skills/`). Se estiver usando outra ferramenta, adapte os caminhos conforme a convenção dela.

```
desafio-skills/
├── README.md                              # Sua documentação
│
├── code-smells-project/                   # Projeto 1 — Python/Flask (API de E-commerce)
│   ├── .claude/
│   │   └── skills/
│   │       └── refactor-arch/             # ← SUA SKILL AQUI
│   │           ├── SKILL.md
│   │           └── (arquivos de referência)
│   ├── app.py
│   ├── controllers.py
│   ├── models.py
│   ├── database.py
│   └── requirements.txt
│
├── ecommerce-api-legacy/                  # Projeto 2 — Node.js/Express (LMS API com checkout)
│   ├── .claude/
│   │   └── skills/
│   │       └── refactor-arch/             # ← CÓPIA DA SKILL
│   │           └── ...
│   ├── src/
│   │   ├── app.js
│   │   ├── AppManager.js
│   │   └── utils.js
│   ├── api.http
│   └── package.json
│
├── task-manager-api/                      # Projeto 3 — Python/Flask (API de Task Manager)
│   ├── .claude/
│   │   └── skills/
│   │       └── refactor-arch/             # ← CÓPIA DA SKILL
│   │           └── ...
│   ├── app.py
│   ├── database.py
│   ├── seed.py
│   ├── requirements.txt
│   ├── models/
│   ├── routes/
│   ├── services/
│   └── utils/
│
└── reports/                               # Relatórios gerados
    ├── audit-project-1.md                 # Saída da Fase 2 no projeto 1
    ├── audit-project-2.md                 # Saída da Fase 2 no projeto 2
    └── audit-project-3.md                 # Saída da Fase 2 no projeto 3
```

**O que você vai criar:**

- `.claude/skills/refactor-arch/` — A skill completa (SKILL.md + arquivos de referência)
- Código refatorado dos 3 projetos — resultado da execução da Fase 3, commitado no repositório
- `reports/audit-project-{1,2,3}.md` — Relatório de auditoria de cada projeto
- `README.md` — Documentação do seu processo

**O que já vem pronto:**

- `code-smells-project/` — API de E-commerce Python/Flask com code smells intencionais
- `ecommerce-api-legacy/` — LMS API Node.js/Express (com fluxo de checkout) e problemas de implementação
- `task-manager-api/` — API de Task Manager Python/Flask com organização parcial e problemas de segurança/qualidade

> **Dica:** Cada projeto contém problemas intencionais de diferentes severidades (CRITICAL, HIGH, MEDIUM, LOW), incluindo falhas de segurança, violações arquiteturais e problemas de qualidade de código. Parte do desafio é identificá-los por conta própria através da análise manual do código.

### README.md deve conter

**A) Seção "Análise Manual":**

- Lista dos problemas identificados manualmente em cada projeto
- Classificação por severidade
- Justificativa de por que cada problema é relevante

**B) Seção "Construção da Skill":**

- Decisões de design: como estruturou o SKILL.md e os arquivos de referência
- Quais anti-patterns incluiu no catálogo e por quê
- Como garantiu que a skill é agnóstica de tecnologia
- Desafios encontrados e como resolveu

**C) Seção "Resultados":**

- Resumo dos relatórios de auditoria dos 3 projetos (quantos findings por severidade em cada)
- Comparação antes/depois da estrutura de cada projeto
- Checklist de validação preenchido para cada projeto
- Screenshots ou logs mostrando as aplicações rodando após refatoração
- Observações sobre como a skill se comportou em stacks diferentes

**D) Seção "Como Executar":**

- Pré-requisitos (a ferramenta escolhida — Claude Code, Gemini CLI ou Codex — instalada e configurada)
- Comandos para executar a skill em cada projeto
- Como validar que a refatoração funcionou

### Ordem de execução sugerida

**1. Analisar os projetos manualmente**

Leia o código dos três projetos e documente os problemas encontrados.

**2. Criar a skill**

Escreva o SKILL.md e os arquivos de referência.

**3. Executar nos 3 projetos**

```bash
# Projeto 1
cd code-smells-project
claude "/refactor-arch"

# Projeto 2
cd ../ecommerce-api-legacy
claude "/refactor-arch"

# Projeto 3
cd ../task-manager-api
claude "/refactor-arch"
```

Salve a saída da Fase 2 de cada projeto em `reports/audit-project-{1,2,3}.md`.

**4. Iterar**

Se a skill não detectou problemas suficientes ou a refatoração falhou, ajuste os arquivos de referência e execute novamente. É normal precisar de 2-4 iterações.

## Critérios de Aceite

A skill deve atingir os seguintes mínimos em **todos os 3 projetos**:

| Critério | Requisito |
|---|---|
| Fase 1 detecta stack corretamente | OBRIGATÓRIO (3/3 projetos) |
| Fase 2 encontra >= 5 findings | OBRIGATÓRIO (3/3 projetos) |
| Fase 2 inclui pelo menos 1 CRITICAL ou HIGH | OBRIGATÓRIO (3/3 projetos) |
| Fase 3 aplicação funciona após refatoração | OBRIGATÓRIO (3/3 projetos) |

**IMPORTANTE:** Todos os critérios devem ser atingidos nos 3 projetos, não apenas em um!

> **Sobre o projeto 3 (task-manager-api):** Este projeto já possui alguma organização. "aplicação funciona" significa que a API inicia sem erros e todos os endpoints continuam respondendo corretamente.

## Referências

- [Claude Code: Skills](https://docs.anthropic.com/en/docs/claude-code/skills) — Documentação oficial sobre como criar e estruturar Skills
- [Claude Code: Overview](https://docs.anthropic.com/en/docs/claude-code/overview) — Visão geral do Claude Code e suas capacidades
- [The Complete Guide to Building Skills for Claude (PDF)](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf) — Guia completo da Anthropic sobre construção de Skills
- [Equipping Agents for the Real World with Agent Skills](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills) — Blog oficial da Anthropic sobre Agent Skills

---

## Dicas Finais

- **Comece pela análise manual** — entender os problemas profundamente é essencial para criar uma skill que os detecte.
- **O SKILL.md é um prompt** — ele instrui o agente sobre o que fazer, enquanto os arquivos de referência fornecem o conhecimento de domínio.
- **Seja específico nos sinais de detecção** — "código ruim" não ajuda; "query SQL dentro de loop for" é acionável.
- **Teste incrementalmente** — não tente criar a skill perfeita de primeira.
- **A skill deve ser copiável** — se ela só funciona em um projeto específico, está acoplada demais. Teste nos 3 projetos para validar.
- **Projetos diferentes exigem adaptação** — a Fase 3 de um projeto já parcialmente organizado não vai ter as mesmas transformações de um monolito. Sua skill deve se adaptar ao contexto.
- **Pedir confirmação na Fase 2 é obrigatório** — o humano deve revisar o relatório antes de qualquer modificação.
- **Consulte as referências do curso** — revise a documentação oficial da ferramenta escolhida e os materiais das aulas para relembrar a estrutura e anatomia de uma skill.
</details>
