# AURA V12.2 — Arquitetura Multi-Modelo

## Status deste documento

**Atualização:** `intent` (DecisionEngine, nível 5.5) e `autonomy`
(InitiativeEngine) — os dois escolhidos abaixo como ponto de partida —
**foram implementados e têm testes passando** (`tests/test_agent_provider.py`,
`tests/test_decision_engine_agent_integration.py`,
`tests/test_initiative_engine_agent_integration.py`). `ai/agent_provider.py`
não é mais esqueleto: `OllamaProvider.chat()` ganhou o parâmetro `timeout`
que faltava, `config/settings.py::DEFAULTS` tem os 7 blocos `agent_*`, e
`AURA.py::_ensure_ollama()` seta `OLLAMA_MAX_LOADED_MODELS=5` quando é a
própria AURA quem sobe o servidor Ollama.

`memory`, `emotion`, `vision`, `planner` e `reflection` **continuam como
plano, não como código** — a integração com `memory_manager.py`,
`emotion_engine.py`, `context_manager.py` e o fluxo de execução
(`flow_executor.py`/`ReflectionEngine`) descrita mais abaixo neste
documento ainda não foi escrita. Seguem a mesma ordem de risco crescente
já justificada na seção final ("O que este documento NÃO decide ainda").

Este documento substitui a tentativa anterior (workspace descartado por
instrução explícita — continha um bug real de `NameError` em
`ai/intent_engine.py`, ver commit-diff descartado). Não reaproveitei código
daquela tentativa; reaproveitei a ideia central (namespace por agente via
`OllamaProvider`, que já é um padrão validado neste projeto desde a Angela) e
corrigi o que a análise de risco abaixo expôs.

## Por que isso importa: o número que decide o design

O projeto inteiro, desde o V10, escolhe modelos com uma restrição explícita:
**roda em 4GB de RAM** (`qwen2.5:3b`, README). Qualquer arquitetura
multi-modelo precisa respeitar esse número ou dizer claramente que ele mudou.
Fiz a conta antes de desenhar qualquer fluxo:

| Modelo | Tag recomendada | RAM real (quantizada) | Usado por |
|---|---|---|---|
| `qwen2.5:3b` | `qwen2.5:3b` | ~2.2 GB | aura |
| `qwen2.5:1.5b` | `qwen2.5:1.5b` | ~1.0 GB | planner, reflection, vision |
| `smollm2:1.7b` | `smollm2:1.7b-instruct-q4_0` | ~1.0 GB | intent |
| `smollm2:360m` | `smollm2:360m-instruct-q4_K_M` | ~0.3 GB | memory, emotion |
| `llama3.2:1b` | `llama3.2:1b` | ~0.7 GB | autonomy |

**Achado crítico #1 (bom):** `planner`, `reflection` e `vision` usam o
**mesmo arquivo de modelo** (`qwen2.5:1.5b`). Ollama identifica modelo
carregado pelo nome no payload da requisição, não por quem pediu — três
"agentes" cooperando sem custo de RAM triplicado, porque na prática são um
modelo só respondendo com três prompts de sistema diferentes. Mesma coisa
pra `memory`/`emotion` (`smollm2:360m`). **São 5 arquivos de modelo
distintos, não 8.**

**Achado crítico #2 (exige decisão):** `OLLAMA_MAX_LOADED_MODELS` — a
variável que controla quantos modelos DIFERENTES o Ollama mantém carregados
ao mesmo tempo — tem **default 3** em CPU. Com 5 arquivos distintos e
`keep_alive=-1` pedindo residência permanente em todos, os dois que
excederem o limite forçam o Ollama a descarregar e recarregar modelos a
cada troca de agente — e recarregar custa segundos reais, não
milissegundos. Isso destrói exatamente o ganho de velocidade que essa
arquitetura promete entregar.

**Soma de RAM se os 5 ficarem residentes ao mesmo tempo:** ~2.2 + 1.0 + 1.0 +
0.3 + 0.7 ≈ **5.2 GB só de modelos**, fora o resto da AURA (Qt, banco,
Python). Isso **excede** o piso histórico de 4GB do projeto. Não é um
detalhe — é a decisão central deste documento.

### A decisão

Duas peças, as duas necessárias:

1. **`OLLAMA_MAX_LOADED_MODELS=5`** precisa ser setado explicitamente (não é
   o default) — `AURA.py::_ensure_ollama()` é o lugar certo, já é onde o
   projeto sobe o Ollama sozinho se não estiver rodando.
2. **`keep_alive` diferenciado por frequência de uso, não `-1` pra tudo:**
   - `aura` e `intent` — chamados a cada mensagem do usuário. `keep_alive=-1`
     (residente sempre) se justifica.
   - `planner`, `reflection`, `memory`, `emotion` — chamados com frequência
     média (só quando há fluxo multi-etapa, ou periodicamente). `keep_alive="10m"`.
   - `vision`, `autonomy` — chamados raramente (ciclo do `ContextManager`,
     tipicamente a cada 12-24s, e mesmo assim só quando há sinal). `keep_alive="5m"`.

Isso mantém a RAM de pico nos ~5.2GB só quando TUDO está ativo ao mesmo
tempo (raro), mas o uso típico (aura + intent sempre ligados, o resto
entra e sai) fica muito mais próximo do perfil de 4GB histórico. **Ainda
assim, recomendo documentar publicamente que a partir da V12.2, 4GB deixa
de ser confortável — 6GB é o piso realista para usar a arquitetura
completa.** Rodar só com `aura` (sem os agentes) continua funcionando em
4GB — ver "Modo degradado" abaixo.

## Fluxo — quem chama quem

```
                              USUÁRIO
                                 │
                                 ▼
                        DecisionEngine.decide()
                     (regex/fuzzy — já existe, inalterado)
                                 │
                    ┌────────────┼────────────────┐
                    │ confiança  │ confiança       │ confiança
                    │ alta       │ média            │ baixa/ambígua
                    ▼            ▼                  ▼
              executa direto   INTENT (agente)   AURA (conversa)
              (sem agente)     extrai/classifica       │
                    │                │                 ▼
                    │                ▼          plano com >1 ação?
                    │         volta pro                 │
                    │         DecisionEngine        sim  │  não
                    │                                    │  │
                    │                              PLANNER │ executa
                    │                              quebra  │ direto
                    │                              em passos
                    ▼                                    │
              FlowExecutor executa ──────────────────────┘
                    │
                    ▼
              REFLECTION (agente, só se sucesso=False ou
                          taxa_sucesso do fluxo < 0.6)
                    │
                    ▼
              MEMORY (agente, só quando emotion/afeto/elogio
                      detectado — reaproveita _detect_emotional_category)
                    │
                    ▼
              resposta final ao usuário (sempre via AURA)


          ── EM PARALELO, fora do turno de conversa ──

    ContextManager (loop já existente, 12-24s)
              │
              ▼
        VISION (agente, resume contexto bruto em interpretação)
              │
              ▼
        AUTONOMY (agente, avalia oportunidade — só dispara sugestão
                  acima de um limiar de confiança, nunca executa nada)
              │
              ▼
        bus.publish("aura.response", ...) se houver sugestão

    EMOTION (agente, chamado pelo EmotionEngine nas transições de
             estado já existentes — enriquece, não substitui a
             máquina de estados atual)
```

### Regras estruturais (quem nunca chama quem)

- **Só a `aura` fala com o usuário.** Nenhum outro agente gera texto que
  vai direto pro chat — `planner`/`reflection`/`memory`/`vision`/`autonomy`/
  `emotion` retornam dados estruturados (JSON) que o código Python
  interpreta, nunca prosa solta exibida como veio.
- **Nenhum agente chama outro agente diretamente.** Toda orquestração
  passa pelo código Python existente (`ai_engine.py`, `decision_engine.py`,
  `flow_executor.py`) — evita cadeias de latência imprevisíveis e mantém
  o fluxo testável sem precisar rodar um LLM de verdade a cada teste.
- **`autonomy` nunca executa.** Só retorna `{"sugestao": str|null,
  "confianca": float}` — quem decide publicar a sugestão é código Python
  com um limiar fixo, igual ao `InitiativeEngine` já existente.
- **`emotion`/`memory` nunca respondem ao usuário.** Mesma regra que a
  Angela já segue com a AURA — modelos de apoio não têm voz própria na
  conversa.
- **Angela continua 100% isolada.** Nada neste documento toca em
  `angela/` — ela mantém seu próprio `OllamaProvider(settings_namespace="angela")`,
  sem relação com os agentes novos.

## Limites por agente

| Agente | Entrada | Saída | Timeout | Quando NÃO usar |
|---|---|---|---|---|
| `intent` | texto do usuário (normalizado) | `{"acao","tipo","alvo","confianca"}` | 3s | `DecisionEngine` já resolveu com confiança ≥0.82 (regex é mais rápido e determinístico — não gastar um agente no que já funciona) |
| `planner` | objetivo + ferramentas disponíveis | lista de passos estruturados | 5s | Plano de 1 ação só (não vale o overhead) |
| `reflection` | plano + resultado + objetivo | `{"erros","melhorias","repetir":bool}` | 5s | Fluxo teve sucesso E taxa_sucesso histórica ≥0.6 (não gastar ciclo revisando o que já vai bem) |
| `memory` | trecho da conversa | `{"categoria","chave","valor"}` ou null | 3s | Toda mensagem (caro demais) — só quando `_detect_emotional_category` sinalizar algo |
| `vision` | dump bruto do `ContextManager` | resumo em 1-2 frases | 4s | Nada mudou desde a última coleta (cache o resumo, não regenera à toa) |
| `autonomy` | contexto + histórico recente | `{"sugestao","confianca"}` | 3s | Cooldown ainda ativo (mesmo padrão de `_comment_cooldown` do `EmotionEngine`) |
| `emotion` | estado atual + evento | novo estado | 2s | Toda transição trivial (idle→thinking) não precisa de agente, só as que já disparam heurística hoje |

"Timeout" aqui significa: se o agente não responder dentro do prazo, o
código cai pro comportamento **atual** (regra/heurística existente) —
nenhum destes agentes é obrigatório pro sistema funcionar. Isso é o "modo
degradado" abaixo.

## Modo degradado (Ollama sem RAM pros agentes, ou agentes desligados)

Todo agente tem um fallback determinístico que já existe no código hoje:

- `intent` indisponível → `IntentEngine` regex/fuzzy atual (sem mudança).
- `planner` indisponível → `Planner.plan_from_flow()` atual.
- `reflection` indisponível → `ReflectionEngine.suggest_optimization()` atual (regras fixas).
- `memory` indisponível → `classify_importance()` regex atual.
- `vision` indisponível → `ContextManager.build_context_string()` atual (texto bruto).
- `autonomy` indisponível → `InitiativeEngine.get_suggestion()` atual (15% chance).
- `emotion` indisponível → `EmotionEngine` máquina de estados atual, sem enriquecimento.

Nenhum destes é substituição — são **enriquecimento opcional**. `config/settings.json`
ganha uma chave `"agents_enabled": true|false` (default `true` só se
`OLLAMA_MAX_LOADED_MODELS` estiver configurado E houver ≥6GB de RAM
detectável via `psutil` — senão, `false` automático, sem exigir que o
usuário saiba dessa conta).

## Integração com módulos existentes

| Módulo | O que muda | O que NÃO muda |
|---|---|---|
| `ai/agent_provider.py` | Novo — `AgentProvider` com 1 `OllamaProvider` por agente, `keep_alive` diferenciado (ver tabela acima) | — |
| `ai/ai_engine.py` | `process()._run()` ganha checkpoints opcionais que consultam agentes antes de cair no modelo principal | Toda a lógica de `_quick_casual`, `_detect_emotional_category`, o fix de concorrência da V12.1 — intactos |
| `automation/decision_engine.py` | `IntentEngine`/fuzzy continuam sendo o primeiro filtro; `intent` (agente) só entra depois | Hierarquia "mais rápido → mais lento" já documentada no próprio arquivo |
| `automation/decision_engine.py::ReflectionEngine` | Ganha chamada opcional ao agente `reflection` | `flow_library.register_execution()` continua sendo a fonte de verdade das métricas |
| `automation/decision_engine.py::InitiativeEngine` | `get_suggestion()` passa a poder consultar `autonomy` | Cooldown e lógica de disparo continuam em Python, não no agente |
| `memory/memory_manager.py` | `classify_importance()` ganha caminho opcional via agente `memory` | Armazenamento (`PermanentMemory.save()`) inalterado |
| `vision/context_manager.py` | Novo passo opcional chamando `vision` no loop já existente | Coleta de dados bruta (`_get_open_programs` etc.) inalterada |
| `ai/emotion_engine.py` | Transições de estado podem consultar `emotion` | Máquina de estados e `STATE_COLORS`/mapeamento pro avatar inalterados |
| `config/settings.py` | Novo bloco `"agents"` com um `sub-dict` por agente (mesmo padrão de `"angela"` já existente) | Namespaces `"ai"` e `"angela"` inalterados |

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| RAM insuficiente no hardware do usuário | Detecção via `psutil` + `agents_enabled=false` automático (ver Modo degradado) |
| Latência agregada (vários agentes em cadeia num turno só) | Cada consulta a agente tem timeout curto (2-5s) com fallback determinístico — pior caso é cair pro comportamento atual, nunca travar |
| `OLLAMA_MAX_LOADED_MODELS` não configurado pelo usuário que já tinha Ollama rodando antes | `AURA.py::_ensure_ollama()` só consegue setar a env var se for ELE quem sobe o processo — se o usuário já tem `ollama serve` rodando com outra configuração, documentar isso claramente em `docs/INSTALL_MODELS.md` como passo manual |
| Migração de usuários existentes (V12.1 sem agentes) | `agents_enabled` é aditivo — sistema funciona idêntico a hoje se `false` ou se os modelos não estiverem baixados |
| Cinco modelos novos pra baixar (~5.2GB de disco) | `scripts/download_models.py` com `--minimal` (só instala) vs completo (ver `docs/INSTALL_MODELS.md`) |

## O que este documento NÃO decide ainda

Meu plano de implementação (próximo passo, pendente de confirmação de
vocês): começar por **`intent` e `autonomy`** — são os dois com escopo
mais isolado e menor risco de regressão (não tocam no caminho principal de
execução de ação), e validam o padrão `AgentProvider` antes de estender
pros outros 5. Só depois disso passo pra `memory`/`emotion` (also baixo
risco) e por último `planner`/`reflection`/`vision`, que tocam mais fundo
no fluxo de execução.
