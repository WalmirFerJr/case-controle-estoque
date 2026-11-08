# Architecture Decision Records (ADRs)

Cada decisão relevante tem um registro curto: **Contexto → Opções consideradas → Decisão → Consequências**.
Decisões de *não* fazer algo também são registradas, porque escopo também é decisão técnica.

| # | Decisão | Status |
|---|---|---|
| [0001](0001-python-fastapi.md) | Python 3.12 + FastAPI | Aceita |
| [0002](0002-clean-architecture.md) | Clean Architecture com regra de dependência verificada no CI | Aceita |
| [0003](0003-postgresql.md) | PostgreSQL como persistência | Aceita |
| [0004](0004-modelo-de-dados.md) | Modelo: saldos no produto, holds unificados, ledger e `available` derivado | Aceita |
| [0005](0005-controle-de-concorrencia.md) | Lock pessimista por produto (`SELECT … FOR UPDATE`) | Aceita |
| [0006](0006-erros-problem-details.md) | Erros de domínio tipados → Problem Details HTTP | Aceita |
| [0007](0007-sem-front-end.md) | **Sem front-end** (decisão deliberada) | Aceita |
| [0008](0008-sem-deploy-cloud.md) | **Sem deploy em cloud** (decisão deliberada) | Aceita |
| [0009](0009-estrategia-de-testes.md) | Estratégia de testes em camadas | Aceita |
| [0010](0010-idempotencia.md) | Idempotência de requisições | Adiada (desenho pronto) |
