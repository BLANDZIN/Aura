# AURA v4 — Assistente Virtual Inteligente

Avatar animado na área de trabalho com IA local, controle do computador e pipeline Live2D.
Inclui a Angela — Chief Engineer própria, que audita, investiga e evolui o código da AURA.

## Instalação rápida

```bash
# 1. Instale dependências
instalar.bat        ← Windows (duplo clique)
./instalar.sh        ← Linux

# 2. Instale Ollama + os dois modelos
# https://ollama.com/download
ollama pull qwen2.5:3b     # AURA — conversa, rápida
ollama pull qwen3:4b       # Angela — engenharia, precisa

# 3. Inicie
iniciar.bat          ← Windows (duplo clique)
./iniciar.sh          ← Linux
```

Linux: se a interface travar na inicialização com um erro mencionando
"xcb platform plugin", rode `./instalar.sh` de novo — ele instala as
libs de sistema que o Qt6 precisa (`libxcb-cursor0` e afins).

## O que funciona

- Avatar animado (5 estados: idle, thinking, speaking, working, error)
- Chat com IA local via Ollama ou LM Studio
- 37 ferramentas: abrir programas, pastas, sites, pesquisar, criar tarefas, métricas de desempenho
- Suporte multiplataforma (Windows e Linux) via `platforms/` — a AURA não sabe qual SO está usando
- Busca fuzzy (tolera erros de digitação)
- Memória em 3 níveis (RAM, SQLite, procedimentos)
- Fluxos multi-ação (abrir Chrome + pesquisar YouTube em sequência)
- Procedimentos reutilizáveis ("execute rotina_manha")
- Aprendizado de automações repetidas
- Consciência de contexto (sabe o que está aberto, clipboard, hora)
- TTS (pyttsx3) + STT (faster-whisper, opcional)
- Pipeline Live2D para geração de avatar animado
- **Angela** — Chief Engineer própria (auditoria, investigação, git, raciocínio via Qwen3 4B). Veja `README_ANGELA.md`.
- Observabilidade real (tempo de modelo/ferramenta/EventBus/fluxo) — ferramenta `obter_metricas`
- Autoengenharia: falhas recorrentes disparam investigação automática da Angela
- Suíte de testes automatizados (`pytest tests/`)

## Configuração

Edite `config/settings.json`:
- `ai.model` — modelo do Ollama para a AURA (qwen2.5:3b recomendado)
- `angela.model` — modelo do Ollama para a Angela (qwen3:4b), config própria e separada da AURA
- `voice.auto_speak` — fala automática das respostas

Edite `config/personality.json`:
- `humor` (0-100), `energia` (0-100), `formalidade` (0-100)

## Testes

```bash
pip install pytest --break-system-packages
pytest tests/ -q
```

## Estrutura

```
AURA/
├── main.py          ← entrada
├── ai/              ← motor de IA (AURA)
├── angela/          ← Chief Engineer (auditoria, git, workflow, LLM próprio)
├── platforms/        ← abstração Windows/Linux
├── tools/           ← 37 ferramentas, por categoria
├── automation/      ← Planner + FlowExecutor
├── memory/          ← memória em 3 níveis
├── vision/          ← contexto do computador
├── voice/           ← TTS + STT
├── ui/              ← interface PyQt6
├── tasks/           ← gerenciador de tarefas
├── core/            ← EventBus, logger, métricas
├── tests/           ← suíte automatizada
├── assets/live2d/   ← pipeline de avatar
└── config/          ← settings.json, personality.json
```

