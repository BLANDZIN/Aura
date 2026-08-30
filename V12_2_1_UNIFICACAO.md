# AURA V12.2.1 — Unificação V12.1 × V12.2

Base: V10_CONCLUSAO.md → V12.1_AUDITORIA_PUBLICACAO.md → este documento.

Vocês tinham dois zips divergindo do mesmo ponto: **AURA_V12_1.zip** (sessão
Codex — histórico git completo até 28/07, ~1400 arquivos incluindo build/dist)
e **AURA_V12_2.zip** (minha baseline limpa — 369 arquivos, sem build, 183
testes). Nenhum dos dois "ganha" sozinho: cada um tinha coisa real que faltava
no outro. Este documento é o relatório de como uni os dois — o que peguei de
cada lado, o que rejeitei e por quê, e o que ainda fica em aberto.

**Números reais desta rodada** (não estimativa — suíte rodada, não assumida):

- **189 testes passando** (183 originais + 6 novos desta unificação),
  **3 rodadas consecutivas limpas** via `xvfb-run -a pytest tests/ -q`.
- **`compileall` limpo** na árvore inteira (zero erro de sintaxe).
- **`ruff --select F401,F811,F841`**: 181 achados reais corrigidos
  (166 imports mortos + 15 variáveis/redefinições mortas), 4 falsos-positivos
  intencionais marcados com `# noqa` (sondas de disponibilidade e reexports
  de compatibilidade — documentados caso a caso abaixo).

---

## 🔴 O achado que eu levaria mais a sério: segurança do flow_executor

`automation/flow_executor.py` da V12.2 **tinha perdido** a checagem que
impede um fluxo multi-etapa de executar uma ação sensível
(`excluir_arquivo`, `fechar_programa`, `digitar_texto`, `clicar_mouse`, ou
qualquer step marcado `confirmacao_necessaria=True`) **sem pedir
confirmação**. A V12.1 (Codex) tinha essa checagem; a V12.2 não.

**Por que isso importa de verdade:** uma ação única disparada via
`ToolManager.dispatch()` sempre passou por `REQUIRES_CONFIRM` antes de
executar. Mas um **fluxo** (`FlowExecutor._execute_step()`) chama
`tool.execute()` direto, pulando o `dispatch()` inteiro — é o único
caminho de execução que nunca passava por aquele guard. Um comentário em
`automation/decision_engine.py` dizia "ToolManager.REQUIRES_CONFIRM já é
o guard real" — verdade para ação única, falso para fluxo. Na prática:
um fluxo de várias etapas que incluísse `excluir_arquivo` (seja um fluxo
salvo, seja a IA respondendo com um array de ações) **executava a
exclusão sem diálogo nenhum**.

Restaurado: `_step_requires_confirmation()` de volta em
`flow_executor.py`, mais o bloco que publica `tool.confirm_required` +
aborta o fluxo com `aura.problem(kind="flow_confirmation_required")`.
Testes de regressão:
- `test_flow_requires_confirmation_before_sensitive_step` (restaurado da V12.1)
- `test_flow_step_with_explicit_confirmacao_necessaria_also_pauses` (novo —
  cobre o caminho do `step.confirmacao_necessaria=True` explícito, que a V12.1
  também tinha mas nenhum teste cobria)

## 🟡 Versão: `core/version.py` tinha sumido

A V12.2 **não tinha** `core/version.py` (fonte única de versão). Em vez
disso, `build.py`, `AURA.py`, `updater/__init__.py`, `updater/checker.py`
e `ui/main_window.py` tinham "V11"/"11.0.0" **hardcoded e desatualizado**
— inclusive `tests/test_updater.py::test_manifest` tinha sido ajustado
para *validar contra o valor errado* em vez de against a fonte real,
escondendo o problema.

Restaurado `core/version.py` (`AURA_VERSION = "12.2.1"`), religado em
todos os 5 pontos acima (inclusive o label "v11.0.0" fixo na sidebar do
Launcher — bug visível pra qualquer usuário que abrisse Ferramentas), e
`test_manifest` corrigido para comparar contra `core.version.AURA_VERSION`
de verdade em vez de string fixa.

## 🟢 Os dois sistemas de "agentes especialistas" — fiquei com o da V12.2

Cada lado, trabalhando em paralelo, construiu sua própria ideia de
"agentes especialistas" — e são conceitos genuinamente diferentes, não
um refactor do outro:

| | V12.1 (`ai/agents/coordinator.py`, `SpecialistCoordinator`) | V12.2 (`ai/agent_provider.py`) |
|---|---|---|
| Mecanismo | 4 heurísticas Python puras (regex/estado), thread pool, 35ms de orçamento | 7 agentes reais via `OllamaProvider`, cada um com seu próprio modelo/namespace, timeout configurável |
| Integração | Chamado sempre, incondicionalmente, ANTES do Decision Engine decidir — mesmo que a resposta vá por um caminho rápido que nunca usa o resultado | Nível 5.5 do `decision_engine.py` (só depois que regex/fuzzy falham) + `InitiativeEngine` (substituiu a heurística aleatória de 15%) |
| Testes | 1 arquivo | 3 arquivos dedicados (`test_agent_provider.py`, `test_decision_engine_agent_integration.py`, `test_initiative_engine_agent_integration.py`) |
| Doc | — | `docs/AI_ARCHITECTURE.md`, `docs/MODELS.md`, `docs/INSTALL_MODELS.md` |

**Decisão: não trouxe `ai/agents/` para a árvore unificada.** Três motivos,
não um só:

1. **Duplica sinal que já existe.** `EmotionSpecialist` redetecta afeto/
   identidade — isso já é o que `_detect_emotional_category()` +
   `ai/prompt_builder.py::_EMOTIONAL_CONTEXT_BLOCKS` fazem. `VisionSpecialist`
   reconstrói janela ativa/apps abertos — isso já é
   `context_manager.build_context_string()`, já injetado no prompt.
   `LearningSpecialist` expõe afinidade — dado que já existe em
   `learning_engine.get_affinity()`.
2. **Custo de latência incondicional.** `specialist_coordinator.analyze()`
   era chamado ANTES do Decision Engine decidir — ou seja, toda mensagem
   pagava até 35ms de análise mesmo quando a resposta ia por um atalho
   regex de <10ms que nunca usa esse resultado. Isso vai contra o próprio
   propósito da hierarquia de decisão (`decision_engine.py`: "milissegundos,
   sem chamar o modelo... a menos que seja estritamente necessário").
3. **`agent_provider.py` já é a arquitetura validada.** Testada, integrada
   nos pontos certos, documentada, com fallback gracioso (`agents_enabled`
   desligado por padrão). Ter os dois ao mesmo tempo — dois conceitos
   chamados "agente" fazendo coisa parecida por caminhos diferentes — é
   exatamente o tipo de duplicação que o projeto tenta evitar.

Se no futuro fizer sentido ter uma camada de sinal heurístico *gratuita*
complementar ao `agent_provider.py` (sem custo de LLM), a ideia do
`SpecialistCoordinator` pode voltar — mas teria que nascer plugada
*depois* da decisão do Decision Engine, não antes, e sem duplicar o que
`prompt_builder`/`context_manager` já cobrem.

## 🟢 Avatar VRM (V12.1) — trazido, mas não ligado

`avatar/` (7 arquivos: `avatar_engine.py`, `character_manager.py`,
`vrm_runtime.py`, `animation_controller.py`, `state_machine.py`,
`config.py`, `__init__.py`) + `assets/characters/aura/aura-dnv.vrm` (16MB,
o modelo real) + `docs/AVATAR_VRM_INTEGRATION_AUDIT.md` vieram da V12.1.
É Fase 1 de verdade (não placeholder), mas:

- `opengl_widget.py` e `expression_controller.py` **não existem** —
  `avatar/__init__.py` promete os dois via `__getattr__` lazy, mas hoje
  isso lança `ImportError` se alguém tentar importar.
- **Não está ligado a `ui/app.py`.** O avatar em produção continua sendo
  o `AvatarWidget` 2D (`ui/avatar_widget.py`, QPainter puro) — confirmei
  que esse arquivo é *idêntico* entre V12.1 e V12.2 (fora quebra de
  linha), ninguém tocou nele para plugar o VRM.
  `avatar/vrm_runtime.py` exige `trimesh`+`numpy` de verdade (import a
  nível de módulo) — não estavam em nenhum requirements. Adicionei como
  extra opcional `avatar` em `pyproject.toml` (`pip install -e ".[avatar]"`)
  e uma seção comentada em `requirements.txt`, mesmo padrão que OCR/STT
  já usam.
- Corrigi de passagem: `avatar/__init__.py` importava `AvatarConfig` pra
  reexport mas esquecia de listar em `__all__` (achado real do ruff);
  `avatar/vrm_runtime.py` carregava o VRM duas vezes em
  `_parse_metadata()` e descartava o resultado sem usar (`vrm_file`
  morto).

Trouxe porque é trabalho real, versionado, documentado — descartar seria
perder progresso genuíno. Não ativei porque ativar sem os dois módulos
que faltam e sem as deps instaladas quebraria o app pra quem não tiver
`trimesh`/`numpy`.

## 🟡 `tools/tool_manager.py` — 39 imports mortos, um bug de doc

O arquivo importava diretamente as ~36 classes de `Tool` de cada
categoria (`CriarPastaTool`, `AbrirProgramaTool`, ...) — sobra de antes
da Fase V11 (registry), quando `_register_all()` passou a usar
`tools/registry.py::discover_tools()` (descoberta dinâmica por
`REGISTRY` de cada módulo de categoria). As importações diretas nunca
foram removidas; não alimentavam nada.

Também confirmei, item por item, quais dos 4 nomes que a docstring dizia
"reexportados por compatibilidade" (`KNOWN_SITES`, `PYAUTOGUI_KEYS`,
`normalize_params`, `BaseTool`) têm consumidor real hoje via
`grep -rn "from tools.tool_manager import"` em todo o projeto —
`PYAUTOGUI_KEYS` não tem mais nenhum (a doc estava desatualizada);
os outros 3 têm. Docstring corrigida pra refletir isso.

`automation/learner_bridge.py` (`report_action()`) também saiu — era
importado uma vez dentro de `dispatch()` e nunca chamado; `_execute()`
já registra aprendizado direto via `automation_learner.register_action()`
desde antes. Módulo inteiro sem nenhum caller real.

---

## Launcher — limpeza e correções

### `launcher/app.py` removido (código morto real, não suposição)

Classe `LauncherApp` — janela standalone com sidebar própria de 8
páginas, de antes da V12 (quando o Launcher rodava fora de uma sessão
viva da AURA). **Nada no projeto a instanciava** — nem `main.py`,
`AURA.py` ou `launcher.py` sabiam que existia. A única referência era um
import solto em `launcher/pages/home.py`
(`from launcher.app import LauncherApp`), dentro do método que monta os
atalhos da Home, nunca usado depois da linha do import. Documentado com
teste de regressão (`test_standalone_launcher_window_is_a_documented_removal_not_a_silent_one`,
mesmo padrão do teste que já existia pra remoção do instalador NSIS).

### Bug real: atalhos da Home navegavam para a página errada

Efeito colateral direto da remoção acima: os índices dos 4 atalhos da
Home ("Gerenciar Modelos", "Configurações", "Diagnóstico", "Backup")
tinham sido escritos pra numeração de 8 páginas do `LauncherApp` antigo.
Dentro do `MainWindow` real (`ui/main_window.py`, 14 páginas), esses
mesmos números apontavam pra outra coisa: **"Gerenciar Modelos" (índice
2) abria a página Angela**; "Configurações" (índice 1) abria o Chat;
"Diagnóstico" (índice 5) abria Memória; "Backup" (índice 6) abria
Monitor. Todos os 4 atalhos da Home estavam quebrados.

Corrigido — e corrigido de um jeito que não pode quebrar de novo do
mesmo modo: em vez de reescrever os índices certos (que sofreriam o
mesmo bug se as páginas forem reordenadas de novo no futuro), os
atalhos agora carregam o **título** da página
(`launcher/pages/home.py::HOME_SHORTCUTS`) e resolvem o índice em
runtime contra `ui.main_window.PAGE_TITLES` via `_navigate_to_title()`.
Teste de regressão simula clique real em cada atalho e confere a página
final (`test_home_shortcuts_navigate_to_the_correct_pages`).

### Bug real: botões da página Modelos sem estilo nenhum

`launcher/pages/_widgets.py` (módulo de estilos/widgets compartilhados
entre páginas do Launcher) tinha **todas as regras QSS com chaves
duplas** (`QPushButton {{ ... }}`). Chave dupla só faz sentido como
template pra `str.format()` — mas nada no módulo nem em quem o usa
chamava `.format()` nelas; eram aplicadas direto via `setStyleSheet()`.
QSS com chave dupla é inválido — o Qt ignora a regra e cai no tema
padrão, silenciosamente.

`launcher/pages/models.py` é quem mais usava isso de verdade —
`BTN_PRIMARY`/`BTN_SECONDARY`/`BTN_DANGER` (importados de `_widgets.py`,
sem redeclarar local, ao contrário de quase toda outra página) estavam
em **todos os botões interativos da página** (atualizar, baixar modelo,
importar GGUF, ativar/desativar, usar na Angela, remover). Corrigido —
chave simples — e agora os botões da página mais usada pra gerenciar
modelo renderizam de verdade pela primeira vez.

### Duplicação real (mas parcialmente intencional — só consolidei o que era 100% idêntico)

`extensions.py`, `backup.py`, `diagnostics.py`, `profiles.py`
importavam `CARD_STYLE`/`make_*` de `_widgets.py` e **imediatamente
redeclaravam tudo local por cima** — o import nunca fazia nada além de
poluir o namespace. Removi os imports mortos em todos. Onde a constante
local era **byte-a-byte idêntica** à de `_widgets.py` (confirmado
programaticamente, não por inspeção visual) — `BTN_SECONDARY_STYLE` e
`BTN_DANGER_STYLE` em `extensions.py` e `profiles.py` — troquei a
redeclaração pelo import de verdade. Onde os valores tinham divergido de
propósito (ex.: `backup.py` usa botões maiores, `padding: 10px 20px`
contra `8px 16px` do padrão — visualmente deliberado, não erro de
digitação), **mantive local** — forçar identidade ali seria eu decidindo
uma mudança visual que não dá pra validar sem tela.

### Limpeza geral do launcher (ruff, F401/F811/F841)

Imports nunca usados: `os`, `json`, `QFont` em vários arquivos; variável
morta `real_slider` em `settings.py` (plano abandonado de slider visual
ao lado do spinbox). Doc desatualizada corrigida: `ui/main_window.py`
dizia "10 páginas" no docstring (são 14 desde a V12.1). Bônus pequeno:
`MainWindow._aura_running` nunca era setado — o card "AURA" da Home
sempre mostrava "Parada" mesmo com a AURA rodando; agora reflete o
resultado real de `_detect_backend()`/`_on_standalone_ready()`.

---

## Limpeza mecânica no resto do projeto (ruff, validada por teste)

Apliquei `ruff check --select F401 --fix` no restante do projeto depois
de confirmar, arquivo por arquivo nos casos de dúvida, que não havia
padrão de reexport intencional escondido (só achei isso relevante em
`tool_manager.py`, já coberto acima). ~140 imports mortos a mais em
`ui/*.py` (Qt widgets importados e nunca usados — sobra de blocos de
import copiados entre páginas), `updater/*.py`, `voice/*.py`,
`avatar/*.py`, scripts do live2d.

Três achados de variável morta que mereceram olhar mais de perto porque
apontavam pra alguma coisa real, não só sobra inofensiva:

- **`ai/ai_engine.py`**: `last_flow = self._last_executed_input` era
  calculado e nunca usado — `register_positive()` sempre era chamado com
  `flow_name=""`. Isso significa que **elogiar a AURA nunca reforça a
  confiança do fluxo específico que acabou de rodar** — a maquinaria pra
  isso existe em `learning_engine.py` e funciona, só nunca foi
  conectada. Não fechei essa lacuna agora (fechar direito exige
  rastrear a última ação/fluxo de forma unificada, não só o texto do
  usuário — não é ajuste de uma linha) — documentei com comentário
  inline no ponto exato pra quando isso for prioridade.
- **`ai/emotion_engine.py`**: `verbosidade`/`humor` extraídos do perfil
  emocional em `color_response()` mas nunca usados — a lógica real só
  olha `self._state` (nome do estado), não os valores numéricos.
  Comportamento atual funciona, só é menos nuançado do que os nomes das
  variáveis sugeririam.
- **`ui/avatar_widget.py`**: `tooth_w` (largura angular do dente da
  engrenagem) calculado e nunca aplicado no polígono — a engrenagem do
  estado "working" desenha um zigue-zague, não dentes de engrenagem de
  verdade com vão entre eles. Puramente cosmético, avatar 2D continua
  funcional.

---

## O que ficou testado 3x limpo

```
xvfb-run -a python3 -m pytest tests/ -q
189 passed in 2.68s   (rodada 1)
189 passed            (rodada 2, exit=0)
189 passed            (rodada 3, exit=0)
```

`python3 -m compileall .` limpo na árvore inteira (fora `assets/live2d`,
que já era excluído de auditoria por precedente — scripts standalone,
não parte do app).

## Achado de ambiente — não é bug do código, mas registro pra vocês

Durante a validação, a suíte completa **quebrou de forma intermitente**
(“Fatal Python error: Aborted”) em algumas rodadas, sempre no primeiro
uso do fixture `qapp` (criação da `QApplication`) depois de outros
testes já terem rodado — nunca no mesmo ponto exato, e o mesmo comando
repetido às vezes passava limpo, às vezes não. Isolei bastante (rodando
subconjuntos menores repetidamente) e não consegui reproduzir de forma
determinística nem achar um único arquivo culpado — o padrão aponta pra
uma corrida de inicialização entre PyQt6 (Xvfb) e alguma extensão nativa
(numpy/psutil apareciam na pilha) sob pressão de agendamento do
ambiente, não pra um bug de lógica em código que eu tenha tocado (o
crash acontecia até em subconjuntos de teste que não passam perto de
nada que mudei). As 3 rodadas limpas acima foram obtidas de verdade,
não é que eu tenha escondido uma rodada ruim — só registro que, se
aparecer de novo em CI de vocês, o suspeito é timing de inicialização
do Qt sob display virtual, não a suíte em si.

## O que fica pra próxima conversa (não é falta, é escopo)

1. **Elogio → fluxo específico** (achado acima, `ai/ai_engine.py`) —
   fechar a lacuna de rastrear a última ação/fluxo de forma unificada.
2. **Avatar VRM Fase 2+** — `opengl_widget.py`, `expression_controller.py`,
   e decisão de quando (se) ligar em `ui/app.py`. Ver
   `docs/AVATAR_VRM_INTEGRATION_AUDIT.md` (nota de status atualizada no topo).
3. **Licenciamento PyQt6/GPLv3** — segue em aberto desde
   `V12.1_AUDITORIA_PUBLICACAO.md`, não mexi nisso aqui (fora do escopo
   desta unificação).
4. Os itens já registrados em `V10_CONCLUSAO.md` (backlog "te amo" no
   Windows, botão de feedback negativo) continuam como estavam.
