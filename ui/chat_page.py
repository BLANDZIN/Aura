"""
ui/chat_page.py
===============
Página de Chat embutida na janela principal da AURA V11.

Substitui o antigo ChatPanel flutuante por uma experiência integrada.
Reutiliza MessageBubble, StreamingBubble e TypingIndicator do chat_panel.py.
"""

import time
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QTextEdit,
    QSizePolicy, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent

from core.event_bus import bus
from core.logger import setup_logger

logger = setup_logger("chat_page")

# Reutiliza os mesmos widgets visuais do chat_panel.py
from ui.chat_panel import MessageBubble, StreamingBubble, TypingIndicator

# ── Estilos adaptados para integração ─────────────────────────────────────────

STYLE_INPUT = """
    QTextEdit {
        background: #161B22; color: #E6EDF3;
        border: 1px solid #334155; border-radius: 12px;
        padding: 14px 18px; font-size: 14px;
        selection-background-color: #1F6FEB;
    }
    QTextEdit:focus { border-color: #388BFD; }
"""

STYLE_SEND = """
    QPushButton {
        background: #1F6FEB; color: #fff;
        border: none; border-radius: 12px;
        font-size: 20px; font-weight: bold;
        min-width: 48px; min-height: 48px;
    }
    QPushButton:hover  { background: #388BFD; }
    QPushButton:pressed{ background: #0D4A9E; }
    QPushButton:disabled { background: #21262D; color: #484F58; }
"""


class ChatPage(QWidget):
    """
    Página de chat integrada. Sempre visível, ocupa toda a área.
    Comporta-se como um chat moderno: histórico, input, indicadores.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._streaming_bubble: Optional[StreamingBubble] = None
        self._typing_indicator: Optional[TypingIndicator] = None
        self._ai_enabled = True
        self._response_count = 0
        self._last_response_time = 0

        self._build_ui()
        self._connect_bus()

        logger.info("ChatPage iniciada")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Área de mensagens ──────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #0D1117; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #1E3A5F; border-radius: 3px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(32, 24, 32, 12)
        self._msg_layout.setSpacing(10)
        self._msg_layout.addStretch()

        self._scroll.setWidget(self._msg_container)
        layout.addWidget(self._scroll, 1)

        # ── Barra de input ─────────────────────────────────────────────────
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background: #0D1117;
                border-top: 1px solid #1E293B;
            }
        """)
        input_frame.setMinimumHeight(80)
        input_frame.setMaximumHeight(120)

        input_row = QHBoxLayout(input_frame)
        input_row.setContentsMargins(24, 12, 24, 12)
        input_row.setSpacing(12)

        # Texto
        self._input = QTextEdit()
        self._input.setPlaceholderText("Digite sua mensagem... (Enter = enviar, Shift+Enter = nova linha)")
        self._input.setStyleSheet(STYLE_INPUT)
        self._input.installEventFilter(self)
        self._input.setMaximumHeight(90)
        input_row.addWidget(self._input, 1)

        # Botão enviar
        self._btn_send = QPushButton("↑")
        self._btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_send.setStyleSheet(STYLE_SEND)
        self._btn_send.setToolTip("Enviar (Enter)")
        self._btn_send.clicked.connect(self._send_message)
        input_row.addWidget(self._btn_send)

        # Microfone
        self._btn_mic = QPushButton("🎤")
        self._btn_mic.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_mic.setCheckable(True)
        self._btn_mic.setFixedSize(48, 48)
        self._btn_mic.setStyleSheet("""
            QPushButton {
                background: #21262D; color: #8B949E;
                border: 1px solid #30363D; border-radius: 12px;
                font-size: 20px;
            }
            QPushButton:hover  { background: #30363D; color: #E6EDF3; }
            QPushButton:checked { background: #3D1F1F; color: #EF5350; border-color: #EF5350; }
        """)
        self._btn_mic.clicked.connect(self._toggle_mic)
        input_row.addWidget(self._btn_mic)

        layout.addWidget(input_frame)

    # ══════════════════════════════════════════════════════════════════════
    # Foco
    # ══════════════════════════════════════════════════════════════════════

    def focus_input(self):
        """Dá foco ao campo de input."""
        self._input.setFocus()

    # ══════════════════════════════════════════════════════════════════════
    # Event Filter (Enter)
    # ══════════════════════════════════════════════════════════════════════

    def eventFilter(self, obj, event) -> bool:
        if obj is self._input and isinstance(event, QKeyEvent):
            if (event.type() == QKeyEvent.Type.KeyPress
                    and event.key() == Qt.Key.Key_Return
                    and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
                self._send_message()
                return True
        return super().eventFilter(obj, event)

    # ══════════════════════════════════════════════════════════════════════
    # Envio de mensagem
    # ══════════════════════════════════════════════════════════════════════

    def _send_message(self):
        text = self._input.toPlainText().strip()
        if not text or not self._ai_enabled:
            return

        self._input.clear()
        self._add_bubble(text, "user")

        from ai.ai_engine import ai_engine
        self._last_response_time = time.time()
        ai_engine.process(text)

    def _toggle_mic(self):
        """Gravação de voz."""
        try:
            from voice.voice_manager import voice_manager
            if self._btn_mic.isChecked():
                self._add_system_message("🎤 Ouvindo... fale agora")
                voice_manager.listen(duration=5.0)
                QTimer.singleShot(5500, lambda: self._btn_mic.setChecked(False))
        except Exception:
            self._add_system_message("🎤 Voz não disponível")
            self._btn_mic.setChecked(False)

    # ══════════════════════════════════════════════════════════════════════
    # Mensagens
    # ══════════════════════════════════════════════════════════════════════

    def _add_bubble(self, text: str, role: str) -> None:
        bubble = MessageBubble(text, role)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _add_system_message(self, text: str):
        self._add_bubble(text, "system")

    def _show_typing(self):
        if self._typing_indicator:
            return
        self._typing_indicator = TypingIndicator()
        self._msg_layout.insertWidget(
            self._msg_layout.count() - 1, self._typing_indicator
        )
        self._btn_send.setEnabled(False)
        self._ai_enabled = False
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _hide_typing(self):
        if self._typing_indicator:
            self._typing_indicator.deleteLater()
            self._typing_indicator = None
        self._btn_send.setEnabled(True)
        self._ai_enabled = True

    def _scroll_to_bottom(self):
        sb = self._scroll.verticalScrollBar()
        QTimer.singleShot(30, lambda: sb.setValue(sb.maximum()))

    # ══════════════════════════════════════════════════════════════════════
    # EventBus
    # ══════════════════════════════════════════════════════════════════════

    def _connect_bus(self):
        bus.subscribe("ai.thinking",           self._on_thinking)
        bus.subscribe("ai.response",           self._on_response)
        bus.subscribe("ai.stream.token",       self._on_stream_token)
        bus.subscribe("ai.stream.done",        self._on_stream_done)
        bus.subscribe("ai.error",              self._on_error)
        bus.subscribe("tool.result",           self._on_tool_result)
        bus.subscribe("tool.confirm_required", self._on_confirm)
        bus.subscribe("flow.started",          self._on_flow_started)
        bus.subscribe("flow.step",             self._on_flow_step)
        bus.subscribe("flow.done",             self._on_flow_done)
        bus.subscribe("automation.suggestion", self._on_suggestion)

    def _on_thinking(self, status: bool):
        if status:
            self._show_typing()
        else:
            self._hide_typing()

    def _on_response(self, text: str):
        elapsed = time.time() - self._last_response_time if self._last_response_time else 0
        self._hide_typing()
        self._response_count += 1

        # Mostra tempo e modelo
        try:
            from config.settings import settings
            model = settings.get("ai", "model", default="?")
            meta = f"🧠 {model}  ·  ⏱ {elapsed:.1f}s"
        except Exception:
            meta = f"⏱ {elapsed:.1f}s"

        self._add_bubble(text, "assistant")
        self._add_system_message(meta)

    def _on_stream_token(self, token: str):
        self._hide_typing()
        if not self._streaming_bubble:
            self._streaming_bubble = StreamingBubble()
            self._msg_layout.insertWidget(
                self._msg_layout.count() - 1, self._streaming_bubble
            )
        self._streaming_bubble.append_token(token)
        self._scroll_to_bottom()

    def _on_stream_done(self, full_text: str):
        if self._streaming_bubble:
            self._streaming_bubble.finalize()
            self._streaming_bubble = None

        elapsed = time.time() - self._last_response_time if self._last_response_time else 0
        self._add_system_message(f"⏱ {elapsed:.1f}s")
        self._hide_typing()

    def _on_error(self, error: str):
        self._hide_typing()
        self._add_system_message(f"⚠️ {error}")

    def _on_tool_result(self, sucesso: bool, mensagem: str, resultado):
        icon = "✅" if sucesso else "❌"
        self._add_system_message(f"{icon} {mensagem}")

    def _on_confirm(self, intent: dict):
        from ui.confirm_dialog import ConfirmDialog
        from tools.tool_manager import tool_manager
        dialog = ConfirmDialog(intent, self)
        dialog.confirmed.connect(tool_manager.execute_confirmed)
        dialog.rejected_action.connect(
            lambda: self._add_system_message("🚫 Ação cancelada")
        )
        dialog.exec()

    def _on_flow_started(self, descricao: str, total: int):
        self._add_system_message(f"⚙️ Iniciando: {descricao} ({total} etapa(s))")

    def _on_flow_step(self, n: int, total: int, acao: str,
                      descricao: str = "", status: str = "", mensagem: str = ""):
        icons = {"executando": "▶️", "ok": "✅", "erro": "❌"}
        icon = icons.get(status, "•")
        txt = f"{icon} [{n}/{total}] {acao}"
        if mensagem:
            txt += f": {mensagem}"
        self._add_system_message(txt)

    def _on_flow_done(self, resultado):
        if resultado.sucesso:
            self._add_system_message(
                f"✅ Concluído: {resultado.steps_ok}/{resultado.steps_total} "
                f"etapas em {resultado.duracao_total}s"
            )
        else:
            self._add_system_message(
                f"⚠️ Fluxo com {resultado.steps_fail} falha(s)"
            )

    def _on_suggestion(self, sequencia, descricao, contagem, mensagem):
        self._add_system_message(f"💡 {mensagem}")
