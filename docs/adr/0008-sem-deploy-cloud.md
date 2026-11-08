# ADR-0008: Sem deploy em cloud (decisão deliberada)

## Contexto
Tenho experiência com AWS (Lambda, SQS, S3, Secrets Manager, EC2) e considerei publicar a
solução. O enunciado pede **execução local** com instruções claras e diz que "o objetivo não é
construir um sistema completo de produção".

## Opções consideradas
| Opção | Avaliação |
|---|---|
| Deploy real (ECS/Lambda + RDS, com IaC) | Custo financeiro contínuo, horas de setup, e o avaliador provavelmente não acessaria; risco de credenciais/infra expostas |
| **Execução local reproduzível + arquitetura-alvo documentada** | `docker compose up` sobe tudo; o conhecimento de cloud aparece no desenho de produção |

## Decisão
Sem deploy. Entrega 100% reproduzível localmente (Docker Compose) e CI no GitHub Actions.
A arquitetura de produção na AWS está descrita no README ("O que eu faria diferente em produção").

## Consequências
- Qualquer pessoa roda o projeto com Docker, sem conta em cloud.
- O código já está preparado para isso: configuração 100% por variáveis de ambiente
  (12-factor), imagem Docker sem root, health check com verificação do banco e migrations
  aplicadas no start.
