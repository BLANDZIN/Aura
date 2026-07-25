# AUDITORIA COMPLETA — Integração Avatar VRM na AURA V12.1

## 1. VISÃO GERAL DA AUDITORIA

**Data**: 2026-07-25  
**Escopo**: Integração do arquivo `assets/characters/aura/aura-dnv.vrm` respeitando a arquitetura modular  
**Princípio**: A IA publica eventos → Avatar responde via EventBus  

---

## 2. ESTADO ATUAL DA ARQUITETURA

### 2.1 Sistema de Eventos (EventBus)
**Localização**: `core/event_bus.py`

**Evento Principal**: `EventBus` com pub/sub thread-safe
- ✅ Suporta múltiplas callbacks por evento
- ✅ Dispatch automático para thread da Qt quando necessário
- ✅ Logging de performance via `metrics`

**Evento Publicado Hoje**:
```
ai.thinking       → IA começou a processar
ai.response       → Resposta do texto gerada
ai.stream.token   → Token de streaming recebido
ai.stream.done    → Streaming finalizado
ai.error          → Erro durante processamento
tool.result       → Resultado da execução de ferramenta
avatar.set_state  → Estado emocional calculado (NOVO — achado V12.1)
emotion.changed   → Emoção mudou (EmotionEngine)
voice.listening   → Começou a ouvir (STT)
voice.speaking_start → Começou a falar (TTS)
voice.speaking_end   → Finalizou fala (TTS)
voice.error       → Erro de voz
flow.done         → Fluxo completo (tarefas)
flow.aborted      → Fluxo abortado
tasks.*           → Eventos de tarefas (created, completed, updated, cancelled)
system.*          → Eventos de sistema (quando implementados)
```

### 2.2 Avatar Atual (AvatarWidget)
**Localização**: `ui/avatar_widget.py`

**Arquitetura Atual**:
- ❌ Avatar é 100% renderizado via QPainter (desenho 2D procedural)
- ❌ Estados: `idle`, `thinking`, `speaking`, `working`, `error`
- ❌ Tightly coupled com Qt (QWidget, QTimer, QPainter)
- ✅ Thread-safe via signals (`_AvatarSignals.set_state_signal`)
- ✅ Animações via timers (60 FPS)
- ✅ Arrastável e clicável

**API Pública**:
```python
widget.set_state(state: str)  # Estados: idle, thinking, speaking, working, error
widget.clicked                 # Signal quando clicado
```

### 2.3 Fluxo de Eventos (UI)
**Localização**: `ui/app.py`

**Mapeamento de Eventos → Estados Avatar**:
- `ai.thinking` → `"thinking"`
- `ai.response` → `"speaking"` (com timeout de 2s+ por palavra)
- `ai.error` → `"error"` (com timeout 4s)
- `tool.result` (sucesso) → `"working"` (2s), depois `"idle"`
- `avatar.set_state` → estado direto do EmotionEngine
- `voice.listening` → `"thinking"` se ligado, `"idle"` se desligado
- `voice.speaking_start` → `"speaking"`
- `flow.done` / `flow.aborted` → feedback visual

### 2.4 EmotionEngine
**Localização**: `ai/emotion_engine.py`

**Estados Emocionais**:
```python
{
    "calma":       {"energia": 0.5, "humor": 0.5, "verbosidade": 0.5},
    "animada":     {"energia": 0.9, "humor": 0.8, "verbosidade": 0.7},
    "curiosa":     {"energia": 0.6, "humor": 0.6, "verbosidade": 0.8},
    "concentrada": {"energia": 0.7, "humor": 0.3, "verbosidade": 0.2},
    "orgulhosa":   {"energia": 0.8, "humor": 0.7, "verbosidade": 0.6},
    "pensativa":   {"energia": 0.4, "humor": 0.4, "verbosidade": 0.5},
    "brincalhona": {"energia": 0.8, "humor": 0.9, "verbosidade": 0.7},
    "frustrada":   {"energia": 0.5, "humor": 0.2, "verbosidade": 0.4},
    "cansada":     {"energia": 0.3, "humor": 0.3, "verbosidade": 0.3},
}
```

**Publicação**: `emotion.changed` → `estado`, `anterior`

**Mapeamento para Avatar UI**:
```python
"calma"       → "idle"
"animada"     → "speaking"
"curiosa"     → "thinking"
"concentrada" → "working"
"orgulhosa"   → "speaking"
"pensativa"   → "thinking"
"brincalhona" → "speaking"
"frustrada"   → "error"
"cansada"     → "idle"
```

### 2.5 Voice Engine
**Localização**: `voice/voice_engine.py`

**Eventos Publicados**:
```
voice.listening (status: bool)    → Começou/parou de ouvir
voice.speaking_start (text: str)  → Começou a falar
voice.speaking_end ()             → Parou de falar
voice.transcribed (text: str)     → Texto capturado (STT)
voice.error (mensagem: str)       → Erro
```

**Status Atual**: ✅ Tudo conectado em `ui/app.py` V12.1

### 2.6 Pontos de Extensão Identificados

#### 2.6.1 Pontos Críticos Encontrados (Achados V12.1)
1. ✅ **EventBus está perfeitamente estruturado** → Sistema de sub/pub já existe
2. ✅ **Avatar.set_state() é thread-safe** → Pode ser chamado de qualquer thread
3. ✅ **Todos os eventos já existem** → Nenhuma duplicação necessária
4. ✅ **EmotionEngine.get_avatar_state()** → Mapping direto para estados do avatar

#### 2.6.2 Gaps Encontrados
1. ❌ **Não existe avatar_engine.py** → Módulo de renderização de avatar não existe
2. ❌ **Não existe character_manager.py** → Gestor de personagens não existe
3. ❌ **assets/characters/ está vazio** → Estrutura de caracteres não foi criada
4. ❌ **Sem suporte a múltiplos personagens** → Hoje é hard-coded em `ui/avatar_widget.py`
5. ❌ **Sem configuração de avatar** → Tipo de avatar não é selecionável
6. ❌ **Sem suporte a VRM** → Nenhuma biblioteca VRM está integrada

---

## 3. DEPENDÊNCIAS E COMPATIBILIDADES

### 3.1 Plataformas a Suportar
- ✅ Windows 10+
- ✅ Linux (Debian/Ubuntu)
- ❓ macOS (não testado, mas Python é cross-platform)

### 3.2 Dependências Necessárias para VRM
```
# VRM Loaders
pyvrmlib>=0.1.0          # Parser VRM 0.0 (simples)
  OR
pyassimp>=4.1.0          # Parser VRM 1.0 (complexo, requer assimp C++)
  OR
trimesh>=3.15.0          # Loader 3D genérico (suporta VRM)

# Renderização 3D
PyOpenGL>=3.1.5          # OpenGL via Python
PyGLM>=2.6.0             # Matemática de gráficos (vectors, matrizes)
glfw>=2.6.0              # Janela OpenGL (alternativa a Qt, não recomendado)
  OR
vispy>=0.13              # Visualização científica (abstração Qt/GL)

# Animação
numpy>=1.20.0            # Álgebra linear (já está em requirements.txt)
scipy>=1.7.0             # Interpolação para animações

# Áudio (lip-sync com fala)
librosa>=0.10.0          # Análise de áudio
```

### 3.3 Restrição Arquitetural Crítica
**O avatar 3D NÃO pode ser renderizado em PyQt6 nativamente.**

Opções:
1. **OpenGL Embedded em Qt** (RecomendadoRecomendado): QOpenGLWidget com OpenGL puro
2. **Vispy** (Mais simples): Abstração que funciona em Qt
3. **Pyglet/GLFW** (Não recomendado): Janela separada, hard de integrar

---

## 4. PLANO DE INTEGRAÇÃO ARQUITETURAL

### 4.1 Estrutura de Diretórios Proposta

```
avatar/
├── __init__.py
├── avatar_engine.py           # Engine principal de renderização 3D
├── character_manager.py       # Gerenciador de personagens (multiplayer)
├── animation_controller.py    # Controlador de animações
├── expression_controller.py   # Expressões e lip-sync
├── vrm_runtime.py             # Carregador e runtime VRM
├── state_machine.py           # Máquina de estados do avatar
├── config.py                  # Configurações do avatar
└── opengl_widget.py           # Integração Qt + OpenGL

assets/
└── characters/
    └── aura/
        ├── aura-dnv.vrm       # Modelo VRM
        └── config.json        # Config específica do personagem
    └── angela/
        ├── angela.vrm
        └── config.json

config/
├── avatar.json                # Config padrão do avatar (novo)
```

### 4.2 Fluxo de Eventos Proposto

```
┌──────────────────┐
│   AI Engine      │
└────────┬─────────┘
         │
         v
┌──────────────────┐         ┌──────────────────┐
│   EventBus       │────────>│ EmotionEngine    │
│                  │         └────────┬─────────┘
│ • ai.thinking    │                  │
│ • ai.response    │                  v
│ • ai.error       │         ┌──────────────────┐
│ • emotion.changed├────────>│ AvatarEngine     │
│ • voice.*        │         └────────┬─────────┘
│ • flow.*         │                  │
└──────────────────┘                  v
                         ┌──────────────────────┐
                         │  VRM Avatar Widget   │
                         │  (OpenGL em Qt)      │
                         │                      │
                         │ • Animações         │
                         │ • Expressões        │
                         │ • Lip-sync          │
                         │ • Estados           │
                         └──────────────────────┘
```

### 4.3 Máquina de Estados do Avatar (Independente da Emoção)

```
Estados Base (Visual):
├─ IDLE          → respiração suave, estado padrão
├─ THINKING      → partículas orbitando (mesmo que hoje)
├─ SPEAKING      → ondas sonoras + boca se movendo (lip-sync)
├─ LISTENING     → orelhas levantadas (novo)
├─ WORKING       → engrenagem/progresso (mesmo que hoje)
├─ SLEEPING      → olhos fechados, postura relaxada (novo)
├─ HAPPY         → sorriso, corpo energizado (novo)
├─ CURIOUS       → cabeça inclinada, olhar investigador (novo)
├─ CONFUSED      → cabeça balançando, olhos piscando confusos (novo)
├─ ERROR         → cores vermelhas, corpo tenso (mesmo que hoje)
└─ POWERED_DOWN  → versão desfocada/translúcida do SLEEPING (novo)
```

**Transições**:
```
emotion.changed (calma→animada) → IDLE (mantém) ou HAPPY (se ação bem-sucedida)
emotion.changed (→concentrada)  → WORKING
emotion.changed (→curiosa)      → CURIOUS
emotion.changed (→frustrada)    → ERROR/CONFUSED
voice.listening (true)          → LISTENING
voice.speaking_start           → SPEAKING
ai.thinking (true)             → THINKING
```

---

## 5. IMPLEMENTAÇÃO POR FASES

### FASE 1: Foundation (Semana 1)
- ✅ Criar `avatar/avatar_engine.py` (stub + loaders)
- ✅ Criar `avatar/vrm_runtime.py` (parser + carregador VRM)
- ✅ Criar `avatar/opengl_widget.py` (QOpenGLWidget básico)
- ✅ Criar `avatar/config.py` (configurações)
- ⚠️ Integrar em `ui/app.py` (substitui AvatarWidget)

### FASE 2: Character Management (Semana 2)
- ✅ Criar `avatar/character_manager.py`
- ✅ Criar `assets/characters/aura/config.json`
- ✅ Suportar hot-swap de personagens
- ✅ Criar `config/avatar.json` (seleção)

### FASE 3: Animation & Expression (Semana 3)
- ✅ Criar `avatar/animation_controller.py` (BlendShapes, animações)
- ✅ Criar `avatar/expression_controller.py` (expressões faciais)
- ✅ Implementar lip-sync com TTS

### FASE 4: State Machine & Polish (Semana 4)
- ✅ Criar `avatar/state_machine.py`
- ✅ Transições suaves entre estados
- ✅ Testes em Windows/Linux
- ✅ Documentação completa

---

## 6. RISCOS E MITIGAÇÕES

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|--------|-----------|
| VRM parsing complexo | Alta | Alto | Usar `trimesh` ou `pyassimp` testados |
| OpenGL não funciona em Linux | Média | Alto | Testas em container Docker |
| Performance 3D em baixos recursos | Alta | Médio | Otimizar mesh, usar LOD, profiles |
| Lip-sync desalinhado | Média | Médio | Usar librosa + correlação com áudio |
| Hot-swap quebra estado | Média | Médio | Salvar/restaurar state machine |
| Qt + OpenGL memory leak | Baixa | Alto | Cleanup explícito em destrutor |

---

## 7. CHECKLIST DE INTEGRAÇÃO

### Verificação de Compatibilidade
- [ ] VRM loads sem erros (parse, malhas, esqueleto)
- [ ] OpenGL renderiza em Qt sem travamentos
- [ ] Mudanças de estado são suaves (sem frame drops)
- [ ] Transições funcionam em Windows 10+
- [ ] Transições funcionam em Linux (Debian 11+)
- [ ] Múltiplos personagens carregam sem conflitos
- [ ] Hot-swap não quebra EventBus

### Verificação de Arquitetura
- [ ] Nenhuma lógica de IA em `avatar/`
- [ ] Nenhuma lógica de UI em `avatar/`
- [ ] Toda comunicação via EventBus
- [ ] CharacterManager é agnóstico de VRM (abstração)
- [ ] Estados são independentes de emoções
- [ ] Zero polling (tudo event-driven)

### Verificação Funcional
- [ ] Avatar responde a todos os eventos do EventBus
- [ ] Lip-sync sincroniza com voz
- [ ] Expressões faciais mudam com emoção
- [ ] Transições são suaves (sem jumps)
- [ ] Performance < 60ms por frame (60 FPS)
- [ ] Memory footprint < 500MB (VRM + OpenGL)

---

## 8. PRÓXIMOS PASSOS

1. **Confirmação de Dependências**: Decidir qual VRM loader usar
   - Recomendação: `trimesh` (mais genérico, menos overhead C++)

2. **Setup de Ambiente**: Adicionar deps em requirements.txt

3. **Implementação Fase 1**: avatar_engine.py + vrm_runtime.py

4. **Testes**: Validar que VRM carrega corretamente

5. **Integração**: Conectar ao EventBus em ui/app.py

---

## 9. MÉTRICAS DE SUCESSO

✅ Avatar VRM renderiza sem erros  
✅ Estados mudam conforme eventos do EventBus  
✅ Múltiplos personagens podem ser selecionados via config  
✅ Nenhum módulo quebrado (backward compatibility)  
✅ Performance ≥ 60 FPS em hardware mid-range  
✅ Código segue SOLID + Low Coupling  
✅ Testes passam em Windows + Linux  

---

**Autor**: Staff Software Engineer (AI Analysis)  
**Data de Criação**: 2026-07-25  
**Status**: 🟡 PRONTO PARA IMPLEMENTAÇÃO
