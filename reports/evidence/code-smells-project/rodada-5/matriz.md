# Matriz de 54 casos — rodada 5

Ferramenta: `tools/matrix4.py` (contrato da rodada 3 + `X-Admin-Token` também nas rotas de D-10/D-11), servidor `python -B app.py` com banco novo. Mesma execução sobre 218ea6c (linha de base desta rodada) e sobre o código final. Comparação de status, corpo e efeito nos dados.

| # | Caso | Método e caminho | Token | 218ea6c | Final | Resultado |
|---:|---|---|---|---|---|---|
| 1 | indice | `GET /` | - | 200 | 200 | Idêntico |
| 2 | health | `GET /health` | - | 200 | 200 | **Mudou por D-9 (b)**: campo `ambiente` removido; demais campos idênticos |
| 3 | listar produtos | `GET /produtos` | - | 200 | 200 | Idêntico |
| 4 | produto existente | `GET /produtos/1` | - | 200 | 200 | Idêntico |
| 5 | produto inexistente | `GET /produtos/999` | - | 404 | 404 | Idêntico |
| 6 | busca por termo | `GET /produtos/busca?q=Mouse` | - | 200 | 200 | Idêntico |
| 7 | busca categoria+faixa | `GET /produtos/busca?categoria=moveis&preco_min=100&preco_max=2000` | - | 200 | 200 | Idêntico |
| 8 | busca com aspas (injecao) | `GET /produtos/busca?q=x%27%20OR%20%271%27%3D%271` | - | 200 | 200 | Idêntico |
| 9 | busca preco_min invalido | `GET /produtos/busca?preco_min=abc` | - | 400 | 400 | Idêntico |
| 10 | criar produto valido | `POST /produtos` | sim | 201 | 201 | Idêntico |
| 11 | criar produto sem nome | `POST /produtos` | sim | 400 | 400 | Idêntico |
| 12 | criar produto categoria invalida | `POST /produtos` | sim | 400 | 400 | Idêntico |
| 13 | criar produto com aspas | `POST /produtos` | sim | 201 | 201 | Idêntico |
| 14 | criar produto preco string | `POST /produtos` | sim | 400 | 400 | Idêntico |
| 15 | criar produto sem corpo JSON | `POST /produtos` | sim | 400 | 400 | Idêntico |
| 16 | atualizar produto 11 | `PUT /produtos/11` | sim | 200 | 200 | Idêntico |
| 17 | ler produto 11 apos update | `GET /produtos/11` | - | 200 | 200 | Idêntico |
| 18 | atualizar produto inexistente | `PUT /produtos/999` | sim | 404 | 404 | Idêntico |
| 19 | atualizar produto categoria invalida | `PUT /produtos/11` | sim | 400 | 400 | Idêntico |
| 20 | deletar produto 12 | `DELETE /produtos/12` | sim | 200 | 200 | Idêntico |
| 21 | ler produto 12 apos delete | `GET /produtos/12` | - | 404 | 404 | Idêntico |
| 22 | deletar produto inexistente | `DELETE /produtos/999` | sim | 404 | 404 | Idêntico |
| 23 | listar usuarios | `GET /usuarios` | sim | 200 | 200 | Idêntico |
| 24 | usuario existente | `GET /usuarios/1` | sim | 200 | 200 | Idêntico |
| 25 | usuario inexistente | `GET /usuarios/999` | sim | 404 | 404 | Idêntico |
| 26 | criar usuario valido | `POST /usuarios` | - | 201 | 201 | Idêntico |
| 27 | criar usuario incompleto | `POST /usuarios` | - | 400 | 400 | Idêntico |
| 28 | login admin valido | `POST /login` | - | 200 | 200 | Idêntico |
| 29 | login usuario criado | `POST /login` | - | 200 | 200 | Idêntico |
| 30 | login senha errada | `POST /login` | - | 401 | 401 | Idêntico |
| 31 | login incompleto | `POST /login` | - | 400 | 400 | Idêntico |
| 32 | login sem corpo JSON | `POST /login` | - | 400 | 400 | Idêntico |
| 33 | login injecao | `POST /login` | - | 401 | 401 | Idêntico |
| 34 | criar pedido valido | `POST /pedidos` | - | 201 | 201 | Idêntico |
| 35 | pedido produto inexistente | `POST /pedidos` | - | 400 | 400 | Idêntico |
| 36 | pedido estoque insuficiente | `POST /pedidos` | - | 400 | 400 | Idêntico |
| 37 | pedido sem usuario | `POST /pedidos` | - | 400 | 400 | Idêntico |
| 38 | pedido sem itens | `POST /pedidos` | - | 400 | 400 | Idêntico |
| 39 | pedido quantidade negativa | `POST /pedidos` | - | 400 | 400 | Idêntico |
| 40 | pedido produto_id com injecao | `POST /pedidos` | - | 400 | 400 | Idêntico |
| 41 | listar pedidos | `GET /pedidos` | sim | 200 | 200 | Idêntico |
| 42 | pedidos do usuario 2 | `GET /pedidos/usuario/2` | sim | 200 | 200 | Idêntico |
| 43 | pedidos de usuario sem pedidos | `GET /pedidos/usuario/999` | sim | 200 | 200 | Idêntico |
| 44 | status aprovado | `PUT /pedidos/1/status` | sim | 200 | 200 | Idêntico |
| 45 | status invalido | `PUT /pedidos/1/status` | sim | 400 | 400 | Idêntico |
| 46 | status pedido inexistente | `PUT /pedidos/999/status` | sim | 404 | 404 | Idêntico |
| 47 | status sem corpo JSON | `PUT /pedidos/1/status` | sim | 400 | 400 | Idêntico |
| 48 | relatorio vendas | `GET /relatorios/vendas` | sim | 200 | 200 | Idêntico |
| 49 | health apos escritas | `GET /health` | - | 200 | 200 | **Mudou por D-9 (b)**: campo `ambiente` removido; demais campos idênticos |
| 50 | admin query predefinida | `POST /admin/query` | sim | 200 | 200 | Idêntico |
| 51 | admin query sem consulta | `POST /admin/query` | sim | 400 | 400 | Idêntico |
| 52 | admin reset-db | `POST /admin/reset-db` | sim | 200 | 200 | Idêntico |
| 53 | listar produtos apos reset | `GET /produtos` | - | 200 | 200 | Idêntico |
| 54 | health apos reset | `GET /health` | - | 200 | 200 | **Mudou por D-9 (b)**: campo `ambiente` removido; demais campos idênticos |

Resultado: 51 idênticos; 3 mudaram (casos 2, 49, 54), todos por D-9 (b). Diferenças não justificadas: 0.

As decisões D-10 (a) e D-11 (a) não mudam nenhum resultado da matriz porque as chamadas às rotas protegidas levam token válido; as negações (403/401, dados antes e depois) estão em `specific.txt` grupo 9 e em `tests/test_seguranca.py`. D-4R não muda a matriz porque ela usa banco novo.

## Comparação com o código original (`../baseline.json`, `rodada-2/tools/compare.py`)

| # | Caso | Método e caminho | Original | Refatorado | Resultado |
|---:|---|---|---|---|---|
| 1 | indice | `GET /` | 200 | 200 | Preservado (status e corpo idênticos) |
| 2 | health | `GET /health` | 200 | 200 | Correção intencional (5.4 item 2, F-07/F-08): sem secret_key e db_path; debug reflete a configuração (false) |
| 3 | listar produtos | `GET /produtos` | 200 | 200 | Preservado (status e corpo idênticos) |
| 4 | produto existente | `GET /produtos/1` | 200 | 200 | Preservado (status e corpo idênticos) |
| 5 | produto inexistente | `GET /produtos/999` | 404 | 404 | Preservado (status e corpo idênticos) |
| 6 | busca por termo | `GET /produtos/busca?q=Mouse` | 200 | 200 | Preservado (status e corpo idênticos) |
| 7 | busca categoria+faixa | `GET /produtos/busca?categoria=moveis&preco_min=100&preco_max=2000` | 200 | 200 | Preservado (status e corpo idênticos) |
| 8 | busca com aspas (injecao) | `GET /produtos/busca?q=x%27%20OR%20%271%27%3D%271` | 200 | 200 | Preservado (status e corpo idênticos) |
| 9 | busca preco_min invalido | `GET /produtos/busca?preco_min=abc` | 500 | 400 | Correção intencional (5.4 item 4, F-14): 500 com str(e) → 400 controlado |
| 10 | criar produto valido | `POST /produtos` | 201 | 201 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 11 | criar produto sem nome | `POST /produtos` | 400 | 400 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 12 | criar produto categoria invalida | `POST /produtos` | 400 | 400 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 13 | criar produto com aspas | `POST /produtos` | 500 | 201 | Correção intencional (5.4 item 8, F-01): aspas tratadas como texto; o original falhava com erro de sintaxe SQL |
| 14 | criar produto preco string | `POST /produtos` | 500 | 400 | Correção intencional (5.4 item 4, F-14) |
| 15 | criar produto sem corpo JSON | `POST /produtos` | 500 | 400 | Correção intencional (5.4 item 4, F-14): o original devolvia 415 embrulhado em 500 |
| 16 | atualizar produto 11 | `PUT /produtos/11` | 200 | 200 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 17 | ler produto 11 apos update | `GET /produtos/11` | 200 | 200 | Preservado (status e corpo idênticos) |
| 18 | atualizar produto inexistente | `PUT /produtos/999` | 404 | 404 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 19 | atualizar produto categoria invalida | `PUT /produtos/11` | 200 | 400 | Correção intencional (5.4 item 7, F-17): PUT aplica as regras do POST |
| 20 | deletar produto 12 | `DELETE /produtos/12` | 404 | 200 | Consequência do caso 'criar produto com aspas': o produto 12 agora existe e é excluído (efeito conferido) |
| 21 | ler produto 12 apos delete | `GET /produtos/12` | 404 | 404 | Preservado (status e corpo idênticos) |
| 22 | deletar produto inexistente | `DELETE /produtos/999` | 404 | 404 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 23 | listar usuarios | `GET /usuarios` | 200 | 200 | Correção intencional (5.4 item 1, F-03): sem o campo senha; os demais campos são idênticos; exige X-Admin-Token (D-6 b) |
| 24 | usuario existente | `GET /usuarios/1` | 200 | 200 | Correção intencional (5.4 item 1, F-03); exige X-Admin-Token (D-6 b) |
| 25 | usuario inexistente | `GET /usuarios/999` | 404 | 404 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 26 | criar usuario valido | `POST /usuarios` | 201 | 201 | Preservado (status e corpo idênticos) |
| 27 | criar usuario incompleto | `POST /usuarios` | 400 | 400 | Preservado (status e corpo idênticos) |
| 28 | login admin valido | `POST /login` | 200 | 200 | Preservado (status e corpo idênticos) |
| 29 | login usuario criado | `POST /login` | 200 | 200 | Preservado (status e corpo idênticos) |
| 30 | login senha errada | `POST /login` | 401 | 401 | Preservado (status e corpo idênticos) |
| 31 | login incompleto | `POST /login` | 400 | 400 | Preservado (status e corpo idênticos) |
| 32 | login sem corpo JSON | `POST /login` | 500 | 400 | Correção intencional (5.4 item 4, F-14) |
| 33 | login injecao | `POST /login` | 200 | 401 | Correção intencional (5.4 item 8, F-01): o original autenticava o admin sem senha |
| 34 | criar pedido valido | `POST /pedidos` | 201 | 201 | Preservado (status e corpo idênticos) |
| 35 | pedido produto inexistente | `POST /pedidos` | 400 | 400 | Preservado (status e corpo idênticos) |
| 36 | pedido estoque insuficiente | `POST /pedidos` | 400 | 400 | Preservado (status e corpo idênticos) |
| 37 | pedido sem usuario | `POST /pedidos` | 400 | 400 | Preservado (status e corpo idênticos) |
| 38 | pedido sem itens | `POST /pedidos` | 400 | 400 | Preservado (status e corpo idênticos) |
| 39 | pedido quantidade negativa | `POST /pedidos` | 201 | 400 | Correção intencional (5.4 item 5, F-14): o original aceitava e AUMENTAVA o estoque (10→15) |
| 40 | pedido produto_id com injecao | `POST /pedidos` | 201 | 400 | Correção intencional (5.4 item 5, F-01/F-14): o original criava o pedido com id injetado |
| 41 | listar pedidos | `GET /pedidos` | 200 | 200 | Consequência dos dois casos acima: o original listava 3 pedidos (2 inválidos); o pedido 1 é idêntico (verificado) |
| 42 | pedidos do usuario 2 | `GET /pedidos/usuario/2` | 200 | 200 | Idem: o pedido 1 é idêntico; os pedidos 2 e 3 do original eram inválidos |
| 43 | pedidos de usuario sem pedidos | `GET /pedidos/usuario/999` | 200 | 200 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 44 | status aprovado | `PUT /pedidos/1/status` | 200 | 200 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 45 | status invalido | `PUT /pedidos/1/status` | 400 | 400 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 46 | status pedido inexistente | `PUT /pedidos/999/status` | 200 | 404 | Correção intencional (5.4 item 6, F-14): 200 sem efeito → 404 |
| 47 | status sem corpo JSON | `PUT /pedidos/1/status` | 500 | 400 | Correção intencional (5.4 item 4, F-14) |
| 48 | relatorio vendas | `GET /relatorios/vendas` | 200 | 200 | Consequência dos pedidos inválidos rejeitados (o faturamento do original ficava negativo); regra de desconto idêntica em 9 faixas (testes, seção 6); exige X-Admin-Token (D-6 b) |
| 49 | health apos escritas | `GET /health` | 200 | 200 | Correção intencional (5.4 item 2); contagens diferem pelos pedidos inválidos que o original aceitava |
| 50 | admin query predefinida | `POST /admin/query` | 200 | 200 | Mudança de contrato aprovada (D-1 c): corpo {consulta}; o caso original {sql} é rejeitado com 400 (testes, seção 2) |
| 51 | admin query sem consulta | `POST /admin/query` | 400 | 400 | Mudança de contrato aprovada (D-1 c): mensagem 'Consulta não informada' (adaptação de 'Query não informada') |
| 52 | admin reset-db | `POST /admin/reset-db` | 200 | 200 | Preservado (status e corpo idênticos); exige X-Admin-Token |
| 53 | listar produtos apos reset | `GET /produtos` | 200 | 200 | Preservado (status e corpo idênticos) |
| 54 | health apos reset | `GET /health` | 200 | 200 | Correção intencional (5.4 item 2) |

Casos: 54 | idênticos: 32 | diferenças classificadas: 22 | regressões: 0
