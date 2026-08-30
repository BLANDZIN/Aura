# AURA V12.2.1 — Fix (sessão de correção de bugs relatados)

Base: AURA_V12.2.1_unificado. Este pacote contém a correção de 2 bugs
relatados pelo Bland em produção, com causa raiz identificada e
validada por testes reais (não hipótese) antes da entrega.

**Nota sobre o zip original**: o arquivo `AURA_V12_2_1_unificado.zip`
enviado no início desta sessão não chegou de forma acessível ao
ambiente de execução (diretório de uploads ficou vazio, mount
confirmado). O conteúdo usado como base foi o próprio código-fonte já
presente no contexto da conversa (a mesma versão, conforme confirmado
pelo Bland). O GitHub (`BLANDZIN/Aura`) foi checado e está em uma
versão anterior (V12.1, sem a unificação) — **não foi usado como base**
para não reverter trabalho já feito localmente.

---

## Bug 1 — Ação com aspas simples exibida como texto cru (screenshot)

### Sintoma
Usuário pede "abre o youtube" (ou variações). A AURA responde
literalmente `{'acao': 'abrir_site', 'parametros': {'url': 'youtube'}}`
como se fosse fala — a ação nunca é executada, o YouTube nunca abre.
Aconteceu 2x seguidas na conversa relatada.

### Causa raiz
O modelo local (`qwen2.5:3b`) às vezes responde a ação em **sintaxe de
dict Python** (aspas simples) em vez de JSON estrito (aspas duplas),
mesmo com o system prompt pedindo JSON explicitamente — comportamento
conhecido de modelos pequenos sob temperatura não-zero.

`ai/ai_engine.py::_extract_json_objects()` usava só `json.loads()`,
que **rejeita aspas simples silenciosamente** (`except Exception:
pass`). Sem erro, sem log, sem fallback — o parser simplesmente não
achava nenhuma ação, e `_parse_intent()` caía direto no ramo de texto
puro, exibindo o dict malformado como se fosse a resposta da AURA.

Pior: a rede de segurança que deveria pegar esse caso
(`_detect_text_action()`, que reenvia ao modelo pedindo confirmação
quando ele descreve uma ação em texto livre) também checava só por
`'"acao"'` com aspas duplas — então nem essa segunda camada pegava o
problema. O erro passava por **dois** pontos de checagem sem ser
detectado.

Reproduzido isoladamente antes de qualquer correção (ver seção de
validação) com a string exata do screenshot.

### Correção
`ai/ai_engine.py`:
- Nova função `_parse_action_json()`: tenta `json.loads()` primeiro
  (caminho feliz, zero mudança de comportamento para JSON válido); se
  falhar, tenta `ast.literal_eval()` como fallback — aceita sintaxe de
  literal Python (aspas simples, dicts/listas aninhados) **com
  segurança total** (`literal_eval` nunca executa código arbitrário,
  só interpreta literais: dict, list, str, num, bool, None).
- `_detect_text_action()`: a checagem de "já é JSON" agora reconhece
  `'acao'` OU `"acao"`, fechando a segunda camada que também estava
  cega para aspas simples.

### Validação
- Reprodução isolada do bug com o parser original (sem patch) —
  confirmado que falha silenciosamente.
- Bateria de 8 casos com o parser corrigido: o caso exato do
  screenshot, JSON válido de ação única (regressão), array multi-ação
  válido (regressão), array multi-ação com aspas simples, ação com
  campo `mensagem`, três casos de texto puro/edge-case que **não**
  podem virar ação falsa (nenhuma regressão encontrada).
- Teste de pipeline completo: a string exata do screenshot processada
  pelo `ai_engine._parse_intent()` real → `_dispatch_intent()` real →
  `tool_manager.dispatch()` real → `abrir_site` chama
  `webbrowser.open()` com a URL correta do YouTube. Confirmado com a
  árvore de dependências real (não mocks isolados).

---

## Bug 2 — Incoerência de visão ("não tenho acesso ao computador")

### Sintoma
Usuário pergunta sobre o que está acontecendo na tela/computador dele.
A AURA responde: *"Não tenho a capacidade de acessar nada do seu
computador diretamente. Só posso responder por aqui e imaginar como
estaria a sua tela."* — apesar do `ContextManager` já coletar e
injetar, em **toda mensagem**, dados reais (janela ativa, programas
abertos, CPU/RAM, clipboard, arquivos do desktop).

### Causa raiz
`vision/context_manager.py::build_context_string()` já injetava o
bloco `CONTEXTO ATUAL DO COMPUTADOR:` no system prompt corretamente —
o dado real estava lá. O problema é que nada no prompt dizia
explicitamente ao modelo *que aquilo era acesso real* nem estabelecia
o limite certo (sem visão de pixels/imagem, mas com metadados reais +
OCR sob pedido via `ler_tela`). Um modelo local pequeno, sem essa
instrução explícita, cai no padrão de treinamento genérico de "IA sem
acesso ao seu computador" — negando um dado que está literalmente no
próprio prompt dele.

Mesma classe de problema que já existia (e já foi resolvida) para
perguntas de identidade ("você é o ChatGPT?") — resolvida ali com um
fast-path determinístico (`_try_identity_question`) em vez de confiar
só em instrução de prompt.

### Correção
Duas camadas, mesmo padrão já usado para identidade:

1. `vision/context_manager.py::build_context_string()` — cabeçalho do
   bloco de contexto reforçado para deixar explícito, junto do próprio
   dado, que é acesso real ("nunca diga que não tem acesso ao
   computador do usuário; você não vê pixels da tela, mas tem isto +
   OCR via ler_tela"). Reforço no lugar exato onde a informação
   relevante está, mensagem a mensagem — mesmo princípio já usado em
   `_EMOTIONAL_CONTEXT_BLOCKS`.

2. `ai/ai_engine.py` — novo **Nível 0.3** (entre identidade 0.2 e
   reforço positivo 0.5): `_try_vision_question()` intercepta
   perguntas explícitas sobre "ver a tela" e responde
   deterministicamente com o contexto REAL coletado pelo
   `ContextManager` (janela ativa, apps abertos, clipboard), sem
   depender do modelo acertar sozinho — mesma arquitetura de
   `_try_identity_question`, pelo mesmo motivo: um modelo de 3B não é
   confiável o bastante para esse tipo de pergunta só com instrução de
   prompt.

### Validação
- Bateria de testes do fast-path: pergunta direta com contexto real
  disponível (resposta usa os dados de verdade), pergunta sem contexto
  ainda carregado (resposta honesta sobre isso, sem negar capacidade
  em geral), variações de fraseado.
- Testes de falso-positivo: mensagens comuns (inclusive as do Bug 1)
  não disparam o fast-path por engano.
- Import real de `vision/context_manager.py` com o cabeçalho corrigido
  na árvore completa, sem quebrar nenhum consumidor existente
  (`ai/prompt_builder.py`, `ai/ai_engine.py`).

---

## O que este pacote contém

Reconstrução completa e validada da **camada de lógica/backend** do
AURA V12.2.1 (core, database, config, ai/*, memory, vision, automation/*,
tools/*, tasks, platforms/*) com as duas correções acima já aplicadas
e testadas de ponta a ponta nesta árvore.

**Os dois arquivos efetivamente alterados** (aplicar sobre o projeto
real de vocês, sem tocar em mais nada):

- `ai/ai_engine.py`
- `vision/context_manager.py`

Todo o resto dos arquivos deste zip está no estado em que foi
fornecido nesta conversa, sem alterações — incluído para que a árvore
importe e rode de ponta a ponta durante a validação, e para servir de
referência caso seja útil. **Camadas de UI (PyQt6), launcher, voice,
avatar, updater, angela, scripts e testes/ não foram reconstruídas
neste pacote** — nenhuma delas foi tocada pela correção, e
reconstruí-las de memória/texto colado traria risco real de divergir
do que vocês já têm rodando (ex.: achei uma inconsistência real entre
o texto colado e a própria auditoria de unificação de vocês sobre
`launcher/app.py` — não mexi nisso, não é meu lugar decidir sem
verificar o arquivo real).

## Como aplicar

**Opção recomendada** (mais segura): copie apenas os dois arquivos
corrigidos acima para cima do projeto V12.2.1 real de vocês (o zip
local que já está rodando, não o GitHub — o GitHub está desatualizado,
ainda em V12.1). Depois disso, se tudo continuar passando na suíte
completa de vocês (189 testes, `xvfb-run -a pytest tests/ -q`), o
commit para o GitHub fica limpo e pequeno: só a correção real, sem
misturar com reconstrução de arquivo nenhum.

## Pendência em aberto — tags de modelos especialistas

O pedido de adicionar tags de rastreabilidade aos modelos usados como
"especialistas" (`ai/agent_provider.py` / sistema de agentes) **não
foi feito nesta sessão**: esse arquivo não está em nenhuma fonte que
eu tenha acesso agora (nem nos documentos desta conversa, nem no
GitHub, nem no zip que não chegou ao ambiente). Antes de mexer nisso,
preciso que o arquivo real seja compartilhado diretamente — inventar a
estrutura dele do zero seria uma decisão arquitetural unilateral que
vocês não pediram.
