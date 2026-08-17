<div align="center">

<img src="assets/aura_banner.gif" width="900">

# ✦ AURA V12

## Artificial Unified Responsive Assistant

### Your Personal AI Companion
<h4>https://blandzin.github.io/AURA-site/</h4>

*"Uma inteligencia projetada para assistir, lembrar e evoluir com voce."*

<br>

[![Python](https://img.shields.io/badge/Python-3.12+-blue?style=for-the-badge&logo=python)]()
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-purple?style=for-the-badge)]()
[![Ollama](https://img.shields.io/badge/AI-Ollama%20Local-red?style=for-the-badge&logo=ollama)]()
[![Tests](https://img.shields.io/badge/tests-158%20passed-brightgreen?style=for-the-badge)]()
[![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)]()
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-orange?style=for-the-badge)]()

</div>

---

# ◈ Welcome to AURA V12

AURA is not just another chatbot. It is an **AI ecosystem for your desktop**.

It converses naturally, controls your computer, remembers what matters, automates repetitive tasks, and evolves alongside you. All powered by **local AI models** running on your own machine.

> *"A tool is controlled by the user. A companion grows with the user."*

---

# ✨ What AURA Can Do

| Capability | Description |
|------------|-------------|
| 💬 **Natural Conversation** | Speaks Portuguese natively with a unique personality |
| 🖥️ **Desktop Control** | Opens apps, navigates folders, types, clicks, controls media |
| 🧠 **Persistent Memory** | 3-level memory (short-term, permanent, procedural) with importance classification |
| 🔧 **38 Tools** | Files, system, browser, OCR, search, tasks, procedures — all categorized |
| 🎤 **Voice** | Neural TTS (edge-tts, PT-BR), speech recognition (SpeechRecognition + Whisper fallback) |
| 👁️ **Vision** | Real-time context: active window, open apps, clipboard, CPU/RAM |
| 🔄 **Multi-Step Automation** | "Open Spotify, wait 5s, play lofi" — all in one command |
| 🛠 **Angela — Chief Engineer** | Built-in AI engineer that audits code, investigates bugs, proposes fixes |
| 🎨 **Launcher V12** | Full visual configuration: models, settings, extensions, backup, profiles, updates, diagnostics |
| 🌐 **Cross-Platform** | Windows & Linux (macOS-ready). Architecture abstracts OS differences |
| 📦 **Standalone Build** | Compiles to `.exe` (Windows) or ELF binary (Linux) via PyInstaller |
| 🔄 **Auto-Updater** | Checks GitHub Releases, downloads, verifies SHA256, rollback on failure |

---

# 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/BLANDZIN/Aura
cd Aura

# 2. Install dependencies
# Windows: double-click scripts\instalar.bat
# Linux:   ./scripts/instalar.sh

# 3. Install Ollama + a model
# https://ollama.com/download
ollama pull qwen2.5:3b      # AURA — fast, conversational
ollama pull qwen3:4b         # Angela — precise, engineering

# 4. Launch
# Windows: double-click scripts\iniciar.bat
# Linux:   ./scripts/iniciar.sh
# Or:      python AURA.py
```

> **Linux note:** If the UI crashes with "xcb platform plugin", run `./scripts/instalar.sh` again — it installs `libxcb-cursor0` and other Qt6 system dependencies.

---

# 🏗 Architecture

```
AURA/                           138 Python files · 24,300+ lines · 158 tests
│
├── AURA.py                      ← single entry point
├── ai/                          ← intelligence layer
│   ├── ai_engine.py             ← core engine (755 lines, executor extracted)
│   ├── ai_provider.py           ← Ollama / LM Studio abstraction
│   ├── prompt_builder.py        ← system prompt construction
│   ├── executor.py              ← flow dispatch & execution
│   ├── intent_engine.py         ← natural language → structured intent
│   ├── emotion_engine.py        ← emotional state machine
│   └── identity_engine.py       ← personality & self-awareness
│
├── automation/                  ← planning & decision
│   ├── decision_engine.py       ← 6-level decision hierarchy (<10ms)
│   ├── planner.py               ← plan construction & resolution
│   ├── flow_executor.py         ← multi-step execution
│   ├── flow_library.py          ← versioned flows with metrics
│   └── error_learning.py        ← learns from mistakes
│
├── tools/                       ← 38 tools in 9 categories
│   ├── registry.py              ← auto-discovery (strict mode)
│   ├── file_tools.py            ← 8 file operations
│   ├── system_tools.py          ← 6 system tools
│   ├── browser_tools.py         ← 4 browser tools
│   ├── control_tools.py         ← 10 desktop control tools
│   ├── search_tools.py          ← web search without opening browser
│   ├── ocr_tools.py             ← OCR (EasyOCR + Tesseract)
│   ├── procedure_tools.py       ← saved procedure execution
│   ├── task_tools.py            ← task management
│   └── memory_tools.py          ← memory operations
│
├── memory/                      ← 3-level memory system
│   └── memory_manager.py        ← importance classification, relevant context
│
├── database/                    ← SQLite with WAL mode + migrations
├── voice/                       ← TTS + STT (edge-tts → native → pyttsx3)
├── vision/                      ← real-time desktop context
├── ui/                          ← PyQt6 interface
│   ├── app.py                   ← AuraApp (avatar + chat)
│   ├── chat_panel.py            ← chat UI with streaming
│   ├── main_window.py           ← Launcher V12 (14 pages)
│   ├── chat_page.py             ← embedded chat
│   ├── angela_page.py           ← Angela integrated
│   ├── tools_page.py            ← tool explorer
│   ├── memory_page.py           ← memory browser
│   ├── monitor_page.py          ← real-time metrics
│   └── developer_page.py        ← debug & diagnostics
│
├── launcher/                    ← V12 Launcher (standalone window)
│   └── pages/
│       ├── home.py              ← dashboard
│       ├── settings.py          ← 6-tab visual config
│       ├── models.py            ← model manager (Ollama + GGUF)
│       ├── updates.py           ← GitHub auto-updater
│       ├── extensions.py        ← plugin manager
│       ├── diagnostics.py       ← system health check
│       ├── backup.py            ← backup/restore .zip
│       └── profiles.py          ← user profiles
│
├── angela/                      ← Chief Engineer (audit, investigate, patch)
├── platforms/                   ← OS abstraction (Windows + Linux)
├── updater/                     ← checker, downloader, installer with rollback
├── core/                        ← EventBus, logger, AuraContext, text utils
├── config/                      ← settings.json, personality.json
├── scripts/                     ← launch & install scripts
└── tests/                       ← 22 test files, 158 tests
```

---

# 🧠 Memory System

AURA remembers. Every conversation builds context.

| Level | Storage | Purpose |
|-------|---------|---------|
| **Short-Term** | RAM | Current conversation history |
| **Permanent** | SQLite | Important facts, preferences, user identity |
| **Procedural** | SQLite | Learned workflows & automations |

```
User Input → Importance Classification (15+ regex rules) → Memory Storage
                                                                    ↓
Future Interactions ← Relevant Context Selection (score-based) ←───┘
```

---

# 🖥️ Launcher V12

**No more editing JSON files.** Everything is visual:

| Page | Function |
|------|----------|
| 🏠 Home | Dashboard: status, model, CPU/RAM |
| ⚙️ Settings | 6 tabs: AI, Voice, UI, Personality, Angela, Advanced |
| 🧠 Models | Install, activate, remove, import GGUF |
| 🔄 Updates | GitHub release checker + installer |
| 🧩 Extensions | Plugin manager |
| 📊 Diagnostics | Full system health check |
| 💾 Backup | Export/import .zip |
| 👤 Profiles | Multiple user profiles |

Access via the **🔧 Tools** button in the chat window (opens `ui/main_window.py`, all 14 pages, embedded in the running app). `launcher.py` at the repo root is a compatibility shim that starts the classic avatar+chat app, not a separate standalone launcher — there currently isn't one; the Launcher only runs inside a live AURA session.

---

# 🛠 Technology Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.12+ |
| **UI** | PyQt6 (Fusion dark theme) |
| **Database** | SQLite (WAL mode, auto-migration) |
| **AI Runtime** | Ollama, LM Studio |
| **Voice TTS** | edge-tts (neural PT-BR) → OS native → pyttsx3 |
| **Voice STT** | SpeechRecognition → faster-whisper |
| **Desktop** | PyAutoGUI, psutil, pyperclip |
| **Build** | PyInstaller (self-generating spec, no static `.spec` files) |
| **Testing** | pytest (158 tests) |

---

# 📦 Build

```bash
# Windows: generates dist\AURA\AURA.exe
python build.py

# Linux: generates dist/AURA/AURA (ELF 64-bit)
python3 build.py

# Run the test suite as part of your own release checklist
python build.py test
```

`build.py` generates the PyInstaller `.spec` on the fly (`generate_spec_content()`) — there's no static `.spec` file checked into the repo to keep in sync by hand. Build output size varies with what gets bundled (numpy/EasyOCR add real weight if not excluded) — verified real builds on Linux landed in the 300-850 MB range depending on the `excludes` list in `generate_spec_content()`. There is currently **no packaged Windows installer** (NSIS support was dropped in V12 without a replacement — see `V12_AUDITORIA.md`); distribution today is the portable `dist/AURA/` folder on both OSes.

---

# 🧪 Tests

```bash
pip install pytest
# Linux headless: needs a display for the PyQt6-dependent tests
xvfb-run -a pytest tests/ -q
# 158 passed
```

22 test files covering: AI engine (incl. a concurrency regression test), automation, tools, memory, tasks, voice, updater, build config, OCR, search, Angela, tool management, context/vision, and launcher page reachability.

---

# 🚀 Roadmap

### ✅ Completed (V12)
- ✅ Core engine with 6-level decision hierarchy
- ✅ 38 tools across 9 categories with auto-registry
- ✅ 3-level memory with importance classification
- ✅ Neural voice (edge-tts PT-BR) with triple fallback
- ✅ Real-time desktop context awareness
- ✅ Launcher V12 (14 pages, all visual — all reachable from the sidebar)
- ✅ Auto-updater with backup/rollback
- ✅ Cross-platform build (Windows .exe + Linux binary)
- ✅ Angela Chief Engineer (audit, investigate, 12-step workflow)
- ✅ PromptBuilder, FlowExecutor, AuraContext extracted
- ✅ 158 tests. SQL column whitelisting on dynamic updates. DB with WAL mode + indices on the hot query paths (tasks, memories, flows).

### 🔄 In Development
- 🔄 PostProcessor extraction from AIEngine
- 🔄 DB indexes for performance
- 🔄 FlowLibrary cache
- 🔄 Memory expansion

### ◈ Future
- ◈ Autonomous agents
- ◈ Vision pipeline (Live2D + real-time analysis)
- ◈ Voice command interface
- ◈ Plugin marketplace
- ◈ Android companion

---

# 🌌 Project Philosophy

> **Privacy.** Your data stays on your machine.
>
> **Evolution.** Software that grows with you.
>
> **Freedom.** You control your AI — not the other way around.

AURA represents an exploration into the future of personal computing: where software stops being just a tool and becomes an intelligent companion that understands, remembers, and amplifies you.

---

<div align="center">

## ✦ Developed by BLAND

*"Building tomorrow's assistants, one module at a time."*

⭐ If you like the project, consider giving it a star.

</div>
