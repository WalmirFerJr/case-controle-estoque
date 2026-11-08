# ADR-0006: Erros de domínio tipados → Problem Details HTTP

## Contexto
O case avalia "tratamento de erros e situações excepcionais". Clientes da API precisam
distinguir "não existe", "não pode agora" e "dados inválidos", e o suporte precisa rastrear falhas.

## Decisão
- Cada regra violada tem uma exceção própria em `domain/exceptions.py` com `code` estável
  (`INSUFFICIENT_AVAILABLE_STOCK`, `HOLD_NOT_ACTIVE`, …).
- A camada HTTP só traduz (`presentation/errors.py`), no formato **Problem Details**
  (RFC 9457, `application/problem+json`):

| Situação | Status | Exemplos de `code` |
|---|---|---|
| Recurso inexistente | 404 | `PRODUCT_NOT_FOUND`, `HOLD_NOT_FOUND` |
| Conflita com o estado atual | 409 | `INSUFFICIENT_AVAILABLE_STOCK`, `HOLD_NOT_ACTIVE`, `INVALID_HOLD_OPERATION`, `STOCK_LIMIT_EXCEEDED` |
| Entrada inválida | 422 | `VALIDATION_ERROR`, `INVALID_SKU`, `INVALID_QUANTITY`, `INVALID_HOLD_DATA` |
| Banco fora / lock timeout | 503 | `SERVICE_UNAVAILABLE` |
| Bug | 500 | `INTERNAL_ERROR` (sem stack trace na resposta) |

- Toda resposta carrega `correlation_id` (também no header `X-Correlation-ID`, aceito na
  entrada) e os logs JSON usam o mesmo id.
- `InsufficientAvailableStockError` devolve `requested` e `available` para o cliente decidir.
- `StockInvariantViolationError` **não** é erro de domínio do cliente: é bug, vira 500 e log.

## Validação em duas camadas
Pydantic valida **formato** na borda (inteiro estrito, campos extras proibidos) e o domínio
valida **regra** (value objects). Duplicação mínima e intencional: o domínio não pode
confiar que todo chamador futuro (fila, CLI, outro serviço) passou pela API.
