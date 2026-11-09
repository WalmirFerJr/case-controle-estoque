# ADR-0002: Clean Architecture com regra de dependência verificada no CI

## Contexto
O case avalia organização, design e **capacidade de evolução**, e avisa que na entrevista
virão novos requisitos. A regra de negócio (saldos e invariantes) é o ativo mais valioso
e precisa ser testável sem banco e sem HTTP.

## Opções consideradas
| Opção | Prós | Contras |
|---|---|---|
| Tudo no router (script FastAPI) | Mínimo de código | Regra misturada com HTTP/SQL; difícil testar e evoluir |
| MVC/camadas "service + model ORM" | Familiar | Entidade = modelo ORM: domínio acoplado ao banco |
| **Clean Architecture leve (ports & adapters)** | Domínio puro, testes rápidos, adaptadores trocáveis | Mais arquivos e mapeamento ORM ↔ entidade |

## Decisão
Quatro camadas com dependência apontando sempre para dentro:

- `domain`: entidades ricas (`Product`, `Hold`, `StockMovement`), value objects (`Sku`, `Quantity`), exceções. Python puro.
- `application`: um caso de uso por classe + ports (`Protocol`) de repositório, Unit of Work e relógio.
- `infrastructure`: SQLAlchemy, Alembic e configuração (implementa os ports).
- `presentation`: FastAPI (schemas, rotas, tradução de erros, correlation id).
- `main.py`: composition root, o único módulo que conhece tudo e faz a ligação.

A regra é **verificada automaticamente** pelo `import-linter` (4 contratos no `pyproject.toml`):
domínio/aplicação não importam frameworks; HTTP e persistência não se conhecem.

## Por que não algo mais "simples"?
O enunciado valoriza simplicidade. A estrutura foi mantida enxuta: sem container de DI,
sem CQRS, sem event bus, sem repositório genérico. O custo extra é basicamente o mapper
ORM ↔ entidade (`infrastructure/persistence/mappers.py`, cerca de 70 linhas), e em troca:
- 71 testes de domínio e de casos de uso rodam em menos de 1s, sem Docker;
- a regra é provada por property-based testing sem banco;
- um requisito novo (ex.: expiração de reserva) vira um caso de uso novo, sem tocar nos existentes.

## Consequências
- Entidades não são modelos ORM: precisa de mapeamento explícito (custo aceito).
- `HoldView`/`ProductStockView` (DTOs) isolam o contrato HTTP do domínio.
