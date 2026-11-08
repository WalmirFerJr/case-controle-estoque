# ADR-0007: Sem front-end (decisão deliberada)

## Contexto
A ideia inicial era incluir um front em React ou Angular. Relendo o enunciado:
- "A implementação deverá ser realizada em uma das seguintes linguagens: Java, C#, Python."
- "Recomendamos dedicar **até 3 horas**."
- O que será avaliado: modelagem, regras de negócio, qualidade de código, arquitetura,
  testes, erros, consistência, evolução, pragmatismo e uso de IA. Interface visual não está entre os critérios.
- "Uma solução simples, bem estruturada e com decisões justificadas poderá ser mais bem
  avaliada do que uma solução complexa sem necessidade."

## Opções consideradas
| Opção | Avaliação |
|---|---|
| Front completo (React/Angular) | Linguagem fora da lista; consumiria boa parte das 3h sem atender critério algum |
| Front mínimo opcional | Mesmo problema, em menor escala; ainda dilui o foco |
| **Sem front; Swagger UI (OpenAPI) como interface** | Zero custo extra; documenta e permite exercitar todo o contrato |

## Decisão
Não desenvolver front-end. O tempo foi reinvestido em concorrência, testes (property-based e
concorrência real) e documentação, que são os pontos avaliados.

## Consequências
- O avaliador usa `http://localhost:8000/docs` (Swagger) ou os exemplos `curl` do README.
- A API REST versionada (`/api/v1`) com OpenAPI **é** o contrato: um front (ou outro serviço)
  pode ser acoplado depois sem mudar nada no back-end. Se fosse necessário, eu geraria o
  client TypeScript a partir do OpenAPI e faria um front React consumindo-o.
