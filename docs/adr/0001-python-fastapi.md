# ADR-0001: Python 3.12 + FastAPI

## Contexto
O case permite Java, C# ou Python e deixa livres framework e forma de exposição. Um dos
critérios é "capacidade de explicar e defender as decisões": a stack precisa ser uma que
eu domine a ponto de defender cada linha.

## Opções consideradas
| Opção | Prós | Contras |
|---|---|---|
| **Python + FastAPI** | Minha stack principal (Itaú e BTG); OpenAPI/Swagger automático; Pydantic valida a borda; tipagem estática com mypy | Menos comum que Java em sistemas core bancários |
| Java + Spring Boot | Padrão em bancos; ecossistema maduro | Mais cerimônia para 3h; domino menos |
| Python + CLI | Mais simples | Não exercita contrato HTTP, erros e concorrência real entre requisições |

## Decisão
Python 3.12 com FastAPI, exposto como API REST.

## Consequências
- Swagger UI em `/docs` serve de interface para o avaliador exercitar todas as operações (ver ADR-0007).
- Endpoints síncronos (`def`) rodam no threadpool do Starlette: simples, compatível com
  SQLAlchemy síncrono e com o modelo de lock por transação. Async não traria ganho real
  aqui, porque o gargalo é o lock no banco, não I/O de rede.
- Python não tem checagem de tipos em runtime: compensado com `mypy --strict` no CI.
