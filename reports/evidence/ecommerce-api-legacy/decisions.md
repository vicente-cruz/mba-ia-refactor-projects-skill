# Decisões do usuário — Fase 3 (ecommerce-api-legacy)

Data da aprovação: 2026-10-31. Relatório aprovado: `reports/audit-project-2.md` (revisão 3).

| ID | Opção escolhida | Resumo |
|---|---|---|
| D-1 | (b) | `GET /api/admin/financial-report` protegido por `ADMIN_TOKEN` (cabeçalho `X-Admin-Token`) |
| D-2 | (b) | `DELETE /api/users/:id` protegido pelo mesmo token |
| D-3 | (b) | usuário com matrículas → 409 sem alterações; usuário sem matrículas pode ser excluído |
| D-4 | (a) | senha válida exigida apenas para usuário novo |
| D-5 | (a) | auditoria na mesma transação do checkout |
| D-6 | (b) | `SEED_USER_PASSWORD` obrigatória, sem fallback; ausência impede a inicialização antes de abrir banco ou porta |

Mudanças de contrato aprovadas: C-1 a C-8, nas formas aplicáveis às opções acima.

Ajustes pedidos na aprovação e incorporados ao relatório antes da refatoração:
1. F-05 e limitações: o construtor de `AppManager` não executa `initDb` e `manager.db` é acessível; a linha de base inclui
   falhas induzidas por triggers `RAISE(ABORT, ...)` em `payments` e `audit_logs` (separadamente), sem acrescentar transações ao original;
   intercalações controladas de concorrência são distinguidas e feitas apenas no refatorado.
2. Seção 5.2.1: serialização registrada como trade-off, sem afirmação de ausência de impacto em desempenho.

Consequência aplicável: R-06 não se aplica (D-3 = b, sem exclusão em cascata).
