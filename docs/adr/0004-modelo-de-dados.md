# ADR-0004: Modelo de dados

## Contexto
Para cada produto o enunciado pede: identificação, total, disponível, reservado e bloqueado,
com **múltiplas reservas e bloqueios simultâneos, inclusive de solicitações diferentes**, e
cada reserva/bloqueio com identificação para consulta e liberação.

## Decisões

### 1. `available` é derivado, nunca armazenado
`available = total - reserved - blocked`. Armazenar os quatro números permitiria que divergissem;
com três números e uma fórmula, a divergência é impossível por construção.

### 2. Saldos agregados no produto + holds individuais
| Opção | Leitura do saldo | Consistência |
|---|---|---|
| Só holds (somar na consulta) | O(n holds) por leitura | Fonte única de verdade |
| **Contadores no produto + holds** | O(1) | Contadores e holds atualizados na mesma transação; validado por teste |

Os contadores permitem validar a regra com **uma linha travada** (o produto). Os testes de
concorrência verificam que `reserved == soma das reservas ACTIVE` após disputa.

### 3. Reserva e bloqueio são a mesma entidade (`Hold`, com `type`)
Têm o mesmo ciclo de vida (criar → consultar → liberar). Duas tabelas quase idênticas
duplicariam código e endpoints. Diferenças: bloqueio aceita `reason` opcional e não pode ser
"consumido" (ver abaixo).

Estados: `ACTIVE → RELEASED | CONSUMED` (finais e imutáveis). Liberar duas vezes → `409 HOLD_NOT_ACTIVE`
(explícito, para não esconder bugs de cliente; com idempotência por chave, ver ADR-0010, o
retry legítimo é tratado sem ambiguidade).

### 4. Ledger append-only (`stock_movements`)
Toda operação grava um movimento (`ENTRY`, `EXIT`, `RESERVE`, `BLOCK`, `RELEASE_*`,
`CONSUME_RESERVATION`). Isso dá auditoria (requisito implícito em contexto bancário) e
reconciliação: `domain/services/ledger.replay()` reconstrói os saldos a partir do histórico,
e os testes provam que o reconstruído é igual ao armazenado.

### 5. Entrada cria o produto (upsert)
O enunciado não define cadastro de produtos. Premissa: a primeira entrada de um SKU cria o
registro. Alternativa considerada: endpoint `POST /products` obrigatório antes da entrada.
Foi descartada para não inventar um fluxo que o enunciado não pede. A criação usa
`INSERT … ON CONFLICT DO NOTHING` para ser segura sob concorrência.

### 6. Extra: consumir reserva (`POST /holds/{id}/consume`)
Fora do enunciado, mas fecha o ciclo de um pedido. Sem ele, expedir um pedido reservado exigiria
"liberar e depois dar saída", abrindo uma janela em que outro pedido pode tomar as unidades.
Só reservas são consumíveis.

## Premissas adicionais
- Quantidades inteiras, `1 ≤ q ≤ 1.000.000` por operação; total por produto ≤ 1.000.000.000.
- SKU: 1–64 caracteres `[A-Za-z0-9._-]`, case-sensitive.
- `reference` (solicitação/pedido) obrigatória em reservas e bloqueios, até 128 caracteres.
- Bloqueio só sobre o **disponível** (regra do enunciado), sem bloquear unidades já reservadas.
- Liberação é sempre **total** (liberação parcial listada como evolução).
