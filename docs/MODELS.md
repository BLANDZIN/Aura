# AURA V12.2 — Modelos dos Agentes

Todos os dados de licença/tamanho abaixo foram verificados por pesquisa
nesta sessão (não confiar em memória de treinamento pra isso — licenças e
disponibilidade de modelo mudam). Ver `docs/AI_ARCHITECTURE.md` para o
porquê da escolha de tag quantizada em cada um.

---

## AURA (conversa) — `qwen2.5:3b`

- **Já em uso** desde a V10 — sem mudança nesta fase.
- **Parâmetros:** 3B. **RAM:** ~2.2GB (quantização padrão do Ollama).
- **Licença:** **Qwen License** (não é Apache 2.0 — Qwen2.5 libera todos os
  tamanhos sob Apache 2.0 *exceto* o 3B e o 72B, que ficam sob licença
  própria da Alibaba). Isso é diferente do resto da família usada nesta
  arquitetura. Não bloqueia o uso local via Ollama (o usuário baixa os
  pesos separadamente, a AURA não os redistribui), mas é uma
  característica real da licença que vale registrar — diferente da
  situação do PyQt6 (ver `V12.1_AUDITORIA_PUBLICACAO.md`), aqui a AURA
  não *distribui* o modelo, só consome via API local.
- **Motivo da escolha:** já validado em produção nesta base de código,
  bom português, equilíbrio velocidade/qualidade pra conversa.
- **Alternativa considerada:** `phi4-mini:3.8b` (concorrente direto no
  mesmo porte) — descartado por não ter o mesmo histórico de uso/ajuste
  fino já feito no `config/personality.py` deste projeto.

## Planner — `qwen2.5:1.5b`

- **Parâmetros:** 1.5B. **RAM:** ~1.0GB.
- **Licença:** Apache 2.0 (confirmado — só o 3B/72B da família Qwen2.5
  ficam fora do Apache).
- **Motivo:** bom em seguir instrução estruturada com pouco parâmetro;
  mesma família do modelo principal, então o mesmo padrão de prompt
  (formato JSON, tom) já é conhecido.
- **Vantagens:** reaproveita o MESMO arquivo de modelo que `reflection` e
  `vision` (ver análise de RAM em `AI_ARCHITECTURE.md`) — três papéis,
  um modelo carregado.
- **Desvantagens:** 1.5B é pequeno pra planos com muitas dependências
  condicionais complexas — mitigado pelo limite explícito ("não usar pra
  plano de 1 ação só" também vale o inverso: planos muito longos/condicionais
  devem cair pro modelo principal, não pro planner).
- **Alternativa:** `llama3.2:1b` — mais leve, mas pior em output
  estruturado (JSON) segundo comparações públicas; ficou reservado pro
  papel de `autonomy`, onde estrutura simples basta.

## Intent — `smollm2:1.7b-instruct-q4_0`

- **Parâmetros:** 1.7B. **RAM:** ~1.0GB (tag `-instruct-q4_0` confirmada
  em 991MB no registry do Ollama — usar esta tag explícita, não
  `smollm2:1.7b` puro).
- **Licença:** Apache 2.0.
- **Motivo:** família feita pela Hugging Face especificamente pra
  classificação/extração rápida em hardware limitado; é o papel mais
  citado como ponto forte do SmolLM2 (extração de intenção, roteamento).
- **Vantagens:** rápido, comunidade grande (Hugging Face mantém
  ativamente), boa documentação.
- **Desvantagens:** menos "mundo" que um modelo maior — por isso só entra
  DEPOIS do regex/fuzzy do `IntentEngine` falhar, nunca como primeira
  tentativa (ver hierarquia em `AI_ARCHITECTURE.md`).
- **Alternativa:** `qwen2.5:1.5b` (mesmo já usado noutros papéis) — mais
  pesado que o SmolLM2 1.7B em RAM real de contexto, escolhido o SmolLM2
  aqui justamente pra não concentrar tudo num único arquivo de modelo.

## Reflection — `qwen2.5:1.5b` (mesmo arquivo do Planner)

- Ver detalhes técnicos acima (Planner). Papel diferente, mesmo modelo —
  chamado com um system prompt de revisão, não de planejamento.
- **Motivo de reusar o mesmo modelo em vez de escolher outro:** RAM.
  Um modelo a mais residente custa ~1GB; reusar custa zero RAM adicional.

## Memory — `smollm2:360m-instruct-q4_K_M`

- **Parâmetros:** 360M. **RAM:** ~0.3GB (a tag *sem* sufixo de
  quantização, `smollm2:360m`, resolve pro F16 de 726MB — quase o
  dobro. Usar a tag `-instruct-q4_K_M` explicitamente).
- **Licença:** Apache 2.0.
- **Motivo:** resumir/classificar é uma tarefa de baixa complexidade
  onde 360M já é suficiente; é literalmente o menor modelo desta
  arquitetura de propósito, porque roda a cada mensagem potencialmente
  relevante.
- **Desvantagens:** não confiar nele pra julgamento sutil — daí o limite
  de só disparar quando `_detect_emotional_category` (já existe, V12.1)
  já filtrou o sinal.

## Vision — `qwen2.5:1.5b` (mesmo arquivo do Planner/Reflection)

- Terceiro papel no mesmo modelo. Recebe **só texto** (OCR, nome de
  janela, lista de programas, clipboard) — nunca a tela em si. Não é
  visão computacional, é interpretação de texto sobre o estado do
  sistema, então não precisa de um modelo multimodal (mais pesado).
- **Nome "Vision" pode confundir** — vale deixar explícito em qualquer
  doc de usuário que não processa imagem, só o que o `ContextManager` já
  coleta como texto.

## Emotion — `smollm2:360m-instruct-q4_K_M` (mesmo arquivo do Memory)

- Ver detalhes técnicos em Memory. Papel diferente (consistência de tom),
  mesmo modelo.

## Autonomy — `llama3.2:1b`

- **Parâmetros:** 1B. **RAM:** ~0.7GB.
- **Licença:** **Llama 3.2 Community License** (Meta) — não é OSI-permissiva
  pura: tem cláusula de limite de usuários ativos mensais acima do qual é
  necessária licença comercial da Meta, e uma Acceptable Use Policy
  própria. Pra um projeto pessoal/comunidade isso não bloqueia nada, mas
  é diferente das licenças Apache 2.0 do resto da lista — vale registrar
  antes de qualquer redistribuição em escala.
- **Motivo:** citado especificamente como bom pra "tool routing,
  classification... com um system prompt bem definido" em comparações
  recentes — exatamente o papel de gerar sugestão pontual e sair.
- **Alternativa:** `qwen2.5:0.5b` (menor ainda, Apache 2.0 — sem a
  cláusula de licença da Meta) — fica como substituto recomendado se a
  licença da Meta virar um problema real pra vocês; qualidade um pouco
  abaixo do Llama 3.2 1B em benchmarks públicos, mas aceitável pro escopo
  limitado de "gerar sugestão curta".

---

## Resumo de disco/RAM

| Modelo (tag exata) | Disco | RAM residente |
|---|---|---|
| `qwen2.5:3b` | ~1.9GB | ~2.2GB |
| `qwen2.5:1.5b` | ~1.0GB | ~1.0GB |
| `smollm2:1.7b-instruct-q4_0` | ~1.0GB | ~1.0GB |
| `smollm2:360m-instruct-q4_K_M` | ~0.3GB | ~0.3GB |
| `llama3.2:1b` | ~0.7GB | ~0.7GB |
| **Total (5 arquivos distintos)** | **~4.9GB disco** | **~5.2GB RAM se tudo residente ao mesmo tempo** |

Ver `docs/AI_ARCHITECTURE.md` para a estratégia de `keep_alive`
diferenciado que evita esse pico de RAM na maior parte do uso real.
