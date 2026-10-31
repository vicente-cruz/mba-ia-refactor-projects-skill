import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
CLASS = {
 "health": "Correção intencional (5.4 item 2, F-07/F-08): sem secret_key e db_path; debug reflete a configuração (false)",
 "health apos escritas": "Correção intencional (5.4 item 2); contagens diferem pelos pedidos inválidos que o original aceitava",
 "health apos reset": "Correção intencional (5.4 item 2)",
 "busca preco_min invalido": "Correção intencional (5.4 item 4, F-14): 500 com str(e) → 400 controlado",
 "criar produto com aspas": "Correção intencional (5.4 item 8, F-01): aspas tratadas como texto; o original falhava com erro de sintaxe SQL",
 "criar produto preco string": "Correção intencional (5.4 item 4, F-14)",
 "criar produto sem corpo JSON": "Correção intencional (5.4 item 4, F-14): o original devolvia 415 embrulhado em 500",
 "atualizar produto categoria invalida": "Correção intencional (5.4 item 7, F-17): PUT aplica as regras do POST",
 "deletar produto 12": "Consequência do caso 'criar produto com aspas': o produto 12 agora existe e é excluído (efeito conferido)",
 "listar usuarios": "Correção intencional (5.4 item 1, F-03): sem o campo senha; os demais campos são idênticos; exige X-Admin-Token (D-6 b)",
 "usuario existente": "Correção intencional (5.4 item 1, F-03); exige X-Admin-Token (D-6 b)",
 "login sem corpo JSON": "Correção intencional (5.4 item 4, F-14)",
 "login injecao": "Correção intencional (5.4 item 8, F-01): o original autenticava o admin sem senha",
 "pedido quantidade negativa": "Correção intencional (5.4 item 5, F-14): o original aceitava e AUMENTAVA o estoque (10→15)",
 "pedido produto_id com injecao": "Correção intencional (5.4 item 5, F-01/F-14): o original criava o pedido com id injetado",
 "listar pedidos": "Consequência dos dois casos acima: o original listava 3 pedidos (2 inválidos); o pedido 1 é idêntico (verificado)",
 "pedidos do usuario 2": "Idem: o pedido 1 é idêntico; os pedidos 2 e 3 do original eram inválidos",
 "status pedido inexistente": "Correção intencional (5.4 item 6, F-14): 200 sem efeito → 404",
 "status sem corpo JSON": "Correção intencional (5.4 item 4, F-14)",
 "relatorio vendas": "Consequência dos pedidos inválidos rejeitados (o faturamento do original ficava negativo); regra de desconto idêntica em 9 faixas (testes, seção 6); exige X-Admin-Token (D-6 b)",
 "admin query predefinida": "Mudança de contrato aprovada (D-1 c): corpo {consulta}; o caso original {sql} é rejeitado com 400 (testes, seção 2)",
 "admin query sem consulta": "Mudança de contrato aprovada (D-1 c): mensagem 'Consulta não informada' (adaptação de 'Query não informada')",
}
print("| # | Caso | Método e caminho | Original | Refatorado | Resultado |")
print("|---:|---|---|---|---|---|")
regress = 0
for i, (x, y) in enumerate(zip(a, b), 1):
    same = x["status"] == y["status"] and x["corpo"] == y["corpo"]
    if same:
        cls = "Preservado (status e corpo idênticos)"
        if y["auth"] != "-": cls += "; exige X-Admin-Token"
    else:
        cls = CLASS.get(y["caso"])
        if cls is None:
            cls = "**REGRESSÃO (não classificada)**"; regress += 1
    caminho = y["caminho"] if x["caminho"] == y["caminho"] else f'{x["caminho"]} / {y["caminho"]}'
    print(f'| {i} | {y["caso"]} | `{y["metodo"]} {caminho}` | {x["status"]} | {y["status"]} | {cls} |')
print()
print(f"Casos: {len(a)} | idênticos: {sum(1 for x,y in zip(a,b) if x['status']==y['status'] and x['corpo']==y['corpo'])} | diferenças classificadas: {sum(1 for x,y in zip(a,b) if not (x['status']==y['status'] and x['corpo']==y['corpo']))-regress} | regressões: {regress}")
