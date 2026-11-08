# ADR-0009: Estratégia de testes em camadas

## Contexto
"A escolha da estratégia, quantidade e abrangência dos testes faz parte da avaliação."
Cada nível de teste deve provar algo que os outros **não** conseguem provar.

## Decisão

| Nível | Pasta | Prova | Infra | Tempo |
|---|---|---|---|---|
| Domínio | `tests/unit/domain` | Cada regra e borda (0, negativo, exato, +1, liberar 2x, estado intacto após erro) | nenhuma | ms |
| Casos de uso | `tests/unit/application` | Orquestração: o que é persistido, ledger gravado, nada persiste em erro | fakes em memória (`tests/fakes.py`) | ms |
| Property-based | `tests/property` | Invariantes valem para **qualquer** sequência de operações (hypothesis `RuleBasedStateMachine`, 200 sequências × até 40 passos, comparadas a um modelo de referência e ao replay do ledger) | nenhuma | ~2s |
| Integração | `tests/integration` | Contrato HTTP, Problem Details, persistência real, CHECK constraints, migrations em sincronia com os models, banco fora → 503 | PostgreSQL real (testcontainers) | ~5s |
| Concorrência | `tests/concurrency` | Sem overselling, sem liberação dupla, sem atualização perdida, sob até 60 transações simultâneas | PostgreSQL real | ~3s |

### Por que não mocks/SQLite para concorrência
Lock de linha, isolamento e CHECK são comportamentos do PostgreSQL. Um teste de
concorrência com SQLite ou mock passaria sem provar nada.

### Validação dos próprios testes
Os testes de concorrência foram executados **com o lock desligado** e falharam (5/5),
o que confirma que detectam o defeito (ver ADR-0005).

## Consequências
- `make test-unit` dá feedback em ~2s sem Docker; `make test` roda tudo (cerca de 15s).
- CI roda tudo com Postgres como service container e exige cobertura ≥ 90% (atual: 98%).
- Cobertura é consequência, não objetivo: o que importa é cada regra ter um teste que falharia se ela quebrasse.
