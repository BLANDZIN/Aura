"""
ui/confirm_dialog.py
Diálogo de confirmação para ações destrutivas do AURA.

Exibido sempre que:
  - Uma ferramenta tem "confirmacao_necessaria": true
  - A ação está na lista de REQUIRES_CONFIRM do ToolManager
  - O usuário precisa aprovar antes da execução

Emite: confirmed(intent) | rejected()
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from typing import Dict, Any
from core.logger import setup_logger

logger = setup_logger("confirm_dialog")

# Ícones e cores por tipo de ação
ACTION_META = {
    "excluir_arquivo":    ("🗑️",  "#EF5350", "Excluir arquivo"),
    "fechar_programa":    ("⛔",  "#FF7043", "Fechar programa"),
    "digitar_texto":      ("⌨️",  "#FFA726", "Digitar no teclado"),
    "clicar_mouse":       ("🖱️",  "#FFA726", "Clicar na tela"),
    "mover_arquivo":      ("📂",  "#42A5F5", "Mover arquivo"),
    "copiar_arquivo":     ("📋",  "#42A5F5", "Copiar arquivo"),
}
_DEFAULT_META = ("⚠️", "#FFCA28", "Ação no sistema")


class ConfirmDialog(QDialog):
    """
    Diálogo modal de confirmação.

    Uso:
        dialog = ConfirmDialog(intent, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            tool_manager.execute_confirmed(intent)
    """

    confirmed = pyqtSignal(dict)
    rejected_action = pyqtSignal()

    def __init__(self, intent: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._intent = intent
        self._setup_ui()

    def _setup_ui(self) -> None:
        acao = self._intent.get("acao", "acao_desconhecida")
        params = self._intent.get("parametros", {})
        mensagem = self._intent.get("mensagem", "")

        icon, color, label = ACTION_META.get(acao, _DEFAULT_META)

        self.setWindowTitle("AURA — Confirmação")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(360)

        # ── Layout principal ──────────────────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Card com fundo escuro
        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QFrame#card {{
                background-color: #1A1F2E;
                border: 1px solid {color};
                border-radius: 14px;
            }}
        """)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        header = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 28))
        icon_lbl.setFixedWidth(48)

        title_col = QVBoxLayout()
        title_lbl = QLabel(label)
        title_lbl.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: bold;")
        action_lbl = QLabel(f"<code style='color:#90A4AE'>{acao}</code>")
        action_lbl.setTextFormat(Qt.TextFormat.RichText)
        title_col.addWidget(title_lbl)
        title_col.addWidget(action_lbl)

        header.addWidget(icon_lbl)
        header.addLayout(title_col)
        header.addStretch()
        layout.addLayout(header)

        # ── Separador ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {color}; background: {color}; max-height: 1px; opacity: 0.3;")
        layout.addWidget(sep)

        # ── Mensagem da IA ────────────────────────────────────────────────────
        if mensagem:
            msg_lbl = QLabel(f'"{mensagem}"')
            msg_lbl.setStyleSheet("color: #CFD8DC; font-size: 13px; font-style: italic;")
            msg_lbl.setWordWrap(True)
            layout.addWidget(msg_lbl)

        # ── Parâmetros formatados ─────────────────────────────────────────────
        if params:
            params_text = "\n".join(
                f"  • <b>{k}</b>: {v}" for k, v in params.items()
            )
            params_lbl = QLabel(params_text)
            params_lbl.setTextFormat(Qt.TextFormat.RichText)
            params_lbl.setStyleSheet(
                "color: #B0BEC5; font-size: 12px; "
                "background: #0D1117; border-radius: 8px; padding: 10px;"
            )
            params_lbl.setWordWrap(True)
            layout.addWidget(params_lbl)

        # ── Pergunta de confirmação ───────────────────────────────────────────
        question = QLabel("Deseja prosseguir com esta ação?")
        question.setStyleSheet("color: #ECEFF1; font-size: 13px;")
        question.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(question)

        # ── Botões ────────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_cancel = QPushButton("✕  Cancelar")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #263238; color: #90A4AE;
                border: 1px solid #37474F; border-radius: 8px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: #37474F; color: #ECEFF1; }
        """)
        btn_cancel.clicked.connect(self._on_reject)

        btn_confirm = QPushButton(f"✓  Confirmar")
        btn_confirm.setFixedHeight(38)
        btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background: {color}22; color: {color};
                border: 1px solid {color}; border-radius: 8px;
                font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {color}44; }}
        """)
        btn_confirm.clicked.connect(self._on_confirm)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_confirm)
        layout.addLayout(btn_row)

    def _on_confirm(self) -> None:
        logger.info(f"Ação confirmada: {self._intent.get('acao')}")
        self.confirmed.emit(self._intent)
        self.accept()

    def _on_reject(self) -> None:
        logger.info(f"Ação rejeitada: {self._intent.get('acao')}")
        self.rejected_action.emit()
        self.reject()
