# ADR-0005: Controle de concorrência com lock pessimista por produto

## Contexto
Duas requisições simultâneas podem ler "disponível = 1" e ambas reservarem: **overselling**.
É o cenário mais provável de ser discutido na entrevista.

## Opções consideradas
| Opção | Como funciona | Prós | Contras |
|---|---|---|---|
| **Lock pessimista** `SELECT … FOR UPDATE` | Trava a linha do produto até o commit | Simples, correto, regra continua no domínio | Serializa operações **do mesmo SKU** (SKUs diferentes seguem paralelos) |
| Lock otimista (`version`) | `UPDATE … WHERE version = :v`; conflito → retry | Sem espera em baixa contenção | Exige retry; sob alta contenção vira tempestade de retries |
| `UPDATE` condicional atômico | `UPDATE … SET reserved = reserved + :q WHERE total - reserved - blocked >= :q` | Uma ida ao banco, máximo throughput | Regra de negócio migra para o SQL; difícil compor com hold + ledger |
| Lock em memória | `threading.Lock` por SKU | Trivial | Não funciona com mais de uma instância da API |

## Decisão
Lock pessimista na linha do produto, em uma transação por operação (Unit of Work):

```
BEGIN
  SELECT … FROM products WHERE sku = :sku FOR UPDATE   -- fila por SKU
  regra no domínio (Product.reserve / exit / block / release)
  UPDATE products …; INSERT holds …; INSERT stock_movements …
COMMIT   (qualquer exceção → ROLLBACK)
```

Complementos:
- **Ordem de lock fixa** (produto → hold) em liberar/consumir: evita deadlock.
- **Hold relido após o lock** (`populate_existing`): duas liberações simultâneas do mesmo
  hold não contam em dobro.
- **`lock_timeout` de 5s** por conexão: se a fila travar, a requisição falha rápido com 503
  em vez de prender conexões do pool indefinidamente.
- **CHECK constraints** como última barreira.

## Evidência
`tests/concurrency/` dispara até 60 operações simultâneas (com `Barrier`) contra PostgreSQL real.
**Experimento de validação:** com o `FOR UPDATE` desligado, os 5 testes **falham** (ex.: 20
entradas simultâneas resultaram em total 2 em vez de 20, por atualização perdida). Com o
lock, passam. Isso prova que os testes detectam o problema e não passam por acaso.

## Consequências e quando revisitar
- Throughput por SKU limitado pela duração da transação (milissegundos). Para SKUs "quentes"
  (ex.: Black Friday) as evoluções seriam: `UPDATE` condicional, sharding de saldo
  (dividir o estoque em N "baldes") ou fila por SKU. Ver README, seção de produção.
