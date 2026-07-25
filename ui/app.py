"""
ui/app.py
Classe principal AuraApp — orquestra todos os módulos do AURA.

Responsabilidades:
  1. Instanciar AvatarWidget e ChatPanel
  2. Posicionar o ChatPanel adjacente ao Avatar
  3. Conectar eventos do EventBus aos estados do Avatar
  4. Inicializar IA, memória e ferramentas
  5. Exibir mensagem de boas-vindas
  6. Manter referências para evitar garbage collection
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QScreen

from ui.avatar_widget import AvatarWidget
from ui.chat_panel import ChatPanel
from core.event_bus import bus
from config.settings import settings
from config.personality import personality
from core.logger import setup_logger
from avatar import AvatarEngine

logger = setup_logger("app")


class AuraApp:
    """
    Ponto de entrada da aplicação AURA.
    Chamado por main.py após criar o QApplication.

    Uso:
        aura = AuraApp()
        aura.start()
        app.exec()
    """

    def __init__(self):
        self._avatar: AvatarWidget | None = None
        self._avatar_engine: AvatarEngine | None = None
        self._chat:   ChatPanel    | None = None
        self._angela = None            # angela.Angela — Chief Engineer
        self._angela_panel = None      # ui.angela_panel.AngelaPanel (lazy)
        self._initialized = False
        self._pending_timers: list = []  # V11: rastreia timers para cancelar no shutdown


    def start(self) -> None:
        """Inicializa e exibe a interface."""
        logger.info("Iniciando interface AURA...")

        # ── 1. Widgets principais ─────────────────────────────────────────────
        self._avatar = AvatarWidget()
        self._chat   = ChatPanel()

        # ── 2. Conecta avatar ↔ chat ──────────────────────────────────────────
        self._avatar.clicked.connect(self._on_avatar_clicked)

        # ── 3. AvatarEngine recebe eventos e controla o runtime VRM
        self._avatar_engine = AvatarEngine(view=self._avatar)
        self._avatar_engine.start()

        # ── 4. Inicializa módulos pesados em background ───────────────────────
        QTimer.singleShot(100, self._init_modules)

        # Botão exclusivo "🛠 Angela" (do ChatPanel) publica ui.open_angela
        bus.subscribe("ui.open_angela", self._open_angela_panel)
        bus.subscribe("ui.open_launcher", self._open_launcher)


        # ── 5. Exibe avatar ───────────────────────────────────────────────────
        self._avatar.show()
        self._position_chat()

        logger.info("Interface AURA iniciada com sucesso")

    def _init_modules(self) -> None:
        """
        Inicializa IA, memória, ferramentas e tarefas após a UI estar pronta.
        Roda 100ms após o start() para não travar a renderização inicial.
        """
        try:
            from ai.ai_engine import ai_engine
            from memory.memory_manager import memory
            from tools.tool_manager import tool_manager
            from tasks.task_manager import task_manager

            self._ai           = ai_engine
            self._memory       = memory
            self._tools        = tool_manager
            self._task_manager = task_manager

            # Conecta intenções da IA ao executor de ferramentas
            bus.subscribe("ai.intent", tool_manager.dispatch)

            # Conecta eventos de tarefas ao chat e ao avatar
            bus.subscribe("tasks.due",               self._on_task_due)
            bus.subscribe("flow.done",               self._on_flow_done)
            bus.subscribe("flow.aborted",            self._on_flow_aborted)
            bus.subscribe("automation.suggestion",   self._on_automation_suggestion)
            # V12.1 — achado da auditoria do EventBus: _on_voice_listening
            # e _on_voice_speaking já existiam prontos (dão feedback visual
            # no avatar durante uso de voz) mas nunca eram assinados —
            # "voice.listening"/"voice.speaking_start" eram publicados por
            # voice_manager.py/voice_engine.py sem nenhum lado ouvindo.
            bus.subscribe("voice.listening",      self._on_voice_listening)
            bus.subscribe("voice.speaking_start", self._on_voice_speaking)
            bus.subscribe("voice.speaking_end",   self._on_voice_speaking_end)
            bus.subscribe("voice.error",          self._on_voice_error)
            bus.subscribe("tasks.created",   lambda **kw: self._refresh_panel_data())
            bus.subscribe("tasks.completed", lambda **kw: self._refresh_panel_data())
            bus.subscribe("tasks.updated",   lambda **kw: self._refresh_panel_data())
            bus.subscribe("tasks.cancelled", lambda **kw: self._refresh_panel_data())

            # Carrega dados iniciais no painel
            self._refresh_panel_data()

            # Verifica conectividade com a IA
            QTimer.singleShot(500, self._check_ai_connection)

            self._initialized = True
            logger.info("Módulos inicializados")

            # ── Angela — Chief Engineer (agente técnica, roda em background)
            try:
                from angela import Angela
                import os
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                self._angela = Angela(project_root=project_root)
                self._angela.start()
                logger.info("Angela (Chief Engineer) online")
            except Exception as e:
                logger.error(f"Falha ao iniciar Angela: {e}")



        except Exception as e:
            logger.error(f"Erro ao inicializar módulos: {e}")
            self._avatar.set_state("error")

    def _check_ai_connection(self) -> None:
        """Verifica se o provider de IA está acessível e exibe mensagem."""
        try:
            from ai.ai_provider import get_provider
            provider = get_provider()

            if provider.is_available():
                nome = personality.get("nome", "AURA")
                frase = personality.get("frase_abertura", f"Olá! Sou {nome}. Como posso ajudar?")
                bus.publish("ai.response", text=frase)
                self._avatar.set_state("idle")
                logger.info("Provider de IA disponível")
            else:
                provider_name = settings.get("ai", "provider", default="ollama")
                msg = (
                    f"⚠️ {provider_name.capitalize()} não está disponível. "
                    f"Inicie o servidor e reinicie o AURA."
                )
                bus.publish("ai.response", text=msg)
                self._avatar.set_state("error")
                logger.warning(f"Provider '{provider_name}' indisponível")

        except Exception as e:
            logger.error(f"Erro ao checar IA: {e}")
            self._avatar.set_state("error")

    # ── Posicionamento do chat ────────────────────────────────────────────────

    def _position_chat(self) -> None:
        """Posiciona o ChatPanel ao lado do Avatar."""
        if not self._avatar or not self._chat:
            return

        screen = QApplication.primaryScreen().geometry()
        av_x   = self._avatar.x()
        av_y   = self._avatar.y()
        av_w   = self._avatar.width()
        ch_w   = self._chat.width()
        ch_h   = settings.get("ui", "chat_height", default=680)

        self._chat.setFixedHeight(ch_h)

        # Decide se abre à esquerda ou à direita do avatar
        if av_x + av_w + ch_w + 8 <= screen.width():
            # Abre à direita
            chat_x = av_x + av_w + 8
        else:
            # Abre à esquerda
            chat_x = max(0, av_x - ch_w - 8)

        # Alinha verticalmente com o avatar, sem sair da tela
        chat_y = max(0, min(av_y, screen.height() - ch_h))

        self._chat.move(chat_x, chat_y)
        self._chat.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self._chat.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

    # ── Eventos do avatar ─────────────────────────────────────────────────────

    def _on_avatar_clicked(self) -> None:
        """Abre/fecha o painel de chat e reposiciona se necessário."""
        self._position_chat()
        self._chat.toggle()

        if self._chat._is_visible:
            self._refresh_panel_data()

    # ── Eventos do EventBus → estados do avatar ───────────────────────────────

    def _on_ai_thinking(self, status: bool) -> None:
        if status:
            self._avatar.set_state("thinking")

    def _on_avatar_set_state(self, state: str) -> None:
        """
        Recebe o estado calculado pelo EmotionEngine após cada execução
        (ex: 'speaking' quando orgulhosa/animada, 'error' quando frustrada).
        Usa um timer mais curto que o de _on_ai_response para não deixar
        o avatar preso em um estado emocional por tempo desproporcional
        à mensagem real que está sendo mostrada.
        """
        if state not in ("idle", "thinking", "speaking", "working", "error"):
            return
        self._avatar.set_state(state)
        if state != "idle":
            QTimer.singleShot(2500, lambda: self._avatar.set_state("idle"))

    def _on_ai_response(self, text: str) -> None:
        self._avatar.set_state("speaking")
        # Volta ao idle depois de ~2s por palavra (estimativa de leitura)
        duration = max(2000, len(text.split()) * 300)
        QTimer.singleShot(min(duration, 8000), lambda: self._avatar.set_state("idle"))

    def _on_ai_stream(self, token: str) -> None:
        self._avatar.set_state("speaking")

    def _on_ai_stream_done(self, full_text: str) -> None:
        QTimer.singleShot(3000, lambda: self._avatar.set_state("idle"))

    def _on_ai_error(self, error: str) -> None:
        self._avatar.set_state("error")
        QTimer.singleShot(4000, lambda: self._avatar.set_state("idle"))

    def _on_tool_result(self, sucesso: bool, mensagem: str, resultado) -> None:
        if sucesso:
            self._avatar.set_state("working")
            QTimer.singleShot(2000, lambda: self._avatar.set_state("idle"))
        else:
            self._avatar.set_state("error")
            QTimer.singleShot(3000, lambda: self._avatar.set_state("idle"))

    # ── Atualização do painel ─────────────────────────────────────────────────

    def _refresh_panel_data(self) -> None:
        """Carrega tarefas e memórias atualizadas no ChatPanel."""
        if not self._initialized:
            return
        try:
            # Tarefas
            from database.db_manager import db
            tasks = db.fetchall(
                "SELECT * FROM tasks WHERE status != 'cancelada' ORDER BY prioridade, criado_em DESC LIMIT 20"
            )
            self._chat.refresh_tasks(tasks)

            # Memórias (top por importância)
            mems = self._memory.permanent.get_all()[:30]
            self._chat.refresh_memories(mems)

            # Nome da personalidade
            nome = personality.get("nome", "AURA")
            self._chat.set_assistant_name(nome)

        except Exception as e:
            logger.error(f"Erro ao atualizar painel: {e}")

    # ── Encerramento limpo ────────────────────────────────────────────────────

    def _on_flow_done(self, resultado) -> None:
        if resultado.sucesso:
            self._avatar.set_state("idle")
            bus.publish("ai.response", text=f"✅ Concluído: {resultado.steps_ok}/{resultado.steps_total} etapas em {resultado.duracao_total}s")
        else:
            self._avatar.set_state("error")
            bus.publish("ai.response", text=f"⚠️ Fluxo com {resultado.steps_fail} falha(s)")
            QTimer.singleShot(3000, lambda: self._avatar.set_state("idle"))

    def _on_flow_aborted(self, **kw) -> None:
        self._avatar.set_state("error")
        msg = kw.get("mensagem", "Fluxo interrompido")
        bus.publish("ai.response", text=f"⛔ {msg}")
        QTimer.singleShot(3000, lambda: self._avatar.set_state("idle"))

    def _on_automation_suggestion(self, sequencia, descricao, contagem, mensagem) -> None:
        bus.publish("ai.response", text=f"💡 {mensagem}")

    def _on_voice_listening(self, status: bool) -> None:
        if status:
            self._avatar.set_state("thinking")
        else:
            self._avatar.set_state("idle")

    def _on_voice_speaking(self, text: str = "") -> None:
        self._avatar.set_state("speaking")

    def _on_voice_speaking_end(self, **_) -> None:
        self._avatar.set_state("idle")

    def _on_voice_error(self, mensagem: str = "") -> None:
        logger.warning(f"Erro de voz: {mensagem}")
        self._avatar.set_state("idle")

    def _on_task_due(self, task_id: int, titulo: str, mensagem: str) -> None:
        """Tarefa agendada disparou — notifica via chat e avatar."""
        bus.publish("ai.response", text=mensagem)
        self._avatar.set_state("speaking")
        QTimer.singleShot(4000, lambda: self._avatar.set_state("idle"))

    # ── Painel da Angela ─────────────────────────────────────────────────────

    def _open_launcher(self, **_):
        """Abre o Launcher V11 completo como janela separada."""
        try:
            from ui.main_window import MainWindow
            if not hasattr(self, '_launcher_window') or self._launcher_window is None:
                self._launcher_window = MainWindow()
            self._launcher_window.show()
            self._launcher_window.raise_()
            self._launcher_window.activateWindow()
        except Exception as e:
            logger.error("Erro ao abrir Launcher: {}".format(e))

    def _open_angela_panel(self, **_) -> None:
        """Abre o painel dedicado da Angela (Chief Engineer)."""
        if self._angela_panel is None:
            from ui.angela_panel import AngelaPanel
            self._angela_panel = AngelaPanel(parent=None)
            # Conecta o input do painel ao motor real da Angela
            self._angela_panel.request_ready.connect(self._on_angela_request)
        self._angela_panel.show()
        self._angela_panel.raise_()
        self._angela_panel.activateWindow()

    def _on_angela_request(self, text: str) -> None:
        if self._angela is None:
            return
        if text == "__AUDIT__":
            md = self._angela.audit_now()
            if self._angela_panel:
                self._angela_panel.append_audit_result(md)
            return
        self._angela.request(text, source="user")

    def shutdown(self) -> None:
        """Encerramento limpo — chamado pelo QApplication.aboutToQuit."""
        logger.info("Encerrando AURA...")
        # Cancela timers pendentes (V11)
        for t in self._pending_timers:
            try:
                if hasattr(t, 'stop') and t.isActive():
                    t.stop()
            except Exception:
                pass
        self._pending_timers.clear()
        if self._angela is not None:
            try:
                self._angela.shutdown()
            except Exception as e:
                logger.warning(f"Erro ao encerrar Angela: {e}")
        if hasattr(self, '_task_manager'):
            self._task_manager.shutdown()
        # V12.1 — achado da auditoria do EventBus: self._voice nunca era
        # setado (voice_manager.start() é chamado direto por
        # ui/chat_page.py e ui/chat_panel.py, não por AuraApp), então
        # esse hasattr sempre dava False e a thread de TTS nunca era
        # parada explicitamente ao fechar. Para o singleton real,
        # independente de qual painel o iniciou.
        try:
            from voice.voice_manager import voice_manager
            voice_manager.stop()
        except Exception as e:
            logger.debug(f"Encerramento de voz (não crítico): {e}")

        bus.clear()
        if self._avatar:
            self._avatar._save_position()

        try:
            from database.db_manager import db
            db.close()
        except Exception as e:
            logger.warning(f"Erro ao fechar banco de dados: {e}")
