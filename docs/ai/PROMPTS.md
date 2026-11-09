# Registro de prompts e interações com IA

**Ferramenta:** Claude Code (agente com acesso a arquivos e terminal), com o
[`CLAUDE.md`](../../CLAUDE.md) do repositório como contexto persistente em todas as sessões.

**Como ler este registro:**
- As entradas estão em ordem cronológica e incluem só as interações que mudaram decisões ou código.
- Os prompts aparecem em versão consolidada e editada para clareza. A intenção, o conteúdo e as
  decisões são fiéis às interações reais.
- As respostas da IA estão resumidas.

**Princípio de trabalho:** eu conduzo e a IA executa e contesta. Eu defino o problema, os critérios
de pronto e as restrições. A IA levanta alternativas, aponta lacunas e produz código com evidência
de verificação. Eu valido cada saída antes de seguir.

Legenda da decisão: ✅ aceitei · ✏️ aceitei com ajustes · ❌ não adotei

---

## Fase 1: Planejamento (*plan mode*: a IA analisa e propõe, sem permissão para alterar arquivos)

### P1. Revisão crítica dos requisitos e da estratégia
**Prompt:**
> Levantei os requisitos funcionais do case (entrada, saída, reserva, bloqueio, liberação e
> consulta), as restrições e os critérios de avaliação. Considerei Python + FastAPI + PostgreSQL
> e avaliei um front-end e um deploy em AWS como possíveis diferenciais.
> Faça uma revisão crítica cruzando essa leitura com o enunciado:
> 1. Há restrição, critério de avaliação ou ambiguidade que eu não tenha considerado?
> 2. Front-end e cloud valem o custo frente ao que será avaliado?
> 3. Onde está a maior oportunidade de diferenciação técnica?
>
> Antes de propor o plano, liste as perguntas cuja resposta muda a estratégia.

**Resposta da IA (resumo):**
- Confirmou dois pontos que pesam contra front e deploy: a restrição de linguagens
  (Java/C#/Python) e a orientação de que uma solução simples e bem justificada pode ser mais bem
  avaliada.
- Concordou com Python + FastAPI + PostgreSQL.
- Apontou como maior oportunidade a consistência sob concorrência (`SELECT … FOR UPDATE`),
  validada com testes de concorrência e property-based.
- Antes de seguir, perguntou como tratar front e cloud.

**Decisão:** ✅ Front-end e deploy ficaram fora do escopo como **decisões deliberadas e
documentadas** (ADR-0007 e ADR-0008), com a arquitetura AWS descrita no README. O tempo foi para
o que o case avalia.

### P2. Documentação e arquitetura como requisitos do plano
**Prompt:**
> Revise o plano tratando documentação e arquitetura como requisitos, não como etapa final:
> - Toda solução, decisão e trade-off registrados em ADR, inclusive o que decidimos **não** fazer
>   (front-end e deploy), com a justificativa ligada às restrições do case.
> - Clean Architecture com regra de dependência explícita e Clean Code.
>
> Proponha como **verificar automaticamente** essas regras, em vez de apenas declará-las.

**Resposta da IA (resumo):**
- Estruturou 10 ADRs, incluindo as decisões deliberadas de escopo.
- Organizou o código em camadas, com ports (`typing.Protocol`) e um caso de uso por classe.
- Propôs o `import-linter` no CI para quebrar o build se a regra de dependência for violada.

**Decisão:** ✏️ Aceito com ajustes: documentação passou a ser critério de pronto de cada
etapa, e não uma fase no fim.

### P3. Cobertura dos critérios de avaliação e transparência no uso de IA
**Prompt:**
> Releia o enunciado e garanta que **cada** critério de avaliação e cada entregável tenha uma
> resposta clara no escopo, com a evidência correspondente no repositório. Transforme as
> ambiguidades do enunciado em premissas explícitas. Inclua também como a IA será usada em
> cada fase e qual o controle humano em cada uma.

**Resposta da IA (resumo):**
1. Criou uma **matriz de rastreabilidade**: critério avaliado → como atendemos → evidência no
   repositório.
2. Transformou as ambiguidades em premissas documentadas, por exemplo: "a entrada cria o
   produto?", "liberar duas vezes?", "bloquear o que já está reservado?".
3. Descreveu o fluxo de trabalho com IA por fase, com o controle humano de cada uma.
4. Priorizou o escopo com MoSCoW.

**Decisão:** ✅ A matriz virou o checklist final de entrega.

---

## Fase 2: Implementação (a IA executa por etapas; eu reviso e aprovo cada uma)

### P4. Domínio com TDD
**Prompt:**
> Implemente o domínio (`Product`, `Hold`, `StockMovement`, value objects e exceções) com TDD.
> Cada regra de negócio precisa de teste, incluindo as bordas e a garantia de que o estado não
> muda quando uma operação é rejeitada. O domínio não pode depender de nenhum framework.

**Resultado:** 48 testes de domínio. Um caso de borda tratado: `Quantity(True)`. Em Python, `bool`
é subclasse de `int`, e sem essa validação `{"quantity": true}` viraria 1 unidade.
**Decisão:** ✅ Revisado linha a linha.

### P5. Property-based testing
**Prompt:**
> Crie uma máquina de estados com hypothesis que aplique sequências aleatórias de operações,
> válidas e inválidas, e compare `Product` com um modelo de referência simples e com o replay
> do ledger após cada passo.

**Resultado:** 200 sequências aleatórias de até 40 operações cada, com as invariantes verificadas
em todos os passos.
**Decisão:** ✅

### P6. Persistência e concorrência
**Prompt:**
> Implemente os repositórios SQLAlchemy e a Unit of Work com uma transação por operação:
> - `SELECT … FOR UPDATE` no produto e ordem de lock fixa (produto → hold) para evitar deadlock;
> - CHECK constraints como última linha de defesa;
> - criação segura da primeira entrada de um SKU sob concorrência.
>
> Documente no código o porquê da ordem de lock.

**Resultado:** `INSERT … ON CONFLICT DO NOTHING` na primeira entrada, `lock_timeout` configurável
e CHECKs no schema.
**Decisão:** ✅

### P7. Validação dos testes de concorrência
**Prompt:**
> Um teste de concorrência que passa não prova nada sozinho: pode passar por sorte de
> escalonamento. Desligue o lock (troque `get_for_update` por `get`) e rode os testes. Eles
> precisam falhar.

**Resultado:**
- Sem o lock, **5 de 5 testes falharam**. Exemplo: 20 entradas simultâneas resultaram em
  total 2 (atualização perdida).
- Com o lock, 5 de 5 passaram.

**Decisão:** ✅ Virou evidência no ADR-0005.

### P8. Revisão adversarial
**Prompt:**
> Revise o código como um revisor adversarial: procure cenários de falha não testados em
> concorrência, falhas de infraestrutura e bordas. Para cada achado, proponha teste ou
> correção e o custo-benefício.

**Resultado:** dois achados.
1. **`lock_timeout` estourado** deveria virar 503, mas não tinha teste. ✅ Adicionei um teste em
   que outra transação segura o lock: a API responde 503 em cerca de 200 ms sem alterar o estoque.
2. **`GET /products/{sku}`** lê saldo e holds em dois `SELECT`s (READ COMMITTED). Sob escrita
   concorrente, as leituras podem refletir instantes diferentes. ❌ Não corrigi, porque afeta só
   a consulta e nunca a escrita. ✏️ Ficou documentado como limitação conhecida no README.

### P9. Documentação a partir do código real
**Prompt:**
> Escreva o README, os ADRs e o `ENGINEERING_VISION.md` a partir do plano aprovado e do código
> real. Todo número citado (quantidade de testes, cobertura) deve vir da saída real dos
> comandos, não de estimativa.

**Decisão:** ✏️ Revisei o texto e conferi cada número com a saída de `make check` antes de
publicar.

---

## Fase 3: Versionamento e publicação

### P10. Histórico versionado por branch
**Prompt:**
> Organize o histórico do repositório com uma branch por camada e commits convencionais,
> integradas na `main` com merge `--no-ff`, para que a evolução do projeto possa ser lida
> commit a commit. Cada commit deve passar nos testes. Inclua no `AI_USAGE.md` como uma IA
> com harness pode apoiar o processo de engenharia de software.

**Resposta da IA (resumo):**
- Criou as branches `feature/domain`, `feature/application`, `feature/infrastructure`,
  `feature/api`, `test/integration-concurrency`, `ci/docker-pipeline` e `docs/documentation`.
- Integrou todas na `main` com a tag `v1.0.0`.
- Verificou que os testes passam a partir do commit do domínio.
- Ampliou o `AI_USAGE.md` com a seção sobre harness.
- A autenticação para o push foi feita por mim: a IA não tem acesso a credenciais.

**Decisão:** ✅ Este registro foi publicado depois, em um commit próprio, após a minha revisão.

---

## Fase 4: Evolução

### P11. Usabilidade da API: listagem de produtos e documentação do Swagger
**Prompt:**
> Usando a API pelo Swagger como um consumidor faria, senti falta de uma visão geral do estoque.
> Crie um `GET` que liste a situação de todos os produtos cadastrados, com os quatro saldos.
> Depois revise a documentação da API procurando o que dificulta o uso: parâmetros sem
> descrição, falta de exemplos, ponto de entrada pouco claro.
> Mantenha README, ADRs e testes coerentes com cada mudança.

**Resposta da IA (resumo):**
- Criou `GET /api/v1/products` com um caso de uso novo (`ListProducts`) e um método novo no port
  do repositório. É um único SELECT, paginado (`limit` ≤ 500) e em ordem de SKU.
- No Swagger, encontrou parâmetros de rota e de consulta sem descrição nem exemplo, campos de
  resposta sem significado e a raiz `/` respondendo 404. Para resolver:
  - parâmetros documentados uma única vez (`_params.py`);
  - enums visíveis nos campos `type` e `status`;
  - roteiro de "Primeiros passos" na página do Swagger;
  - redirecionamento da raiz `/` para `/docs`.
- Acrescentou 8 testes: casos de uso, integração e validação da paginação.

**Decisão:** ✅ Validei rodando a API com Docker e percorrendo o fluxo pelo Swagger e por `curl`.
✏️ A listagem não traz os holds de cada produto, para evitar consultas N+1. O detalhe continua em
`GET /products/{sku}`.
