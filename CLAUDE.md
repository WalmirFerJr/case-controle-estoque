# CLAUDE.md: contexto do projeto para assistentes de IA

> Este arquivo é lido automaticamente pelo Claude Code em cada sessão. Ele existe para que
> o código gerado com IA siga **as mesmas convenções** do código escrito à mão, sem
> precisar repetir as regras em todo prompt. É versionado de propósito, como evidência
> de como a IA foi guiada (ver `docs/ai/AI_USAGE.md`).

## O que é
API de controle de estoque (case técnico). Saldos por produto: total, disponível,
reservado e bloqueado; reservas/bloqueios com identificação, consulta e liberação.

## Arquitetura (Clean Architecture): regra de dependência obrigatória
```
presentation (FastAPI)  ─┐
                         ├─> application (casos de uso + ports) ─> domain (regras puras)
infrastructure (SQLAlchemy)┘
main.py = composition root (único que conhece todas as camadas)
```
- `domain/` e `application/` **nunca** importam fastapi, starlette, pydantic, sqlalchemy,
  psycopg ou alembic. O `lint-imports` quebra o build se isso acontecer.
- `presentation` e `infrastructure` não se importam entre si.
- Regra de negócio mora na **entidade** (`Product.reserve`, `Hold.release`), não no caso
  de uso nem no router. Caso de uso só orquestra: lock, regra, persistência e ledger.
- Um caso de uso por arquivo/classe, com método `execute`.
- Todo caso de uso que altera saldo: `with uow:` → `lock_product` (FOR UPDATE) → método da
  entidade → `save` → `movements.add` → `commit`. Sem commit = rollback.
- Locks sempre na ordem **produto → hold** (evita deadlock).

## Convenções
- Código e identificadores em inglês; docstrings, comentários, mensagens de erro e docs em
  português. Docstring explica o **porquê** da regra, não o óbvio.
- Exceção de domínio nova = classe em `domain/exceptions.py` com `code` estável, e mapeamento
  de status em `presentation/errors.py` (`STATUS_BY_DOMAIN_ERROR`).
- Erros HTTP sempre em Problem Details (`application/problem+json`).
- Mudança de schema = nova migration Alembic (o teste `command.check` falha se o model divergir).
- Type hints em tudo (`mypy --strict`). Sem números mágicos: constantes nomeadas no domínio.

## Testes (o que cada mudança precisa)
- Regra nova → teste em `tests/unit/domain` (incluindo bordas e "estado não muda após erro").
- Orquestração nova → `tests/unit/application` com `tests/fakes.py` (UoW em memória).
- Endpoint novo → `tests/integration/test_api.py` (status, payload e código de erro).
- Algo que mexe em lock/transação → `tests/concurrency`.
- Nunca usar SQLite ou mocks para provar concorrência: só PostgreSQL real.

## Comandos
```
make install   make test   make test-unit   make check   make up   make run
```

## Definição de pronto
`make check` verde (ruff, format, mypy strict, import-linter, testes com cobertura ≥ 90%)
e documentação atualizada (README/ADR) quando houver decisão nova.

## Política de uso de IA
Nenhum código gerado entra sem: (a) teste cobrindo, (b) entendimento linha a linha por
quem faz o commit, (c) `make check` verde. Interações relevantes vão para `docs/ai/PROMPTS.md`.
