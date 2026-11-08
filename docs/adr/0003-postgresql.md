# ADR-0003: PostgreSQL como persistência

## Contexto
A regra central do case é **consistência**: "uma operação inválida não deve deixar o estoque
em estado inconsistente". A entrevista vai explorar concorrência, falhas e escala.

## Opções consideradas
| Opção | Prós | Contras |
|---|---|---|
| Memória (dict + `threading.Lock`) | Zero infra | Perde dados ao reiniciar; lock só vale para 1 processo (não escala horizontalmente) |
| SQLite | Arquivo único, sem Docker | Lock de banco inteiro; sem `SELECT … FOR UPDATE`; não representa produção |
| **PostgreSQL** | ACID, lock de linha, CHECK constraints, `ON CONFLICT`; padrão de mercado (RDS/Aurora) | Requer Docker para rodar e testar |
| DynamoDB | Escala, conditional writes | Transações multi-item mais limitadas; mais difícil rodar localmente |

## Decisão
PostgreSQL 16, com schema versionado por Alembic. Docker Compose para rodar local e
testcontainers nos testes (um banco descartável por execução).

## Consequências
- A consistência vale entre **várias instâncias** da API, já que o lock está no banco e não no processo.
- CHECK constraints dão uma segunda linha de defesa independente do código.
- Para rodar os testes de integração é preciso Docker; os testes unitários (domínio,
  casos de uso, property-based) rodam sem nada (`make test-unit`).
