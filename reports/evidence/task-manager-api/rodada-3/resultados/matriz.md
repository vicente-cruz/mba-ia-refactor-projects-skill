# Matriz — rodada 3 (original × refatorado)

Gerada por `tools/compare.py`. Valores sensíveis não aparecem.

## Totais

```
{
 "registros_original": 377,
 "registros_refatorado": 400,
 "http_refatorado": 383,
 "fatos_refatorado": 17,
 "comparados": 377,
 "so_refatorado": 23,
 "preservados": 166,
 "intencionais": 211,
 "falhas": 0,
 "problemas": 0,
 "controles": 6,
 "controles_aprovados": 6,
 "mutacoes": 37,
 "mutacoes_detectadas": 37,
 "inventario_casos": {
  "original": 377,
  "refatorado": 400
 }
}
```

## Diferenças intencionais por classe

| Classe | Casos |
|---|---:|
| intencional C-01 | 19 |
| intencional C-02 | 7 |
| intencional C-03 | 4 |
| intencional C-04 | 3 |
| intencional C-05 | 3 |
| intencional C-06 | 9 |
| intencional C-07 | 2 |
| intencional C-08 | 3 |
| intencional C-09 | 1 |
| intencional C-10 | 4 |
| intencional C-11 | 2 |
| intencional C-12 | 17 |
| intencional C-JSON | 8 |
| intencional D-1a | 32 |
| intencional D-1a(token), F-01 | 2 |
| intencional D-2a | 1 |
| intencional F-01 | 32 |
| intencional F-01, F-02 | 4 |
| intencional F-06 | 2 |
| intencional M-01 | 2 |
| intencional M-02 | 4 |
| intencional M-03 | 5 |
| intencional M-04 | 2 |
| intencional R-01 | 7 |
| intencional R-02 | 3 |
| intencional R-03 | 5 |
| intencional R-04 | 8 |
| intencional R-05 | 6 |
| intencional R-06 | 3 |
| intencional R-07 | 2 |
| intencional R-08 | 4 |
| intencional R-09 | 5 |

## Verificações do comparador (controles positivos e mutações negativas)

| Tipo | Verificação | Resultado | OK |
|---|---|---|---|
| controle | sem mutação: POST /users sucesso | intencional F-01, F-02 | sim |
| controle | sem mutação: PUT /tasks/1 tags 0 | intencional R-05 | sim |
| controle | sem mutação: auth PUT anonimo | intencional D-1a | sim |
| controle | sem mutação: GET /tasks seed | preservado | sim |
| controle | sem mutação: conflito forçado PUT /users/2 | intencional C-07 | sim |
| controle | sem mutação: conflito forçado POST /users | intencional C-07 | sim |
| mutação | C-07 role do usuário-alvo alterada | FALHA expectativa/verificação | sim |
| mutação | C-07 contagem de tarefas zerada | FALHA expectativa/verificação | sim |
| mutação | C-07 tarefas removidas da listagem | FALHA expectativa/verificação | sim |
| mutação | C-07 outro usuário alterado | FALHA expectativa/verificação | sim |
| mutação | C-07 categoria alterada | FALHA expectativa/verificação | sim |
| mutação | C-07 email do alvo alterado | FALHA expectativa/verificação | sim |
| mutação | C-07 linha concorrente ausente | FALHA expectativa/verificação | sim |
| mutação | C-07 campo extra no corpo de erro | FALHA corpo de erro com campos além de "error" em C-07 | sim |
| mutação | C-07 password exposto no estado posterior | FALHA expectativa/verificação | sim |
| mutação | F-01 identidade errada (id) | FALHA expectativa/verificação | sim |
| mutação | F-01 nome incorreto | FALHA expectativa/verificação | sim |
| mutação | F-01 password exposto | FALHA expectativa/verificação | sim |
| mutação | F-01 auth_nonce exposto | FALHA expectativa/verificação | sim |
| mutação | F-01 campo removido (email) | FALHA expectativa/verificação | sim |
| mutação | F-01 contagem posterior errada | FALHA expectativa/verificação | sim |
| mutação | F-01 banco não alterado | FALHA expectativa/verificação | sim |
| mutação | F-01 hash fraco gravado | FALHA expectativa/verificação | sim |
| mutação | F-01 data incoerente | FALHA expectativa/verificação | sim |
| mutação | R-05 banco alterado | FALHA expectativa/verificação | sim |
| mutação | R-05 tags alteradas no GET posterior | FALHA expectativa/verificação | sim |
| mutação | R-05 mensagem errada | FALHA expectativa/verificação | sim |
| mutação | R-05 status 200 | FALHA expectativa/verificação | sim |
| mutação | R-05 password exposto no GET posterior | FALHA expectativa/verificação | sim |
| mutação | R-05 expectativa enfraquecida | FALHA expectativa fraca para R-05 | sim |
| mutação | R-05 campo extra no corpo de erro | FALHA corpo de erro com campos além de "error" em R-05 | sim |
| mutação | R-05 visão posterior alterada com digest igual | FALHA expectativa/verificação | sim |
| mutação | D-1a banco alterado | FALHA expectativa/verificação | sim |
| mutação | D-1a status 200 | FALHA expectativa/verificação | sim |
| mutação | D-1a sem WWW-Authenticate | FALHA expectativa/verificação | sim |
| mutação | D-1a nome alterado | FALHA expectativa/verificação | sim |
| mutação | sem classe: ordem alterada | FALHA expectativa/verificação | sim |
| mutação | sem classe: valor errado (overdue) | FALHA expectativa/verificação | sim |
| mutação | sem classe: prazo errado com formato válido | FALHA expectativa/verificação | sim |
| mutação | sem classe: campo removido | FALHA expectativa/verificação | sim |
| mutação | sem classe: cópia de outro endpoint | FALHA expectativa/verificação | sim |
| mutação | sem classe: classe inventada | FALHA expectativa/verificação | sim |
| mutação | expectativa falha com respostas idênticas | FALHA expectativa/verificação | sim |

## Problemas: 0


## Casos

| Grupo | Caso | Original | Refatorado | cls | Resultado |
|---|---|---|---|---|---|
| seed_leitura | caminho efetivo do banco | `"instance/tasks.db"` | `"instance/tasks.db"` |  | preservado |
| seed_leitura | GET / | 200 | 200 |  | preservado |
| seed_leitura | GET /health | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks seed | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/1 atrasada | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/2 nao atrasada | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/999 | 404 `Task não encontrada` | 404 `Task não encontrada` |  | preservado |
| seed_leitura | GET /tasks/abc conversor | 404 (HTML) | 404 `Recurso não encontrado` | M-03 | intencional M-03 |
| seed_leitura | GET /tasks/search?q=login | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?q=%25 | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?q=x'%20OR%20'1'='1 | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?status=pending | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?status=xyz | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?priority=2 | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?priority=%202%20 | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?priority=%2B2 | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?user_id=1 | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?q=a&status=pending&priority=1 | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search? | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?priority=1&priority=2 | 200 | 200 |  | preservado |
| seed_leitura | GET /tasks/search?priority=abc | 500 (HTML) | 400 `Prioridade inválida` | C-05 | intencional C-05 |
| seed_leitura | GET /tasks/search?priority=2.5 | 500 (HTML) | 400 `Prioridade inválida` | C-05 | intencional C-05 |
| seed_leitura | GET /tasks/search?user_id=abc | 500 (HTML) | 400 `Usuário inválido` | C-05 | intencional C-05 |
| seed_leitura | GET /tasks/stats | 200 | 200 |  | preservado |
| seed_leitura | GET /users | 200 | 200 |  | preservado |
| seed_leitura | GET /users/1 | 200 | 200 | F-01 | intencional F-01 |
| seed_leitura | GET /users/999 | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` |  | preservado |
| seed_leitura | GET /users/2/tasks | 200 | 200 |  | preservado |
| seed_leitura | GET /users/999/tasks | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` |  | preservado |
| seed_leitura | GET /reports/summary | 200 | 200 |  | preservado |
| seed_leitura | GET /reports/user/1 | 200 | 200 |  | preservado |
| seed_leitura | GET /reports/user/3 | 200 | 200 |  | preservado |
| seed_leitura | GET /reports/user/999 | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` |  | preservado |
| seed_leitura | GET /categories | 200 | 200 |  | preservado |
| seed_leitura | GET /nao-existe | 404 (HTML) | 404 `Recurso não encontrado` | M-03 | intencional M-03 |
| vazio | vazio GET /tasks | 200 | 200 |  | preservado |
| vazio | vazio GET /tasks/stats | 200 | 200 |  | preservado |
| vazio | vazio GET /users | 200 | 200 |  | preservado |
| vazio | vazio GET /reports/summary | 200 | 200 |  | preservado |
| vazio | vazio GET /categories | 200 | 200 |  | preservado |
| vazio | vazio GET /tasks/search | 200 | 200 |  | preservado |
| bordas | bordas GET /tasks | 200 | 200 |  | preservado |
| bordas | bordas GET /tasks/1 | 200 | 200 |  | preservado |
| bordas | bordas GET /tasks/3 done atrasada | 200 | 200 |  | preservado |
| bordas | bordas GET /tasks/stats | 200 | 200 |  | preservado |
| bordas | bordas GET /users | 200 | 200 |  | preservado |
| bordas | bordas GET /users/2/tasks | 200 | 200 |  | preservado |
| bordas | bordas GET /users/1/tasks | 200 | 200 |  | preservado |
| bordas | bordas GET /reports/summary | 200 | 200 |  | preservado |
| bordas | bordas GET /reports/user/1 | 200 | 200 |  | preservado |
| bordas | bordas GET /reports/user/2 | 200 | 200 |  | preservado |
| bordas | bordas GET /categories | 200 | 200 |  | preservado |
| bordas | bordas GET /tasks/search?user_id=1 | 200 | 200 |  | preservado |
| tasks_escrita | POST /tasks minimo | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks completo | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks title 200 | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks description null | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks priority 2.0 | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks due_date sem zero | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks due_date "" | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks tags elemento vazio | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks tags string | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks tags 0 (POST: falso = sem tags) | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks campos extras | 201 | 201 |  | preservado |
| tasks_escrita | POST /tasks corpo null | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| tasks_escrita | POST /tasks corpo {} | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| tasks_escrita | POST /tasks corpo [] | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| tasks_escrita | POST /tasks corpo "" | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| tasks_escrita | POST /tasks corpo 0 | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| tasks_escrita | POST /tasks corpo false | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| tasks_escrita | POST /tasks corpo [1] | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| tasks_escrita | POST /tasks corpo "x" | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| tasks_escrita | POST /tasks corpo 5 | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| tasks_escrita | POST /tasks corpo true | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| tasks_escrita | POST /tasks title ausente | 400 `Título é obrigatório` | 400 `Título é obrigatório` |  | preservado |
| tasks_escrita | POST /tasks title null | 400 `Título é obrigatório` | 400 `Título é obrigatório` |  | preservado |
| tasks_escrita | POST /tasks title "" | 400 `Título é obrigatório` | 400 `Título é obrigatório` |  | preservado |
| tasks_escrita | POST /tasks title curto | 400 `Título muito curto` | 400 `Título muito curto` |  | preservado |
| tasks_escrita | POST /tasks title longo | 400 `Título muito longo` | 400 `Título muito longo` |  | preservado |
| tasks_escrita | POST /tasks title numero | 500 (HTML) | 400 `Título inválido` | C-02 | intencional C-02 |
| tasks_escrita | POST /tasks title true | 500 (HTML) | 400 `Título inválido` | C-02 | intencional C-02 |
| tasks_escrita | POST /tasks title lista 2 | 400 `Título muito curto` | 400 `Título inválido` | C-02 | intencional C-02 |
| tasks_escrita | POST /tasks title lista 3 | 500 `Erro ao criar task` | 400 `Título inválido` | C-02 | intencional C-02 |
| tasks_escrita | POST /tasks description numero | 201 | 400 `Descrição inválida` | R-02 | intencional R-02 |
| tasks_escrita | POST /tasks description true | 201 | 400 `Descrição inválida` | R-02 | intencional R-02 |
| tasks_escrita | POST /tasks description lista | 500 `Erro ao criar task` | 400 `Descrição inválida` | C-10 | intencional C-10 |
| tasks_escrita | POST /tasks description objeto | 500 `Erro ao criar task` | 400 `Descrição inválida` | C-10 | intencional C-10 |
| tasks_escrita | POST /tasks status invalido | 400 `Status inválido` | 400 `Status inválido` |  | preservado |
| tasks_escrita | POST /tasks status null | 400 `Status inválido` | 400 `Status inválido` |  | preservado |
| tasks_escrita | POST /tasks status numero | 400 `Status inválido` | 400 `Status inválido` |  | preservado |
| tasks_escrita | POST /tasks priority false | 400 `Prioridade deve ser entre 1 e 5` | 400 `Prioridade inválida` | M-04 | intencional M-04 |
| tasks_escrita | POST /tasks priority true | 201 | 400 `Prioridade inválida` | R-03 | intencional R-03 |
| tasks_escrita | POST /tasks priority 2.5 | 201 | 400 `Prioridade inválida` | R-03 | intencional R-03 |
| tasks_escrita | POST /tasks priority 0 | 400 `Prioridade deve ser entre 1 e 5` | 400 `Prioridade deve ser entre 1 e 5` |  | preservado |
| tasks_escrita | POST /tasks priority 6 | 400 `Prioridade deve ser entre 1 e 5` | 400 `Prioridade deve ser entre 1 e 5` |  | preservado |
| tasks_escrita | POST /tasks priority 2^63 | 400 `Prioridade deve ser entre 1 e 5` | 400 `Prioridade deve ser entre 1 e 5` |  | preservado |
| tasks_escrita | POST /tasks priority "2" | 500 (HTML) | 400 `Prioridade inválida` | C-03 | intencional C-03 |
| tasks_escrita | POST /tasks priority null | 500 (HTML) | 400 `Prioridade inválida` | C-03 | intencional C-03 |
| tasks_escrita | POST /tasks priority lista | 500 (HTML) | 400 `Prioridade inválida` | C-03 | intencional C-03 |
| tasks_escrita | POST /tasks user_id 999 | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` |  | preservado |
| tasks_escrita | POST /tasks user_id 2^63 | 500 (HTML) | 404 `Usuário não encontrado` | C-12 | intencional C-12 |
| tasks_escrita | POST /tasks user_id 0 | 201 | 400 `Usuário inválido` | R-04 | intencional R-04 |
| tasks_escrita | POST /tasks user_id false | 201 | 400 `Usuário inválido` | R-04 | intencional R-04 |
| tasks_escrita | POST /tasks user_id "" | 201 | 400 `Usuário inválido` | R-04 | intencional R-04 |
| tasks_escrita | POST /tasks user_id "1" | 201 | 400 `Usuário inválido` | R-04 | intencional R-04 |
| tasks_escrita | POST /tasks user_id true | 201 | 400 `Usuário inválido` | R-04 | intencional R-04 |
| tasks_escrita | POST /tasks user_id -1 | 404 `Usuário não encontrado` | 400 `Usuário inválido` | M-02 | intencional M-02 |
| tasks_escrita | POST /tasks user_id 1.5 | 404 `Usuário não encontrado` | 400 `Usuário inválido` | M-02 | intencional M-02 |
| tasks_escrita | POST /tasks user_id "abc" | 404 `Usuário não encontrado` | 400 `Usuário inválido` | M-02 | intencional M-02 |
| tasks_escrita | POST /tasks user_id lista | 500 `Erro ao criar task` | 400 `Usuário inválido` | C-11 | intencional C-11 |
| tasks_escrita | POST /tasks user_id objeto | 500 `Erro ao criar task` | 400 `Usuário inválido` | C-11 | intencional C-11 |
| tasks_escrita | POST /tasks category_id 999 | 404 `Categoria não encontrada` | 404 `Categoria não encontrada` |  | preservado |
| tasks_escrita | POST /tasks category_id 2^63 | 500 (HTML) | 404 `Categoria não encontrada` | C-12 | intencional C-12 |
| tasks_escrita | POST /tasks category_id 0 | 201 | 400 `Categoria inválida` | R-04 | intencional R-04 |
| tasks_escrita | POST /tasks category_id "1" | 201 | 400 `Categoria inválida` | R-04 | intencional R-04 |
| tasks_escrita | POST /tasks category_id -1 | 404 `Categoria não encontrada` | 400 `Categoria inválida` | M-02 | intencional M-02 |
| tasks_escrita | POST /tasks due_date invalida | 400 `Formato de data inválido. Use YYYY-MM-DD` | 400 `Formato de data inválido. Use YYYY-MM-DD` |  | preservado |
| tasks_escrita | POST /tasks due_date numero | 400 `Formato de data inválido. Use YYYY-MM-DD` | 400 `Formato de data inválido. Use YYYY-MM-DD` |  | preservado |
| tasks_escrita | POST /tasks due_date dd/mm | 400 `Formato de data inválido. Use YYYY-MM-DD` | 400 `Formato de data inválido. Use YYYY-MM-DD` |  | preservado |
| tasks_escrita | POST /tasks tags elemento numero | 500 (HTML) | 400 `Tags inválidas` | C-04 | intencional C-04 |
| tasks_escrita | POST /tasks tags com virgula | 201 | 400 `Tags inválidas` | R-05 | intencional R-05 |
| tasks_escrita | POST /tasks tags numero | 201 | 400 `Tags inválidas` | R-05 | intencional R-05 |
| tasks_escrita | POST /tasks tags true | 201 | 400 `Tags inválidas` | R-05 | intencional R-05 |
| tasks_escrita | POST /tasks tags objeto | 500 `Erro ao criar task` | 400 `Tags inválidas` | C-04 | intencional C-04 |
| tasks_escrita | POST /tasks priority NaN | 201 | 400 `Prioridade inválida` | R-03 | intencional R-03 |
| tasks_escrita | POST /tasks priority Infinity | 400 `Prioridade deve ser entre 1 e 5` | 400 `Prioridade inválida` | M-01 | intencional M-01 |
| tasks_escrita | POST /tasks priority -Infinity | 400 `Prioridade deve ser entre 1 e 5` | 400 `Prioridade inválida` | M-01 | intencional M-01 |
| tasks_escrita | POST /tasks ctype texto | 415 (HTML) | 415 `Dados inválidos` | C-JSON | intencional C-JSON |
| tasks_escrita | POST /tasks json malformado | 400 (HTML) | 400 `Dados inválidos` | C-JSON | intencional C-JSON |
| tasks_escrita | PUT /tasks/1 title | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 description | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 status | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 priority 5 | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 desvincula user | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 desvincula category | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 user 2 | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 due null | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 due valida | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 tags lista | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 tags null limpa | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 tags "" limpa | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 tags [] limpa | 200 | 200 |  | preservado |
| tasks_escrita | PUT /tasks/1 user 999 | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` |  | preservado |
| tasks_escrita | PUT /tasks/1 user 2^63 | 500 (HTML) | 404 `Usuário não encontrado` | C-12 | intencional C-12 |
| tasks_escrita | PUT /tasks/1 due invalida | 400 `Formato de data inválido` | 400 `Formato de data inválido` |  | preservado |
| tasks_escrita | PUT /tasks/1 combinado titulo+prioridade invalida | 400 `Prioridade deve ser entre 1 e 5` | 400 `Prioridade deve ser entre 1 e 5` |  | preservado |
| tasks_escrita | PUT /tasks/1 corpo {} | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| tasks_escrita | PUT /tasks/1 corpo null | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| tasks_escrita | PUT /tasks/1 corpo [1] | 200 | 400 `Dados inválidos` | R-01 | intencional R-01 |
| tasks_escrita | PUT /tasks/1 corpo "x" | 200 | 400 `Dados inválidos` | R-01 | intencional R-01 |
| tasks_escrita | PUT /tasks/1 corpo 5 | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| tasks_escrita | PUT /tasks/1 corpo true | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| tasks_escrita | PUT /tasks/1 corpo "title" | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| tasks_escrita | PUT /tasks/1 title null | 500 (HTML) | 400 `Título inválido` | C-02 | intencional C-02 |
| tasks_escrita | PUT /tasks/1 title numero | 500 (HTML) | 400 `Título inválido` | C-02 | intencional C-02 |
| tasks_escrita | PUT /tasks/1 title false | 500 (HTML) | 400 `Título inválido` | C-02 | intencional C-02 |
| tasks_escrita | PUT /tasks/1 title "" | 400 `Título muito curto` | 400 `Título muito curto` |  | preservado |
| tasks_escrita | PUT /tasks/1 priority false | 400 `Prioridade deve ser entre 1 e 5` | 400 `Prioridade inválida` | M-04 | intencional M-04 |
| tasks_escrita | PUT /tasks/1 priority true | 200 | 400 `Prioridade inválida` | R-03 | intencional R-03 |
| tasks_escrita | PUT /tasks/1 priority "2" | 500 (HTML) | 400 `Prioridade inválida` | C-03 | intencional C-03 |
| tasks_escrita | PUT /tasks/1 priority 2.5 | 200 | 400 `Prioridade inválida` | R-03 | intencional R-03 |
| tasks_escrita | PUT /tasks/1 user_id 0 | 200 | 400 `Usuário inválido` | R-04 | intencional R-04 |
| tasks_escrita | PUT /tasks/1 description numero | 200 | 400 `Descrição inválida` | R-02 | intencional R-02 |
| tasks_escrita | PUT /tasks/1 tags 0 | 200 | 400 `Tags inválidas` | R-05 | intencional R-05 |
| tasks_escrita | PUT /tasks/1 tags false | 200 | 400 `Tags inválidas` | R-05 | intencional R-05 |
| tasks_escrita | PUT /tasks/1 tags 0.0 | 200 | 400 `Tags inválidas` | R-05 | intencional R-05 |
| tasks_escrita | PUT /tasks/1 tags {} | 500 `Erro ao atualizar` | 400 `Tags inválidas` | C-04 | intencional C-04 |
| tasks_escrita | PUT /tasks/999 | 404 `Task não encontrada` | 404 `Task não encontrada` |  | preservado |
| tasks_escrita | DELETE /tasks/1 | 200 | 200 |  | preservado |
| tasks_escrita | DELETE /tasks/1 repetido | 404 `Task não encontrada` | 404 `Task não encontrada` |  | preservado |
| tasks_escrita | GET /tasks/stats apos criar e concluir | 200 | 200 |  | preservado |
| users_escrita | POST /users sucesso | 201 | 201 | F-01 | intencional F-01, F-02 |
| users_escrita | POST /users role admin com admin | 201 | 201 | F-01 | intencional F-01, F-02 |
| users_escrita | POST /users role user com user | 201 | 201 | F-01 | intencional F-01, F-02 |
| users_escrita | POST /users active ignorado | 201 | 201 | F-01 | intencional F-01, F-02 |
| users_escrita | POST /users duplicado | 409 `Email já cadastrado` | 409 `Email já cadastrado` |  | preservado |
| users_escrita | POST /users sem name | 400 `Nome é obrigatório` | 400 `Nome é obrigatório` |  | preservado |
| users_escrita | POST /users sem email | 400 `Email é obrigatório` | 400 `Email é obrigatório` |  | preservado |
| users_escrita | POST /users sem password | 400 `Senha é obrigatória` | 400 `Senha é obrigatória` |  | preservado |
| users_escrita | POST /users name numero | 201 | 400 `Nome inválido` | R-06 | intencional R-06 |
| users_escrita | POST /users name lista | 500 `Erro ao criar usuário` | 400 `Nome inválido` | C-10 | intencional C-10 |
| users_escrita | POST /users email numero | 500 (HTML) | 400 `Email inválido` | C-06 | intencional C-06 |
| users_escrita | POST /users email invalido | 400 `Email inválido` | 400 `Email inválido` |  | preservado |
| users_escrita | POST /users password numero | 500 (HTML) | 400 `Senha inválida` | C-06 | intencional C-06 |
| users_escrita | POST /users password curta | 400 `Senha deve ter no mínimo 4 caracteres` | 400 `Senha deve ter no mínimo 4 caracteres` |  | preservado |
| users_escrita | POST /users password lista | 500 (HTML) | 400 `Senha inválida` | C-06 | intencional C-06 |
| users_escrita | POST /users role invalido | 400 `Role inválido` | 400 `Role inválido` |  | preservado |
| users_escrita | POST /users role null | 400 `Role inválido` | 400 `Role inválido` |  | preservado |
| users_escrita | POST /users role admin anonimo | 201 | 401 `Token ausente` | D-1a | intencional D-1a |
| users_escrita | POST /users role manager com user | 201 | 403 `Permissão negada` | D-1a | intencional D-1a |
| users_escrita | POST /users bearer invalido em cadastro anonimo | 201 | 401 `Token inválido` | D-1a | intencional D-1a |
| users_escrita | POST /users corpo null | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| users_escrita | POST /users corpo [1] | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| users_escrita | POST /users corpo 5 | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| users_escrita | PUT /users/2 name (admin) | 200 | 200 |  | intencional F-01 |
| users_escrita | PUT /users/2 email (admin) | 200 | 200 |  | intencional F-01 |
| users_escrita | PUT /users/2 role manager (admin) | 200 | 200 |  | intencional F-01 |
| users_escrita | PUT /users/2 active false (admin) | 200 | 200 |  | intencional F-01 |
| users_escrita | PUT /users/2 password (admin) | 200 | 200 |  | intencional F-01 |
| users_escrita | PUT /users/2 email duplicado (admin) | 409 `Email já cadastrado` | 409 `Email já cadastrado` |  | intencional F-01 |
| users_escrita | PUT /users/2 email invalido (admin) | 400 `Email inválido` | 400 `Email inválido` |  | intencional F-01 |
| users_escrita | PUT /users/2 email numero (admin) | 500 (HTML) | 400 `Email inválido` | C-06 | intencional C-06 |
| users_escrita | PUT /users/2 email null (admin) | 500 (HTML) | 400 `Email inválido` | C-06 | intencional C-06 |
| users_escrita | PUT /users/2 password curta (admin) | 400 `Senha muito curta` | 400 `Senha muito curta` |  | intencional F-01 |
| users_escrita | PUT /users/2 password null (admin) | 500 (HTML) | 400 `Senha inválida` | C-06 | intencional C-06 |
| users_escrita | PUT /users/2 password numero (admin) | 500 (HTML) | 400 `Senha inválida` | C-06 | intencional C-06 |
| users_escrita | PUT /users/2 role invalido (admin) | 400 `Role inválido` | 400 `Role inválido` |  | intencional F-01 |
| users_escrita | PUT /users/2 active 0 (admin) | 200 | 400 `Campo active inválido` | R-07 | intencional R-07 |
| users_escrita | PUT /users/2 active "x" (admin) | 500 `Erro ao atualizar` | 400 `Campo active inválido` | C-06 | intencional C-06 |
| users_escrita | PUT /users/2 active null (admin) | 200 | 400 `Campo active inválido` | R-07 | intencional R-07 |
| users_escrita | PUT /users/2 name null (admin) | 500 `Erro ao atualizar` | 400 `Nome inválido` | C-06 | intencional C-06 |
| users_escrita | PUT /users/2 name "" (admin) | 200 | 400 `Nome inválido` | R-06 | intencional R-06 |
| users_escrita | PUT /users/2 name numero (admin) | 200 | 400 `Nome inválido` | R-06 | intencional R-06 |
| users_escrita | PUT /users/2 corpo {} (admin) | 400 `Dados inválidos` | 400 `Dados inválidos` |  | intencional F-01 |
| users_escrita | PUT /users/2 corpo [1] (admin) | 200 | 400 `Dados inválidos` | R-01 | intencional R-01 |
| users_escrita | PUT /users/2 corpo 5 (admin) | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| users_escrita | PUT /users/2 corpo "name" (admin) | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| users_escrita | PUT /users/999 (admin) | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` |  | preservado |
| users_escrita | DELETE /users/3 com 3 tasks (admin) | 200 | 200 |  | preservado |
| users_escrita | DELETE /users/4 sem tasks (admin) | 200 | 200 |  | preservado |
| users_escrita | DELETE /users/999 (admin) | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` |  | preservado |
| users_escrita | POST /login correto | 200 | 200 | D-1a | intencional D-1a(token), F-01 |
| users_escrita | POST /login senha errada | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| users_escrita | POST /login email inexistente | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| users_escrita | POST /login campos ausentes | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| users_escrita | POST /login sem senha | 400 `Email e senha são obrigatórios` | 400 `Email e senha são obrigatórios` |  | preservado |
| users_escrita | POST /login email numero | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` | M-05 | preservado |
| users_escrita | POST /login email true | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` | M-05 | preservado |
| users_escrita | POST /login email lista | 500 (HTML) | 401 `Credenciais inválidas` | C-08 | intencional C-08 |
| users_escrita | POST /login email objeto | 500 (HTML) | 401 `Credenciais inválidas` | C-08 | intencional C-08 |
| users_escrita | POST /login senha numero email existente | 500 (HTML) | 401 `Credenciais inválidas` | C-08 | intencional C-08 |
| users_escrita | POST /login senha numero email inexistente | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| users_escrita | POST /login corpo null | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| users_escrita | POST /login corpo [1] | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| users_escrita | POST /login corpo 5 | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| users_escrita | POST /login inativo | 403 `Usuário inativo` | 403 `Usuário inativo` |  | preservado |
| categories_escrita | POST /categories padrao | 201 | 201 |  | preservado |
| categories_escrita | POST /categories cor valida | 201 | 201 |  | preservado |
| categories_escrita | POST /categories descricao null | 201 | 201 |  | preservado |
| categories_escrita | POST /categories cor invalida | 201 | 400 `Cor inválida` | R-09 | intencional R-09 |
| categories_escrita | POST /categories cor null | 201 | 400 `Cor inválida` | R-09 | intencional R-09 |
| categories_escrita | POST /categories cor com \n final | 201 | 400 `Cor inválida` | R-09 | intencional R-09 |
| categories_escrita | POST /categories sem nome | 400 `Nome é obrigatório` | 400 `Nome é obrigatório` |  | preservado |
| categories_escrita | POST /categories nome numero | 201 | 400 `Nome inválido` | R-08 | intencional R-08 |
| categories_escrita | POST /categories nome lista | 500 `Erro ao criar categoria` | 400 `Nome inválido` | C-10 | intencional C-10 |
| categories_escrita | POST /categories descricao numero | 201 | 400 `Descrição inválida` | R-08 | intencional R-08 |
| categories_escrita | POST /categories corpo null | 400 `Dados inválidos` | 400 `Dados inválidos` |  | preservado |
| categories_escrita | POST /categories corpo [1] | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| categories_escrita | POST /categories corpo 5 | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| categories_escrita | PUT /categories/1 parcial | 200 | 200 |  | preservado |
| categories_escrita | PUT /categories/1 cor valida | 200 | 200 |  | preservado |
| categories_escrita | PUT /categories/1 corpo {} | 200 | 200 |  | preservado |
| categories_escrita | PUT /categories/1 corpo null | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| categories_escrita | PUT /categories/1 corpo 0 | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| categories_escrita | PUT /categories/1 corpo false | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| categories_escrita | PUT /categories/1 corpo 5 | 500 (HTML) | 400 `Dados inválidos` | C-01 | intencional C-01 |
| categories_escrita | PUT /categories/1 corpo [] | 200 | 400 `Dados inválidos` | R-01 | intencional R-01 |
| categories_escrita | PUT /categories/1 corpo "" | 200 | 400 `Dados inválidos` | R-01 | intencional R-01 |
| categories_escrita | PUT /categories/1 corpo [1] | 200 | 400 `Dados inválidos` | R-01 | intencional R-01 |
| categories_escrita | PUT /categories/1 corpo "x" | 200 | 400 `Dados inválidos` | R-01 | intencional R-01 |
| categories_escrita | PUT /categories/1 nome null | 500 `Erro ao atualizar` | 400 `Nome é obrigatório` | C-09 | intencional C-09 |
| categories_escrita | PUT /categories/1 nome "" | 200 | 400 `Nome inválido` | R-08 | intencional R-08 |
| categories_escrita | PUT /categories/1 nome numero | 200 | 400 `Nome inválido` | R-08 | intencional R-08 |
| categories_escrita | PUT /categories/1 cor invalida | 200 | 400 `Cor inválida` | R-09 | intencional R-09 |
| categories_escrita | PUT /categories/1 cor com \n final | 200 | 400 `Cor inválida` | R-09 | intencional R-09 |
| categories_escrita | PUT /categories/999 | 404 `Categoria não encontrada` | 404 `Categoria não encontrada` |  | preservado |
| categories_escrita | DELETE /categories/1 com tasks | 200 | 200 |  | preservado |
| categories_escrita | DELETE /categories/5 sem tasks | 200 | 200 |  | preservado |
| categories_escrita | DELETE /categories/999 | 404 `Categoria não encontrada` | 404 `Categoria não encontrada` |  | preservado |
| auth | auth PUT anonimo | 200 | 401 `Token ausente` | D-1a | intencional D-1a |
| auth | auth DELETE anonimo | 200 | 401 `Token ausente` | D-1a | intencional D-1a |
| auth | auth header Bearer sem token | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| auth | auth header Basic | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| auth | auth header dois espacos | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| auth | auth header token vazio | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| auth | auth header adulterado | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| auth | auth header outra chave | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| auth | auth header longo demais | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| auth | auth bearer minusculo valido | 200 | 200 |  | intencional F-01 |
| auth | auth payload uid str | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload uid bool | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload uid 0 | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload uid negativo | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload uid 2^63 | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload uid -2^63-1 | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload sem sid | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload sid curto | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload sid caracteres | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload sid com \n final | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload chave extra | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload payload lista | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload uid inexistente | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload sid de outro | — | 401 `Token inválido` | D-1a | só refatorado |
| auth | auth payload valido assinado pelo harness | — | 200 |  | só refatorado |
| auth | auth token expirado | — | `[401, "Token expirado"]` |  | só refatorado |
| auth | matriz proprio altera nome | 200 | 200 |  | intencional F-01 |
| auth | matriz proprio altera email | 200 | 200 |  | intencional F-01 |
| auth | matriz proprio altera senha | 200 | 200 |  | intencional F-01 |
| auth | matriz outro usuario | 200 | 403 `Permissão negada` | D-1a | intencional D-1a |
| auth | matriz proprio role diferente | 200 | 403 `Permissão negada` | D-1a | intencional D-1a |
| auth | matriz proprio role igual | 200 | 200 |  | intencional F-01 |
| auth | matriz proprio active diferente | 200 | 403 `Permissão negada` | D-1a | intencional D-1a |
| auth | matriz proprio active igual | 200 | 200 |  | intencional F-01 |
| auth | matriz manager outro | 200 | 403 `Permissão negada` | D-1a | intencional D-1a |
| auth | matriz admin outro role | 200 | 200 |  | intencional F-01 |
| auth | matriz admin outro active | 200 | 200 |  | intencional F-01 |
| auth | matriz delete proprio user | 200 | 403 `Permissão negada` | D-1a | intencional D-1a |
| auth | matriz delete outro user | 200 | 403 `Permissão negada` | D-1a | intencional D-1a |
| auth | matriz delete admin outro | 200 | 200 |  | preservado |
| auth | matriz admin rebaixa a si mesmo | 200 | 200 |  | intencional F-01 |
| auth | matriz admin inativa a si mesmo | 200 | 200 |  | intencional F-01 |
| auth | matriz admin exclui a si mesmo (ultimo admin) | 200 | 200 |  | preservado |
| auth | inativo usa token | 200 | 403 `Usuário inativo` | D-1a | intencional D-1a |
| auth | inativo POST /users com bearer | 201 | 403 `Usuário inativo` | D-1a | intencional D-1a |
| auth | reativado usa token | 200 | 200 |  | intencional F-01 |
| auth | promovido opera como admin | 200 | 200 |  | intencional F-01 |
| auth | rebaixado perde admin na hora | 200 | 403 `Permissão negada` | D-1a | intencional D-1a |
| auth | POST /users bearer de conta excluida | 201 | 401 `Token inválido` | D-1a | intencional D-1a |
| ciclo_token | reuso de ID (Y user): Y recebeu o mesmo ID de X | `true` | `true` |  | preservado |
| ciclo_token | reuso de ID (Y user): token antigo de X | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| ciclo_token | reuso de ID (Y user): controle com token novo de Y | 200 | 200 |  | intencional F-01 |
| ciclo_token | reuso de ID (Y admin): Y recebeu o mesmo ID de X | `true` | `true` |  | preservado |
| ciclo_token | reuso de ID (Y admin): token antigo de X | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| ciclo_token | reuso de ID (Y admin): controle com token novo de Y | 200 | 200 |  | intencional F-01 |
| ciclo_token | novo seed: admin mantém id 1 | `1` | `1` |  | preservado |
| ciclo_token | novo seed: nonce do admin mudou | — | `true` |  | só refatorado |
| ciclo_token | novo seed: token antigo do admin | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| ciclo_token | novo seed: token novo do admin | 200 | 200 |  | intencional F-01 |
| ciclo_token | senha: troca com T1 | 200 | 200 |  | intencional F-01 |
| ciclo_token | senha: T1 depois da troca | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| ciclo_token | senha: T2 depois da troca | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| ciclo_token | senha: login com a antiga | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| ciclo_token | senha: token novo funciona | 200 | 200 |  | intencional F-01 |
| ciclo_token | senha: admin troca senha de pedro | 200 | 200 |  | intencional F-01 |
| ciclo_token | senha: token antigo de pedro | 200 | 401 `Token inválido` | D-1a | intencional D-1a |
| ciclo_token | senha: token do admin continua | 200 | 200 |  | intencional F-01 |
| ciclo_token | senha: commit falha (induzida) | 500 `Erro ao atualizar` | 500 `Erro ao atualizar` |  | preservado |
| ciclo_token | senha: commit falho mantém hash e nonce | `true` | `true` |  | preservado |
| ciclo_token | senha: T1 continua válido após falha | 200 | 200 |  | intencional F-01 |
| ciclo_token | md5 legado: formato do hash após login | `"md5"` | `"werkzeug-scrypt"` | D-2a | intencional D-2a |
| ciclo_token | md5 legado: nonce mantido | — | `true` |  | só refatorado |
| ciclo_token | md5 legado: token anterior continua | — | 200 |  | só refatorado |
| ciclo_token | md5 legado: login seguinte | 200 | 200 | D-1a | intencional D-1a(token), F-01 |
| ciclo_token | md5 legado: senha errada | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| ciclo_token | hash malformado vazio | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| ciclo_token | hash malformado abc | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| ciclo_token | hash malformado werkzeug truncado | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| ciclo_token | hash malformado md5 31 | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| ciclo_token | hash malformado md5 maiusculo | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| ciclo_token | hash malformado md5 com \n final | 401 `Credenciais inválidas` | 401 `Credenciais inválidas` |  | preservado |
| rollback | conflito forçado POST /users | 500 `Erro ao criar usuário` | 409 `Email já cadastrado` | C-07 | intencional C-07 |
| rollback | recuperação da aplicação após conflito | 200 | 200 |  | preservado |
| rollback | conflito forçado PUT /users/2 | 500 `Erro ao atualizar` | 409 `Email já cadastrado` | C-07 | intencional C-07 |
| rollback | recuperação da aplicação após conflito PUT | 200 | 200 |  | intencional F-01 |
| rollback | falha forçada de flush POST /tasks (induzida) | 500 `Erro ao criar task` | 500 `Erro ao criar task` |  | preservado |
| rollback | recuperação da aplicação após falha de flush | 201 | 201 |  | preservado |
| rollback | mesma sessão: ConflictError | — | `"Email já cadastrado"` |  | só refatorado |
| rollback | mesma sessão: mesmo objeto de sessão | — | `true` |  | só refatorado |
| rollback | mesma sessão: sessão ativa após rollback | — | `true` |  | só refatorado |
| rollback | mesma sessão: commit seguinte persistiu | — | `1` |  | só refatorado |
| seed_falha | seed falha: exceção propagada | `"RuntimeError"` | `"RuntimeError"` |  | preservado |
| seed_falha | seed falha: contagens antes | `{"tasks": 11, "users": 3, "categories": 5}` | `{"tasks": 11, "users": 3, "categories": 5}` |  | preservado |
| seed_falha | seed falha: banco idêntico ao anterior | `false` | `true` | F-06 | intencional F-06 |
| seed_falha | seed falha: contagens depois | `{"tasks": 0, "users": 3, "categories": 4}` | `{"tasks": 11, "users": 3, "categories": 5}` | F-06 | intencional F-06 |
| bigint | 2^63 GET /tasks/<2^63> | 500 (HTML) | 404 `Task não encontrada` | C-12 | intencional C-12 |
| bigint | 2^63 GET /users/<2^63> | 500 (HTML) | 404 `Usuário não encontrado` | C-12 | intencional C-12 |
| bigint | 2^63 GET /users/<2^63>/tasks | 500 (HTML) | 404 `Usuário não encontrado` | C-12 | intencional C-12 |
| bigint | 2^63 GET /reports/user/<2^63> | 500 (HTML) | 404 `Usuário não encontrado` | C-12 | intencional C-12 |
| bigint | 2^63 PUT /tasks/<2^63> | 500 (HTML) | 404 `Task não encontrada` | C-12 | intencional C-12 |
| bigint | 2^63 DELETE /tasks/<2^63> | 500 (HTML) | 404 `Task não encontrada` | C-12 | intencional C-12 |
| bigint | 2^63 PUT /categories/<2^63> | 500 (HTML) | 404 `Categoria não encontrada` | C-12 | intencional C-12 |
| bigint | 2^63 DELETE /categories/<2^63> | 500 (HTML) | 404 `Categoria não encontrada` | C-12 | intencional C-12 |
| bigint | 2^63 PUT /users/<2^63> | 500 (HTML) | 404 `Usuário não encontrado` | C-12 | intencional C-12 |
| bigint | 2^63 DELETE /users/<2^63> | 500 (HTML) | 404 `Usuário não encontrado` | C-12 | intencional C-12 |
| bigint | 2^63 GET /tasks/search?priority=<2^63> | 500 (HTML) | 200 | C-12 | intencional C-12 |
| bigint | 2^63 GET /tasks/search?user_id=<2^63> | 500 (HTML) | 200 | C-12 | intencional C-12 |
| bigint | 2^63 GET /tasks/search?priority=-<2^63+1> | 500 (HTML) | 200 | C-12 | intencional C-12 |
| bigint | 2^63 GET /tasks/search?user_id=<2^63>&priority=2 | 500 (HTML) | 200 | C-12 | intencional C-12 |
| bigint | 2^63-1 GET /tasks/<max> (dentro da faixa) | 404 `Task não encontrada` | 404 `Task não encontrada` |  | preservado |
| bigint | 2^63-1 GET /tasks/search?user_id=<max> | 200 | 200 |  | preservado |
| http | 405 POST / | 405 (HTML) | 405 `Método não permitido` | M-03 | intencional M-03 |
| http | 405 DELETE /tasks | 405 (HTML) | 405 `Método não permitido` | M-03 | intencional M-03 |
| http | 405 PATCH /tasks/1 | 405 (HTML) | 405 `Método não permitido` | M-03 | intencional M-03 |
| http | PUT /tasks/999 inexistente + json malformado | 404 `Task não encontrada` | 404 `Task não encontrada` |  | preservado |
| http | PUT /categories/999 inexistente + json malformado | 404 `Categoria não encontrada` | 404 `Categoria não encontrada` |  | preservado |
| http | PUT /users/999 inexistente + json malformado | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` |  | preservado |
| http | PUT /users/999 anonimo + json malformado | 404 `Usuário não encontrado` | 401 `Token ausente` | D-1a | intencional D-1a |
| http | PUT /users/2 anonimo + json malformado | 400 (HTML) | 401 `Token ausente` | D-1a | intencional D-1a |
| http | PUT /tasks/1 existente + json malformado | 400 (HTML) | 400 `Dados inválidos` | C-JSON | intencional C-JSON |
| http | PUT /categories/1 existente + json malformado | 400 (HTML) | 400 `Dados inválidos` | C-JSON | intencional C-JSON |
| http | PUT /users/2 existente + json malformado | 400 (HTML) | 400 `Dados inválidos` | C-JSON | intencional C-JSON |
| http | PUT /tasks/999 inexistente + content-type texto | 404 `Task não encontrada` | 404 `Task não encontrada` |  | preservado |
| http | PUT /categories/999 inexistente + content-type texto | 404 `Categoria não encontrada` | 404 `Categoria não encontrada` |  | preservado |
| http | PUT /users/999 inexistente + content-type texto | 404 `Usuário não encontrado` | 404 `Usuário não encontrado` |  | preservado |
| http | PUT /users/999 anonimo + content-type texto | 404 `Usuário não encontrado` | 401 `Token ausente` | D-1a | intencional D-1a |
| http | PUT /users/2 anonimo + content-type texto | 415 (HTML) | 401 `Token ausente` | D-1a | intencional D-1a |
| http | PUT /tasks/1 existente + content-type texto | 415 (HTML) | 415 `Dados inválidos` | C-JSON | intencional C-JSON |
| http | PUT /categories/1 existente + content-type texto | 415 (HTML) | 415 `Dados inválidos` | C-JSON | intencional C-JSON |
| http | PUT /users/2 existente + content-type texto | 415 (HTML) | 415 `Dados inválidos` | C-JSON | intencional C-JSON |
| fronteira7 | fronteira 7 dias: /reports/summary com relógio fixo | 200 | 200 |  | preservado |
