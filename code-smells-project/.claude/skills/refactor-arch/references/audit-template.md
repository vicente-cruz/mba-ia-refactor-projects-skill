# Template do relatório de auditoria (Fase 2)

Use esta estrutura para o relatório apresentado na conversa e, após a confirmação, salvo em arquivo. Os textos entre `<...>` são instruções de preenchimento, não conteúdo.

## Regras de preenchimento

- **Não invente evidências para preencher o template.** Se uma informação não foi verificada, escreva "não verificado" e explique em Limitações. Se uma seção não tiver conteúdo, escreva "Nenhum" — não crie itens de exemplo.
- Cada achado vem do código lido nesta execução. Linhas referem-se à versão de referência registrada no cabeçalho.
- Localização no formato `caminho/relativo/ao/projeto.ext:inicio-fim` (ou `:linha` para uma linha). Várias localizações do mesmo achado separadas por `;`.
- Evidência: descrição factual do que o código faz, com trecho curto (até ~5 linhas) quando ajudar. Mascare segredos (`pk_live_12…`).
- Ordem: todos os CRITICAL, depois HIGH, MEDIUM e LOW. Dentro da mesma severidade, ordene por impacto.
- IDs sequenciais `F-01`, `F-02`... na ordem final do relatório.
- O resumo por severidade deve bater exatamente com a quantidade de achados listados.

## Estrutura

````markdown
================================
RELATÓRIO DE AUDITORIA ARQUITETURAL
================================

## 1. Identificação

| Campo | Valor |
|---|---|
| Projeto | <nome> (`<caminho relativo à raiz do repositório>`) |
| Data | <AAAA-MM-DD> |
| Versão de referência | commit `<hash completo>` <+ "com alterações locais em: <arquivos>" ou "working tree limpo para o alvo"> |
| Stack | <linguagem> + <framework> (declarada: <versão>; instalada: <versão ou "não verificado">) |
| Banco | <tecnologia e local> |
| Domínio | <descrição> |
| Ferramenta | refactor-arch (Claude Code) |

## 2. Escopo

- Arquivos de código analisados: <N> | Linhas físicas: <L>
- Lista: <arquivo (linhas)>, ...
- Exclusões: <categorias e arquivos excluídos, com motivo>
- Natureza da análise: leitura estática, sem execução da aplicação, sem instalação de dependências e sem exploração de vulnerabilidades.

## 3. Resumo por severidade

| CRITICAL | HIGH | MEDIUM | LOW | Total |
|---:|---:|---:|---:|---:|
| <n> | <n> | <n> | <n> | <n> |

Confirmados por leitura: <n> | Hipóteses não verificadas: <n>

## 4. Achados

### F-01 — [CRITICAL] <título curto> (AP-xx)

- **Localização:** `<arquivo>:<inicio>-<fim>`; `<arquivo>:<linha>`
- **Status:** Confirmado por leitura | Hipótese não verificada (<o que faltou verificar>)
- **Evidência:** <o que o código faz, com trecho curto se útil>
- **Impacto:** <consequência concreta para segurança, manutenção, testes, desempenho ou legibilidade>
- **Justificativa da severidade:** <por que este nível da escala; ajustes em relação à severidade base>
- **Recomendação:** <direção de correção> (T-xx)

<Para achados de API obsoleta, acrescente:>
- **Fonte oficial:** <URL da documentação da versão pertinente> — <versão consultada>; versão instalada: <versão ou "não verificado">

<Repetir para cada achado, em ordem de severidade.>

## 5. Plano de refatoração proposto

### 5.1 Estrutura-alvo
<Árvore de diretórios proposta, indicando o que é reaproveitado da organização atual e o que é novo. Justificar camadas adicionais, se houver.>

### 5.2 Transformações, em ordem de aplicação
| Ordem | Transformação | Achados tratados | Arquivos afetados |
|---:|---|---|---|
| 1 | T-xx <nome> | F-xx, F-yy | <arquivos> |

### 5.3 Contratos preservados
<Rotas, métodos, campos, códigos de status e comando de inicialização que serão mantidos.>

### 5.4 Mudanças de contrato intencionais
<Cada mudança necessária para corrigir segurança (ex.: remover campo sensível de resposta, proteger endpoint administrativo), com o achado que a motiva. "Nenhuma" se não houver.>

### 5.5 Decisões pendentes do usuário
<Escolhas que só o usuário pode fazer. "Nenhuma" se não houver. Uma linha por decisão:>

| ID | Decisão | Opções | Transformações/arquivos que dependem dela |
|---|---|---|---|
| D-1 | <ex.: destino de um endpoint administrativo> | <ex.: (a) remover; (b) proteger por token; (c) manter e documentar o risco> | <T-xx, arquivos> |

<Não escolha uma opção por conta própria nem a apresente como padrão implícito.>

### 5.6 Validação planejada
- Linha de base: execução do código original em cópia isolada, com dados de teste.
- Ambiente: <como as dependências serão disponibilizadas sem afetar o sistema global (ex.: venv temporário, `npm ci` na cópia)>.
- Endpoints a verificar: <quantidade>, cobrindo métodos, respostas e efeitos nos dados.
- Integrações externas: <como serão neutralizadas (ex.: não acionadas, configuração desabilitada)>.

### 5.7 Destino do relatório e das evidências
Caminhos relativos à raiz do repositório; ambos podem ser substituídos pelo usuário. Nada é gravado antes da confirmação.
- Relatório de auditoria (este documento, sem alterações): `reports/audit-<nome-do-projeto>.md`
- Evidências da Fase 3 (comandos, versões, trechos de logs, matriz de endpoints antes × depois, nova inspeção), com dados sensíveis removidos: `reports/evidence/<nome-do-projeto>/`

## 6. Limitações
<O que não foi verificado e por quê: versões instaladas, documentação não acessível, comportamento em execução, arquivos não lidos integralmente etc.>

================================
Total: <n> achados (CRITICAL: <n> | HIGH: <n> | MEDIUM: <n> | LOW: <n>)
================================
````

## Pergunta de confirmação (encerra a resposta)

Termine a resposta exatamente com um bloco neste formato e não execute mais nenhuma ação:

```
Fase 2 concluída. Nenhum arquivo foi alterado.

Deseja prosseguir com a Fase 3 (refatoração e validação) conforme o plano acima? [s/n]
- Para aprovar, responda explicitamente (ex.: "sim, prosseguir").
- Opcional: informe outros caminhos para o relatório (padrão: reports/audit-<nome-do-projeto>.md)
  e para as evidências (padrão: reports/evidence/<nome-do-projeto>/).
- Decisões pendentes (seção 5.5): <D-1, D-2...>. Indique a opção escolhida para cada uma;
  as alterações que dependem delas não serão feitas sem essa resposta.
```

Se a seção 5.5 estiver vazia, omita a última linha do bloco.

## Arquivo salvo na Fase 3

Ao salvar, grave o relatório exatamente como apresentado, acrescentando apenas, antes da seção 1, uma linha:

```
> Relatório gerado na Fase 2 em <data> e aprovado pelo usuário em <data>. Linhas referem-se ao commit `<hash>`; o código pode ter sido alterado pela Fase 3.
```

Não reescreva achados, linhas ou evidências após a refatoração, e não substitua nem complemente este arquivo com resultados da validação. Os resultados da Fase 3 vão para o destino de evidências (seção 5.7) e para a resposta final na conversa.
