# ADR-0010: Idempotência de requisições (adiada, com desenho pronto)

## Contexto
Em sistemas financeiros, retries são normais (timeout de rede, reprocessamento de fila).
Hoje, se o cliente reenviar `POST /reservations` após um timeout, **cria uma segunda reserva**.
Entrada e saída também não são idempotentes.

## Por que não foi implementada agora
O enunciado não pede, e uma implementação correta tem detalhes que não cabem com qualidade
nas 3h recomendadas: a chave precisa ser gravada **na mesma transação** da operação,
requisições concorrentes com a mesma chave precisam ser serializadas, e é preciso detectar
reuso da chave com payload diferente. Preferi entregar o núcleo sólido e documentar o desenho
a entregar uma idempotência meia-boca.

## Desenho proposto
- Header `Idempotency-Key` (UUID) em todos os `POST` que alteram estado.
- Tabela `idempotency_keys(key PK, request_hash, status_code, response_body, created_at)`.
- No caso de uso, dentro da mesma transação e **depois** do lock do produto:
  1. `SELECT … FROM idempotency_keys WHERE key = :k`;
  2. se existir e `request_hash` for igual → devolve a resposta gravada (sem reexecutar);
  3. se existir com hash diferente → `422 IDEMPOTENCY_KEY_REUSED`;
  4. senão executa e grava a chave com a resposta antes do `COMMIT`.
- Expiração das chaves após 24h (job de limpeza).
- Alternativa mais leve para reservas: unicidade de `(sku, reference)` entre holds ativos,
  se o negócio definir que um pedido tem no máximo uma reserva por produto.

## Status
Adiada. É o primeiro item da lista de evolução para produção.
