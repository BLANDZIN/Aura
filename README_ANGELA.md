# 🛠 Angela — Chief Engineer (AURA v9)

Angela é a **segunda agente** do ecossistema AURA. Ela **não** é uma chatbot,
não conversa com o usuário casualmente e **não substitui a AURA**.

AURA continua sendo o rosto do projeto. Angela cuida da parte técnica.

## O que Angela faz

- analisa código e arquitetura
- investiga bugs
- executa auditorias
- propõe patches (nunca aplica sem autorização)
- executa testes
- supervisiona a saúde técnica do projeto

## Personalidade

Extremamente calma, técnica, educada, segura, racional, organizada, objetiva
e paciente. Nunca responde antes de investigar. Nunca altera código sem
compreender o problema completamente.

## Como AURA e Angela conversam

Elas se comunicam **exclusivamente pelo EventBus** (`core.event_bus`).
Nenhuma chama a outra diretamente. Tópicos oficiais estão em
`angela/communication.py`:

| Tópico                    | Emissor  | Significado                       |
| ------------------------- | -------- | --------------------------------- |
| `aura.needs_angela`       | AURA     | Peço uma análise                  |
| `angela.request`          | Usuário  | Falo direto com a Angela (painel) |
| `angela.acknowledged`     | Angela   | Recebi, vou investigar            |
| `angela.step`             | Angela   | Progresso do workflow             |
| `angela.report`           | Angela   | Análise concluída                 |
| `aura.speak_for_angela`   | Angela   | AURA repassa síntese ao usuário   |
| `aura.problem`            | AURA     | Sinal para autoengenharia         |

## Processo obrigatório (12 passos)

Angela **nunca** pula etapas. `angela/workflow.py` impõe:

1. Receber solicitação
2. Ler arquivos envolvidos (arquivo inteiro, nunca pedaços)
3. Ler arquitetura relacionada
4. Ler histórico
5. Ler logs
6. Encontrar causa raiz
7. Criar hipóteses
8. Comparar soluções
9. Escolher melhor solução
10. Executar testes
11. Gerar relatório
12. Perguntar se deseja aplicar

## Ambiente isolado

Angela **nunca** altera o projeto principal. Todo trabalho acontece em
`angela/workspace/`, um snapshot do projeto. O merge para a versão
principal é **decisão sua**, fora do módulo.

## Autoengenharia

Quando a AURA detecta problemas recorrentes ela publica `aura.problem`.
`angela.autoengineering.AutoEngineeringTrigger` conta ocorrências em janela
de 5 minutos; ao chegar em 3, dispara `aura.needs_angela` automaticamente.

**Conectado de verdade** (Fase 2): `automation/error_learning.py` publica
`aura.problem(kind="tool_failure")` em toda falha de ferramenta observada
via `tool.result`, e `automation/flow_executor.py` publica
`aura.problem(kind="flow_failure")` quando um fluxo é abortado. Antes disso
o gatilho existia mas nada o alimentava.

## Modo Auditoria

Botão **"Auditoria completa"** no painel da Angela. Analisa:

- Arquitetura, código morto, imports inúteis
- Duplicações (com localização arquivo:linha)
- Complexidade, acoplamento, **classes/funções grandes**
- **Dependências circulares** entre módulos de topo
- Cobertura de testes, documentação
- Organização/escalabilidade

Cada detector também existe como ferramenta individual (`Auditor.find_dead_code()`,
`find_duplicates()`, `detect_large_classes()`, `detect_large_functions()`,
`detect_cycles()`), reaproveitando a mesma lógica da auditoria completa —
sem duplicação entre o relatório agregado e as consultas pontuais.

## Angela ↔ Modelo local (Qwen3 4B)

**OpenClaude foi removido desta arquitetura.** O repositório
https://github.com/Gitlawb/openclaude declara no próprio `LICENSE` conter
código derivado do Claude Code da Anthropic sem autorização de
redistribuição — não é uma base aceitável para construir em cima. O
adapter `angela/platforms/openclaude.py` foi mantido no repositório só
como referência de estrutura, com `is_available()` travado em `False`
permanentemente.

O objetivo original (Angela raciocinando com um modelo local, sem editar
arquivos diretamente) continua de pé — só o caminho mudou:

    Angela.chief_engineer
        ↓
    angela/llm/backend.py (AngelaLLM)
        ↓
    ai/ai_provider.py::OllamaProvider(settings_namespace="angela")
        ↓
    Ollama (http://localhost:11434)
        ↓
    Qwen3 4B

`AngelaLLM` reaproveita o **mesmo** `OllamaProvider` que a AURA usa para o
Qwen2.5 3B — só que instanciado com configuração própria
(`config/settings.json → "angela"`: modelo, URL, temperatura, tokens),
sem tocar no namespace `"ai"` da AURA e sem compartilhar histórico. O
modelo **só raciocina** (chamado no passo `s_choose` do workflow, com o
contexto reunido nos passos anteriores); toda ação física continua
passando exclusivamente por `EngineeringPlatform`.

Se o Ollama local não estiver servindo `qwen3:4b`, `AngelaLLM.is_available()`
retorna `False` e a Angela cai de volta nas heurísticas estáticas — mesma
filosofia de fallback graceful que já existia para a plataforma de
execução.

**Trocar o backend de raciocínio no futuro** (outro modelo, outro
provider) = trocar a implementação de `AngelaLLM`. Nenhuma outra parte da
Angela precisa mudar.

## Ferramentas de engenharia (`angela/tools/`)

Construídas **sobre** `EngineeringPlatform` (nunca como métodos novos na
interface abstrata — isso manteria a troca de plataforma restrita aos 9
primitivos originais, não a dezenas de métodos específicos):

- `angela/tools/git_tools.py::GitTools` — status/diff/log/commit/restore,
  sempre dentro do workspace isolado, nunca no projeto real.

Mais ferramentas (busca por símbolo, patch versionado, lint/format,
logs) estão no roadmap — ver `AUDITORIA_V9_ETAPA1.md` para a lista
completa priorizada em camadas.

## Extensão futura

A arquitetura já está preparada para novos especialistas:

    angela/          → Chief Engineer
    (futuro) vision/           → Visual specialist
    (futuro) security/         → Security specialist
    (futuro) infrastructure/   → Infra specialist
    (futuro) planning/         → Planning specialist

Cada um seguirá o mesmo padrão: persona isolada, workflow obrigatório,
plataforma plugável, comunicação por EventBus.

## Uso

```python
from angela import Angela

angela = Angela(project_root=".")
angela.start()

# Disparo direto
angela.request("Analise o Learning Engine")

# Auditoria síncrona
print(angela.audit_now())
```

Na UI da AURA: botão **🛠 Angela** no header do chat.
