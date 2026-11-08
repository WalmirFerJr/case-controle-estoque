# Uso de Inteligência Artificial

> Contexto persistente dado à IA: [`CLAUDE.md`](../../CLAUDE.md)

## Ferramenta e forma de uso
Usei o **Claude Code**, um agente de código que roda no terminal/desktop, lê e edita arquivos e
executa comandos (testes, lint, Docker) dentro de um *harness* com permissões controladas.
A IA trabalhou como **par de engenharia**, não como gerador de código às cegas: ela propõe,
executa e mostra a evidência; eu decido, reviso e corrijo a direção.

## Fluxo de trabalho com IA neste projeto

| Fase | Papel da IA | Meu controle |
|---|---|---|
| 1. Entender o problema | Ler o PDF do case; listar restrições, critérios de avaliação e ambiguidades | Rejeitei duas versões do plano até cada critério do PDF ter uma evidência correspondente |
| 2. Contexto persistente | `CLAUDE.md` com regras de arquitetura, convenções e definição de pronto | Escrito e versionado: toda sessão de IA segue as mesmas regras |
| 3. Modelagem | Comparar alternativas (lock pessimista × otimista × UPDATE condicional; uma × duas tabelas de holds) | Escolha registrada em ADR com trade-offs |
| 4. Implementação | Código camada por camada, com testes junto | Revisão de cada arquivo; `make check` verde a cada etapa |
| 5. Verificação | Rodar testes, lint, tipos, import-linter e o experimento sem lock | A IA não "declara" que funciona: mostra a saída dos comandos |
| 6. Revisão crítica | Procurar cenários de falha não cobertos | Aceitei um achado (lock timeout) e documentei o outro como limitação |
| 7. Documentação | Rascunho de README/ADRs | Números conferidos com a saída real dos comandos |

**Guardrails automáticos**, que valem igualmente para código humano e de IA:
`ruff` · `mypy --strict` · `import-linter` (arquitetura) · 101 testes · cobertura ≥ 90% no CI.

---

## Onde a IA mais ajudou

1. **Leitura crítica do enunciado.** A IA destacou que o PDF restringe as linguagens a
   Java/C#/Python e valoriza simplicidade. Isso derrubou minha ideia inicial de front em
   React/Angular + deploy AWS e redirecionou o tempo para o que é avaliado (ADR-0007, ADR-0008).
   A matriz "critério → evidência" virou o checklist da entrega.
2. **Volume de código estrutural com qualidade constante.** Mapeamento ORM, migration Alembic,
   schemas Pydantic, handlers de erro, Dockerfile e CI: código necessário e de baixo risco
   intelectual, que a IA produz rápido seguindo as convenções do `CLAUDE.md`.
3. **Testes que eu provavelmente não escreveria em 3h.** A máquina de estados com hypothesis e
   os testes de concorrência com `Barrier` (todas as threads soltas no mesmo instante).
4. **Pensar como atacante do próprio código.** Validar os testes de concorrência *desligando o
   lock* transformou "os testes passam" em "os testes detectam o defeito".

## Sugestões da IA que modifiquei ou não usei

| Sugestão | O que fiz | Por quê |
|---|---|---|
| 1ª versão do plano: documentação como etapa final, decisões de escopo implícitas | ✏️ Rejeitei e pedi documentação como princípio, com ADR inclusive para o que **não** foi feito | O case avalia "como você pensa"; decisão não registrada é decisão invisível |
| 2ª versão: plano bom, mas sem amarrar cada critério de avaliação a uma evidência | ✏️ Rejeitei e pedi matriz de rastreabilidade e tabela de ambiguidades → premissas | Garantir que nenhum critério do PDF ficasse sem resposta |
| Implementar `Idempotency-Key` | ❌ Não implementei; ADR-0010 com o desenho completo | Fazer certo exige gravação na mesma transação e tratamento de chaves concorrentes. Preferi núcleo sólido + desenho documentado a uma versão incompleta |
| Corrigir a leitura não-atômica de `GET /products/{sku}` (saldo e holds em 2 SELECTs) | ❌ Não corrigi; documentei como limitação | Só afeta consulta, nunca escrita; a correção muda a Unit of Work por pouco ganho no escopo do case |
| Usar `uv` como gerenciador de pacotes | ✏️ Troquei por `venv` + `pip` | `uv` não estava instalado no ambiente; `pip` é universal e o avaliador não precisa instalar nada extra |

## Erros e limitações encontrados nas respostas da IA

1. **Setup com falha silenciosa.** O primeiro `pip install -e .` falhou porque o `pyproject.toml`
   referenciava um `README.md` que ainda não existia. Os testes passaram mesmo assim (via
   `pythonpath`), mascarando o problema. Detectei lendo a saída do comando em vez de confiar no "ok".
2. **APIs desatualizadas.** A IA usou `testcontainers.postgres` (depreciado, o atual é
   `testcontainers.community.postgres`) e um `alembic.ini` sem `path_separator`. Os warnings
   nos testes denunciaram, e corrigi.
3. **Tentativa de instalar pacote desconhecido para silenciar um warning.** Para remover um
   aviso de depreciação, a IA tentou instalar um pacote (`httpx2`) que eu não conhecia. O
   controle de permissões do harness **bloqueou** a instalação, por risco de cadeia de
   suprimentos. Adotei a alternativa de filtrar o aviso no `pytest`, sem dependência nova.
   Lição: dependência nova é decisão humana.
4. **Código que passa no teste mas viola boas práticas.** Uma versão do teste de concorrência
   usava `lambda x=rng.choice(...)` (argumento default avaliado na definição, um truque frágil).
   O `ruff` (regra B008) apontou e a função foi reescrita de forma explícita.
5. **"Teste verde" não é prova.** Um teste de concorrência pode passar por sorte de escalonamento.
   Só confiei nele depois do experimento sem lock, em que os testes falharam 5/5.

---

## Como uma IA com harness pode auxiliar o processo de engenharia de software

Um modelo de linguagem sozinho só gera texto. O **harness** (o ambiente que dá ao modelo
ferramentas, contexto e limites) é o que o transforma em um participante útil e controlável do
processo de engenharia. Os mecanismos abaixo foram usados neste projeto e valem para qualquer
time.

| Mecanismo do harness | Para que serve | Como apareceu aqui |
|---|---|---|
| **Modo de planejamento** (*plan mode*) | A IA investiga e propõe um plano sem poder alterar nada; o humano aprova antes da execução | O plano foi rejeitado duas vezes e só então aprovado; nenhum código foi escrito antes disso |
| **Contexto persistente** (`CLAUDE.md`) | Regras de arquitetura, convenções e definição de pronto carregadas automaticamente em toda sessão | Evita repetir regras em cada pedido e mantém o código gerado consistente; versionado no repo |
| **Execução de ferramentas** (testes, lint, Docker, git) | A IA valida o próprio trabalho rodando os mesmos comandos que um engenheiro rodaria | Cada etapa terminou com `make check` verde, e a saída real foi exibida |
| **Permissões e bloqueios** | Ações arriscadas (instalar pacote, push, apagar arquivos) exigem aprovação ou são barradas | Instalação de pacote desconhecido bloqueada; push só com autorização explícita |
| **Guardrails determinísticos** | Lint, tipagem estrita, contratos de arquitetura e cobertura mínima no CI | A IA não "convence" o CI: código fora das regras não passa, venha de quem vier |
| **Revisão adversarial** | Pedir à IA que procure falhas no próprio código (concorrência, bordas, falhas de infra) | Gerou o teste de `lock_timeout` → 503 e a limitação documentada da consulta |
| **Experimentos de validação** | Quebrar o sistema de propósito para provar que os testes detectam o defeito | Lock desligado → 5/5 testes de concorrência falharam |
| **Transparência no histórico** | Trailer `Co-Authored-By` nos commits feitos com IA | Quem lê o histórico sabe o que teve participação de IA |

### Onde a IA agrega em cada etapa do ciclo
- **Requisitos:** extrair restrições e ambiguidades de documentos e transformá-las em premissas explícitas.
- **Design:** levantar alternativas com prós e contras rapidamente, para o humano decidir com mais opções na mesa.
- **Implementação:** código estrutural e repetitivo seguindo convenções; o humano foca nas regras críticas.
- **Testes:** sugerir bordas, property-based e cenários concorrentes; gerar o esqueleto que o humano revisa.
- **Revisão:** segunda leitura incansável procurando bugs, código morto e violações de padrão.
- **Documentação:** rascunhos de README/ADR a partir do código real, conferidos por humano.
- **Operação** (evolução): analisar logs, propor hipóteses de incidentes e escrever *runbooks*.

### O que continua sendo responsabilidade humana
Decidir escopo e trade-offs, aprovar dependências, entender e defender cada linha, e garantir que
as afirmações da documentação correspondem à realidade. A IA acelera; a responsabilidade pelo
que vai para produção não muda de dono.
