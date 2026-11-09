# Controle de Estoque: Case Prático de Engenharia de Software

API para controle de estoque com **entrada, saída, reserva, bloqueio, liberação e consulta**,
que preserva a consistência dos saldos mesmo sob requisições concorrentes.

`Python 3.12` · `FastAPI` · `PostgreSQL 16` · `SQLAlchemy 2` · `Alembic` · `pytest + hypothesis + testcontainers` · `Docker` · `GitHub Actions`

```bash
docker compose up --build -d      # API + PostgreSQL
open http://localhost:8000/docs   # Swagger: exercite todas as operações
```

**Índice:**
[Visão geral](#1-visão-geral) ·
[Arquitetura](#2-arquiteturaestrutura) ·
[Decisões técnicas](#3-principais-decisões-técnicas) ·
[Premissas](#4-premissas-consideradas) ·
[Limitações](#5-limitações-conhecidas) ·
[Execução](#6-instruções-para-execução) ·
[Produção](#7-o-que-eu-faria-diferente-em-produção) ·
[Testes](#testes) ·
[Uso de IA](#uso-de-ia) ·
[Visão de engenharia](#visão-de-engenharia)

---

## 1. Visão geral

Para cada produto (identificado por **SKU**) a API mantém:

| Saldo | Significado |
|---|---|
| `total` | Unidades fisicamente em estoque |
| `reserved` | Retidas para solicitações/pedidos (reservas ativas) |
| `blocked` | Indisponíveis por outro motivo: avaria, inspeção… (bloqueios ativos) |
| `available` | **Derivado:** `total − reserved − blocked` (nunca armazenado) |

**Invariantes**, garantidas no domínio **e** por CHECK constraints no banco:
`total ≥ 0`, `reserved ≥ 0`, `blocked ≥ 0` e `reserved + blocked ≤ total` (logo, `available ≥ 0`).

### Funcionalidades (enunciado §3)

| # | Operação | Endpoint | Regra |
|---|---|---|---|
| 1 | Entrada | `POST /api/v1/products/{sku}/entries` | Soma ao total; a 1ª entrada cria o produto |
| 2 | Saída | `POST /api/v1/products/{sku}/exits` | Só até o **disponível** |
| 3 | Reservar | `POST /api/v1/products/{sku}/reservations` | Só até o disponível; gera `id` + exige `reference` (pedido) |
| 4 | Bloquear | `POST /api/v1/products/{sku}/blocks` | Só até o disponível; gera `id`; `reason` opcional |
| 5 | Liberar | `POST /api/v1/holds/{id}/release` | Hold ativo volta ao disponível; liberar 2x → 409 |
| 6 | Consultar | `GET /api/v1/products/{sku}` | Total, disponível, reservado, bloqueado + holds ativos |
| – | Consultar reserva/bloqueio | `GET /api/v1/holds/{id}` | Pela identificação |
| – | Listar por solicitação | `GET /api/v1/holds?reference=&sku=&type=&status=` | Vários holds por produto e por pedido |
| ➕ | Consumir reserva | `POST /api/v1/holds/{id}/consume` | Extra: pedido expedido; reservado sai do estoque ([por quê](docs/adr/0004-modelo-de-dados.md#6-extra-consumir-reserva-post-holdsidconsume)) |
| ➕ | Histórico (auditoria) | `GET /api/v1/products/{sku}/movements` | Ledger append-only de todas as movimentações |
| ➕ | Saúde | `GET /health` | Verifica a aplicação e o banco |

"Hold" é o nome interno comum para **reserva ou bloqueio** (mesmo ciclo de vida, diferenciados por `type`).

---

## 2. Arquitetura/estrutura

**Clean Architecture** (ports & adapters): as dependências apontam para dentro, e o domínio não
conhece framework nenhum. A regra é **verificada automaticamente** pelo `import-linter` no CI.

```mermaid
flowchart LR
    subgraph Adaptadores de entrada
        API["presentation<br/>FastAPI · schemas · Problem Details · correlation id"]
    end
    subgraph Núcleo
        APP["application<br/>casos de uso · ports (Protocol) · DTOs"]
        DOM["domain<br/>Product · Hold · StockMovement · Sku · Quantity · exceções"]
    end
    subgraph Adaptadores de saída
        INFRA["infrastructure<br/>SQLAlchemy · repositórios · Unit of Work · Alembic"]
    end
    DB[(PostgreSQL)]
    MAIN["main.py<br/>composition root"]

    API --> APP --> DOM
    INFRA --> APP
    INFRA --> DB
    MAIN -.liga.-> API
    MAIN -.liga.-> INFRA
```

```
src/stock/
├── domain/              # Regras puras: entidades ricas, value objects, exceções, replay do ledger
├── application/         # 1 caso de uso por classe + ports (repositórios, UoW, relógio) + DTOs
├── infrastructure/      # PostgreSQL: models, mappers, repositórios (FOR UPDATE), UoW, migrations
├── presentation/        # HTTP: rotas /api/v1, schemas Pydantic, erros, logs JSON + correlation id
└── main.py              # Composition root
tests/
├── unit/                # Domínio e casos de uso (fakes em memória). Sem Docker, < 1s
├── property/            # hypothesis: máquina de estados × modelo de referência
├── integration/         # API + PostgreSQL real (testcontainers)
└── concurrency/         # Disputa real entre transações simultâneas
docs/
├── adr/                 # 10 decisões de arquitetura (inclusive o que não foi feito)
├── ai/                  # Uso de IA: análise + registro de prompts
└── ENGINEERING_VISION.md
CLAUDE.md                # Contexto/regras dadas à IA (versionado como evidência)
```

### Modelo de dados

```mermaid
erDiagram
    products ||--o{ holds : "tem"
    products ||--o{ stock_movements : "registra"
    holds ||--o{ stock_movements : "origina"
    products {
        varchar sku PK
        bigint total_quantity "CHECK >= 0"
        bigint reserved_quantity "CHECK >= 0"
        bigint blocked_quantity "CHECK >= 0, reserved+blocked <= total"
    }
    holds {
        uuid id PK
        varchar sku FK
        varchar type "RESERVATION | BLOCK"
        varchar status "ACTIVE | RELEASED | CONSUMED"
        bigint quantity "CHECK > 0"
        varchar reference "solicitação/pedido"
        varchar reason "opcional"
        timestamptz created_at
        timestamptz closed_at "NULL sse ACTIVE"
    }
    stock_movements {
        uuid id PK
        varchar sku FK
        varchar type "ENTRY | EXIT | RESERVE | BLOCK | RELEASE_* | CONSUME_RESERVATION"
        bigint quantity "CHECK > 0"
        uuid hold_id FK "opcional"
        timestamptz occurred_at
    }
```

### Como uma reserva concorrente é serializada

```mermaid
sequenceDiagram
    participant A as Requisição A
    participant B as Requisição B
    participant DB as PostgreSQL
    Note over DB: SKU-1: total=1, available=1
    A->>DB: BEGIN, SELECT … FOR UPDATE (SKU-1)
    B->>DB: BEGIN, SELECT … FOR UPDATE (SKU-1)
    Note over B,DB: B espera o lock de A
    A->>A: Product.reserve(1) ✔
    A->>DB: UPDATE products, INSERT hold, INSERT movement, COMMIT
    DB-->>B: lock liberado, lê available=0
    B->>B: Product.reserve(1) ✖ InsufficientAvailableStock
    B->>DB: ROLLBACK
    Note over B: HTTP 409 INSUFFICIENT_AVAILABLE_STOCK
```

---

## 3. Principais decisões técnicas

Cada decisão tem um ADR com **contexto, alternativas, decisão e consequências** em [`docs/adr/`](docs/adr/README.md).

| Decisão | Resumo | ADR |
|---|---|---|
| Python + FastAPI | Stack que domino; OpenAPI automático serve de interface | [0001](docs/adr/0001-python-fastapi.md) |
| Clean Architecture | Domínio puro e testável; regra de dependência quebrada = build quebrado | [0002](docs/adr/0002-clean-architecture.md) |
| PostgreSQL | ACID, lock de linha e CHECK: consistência que vale entre várias instâncias da API | [0003](docs/adr/0003-postgresql.md) |
| Modelo de dados | `available` derivado; contadores + holds; reserva e bloqueio = mesma entidade; ledger | [0004](docs/adr/0004-modelo-de-dados.md) |
| Concorrência | `SELECT … FOR UPDATE` por produto, ordem de lock fixa, `lock_timeout` | [0005](docs/adr/0005-controle-de-concorrencia.md) |
| Erros | Exceções de domínio tipadas → Problem Details com `code` estável | [0006](docs/adr/0006-erros-problem-details.md) |
| **Sem front-end** | Decisão deliberada: linguagens do case + foco da avaliação; Swagger como interface | [0007](docs/adr/0007-sem-front-end.md) |
| **Sem deploy cloud** | Decisão deliberada: execução local reproduzível; arquitetura AWS documentada | [0008](docs/adr/0008-sem-deploy-cloud.md) |
| Testes | Pirâmide com property-based e concorrência real | [0009](docs/adr/0009-estrategia-de-testes.md) |
| Idempotência | Adiada com desenho pronto | [0010](docs/adr/0010-idempotencia.md) |

### Fora do escopo (decisões deliberadas, não esquecimentos)
- **Front-end:** o enunciado restringe a Java/C#/Python e não avalia interface. A API versionada com OpenAPI é o contrato; um front pode ser acoplado sem mudar o back ([ADR-0007](docs/adr/0007-sem-front-end.md)).
- **Deploy em cloud:** custo e tempo sem retorno avaliativo; tudo roda com `docker compose up` ([ADR-0008](docs/adr/0008-sem-deploy-cloud.md)).
- **Autenticação/autorização:** fora do escopo funcional do case; descrita na seção de produção.

---

## 4. Premissas consideradas

Ambiguidades do enunciado e como foram resolvidas:

| Ponto do enunciado | Premissa adotada |
|---|---|
| "identificação do produto" | SKU único, 1–64 caracteres `[A-Za-z0-9._-]`, case-sensitive |
| Entrada de produto inexistente | A 1ª entrada **cria** o produto (não há cadastro de catálogo no enunciado). Criação segura sob concorrência (`ON CONFLICT DO NOTHING`) |
| Saída | Retira só do **disponível**; unidades reservadas/bloqueadas nunca saem por saída avulsa |
| Reserva "para uma solicitação/pedido" | `reference` obrigatória; vários holds por produto e por referência são permitidos |
| Bloqueio | Também só sobre o **disponível** (regra do enunciado): não bloqueia unidade já reservada. `reason` opcional |
| "Liberar… retornando à condição apropriada" | Reserva e bloqueio liberados voltam ao **disponível** |
| Liberação parcial | Não suportada: libera o hold inteiro |
| Liberar o que já foi liberado/consumido | **409 `HOLD_NOT_ACTIVE`** (explícito, não silencioso) |
| Quantidades | Inteiras, `1 ≤ q ≤ 1.000.000` por operação; total por produto ≤ 1.000.000.000 |
| Consulta "ao menos" os 4 saldos | Retorna os 4 saldos + a lista de holds ativos |

---

## 5. Limitações conhecidas

- **Sem idempotência:** um retry de `POST` após timeout pode duplicar a operação ([desenho pronto no ADR-0010](docs/adr/0010-idempotencia.md)).
- **Sem autenticação/autorização** e sem registro de *quem* fez cada movimento.
- **Reservas não expiram:** uma reserva esquecida retém estoque indefinidamente.
- **Liberação só total**, sem liberação parcial.
- **Consulta do produto não é um snapshot único:** saldo e holds ativos são lidos em dois `SELECT`s (READ COMMITTED). Sob escrita concorrente, a lista de holds pode refletir um instante ligeiramente diferente do saldo. Escritas não são afetadas.
- **Throughput por SKU** limitado pela serialização do lock (um SKU "quente" vira fila; SKUs diferentes seguem em paralelo).
- **Listagens** paginadas por `limit/offset`, sem total de registros nem cursor.
- **Single-region / single-database.**

---

## 6. Instruções para execução

### Pré-requisitos
- **Docker** (com Compose): para rodar a API e os testes de integração.
- **Python 3.12+**: apenas para rodar os testes/a API fora do container.

### Opção A: tudo em Docker (mais simples)
```bash
docker compose up --build -d
```
- Swagger: <http://localhost:8000/docs> · OpenAPI: <http://localhost:8000/openapi.json>
- As migrations são aplicadas automaticamente na subida do container.
- Para derrubar: `docker compose down -v`

### Opção B: API local + banco em Docker
```bash
make install          # cria .venv e instala dependências
make db               # sobe só o PostgreSQL
make migrate          # aplica as migrations
make run              # http://localhost:8000/docs (com reload)
```

### Testes e qualidade
```bash
make test-unit        # domínio, casos de uso e property-based: sem Docker, ~2s
make test             # tudo, incluindo integração e concorrência (sobe Postgres via testcontainers)
make check            # o mesmo que o CI: ruff + format + mypy strict + import-linter + testes com cobertura
```
Sem `make`: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest`

### Exemplo de uso (curl)
```bash
API=http://localhost:8000/api/v1

curl -s -X POST $API/products/NOTE-15/entries -H 'Content-Type: application/json' -d '{"quantity": 10}'
# {"sku":"NOTE-15","total":10,"available":10,"reserved":0,"blocked":0}

curl -s -X POST $API/products/NOTE-15/reservations -H 'Content-Type: application/json' \
     -d '{"quantity": 3, "reference": "PED-2026-0001"}'
# {"id":"<uuid>","type":"RESERVATION","status":"ACTIVE","quantity":3,...}

curl -s -X POST $API/products/NOTE-15/blocks -H 'Content-Type: application/json' \
     -d '{"quantity": 2, "reference": "QA-42", "reason": "Avaria no transporte"}'

curl -s $API/products/NOTE-15
# {"sku":"NOTE-15","total":10,"available":5,"reserved":3,"blocked":2,"active_holds":[...]}

curl -s -X POST $API/products/NOTE-15/exits -H 'Content-Type: application/json' -d '{"quantity": 6}'
# 409 application/problem+json
# {"code":"INSUFFICIENT_AVAILABLE_STOCK","requested":6,"available":5,"correlation_id":"...",...}

curl -s -X POST $API/holds/<uuid>/release
curl -s "$API/holds?reference=PED-2026-0001"
curl -s $API/products/NOTE-15/movements
```

### Contrato de erros
Todas as falhas seguem **Problem Details** (`application/problem+json`) com `code` estável e `correlation_id`:

| Status | Quando | `code` |
|---|---|---|
| 404 | Produto/hold inexistente | `PRODUCT_NOT_FOUND`, `HOLD_NOT_FOUND` |
| 409 | Conflita com o estado atual | `INSUFFICIENT_AVAILABLE_STOCK`, `HOLD_NOT_ACTIVE`, `INVALID_HOLD_OPERATION`, `STOCK_LIMIT_EXCEEDED` |
| 422 | Dados inválidos | `VALIDATION_ERROR`, `INVALID_SKU`, `INVALID_QUANTITY`, `INVALID_HOLD_DATA` |
| 503 | Banco indisponível ou lock demorou mais que `lock_timeout` | `SERVICE_UNAVAILABLE` |
| 500 | Erro inesperado (sem detalhes internos na resposta) | `INTERNAL_ERROR` |

### Configuração (variáveis de ambiente)
| Variável | Padrão | Descrição |
|---|---|---|
| `STOCK_DATABASE_URL` | `postgresql+psycopg://stock:stock@localhost:5432/stock` | Conexão com o banco |
| `STOCK_DB_LOCK_TIMEOUT_MS` | `5000` | Tempo máximo de espera por lock de produto |
| `STOCK_DB_POOL_SIZE` / `STOCK_DB_MAX_OVERFLOW` | `10` / `5` | Pool de conexões |
| `STOCK_LOG_LEVEL` | `INFO` | Nível de log (JSON) |
| `STOCK_TEST_DATABASE_URL` | – | Se definida, os testes usam este banco em vez de subir um container (usado no CI) |

---

## 7. O que eu faria diferente em produção

**Confiabilidade e consistência**
- **Idempotência** com `Idempotency-Key` gravada na mesma transação ([ADR-0010](docs/adr/0010-idempotencia.md)).
- **Expiração de reservas** (TTL por reserva + job que libera as vencidas, gerando movimento `EXPIRE`).
- **Outbox pattern:** gravar eventos (`StockReserved`, `StockReleased`…) na mesma transação e publicar em SQS/EventBridge, para outros sistemas reagirem sem dual-write.
- **Reconciliação periódica** ledger × saldo (o `replay()` já existe) com alerta em divergência.

**Segurança**
- AuthN/AuthZ com OAuth2/JWT e escopos por operação (ex.: só a área de qualidade bloqueia); usuário gravado em cada movimento.
- API Gateway com rate limiting e WAF; segredos no AWS Secrets Manager; TLS ponta a ponta.

**Infraestrutura (AWS)**
- Containers em **ECS Fargate** (ou EKS) atrás de um ALB, com auto scaling; imagem já preparada (sem root, configuração por env, health check).
- **RDS PostgreSQL / Aurora Multi-AZ** com backup automático e PITR; read replica para consultas e relatórios.
- IaC com **Terraform/CDK** e pipeline CI/CD com deploy blue/green ou canary e migrations controladas (expand/contract).

**Observabilidade**
- Métricas (taxa de 409 por SKU, tempo de espera por lock, p95/p99), tracing com **OpenTelemetry**, dashboards e alertas no CloudWatch/Grafana; SLOs definidos.

**Escala**
- Para SKUs muito disputados: `UPDATE` condicional atômico, **sharding do saldo** em N "baldes" por SKU, ou fila por SKU (SQS FIFO com `MessageGroupId = sku`).
- Testes de carga (k6/Locust) para dimensionar pool, `lock_timeout` e instâncias.
- Multi-depósito: o saldo passa a ser por `(sku, warehouse)`, mudança localizada no domínio graças à arquitetura.

---

## Testes

**101 testes · cobertura 98%** (mínimo de 90% exigido no CI). Estratégia completa no [ADR-0009](docs/adr/0009-estrategia-de-testes.md).

| Nível | Qtde | O que prova |
|---|---|---|
| Domínio | 48 | Cada regra e borda; estado intacto após qualquer operação rejeitada |
| Casos de uso | 20 | Orquestração: saldo, hold e ledger persistidos juntos; nada persiste em erro |
| Property-based | 1 (200 sequências × até 40 passos) | Invariantes e replay do ledger valem para **qualquer** sequência de operações |
| Integração | 27 | Contrato HTTP, Problem Details, CHECK constraints, migrations ↔ models, banco fora → 503, lock timeout → 503 |
| Concorrência | 5 | Sem overselling, sem liberação dupla, sem atualização perdida (até 60 transações simultâneas) |

> **Os testes de concorrência foram validados com o lock desligado:** sem `FOR UPDATE`, falham 5/5
> (ex.: 20 entradas simultâneas → total 2 em vez de 20). Com o lock, passam 5/5.

---

## Uso de IA

Desenvolvido com **Claude Code** como par de engenharia, com regras persistentes no [`CLAUDE.md`](CLAUDE.md).
Resumo: a IA leu o enunciado comigo, levantou alternativas e acelerou código estrutural e testes;
eu decidi o escopo e as estratégias, rejeitei duas versões do plano e validei tudo com testes e
guardrails automáticos.

- [`docs/ai/AI_USAGE.md`](docs/ai/AI_USAGE.md): forma de uso, **onde ajudou, o que rejeitei, erros encontrados** e como uma IA com harness pode auxiliar o processo de engenharia
- Commits feitos com IA levam o trailer `Co-Authored-By`

---

## Visão de engenharia

Os 5 aspectos que considero mais importantes, com justificativa em [`docs/ENGINEERING_VISION.md`](docs/ENGINEERING_VISION.md):

1. **Consistência transacional e controle de concorrência**
2. **Testes que provam regras** (bordas, property-based, concorrência real)
3. **Observabilidade e auditabilidade** (ledger, logs estruturados, correlation id)
4. **Resiliência a falhas e idempotência**
5. **Evolutividade** (domínio isolado, regra de arquitetura verificada, contratos versionados, ADRs)
