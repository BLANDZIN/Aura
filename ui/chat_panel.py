"""
ui/chat_panel.py
Painel lateral de conversa do AURA.

Contém:
  - Cabeçalho com nome, estado e botões de ação
  - Histórico de mensagens com bolhas de chat
  - Campo de texto + botão enviar + botão microfone
  - Aba de tarefas rápidas
  - Aba de memórias salvas

Comunicação via EventBus:
  Escuta:  ai.response, ai.thinking, ai.stream.token, ai.stream.done,
           tool.result, tool.confirm_required
  Publica: (chama ai_engine.process diretamente)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QTextEdit,
    QTabWidget, QListWidget, QListWidgetItem,
    QSizePolicy, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QPropertyAnimation,
    QEasingCurve, QRect
)
from PyQt6.QtGui import QFont, QColor, QKeyEvent, QIcon
from typing import Optional
from core.event_bus import bus
from core.logger import setup_logger

logger = setup_logger("chat_panel")

# ── Estilos ───────────────────────────────────────────────────────────────────
STYLE_PANEL = """
QWidget#chat_panel {
    background-color: #0D1117;
    border-left: 1px solid #1E293B;
    border-radius: 16px 0 0 16px;
}
"""
STYLE_SCROLLAREA = """
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: #0D1117; width: 5px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #1E3A5F; border-radius: 2px; min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
STYLE_INPUT = """
QTextEdit {
    background: #161B22; color: #E6EDF3;
    border: 1px solid #21262D; border-radius: 10px;
    padding: 10px 14px; font-size: 14px;
    selection-background-color: #1F6FEB;
}
QTextEdit:focus { border-color: #388BFD; }
"""
STYLE_BTN_SEND = """
QPushButton {
    background: #1F6FEB; color: #fff;
    border: none; border-radius: 10px;
    font-size: 18px; font-weight: bold;
}
QPushButton:hover  { background: #388BFD; }
QPushButton:pressed{ background: #0D4A9E; }
QPushButton:disabled { background: #21262D; color: #484F58; }
"""
STYLE_BTN_MIC = """
QPushButton {
    background: #21262D; color: #8B949E;
    border: 1px solid #30363D; border-radius: 10px;
    font-size: 18px;
}
QPushButton:hover  { background: #30363D; color: #E6EDF3; }
QPushButton:checked { background: #3D1F1F; color: #EF5350; border-color: #EF5350; }
"""
STYLE_TABS = """
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab {
    background: transparent; color: #8B949E;
    padding: 8px 16px; font-size: 12px; border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #4FC3F7; border-bottom: 2px solid #4FC3F7; }
QTabBar::tab:hover    { color: #E6EDF3; }
"""


class MessageBubble(QFrame):
    """Bolha de mensagem individual no histórico de chat."""

    def __init__(self, text: str, role: str, parent=None):
        super().__init__(parent)
        self._role = role

        is_user = (role == "user")
        bg      = "#1F6FEB22" if is_user else "#161B22"
        border  = "#1F6FEB44" if is_user else "#21262D"
        color   = "#E6EDF3"
        align   = Qt.AlignmentFlag.AlignRight if is_user else Qt.AlignmentFlag.AlignLeft

        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
                margin: 2px 0;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Rótulo do autor
        if role == "assistant":
            author = QLabel("AURA")
            author.setStyleSheet("color: #4FC3F7; font-size: 11px; font-weight: bold;")
            layout.addWidget(author)
        elif role == "system":
            author = QLabel("Sistema")
            author.setStyleSheet("color: #8B949E; font-size: 11px;")
            layout.addWidget(author)

        # Texto da mensagem
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent; border: none;")
        lbl.setAlignment(align)
        layout.addWidget(lbl)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)


class StreamingBubble(QFrame):
    """Bolha especial para respostas em streaming (texto se acumula em tempo real)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: #161B22;
                border: 1px solid #21262D;
                border-radius: 12px;
                margin: 2px 0;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)

        author = QLabel("AURA")
        author.setStyleSheet("color: #4FC3F7; font-size: 11px; font-weight: bold;")
        layout.addWidget(author)

        self._lbl = QLabel("▋")
        self._lbl.setWordWrap(True)
        self._lbl.setStyleSheet("color: #E6EDF3; font-size: 14px; background: transparent; border: none;")
        layout.addWidget(self._lbl)

        self._text = ""
        # Cursor piscante
        self._cursor_visible = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        self._cursor_timer.start(530)

    def append_token(self, token: str) -> None:
        self._text += token
        self._lbl.setText(self._text + ("▋" if self._cursor_visible else " "))

    def finalize(self) -> None:
        self._cursor_timer.stop()
        self._lbl.setText(self._text)

    def _blink_cursor(self) -> None:
        self._cursor_visible = not self._cursor_visible
        self._lbl.setText(self._text + ("▋" if self._cursor_visible else " "))


class TypingIndicator(QFrame):
    """Três pontos animados enquanto AURA está processando."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: #161B22;
                border: 1px solid #21262D;
                border-radius: 12px;
                margin: 2px 0;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self._dots = []
        for _ in range(3):
            dot = QLabel("●")
            dot.setStyleSheet("color: #4FC3F7; font-size: 10px;")
            layout.addWidget(dot)
            self._dots.append(dot)
        layout.addStretch()

        self._phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(200)

    def _animate(self) -> None:
        for i, dot in enumerate(self._dots):
            alpha = "FF" if i == self._phase % 3 else "44"
            dot.setStyleSheet(f"color: #4FC3F7{alpha}; font-size: 10px;")
        self._phase += 1


class ChatPanel(QWidget):
    """
    Painel lateral completo de conversa.
    Abre/fecha deslizando a partir do avatar.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._is_visible = False
        self._streaming_bubble: Optional[StreamingBubble] = None
        self._typing_indicator: Optional[TypingIndicator] = None
        self._ai_enabled = True  # desabilitado enquanto processa

        self._setup_ui()
        self._connect_bus()

        # Começa escondido
        self.hide()
        logger.info("ChatPanel iniciado")

    # ── Construção da UI ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setObjectName("chat_panel")
        self.setStyleSheet(STYLE_PANEL)
        self.setFixedWidth(420)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self._build_header())
        main.addWidget(self._build_messages_area())
        main.addWidget(self._build_tabs())
        main.addWidget(self._build_input_area())

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet("""
            QFrame {
                background: #0D1117;
                border-bottom: 1px solid #1E293B;
                border-radius: 16px 0 0 0;
            }
        """)
        row = QHBoxLayout(header)
        row.setContentsMargins(20, 0, 16, 0)

        # Avatar miniatura + nome
        avatar_dot = QLabel("◉")
        avatar_dot.setStyleSheet("color: #4FC3F7; font-size: 22px;")

        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        self._name_lbl = QLabel("AURA")
        self._name_lbl.setStyleSheet("color: #E6EDF3; font-size: 16px; font-weight: bold;")
        self._status_lbl = QLabel("Online")
        self._status_lbl.setStyleSheet("color: #3FB950; font-size: 11px;")
        name_col.addWidget(self._name_lbl)
        name_col.addWidget(self._status_lbl)

        row.addWidget(avatar_dot)
        row.addSpacing(10)
        row.addLayout(name_col)
        row.addStretch()

        # Botão exclusivo para abrir o painel da Angela (Chief Engineer)
        btn_angela = QPushButton("🛠 Angela")
        btn_angela.setToolTip("Falar com Angela — Chief Engineer")
        btn_angela.setFixedHeight(32)
        btn_angela.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_angela.setStyleSheet("""
            QPushButton {
                background: #0F172A; color: #7DD3FC;
                border: 1px solid #1E3A5F; border-radius: 8px;
                padding: 4px 10px; font-size: 12px;
            }
            QPushButton:hover { background: #1E3A5F; color: #BAE6FD; }
        """)
        btn_angela.clicked.connect(lambda: bus.publish("ui.open_angela"))
        row.addWidget(btn_angela)

        # Botão fechar
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(32, 32)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent; color: #8B949E;
                border: none; border-radius: 8px; font-size: 14px;
            }
            QPushButton:hover { background: #21262D; color: #E6EDF3; }
        """)
        btn_close.clicked.connect(self.toggle)
        row.addWidget(btn_close)

        return header


    def _build_messages_area(self) -> QWidget:
        """Área de scroll com histórico de mensagens."""
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(STYLE_SCROLLAREA)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(16, 16, 16, 8)
        self._msg_layout.setSpacing(8)
        self._msg_layout.addStretch()

        self._scroll.setWidget(self._msg_container)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return self._scroll

    def _build_tabs(self) -> QTabWidget:
        """Abas: Tarefas | Memórias."""
        tabs = QTabWidget()
        tabs.setFixedHeight(180)
        tabs.setStyleSheet(STYLE_TABS)

        # Aba Tarefas
        self._task_list = QListWidget()
        self._task_list.setStyleSheet("""
            QListWidget {
                background: #0D1117; color: #E6EDF3;
                border: none; font-size: 13px;
            }
            QListWidget::item { padding: 6px 12px; }
            QListWidget::item:selected { background: #1F6FEB22; }
        """)
        tabs.addTab(self._task_list, "📋  Tarefas")

        # Aba Memórias
        self._memory_list = QListWidget()
        self._memory_list.setStyleSheet(self._task_list.styleSheet())
        tabs.addTab(self._memory_list, "🧠  Memórias")

        self._tabs = tabs
        return tabs

    def _build_input_area(self) -> QWidget:
        """Campo de texto + botões enviar/microfone."""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: #0D1117;
                border-top: 1px solid #1E293B;
                border-radius: 0 0 0 16px;
            }
        """)
        container.setFixedHeight(100)

        row = QHBoxLayout(container)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(8)

        # Campo de texto (Enter envia, Shift+Enter nova linha)
        self._input = QTextEdit()
        self._input.setPlaceholderText("Digite uma mensagem...")
        self._input.setStyleSheet(STYLE_INPUT)
        self._input.setFixedHeight(60)
        self._input.installEventFilter(self)
        row.addWidget(self._input)

        # Coluna de botões
        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)

        self._btn_send = QPushButton("↑")
        self._btn_send.setFixedSize(36, 36)
        self._btn_send.setStyleSheet(STYLE_BTN_SEND)
        self._btn_send.setToolTip("Enviar (Enter)")
        self._btn_send.clicked.connect(self._send_message)

        self._btn_mic = QPushButton("🎤")
        self._btn_mic.setFixedSize(36, 36)
        self._btn_mic.setCheckable(True)
        self._btn_mic.setStyleSheet(STYLE_BTN_MIC)
        self._btn_mic.setToolTip("Microfone (em breve)")
        self._btn_mic.clicked.connect(self._toggle_mic)

        self._btn_cafune = QPushButton("🐾")
        self._btn_cafune.setFixedSize(36, 36)
        self._btn_cafune.setToolTip("Cafuné na AURA ♡")
        self._btn_cafune.setStyleSheet("""
            QPushButton {
                background: #2D1B4E; color: #C792EA;
                border: 1px solid #7C3AED; border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover  { background: #3D2B6E; }
            QPushButton:pressed{ background: #1D0B3E; }
        """)
        self._btn_cafune.clicked.connect(self._on_cafune)

        btn_col.addWidget(self._btn_send)
        btn_col.addWidget(self._btn_mic)
        btn_col.addWidget(self._btn_cafune)
        row.addLayout(btn_col)

        return container

    # ── Event filter (Enter no input) ─────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        if obj is self._input and isinstance(event, QKeyEvent):
            if (event.type() == QKeyEvent.Type.KeyPress
                    and event.key() == Qt.Key.Key_Return
                    and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
                self._send_message()
                return True
        return super().eventFilter(obj, event)

    # ── Visibilidade / animação ───────────────────────────────────────────────

    def toggle(self) -> None:
        if self._is_visible:
            self.hide()
        else:
            self.show()
            self._input.setFocus()
        self._is_visible = not self._is_visible

    def show_panel(self) -> None:
        if not self._is_visible:
            self.toggle()

    def hide_panel(self) -> None:
        if self._is_visible:
            self.toggle()

    # ── Envio de mensagem ─────────────────────────────────────────────────────

    def _send_message(self) -> None:
        text = self._input.toPlainText().strip()
        if not text or not self._ai_enabled:
            return

        self._input.clear()
        self._add_bubble(text, "user")

        # Chama o motor de IA (importação local para evitar circular)
        from ai.ai_engine import ai_engine
        ai_engine.process(text)

    def _on_cafune(self) -> None:
        """Botão de cafuné — aumenta afinidade e mostra resposta natural."""
        try:
            from automation.learning_engine import learning_engine
            resp = learning_engine.register_cafune()
            self._add_system_message(f"🐾 {resp}")
            # Muda avatar para animada
            from core.event_bus import bus
            bus.publish("avatar.set_state", state="speaking")
            QTimer.singleShot(3000, lambda: bus.publish("avatar.set_state", state="idle"))
        except Exception as e:
            self._add_system_message("🐾 *aceita o carinho*")

    def _toggle_mic(self) -> None:
        """Liga/desliga gravação de voz."""
        try:
            from voice.voice_manager import voice_manager
            if self._btn_mic.isChecked():
                self._add_system_message("🎤 Ouvindo... fale agora (5s)")
                voice_manager.listen(duration=5.0)
                # Desativa botão após 5.5s
                QTimer.singleShot(5500, lambda: self._btn_mic.setChecked(False))
            else:
                pass
        except Exception as e:
            self._add_system_message(f"🎤 Voz não disponível: {e}")
            self._btn_mic.setChecked(False)

    # ── Adição de mensagens ao histórico ─────────────────────────────────────

    def _add_bubble(self, text: str, role: str) -> None:
        """Adiciona uma bolha de mensagem ao histórico."""
        bubble = MessageBubble(text, role)
        # Insere antes do stretch final
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _add_system_message(self, text: str) -> None:
        self._add_bubble(text, "system")

    def _show_typing(self) -> None:
        """Exibe indicador de digitação."""
        if self._typing_indicator:
            return
        self._typing_indicator = TypingIndicator()
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, self._typing_indicator)
        self._btn_send.setEnabled(False)
        self._ai_enabled = False
        self._status_lbl.setText("Pensando...")
        self._status_lbl.setStyleSheet("color: #CE93D8; font-size: 11px;")
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _hide_typing(self) -> None:
        """Remove indicador de digitação."""
        if self._typing_indicator:
            self._typing_indicator.deleteLater()
            self._typing_indicator = None
        self._btn_send.setEnabled(True)
        self._ai_enabled = True
        self._status_lbl.setText("Online")
        self._status_lbl.setStyleSheet("color: #3FB950; font-size: 11px;")

    def _scroll_to_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── Conexão com EventBus ──────────────────────────────────────────────────

    def _connect_bus(self) -> None:
        bus.subscribe("ai.thinking",      self._on_thinking)
        bus.subscribe("ai.response",      self._on_response)
        bus.subscribe("ai.stream.token",  self._on_stream_token)
        bus.subscribe("ai.stream.done",   self._on_stream_done)
        bus.subscribe("ai.error",         self._on_ai_error)
        bus.subscribe("tool.result",      self._on_tool_result)
        bus.subscribe("tool.confirm_required",    self._on_confirm_required)
        bus.subscribe("flow.started",              self._on_flow_started)
        bus.subscribe("flow.step",                 self._on_flow_step)
        bus.subscribe("flow.done",                 self._on_flow_done)
        bus.subscribe("flow.aborted",              self._on_flow_aborted)
        bus.subscribe("automation.suggestion",     self._on_automation_suggestion)

    def _on_thinking(self, status: bool) -> None:
        if status:
            self._show_typing()
        else:
            self._hide_typing()

    def _on_response(self, text: str) -> None:
        self._hide_typing()
        self._add_bubble(text, "assistant")

    def _on_stream_token(self, token: str) -> None:
        self._hide_typing()
        if not self._streaming_bubble:
            self._streaming_bubble = StreamingBubble()
            self._msg_layout.insertWidget(
                self._msg_layout.count() - 1, self._streaming_bubble
            )
        self._streaming_bubble.append_token(token)
        self._scroll_to_bottom()

    def _on_stream_done(self, full_text: str) -> None:
        if self._streaming_bubble:
            self._streaming_bubble.finalize()
            self._streaming_bubble = None
        self._hide_typing()

    def _on_ai_error(self, error: str) -> None:
        self._hide_typing()
        self._add_system_message(f"⚠️ Erro: {error}")

    def _on_tool_result(self, sucesso: bool, mensagem: str, resultado) -> None:
        icon = "✅" if sucesso else "❌"
        self._add_system_message(f"{icon} {mensagem}")

    def _on_confirm_required(self, intent: dict) -> None:
        """Exibe diálogo de confirmação para ação destrutiva."""
        from ui.confirm_dialog import ConfirmDialog
        from tools.tool_manager import tool_manager
        dialog = ConfirmDialog(intent, self)
        dialog.confirmed.connect(tool_manager.execute_confirmed)
        dialog.rejected_action.connect(
            lambda: self._add_system_message("🚫 Ação cancelada pelo usuário.")
        )
        dialog.exec()

    # ── Atualização de tarefas e memórias ────────────────────────────────────

    # ── Handlers de fluxo e automação ───────────────────────────────────────

    def _on_flow_started(self, descricao: str, total: int) -> None:
        self._add_system_message(f"⚙️ Iniciando: {descricao} ({total} etapa(s))")
        self._flow_step_lbl = None

    def _on_flow_step(self, n: int, total: int, acao: str,
                      descricao: str, status: str, mensagem: str = "") -> None:
        icon = {"executando": "▶️", "ok": "✅", "erro": "❌"}.get(status, "•")
        txt  = f"{icon} [{n}/{total}] {acao}" + (f": {mensagem}" if mensagem else "")
        self._add_system_message(txt)

    def _on_flow_done(self, resultado) -> None:
        if resultado.sucesso:
            self._add_system_message(
                f"✅ Fluxo concluído: {resultado.steps_ok}/{resultado.steps_total} "
                f"etapas em {resultado.duracao_total}s"
            )
        else:
            self._add_system_message(
                f"⚠️ Fluxo finalizado com {resultado.steps_fail} falha(s)"
            )

    def _on_flow_aborted(self, **kw) -> None:
        msg = kw.get("mensagem", "Fluxo interrompido")
        self._add_system_message(f"⛔ {msg}")

    def _on_automation_suggestion(self, sequencia, descricao,
                                  contagem, mensagem) -> None:
        """Exibe botão de sugestão de automação no chat."""
        from PyQt6.QtWidgets import QHBoxLayout, QPushButton

        container = self._make_suggestion_widget(mensagem, sequencia, descricao)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, container)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _make_suggestion_widget(self, mensagem: str, sequencia, descricao: str):
        from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QPushButton

        card = QFrame()
        card.setStyleSheet("""
            QFrame { background: #1A2744; border: 1px solid #4FC3F7;
                     border-radius: 10px; margin: 2px 0; }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        lbl = QLabel(f"💡 {mensagem}")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #E6EDF3; font-size: 13px; background: transparent; border: none;")
        layout.addWidget(lbl)

        row = QHBoxLayout()
        btn_sim = QPushButton("✓  Salvar automação")
        btn_sim.setStyleSheet("""
            QPushButton { background: #1F6FEB; color: #fff; border: none;
                          border-radius: 7px; padding: 6px 14px; font-size: 12px; }
            QPushButton:hover { background: #388BFD; }
        """)
        btn_nao = QPushButton("✕  Não, obrigado")
        btn_nao.setStyleSheet("""
            QPushButton { background: #21262D; color: #8B949E; border: 1px solid #30363D;
                          border-radius: 7px; padding: 6px 14px; font-size: 12px; }
            QPushButton:hover { background: #30363D; color: #E6EDF3; }
        """)

        def _salvar():
            from automation.automation_learner import automation_learner
            nome = descricao.replace(" ", "_").lower()[:30]
            automation_learner.save_as_procedure(nome, sequencia, descricao)
            self._add_system_message(f"✅ Automação '{nome}' salva! Use: 'executar {nome}'")
            card.deleteLater()

        btn_sim.clicked.connect(_salvar)
        btn_nao.clicked.connect(card.deleteLater)
        row.addWidget(btn_sim)
        row.addWidget(btn_nao)
        row.addStretch()
        layout.addLayout(row)
        return card

    def refresh_tasks(self, tasks: list) -> None:
        """Atualiza a lista de tarefas na aba."""
        self._task_list.clear()
        for task in tasks:
            status_icon = {"pendente": "○", "em_progresso": "◐", "concluida": "●", "cancelada": "✕"}.get(
                task.get("status", "pendente"), "○"
            )
            item = QListWidgetItem(f"{status_icon}  {task['titulo']}")
            item.setData(Qt.ItemDataRole.UserRole, task)
            self._task_list.addItem(item)

    def refresh_memories(self, memories: list) -> None:
        """Atualiza a lista de memórias na aba."""
        self._memory_list.clear()
        for mem in memories:
            imp = mem.get("importance", 5)
            star = "★" if imp >= 8 else ("☆" if imp >= 5 else "·")
            self._memory_list.addItem(
                f"{star}  [{mem['categoria']}] {mem['chave']}: {mem['valor']}"
            )

    def set_assistant_name(self, name: str) -> None:
        self._name_lbl.setText(name)
