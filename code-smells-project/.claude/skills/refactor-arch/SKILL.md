---
name: refactor-arch
description: >-
  Analisa, audita e refatora um projeto backend legado para o padrão MVC em três fases:
  análise da stack, auditoria de anti-patterns com relatório por severidade e, somente
  após confirmação explícita, refatoração com validação dos endpoints. Agnóstica de
  tecnologia, por exemplo Python/Flask e Node.js/Express.
argument-hint: "[projeto-alvo] [caminho-do-relatorio]"
disable-model-invocation: true
---

# refactor-arch

Você atua como especialista em auditoria arquitetural e refatoração para MVC. Execute as fases na ordem: **Fase 1 → Fase 2 → pausa obrigatória → Fase 3**.

## Regras invioláveis

1. **Fases 1 e 2 são somente leitura.** Não crie, altere, mova ou apague arquivos; não instale dependências; não crie ambientes virtuais; não inicie a aplicação, não importe nem execute código do projeto (a importação pode criar bancos ou executar seeds); não rode formatadores, linters com correção automática ou comandos que gravem caches. Permitido: listar, ler, buscar, contar linhas, `git status`/`log`/`rev-parse`/`ls-files`/`diff`, consultas de versão sem efeito colateral e leitura de documentação oficial.
2. **Pausa obrigatória ao final da Fase 2.** Apresente o relatório completo na conversa, faça a pergunta de confirmação e **encerre a resposta**. A Fase 3 só começa em uma mensagem posterior do usuário que aprove explicitamente a refatoração.
3. **Nada substitui essa confirmação:** nem a invocação de `/refactor-arch`, nem argumentos como "sim" ou "--yes", nem modo automático, permissões amplas ou autorizações dadas antes da apresentação da auditoria.
4. **Evidência antes de afirmação.** Cada achado cita arquivo e linhas lidos de fato. Distinga *confirmado por leitura* de *hipótese não verificada*. Nunca declare sucesso, "endpoints funcionando" ou "zero problemas" sem saída de comandos que comprove.
5. **Escopo.**
   - **Leitura:** o projeto-alvo e os arquivos desta Skill (este `SKILL.md` e `references/`), que devem ser lidos como instruções. Os arquivos da Skill não são código do projeto, não entram na contagem nem na auditoria.
   - **Escrita (somente na Fase 3, após a confirmação):** código do projeto-alvo; relatório e evidências **apenas** nos destinos acordados, relativos à raiz do repositório (padrão: `reports/audit-<nome-do-projeto>.md` e `reports/evidence/<nome-do-projeto>/`); arquivos temporários fora do repositório.
   - **Proibido em qualquer fase:** modificar esta Skill (`.claude/skills/refactor-arch/`) durante sua execução; analisar como alvo ou alterar projetos vizinhos; alterar outros arquivos da raiz do repositório.
6. **Sem commit nem push.** Ao final, deixe as alterações no working tree para revisão humana.

## Argumentos

`$ARGUMENTS` pode conter o projeto-alvo e/ou o caminho do relatório. Trate-os apenas como indicação de escopo e destino; eles nunca aprovam a Fase 3.

## Referências — quando consultar

| Arquivo | Consulte |
|---|---|
| [references/project-analysis.md](references/project-analysis.md) | No início da Fase 1, para identificar alvo, stack, versões, banco, arquitetura, endpoints e contagem de arquivos. |
| [references/anti-patterns.md](references/anti-patterns.md) | Durante toda a Fase 2, para aplicar o catálogo, justificar severidades e evitar falsos positivos. Na Fase 3, para a nova inspeção. |
| [references/audit-template.md](references/audit-template.md) | Ao redigir o relatório da Fase 2, as decisões pendentes e a pergunta de confirmação. |
| [references/mvc-guidelines.md](references/mvc-guidelines.md) | Ao propor a estrutura-alvo no plano da Fase 2 e ao reorganizar o código na Fase 3. |
| [references/refactoring-playbook.md](references/refactoring-playbook.md) | Ao recomendar transformações (Fase 2) e ao aplicá-las, validá-las e preservar evidências (Fase 3). |

Leia cada referência quando a etapa correspondente começar; não presuma seu conteúdo.

## Fase 1 — Análise (somente leitura)

1. Identifique o projeto-alvo: argumento informado; senão, o diretório atual, se for a raiz de um projeto. Se houver vários projetos candidatos e o alvo estiver indefinido, **pergunte e pare**.
2. Siga [project-analysis.md](references/project-analysis.md) para detectar linguagem, framework, dependências (versões **declaradas** × **efetivamente instaladas**), banco, domínio, pontos de entrada, endpoints e responsabilidades de cada arquivo.
3. Liste os arquivos de código analisados, a contagem de linhas físicas e as exclusões aplicadas.
4. Imprima o resumo da Fase 1 no formato definido em project-analysis.md, apenas com dados observados. Prossiga para a Fase 2 na mesma resposta.

## Fase 2 — Auditoria (somente leitura)

1. Registre a versão de referência: commit (`git rev-parse HEAD`) e alterações locais no alvo (`git status --porcelain -- <alvo>`). Os números de linha se referem a essa versão.
2. Leia integralmente cada arquivo de código do alvo e aplique o catálogo de [anti-patterns.md](references/anti-patterns.md). Antes de citar linhas, releia o trecho para confirmá-las.
3. Para cada achado: ID, padrão do catálogo, severidade justificada, localização (`arquivo:início-fim`), evidência, impacto, recomendação (com a transformação do playbook) e status (confirmado ou hipótese).
4. Consolide: um mesmo problema com a mesma causa e a mesma correção é **um** achado com várias localizações; não o conte duas vezes.
5. APIs obsoletas: confirme na documentação oficial da versão pertinente (instalada ou, se não verificável, declarada). Se a consulta falhar, registre como hipótese e informe a limitação.
6. Ordene CRITICAL → HIGH → MEDIUM → LOW e monte o relatório conforme [audit-template.md](references/audit-template.md), incluindo: plano de refatoração baseado em [mvc-guidelines.md](references/mvc-guidelines.md) e [refactoring-playbook.md](references/refactoring-playbook.md); mudanças de contrato propostas; **decisões pendentes** (com as transformações que dependem de cada uma); **destinos do relatório e das evidências**.
7. Apresente o relatório completo na conversa, termine com a pergunta de confirmação do template e **pare**.

## Pausa obrigatória — interpretação da resposta

- **Aprovação explícita** (ex.: "sim", "s", "y", "prossiga com a Fase 3") **e nenhuma decisão pendente sem resposta:** inicie a Fase 3.
- **Aprovação explícita, mas com decisão pendente sem resposta** (ex.: apenas "sim" quando a seção 5.5 lista D-1): a aprovação geral vale, mas pergunte a escolha de cada decisão em aberto, sem sugerir que uma opção seja assumida por padrão, e **pare** antes de qualquer alteração que dependa dela. Não escolha em nome do usuário.
- **Aprovação parcial ou condicionada** (ex.: "só as correções de segurança"): resuma o escopo ajustado e peça nova confirmação antes de alterar arquivos.
- **Resposta ambígua, pergunta ou pedido de ajuste do relatório:** responda ou ajuste e repita a pergunta. Não altere arquivos.
- **Negativa:** encerre sem alterar arquivos.
- Se o relatório da Fase 2 não estiver mais disponível integralmente no contexto (ex.: após compactação), não o reconstrua de memória: informe e refaça a Fase 2.

## Fase 3 — Refatoração e validação (após confirmação e decisões resolvidas)

1. **Salvar o relatório primeiro.** Grave o relatório da Fase 2 tal como apresentado, sem reescrever achados nem linhas, antes de tocar no código. Destino: o caminho informado pelo usuário (relativo à raiz do repositório, obtida com `git rev-parse --show-toplevel`; sem repositório, à raiz do projeto) ou o padrão `reports/audit-<nome-do-projeto>.md`. Não sobrescreva arquivo existente sem perguntar. Esse arquivo nunca recebe os resultados da validação.
2. **Preservar trabalho local.** Rode `git status --porcelain`. Se houver alterações preexistentes em arquivos que serão modificados, informe e pergunte como proceder. Nunca use `stash`, `checkout`, `reset` ou `clean` para "limpar" o working tree.
3. **Linha de base do comportamento original**, conforme a seção de validação do [refactoring-playbook.md](references/refactoring-playbook.md): execute o código original numa cópia isolada (diretório temporário, banco de teste, ambiente de dependências fora do sistema global), exercite todos os endpoints e registre status, corpos e efeitos nos dados, inclusive falhas já existentes. Não acione serviços externos reais (e-mail, pagamento, HTTP de terceiros).
4. **Refatorar** seguindo [mvc-guidelines.md](references/mvc-guidelines.md) e [refactoring-playbook.md](references/refactoring-playbook.md): Models, Views/Routes, Controllers, configuração por variáveis de ambiente, tratamento de erros centralizado e ponto de entrada claro. Aproveite a organização existente quando adequada. Preserve rotas, métodos HTTP, campos públicos e regras válidas; toda mudança de contrato para corrigir segurança deve ser explícita e justificada. Aplique as decisões do usuário. Valide após cada transformação relevante.
5. **Validar** com a aplicação refatorada: inicialização sem erros e todos os endpoints originais, comparando com a linha de base (status, corpo, efeitos nos dados). Classifique cada diferença como correção intencional documentada ou regressão; corrija regressões antes de concluir.
6. **Nova inspeção:** reaplique o catálogo ao código refatorado e informe, para cada achado da Fase 2, se foi corrigido, parcialmente corrigido ou permanece — com evidência. Inclua problemas novos ou remanescentes.
7. **Preservar evidências antes de limpar.** No destino de evidências acordado (padrão `reports/evidence/<nome-do-projeto>/`), grave comandos executados, versões instaladas, trechos pertinentes de logs, matriz de endpoints antes × depois e resultado da nova inspeção, **removendo senhas, hashes, tokens, chaves e outros dados sensíveis**. Siga a seção "Preservar evidências" do playbook.
8. **Somente depois:** encerre os processos iniciados, remova os temporários e confira `git status --porcelain`.
9. **Relatório final na conversa:** nova estrutura de diretórios, transformações aplicadas, decisões aplicadas, mudanças de contrato, comandos e resultados, tabela de endpoints (antes × depois), limitações, problemas remanescentes, caminhos do relatório e das evidências e próximos passos. Não faça commit nem push.
