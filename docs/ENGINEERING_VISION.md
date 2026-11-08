# Visão de engenharia: 5 aspectos mais importantes

Para **qualidade, eficiência, confiabilidade e evolução** desta solução, em ordem de importância.

## 1. Consistência transacional e controle de concorrência
**Por quê:** estoque é um recurso disputado. Duas requisições simultâneas que leem o mesmo
saldo podem vender a mesma unidade duas vezes, e esse erro custa dinheiro e confiança.
**Como está na solução:** uma transação por operação, `SELECT … FOR UPDATE` no produto, ordem de
lock fixa (produto → hold), CHECK constraints no banco e `lock_timeout` para falhar rápido.
Provado por testes com até 60 transações simultâneas, que **falham** quando o lock é removido (ADR-0005).

## 2. Testes que provam regras, e não só linhas
**Por quê:** a regra de estoque tem muitas combinações (reservas + bloqueios + saídas + liberações)
e bugs aparecem nas bordas e na concorrência, que testes "de exemplo" raramente cobrem.
**Como está na solução:** pirâmide com unit (bordas), property-based (qualquer sequência
preserva as invariantes), integração com PostgreSQL real e concorrência. Cobertura de 98% como
consequência, com mínimo de 90% exigido no CI (ADR-0009).

## 3. Observabilidade e auditabilidade
**Por quê:** em produção, "o saldo está errado" precisa ser respondido com fatos: o que aconteceu,
quando e em qual requisição. Em contexto bancário, rastreabilidade é requisito.
**Como está na solução:** ledger append-only de todo movimento (com reconstrução de saldo por
replay), logs JSON estruturados, `correlation_id` ponta a ponta (header → log → resposta de erro)
e health check que verifica o banco.
**Próximo passo:** métricas (taxa de 409 por SKU, latência de lock, p99) e tracing com
OpenTelemetry; job de reconciliação ledger × saldo com alerta.

## 4. Resiliência a falhas e idempotência
**Por quê:** redes falham e clientes fazem retry. Sem idempotência, um timeout seguido de retry
cria uma reserva duplicada; sem tratamento de falha, um banco lento derruba a API inteira.
**Como está na solução:** atomicidade (falha no meio = rollback total), banco indisponível ou lock
demorado → 503 previsível com Problem Details, pool com `pre_ping`, erros com `code` estável para
o cliente decidir se repete.
**Próximo passo:** `Idempotency-Key` com desenho pronto no ADR-0010.

## 5. Evolutividade: domínio isolado e contratos explícitos
**Por quê:** os requisitos vão mudar (expiração de reserva, multi-depósito, eventos para outros
sistemas). O custo de mudar precisa continuar baixo.
**Como está na solução:** Clean Architecture com regra de dependência **verificada no CI**
(import-linter), um caso de uso por classe (requisito novo = classe nova), API versionada
(`/api/v1`) com OpenAPI, migrations versionadas (com teste que garante models ↔ migrations em
sincronia) e decisões registradas em ADRs para quem chegar depois.
