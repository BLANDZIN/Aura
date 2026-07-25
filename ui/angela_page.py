"""
ui/angela_page.py
=================
Página dedicada à Angela (Chief Engineer) integrada na janela principal.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.event_bus import bus
from core.logger import setup_logger
from angela.communication import Topics
from angela.personality import PERSONA

logger = setup_logger("angela_page")


class AngelaPage(QWidget):
    """Página da Chief Engineer."""

    request_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._wire_events()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header
        header = QLabel("🛠  Angela — Chief Engineer")
        header.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        layout.addWidget(header)

        sub = QLabel(
            "Engenheira-Chefe. Analisa código, investiga bugs, audita o projeto. "
            "Nunca aplica alterações sem confirmação."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #94A3B8; font-size: 13px;")
        layout.addWidget(sub)

        # Transcript
        self._transcript = QTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setStyleSheet("""
            QTextEdit {
                background: #0B0F14; color: #E6EDF3;
                border: 1px solid #1E293B; border-radius: 10px;
                font-family: 'Consolas', 'Menlo', monospace;
                font-size: 12px; padding: 14px;
            }
        """)
        self._transcript.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._transcript, 1)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ex.: 'analise o Learning Engine', 'adicione OCR', 'planeje v11'...")
        self._input.setStyleSheet("""
            QLineEdit {
                background: #161B22; color: #E6EDF0;
                border: 1px solid #334155; border-radius: 10px;
                padding: 12px 16px; font-size: 14px;
            }
            QLineEdit:focus { border-color: #388BFD; }
        """)
        self._input.returnPressed.connect(self._on_submit)
        input_row.addWidget(self._input, 1)

        send = QPushButton("Enviar")
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet("""
            QPushButton {
                background: #1F6FEB; color: #fff;
                border: none; border-radius: 10px;
                padding: 12px 20px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background: #388BFD; }
        """)
        send.clicked.connect(self._on_submit)
        input_row.addWidget(send)

        audit = QPushButton("Auditoria Completa")
        audit.setCursor(Qt.CursorShape.PointingHandCursor)
        audit.setStyleSheet("""
            QPushButton {
                background: #0F766E; color: #fff;
                border: none; border-radius: 10px;
                padding: 12px 20px; font-size: 14px;
            }
            QPushButton:hover { background: #14857D; }
        """)
        audit.clicked.connect(self._on_audit)
        input_row.addWidget(audit)

        layout.addLayout(input_row)

        self._append_system("Angela pronta. Diga o que precisa.")

    def _wire_events(self):
        bus.subscribe(Topics.ACKNOWLEDGED, self._on_ack)
        bus.subscribe(Topics.STEP,         self._on_step)
        bus.subscribe(Topics.REPORT,       self._on_report)
        bus.subscribe(Topics.FAILED,       self._on_failed)

    def _on_submit(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._append_user(text)
        bus.publish(Topics.REQUEST, text=text)

    def _on_audit(self):
        self._append_user("Auditoria completa do projeto.")
        bus.publish(Topics.REQUEST, text="auditoria completa")

    def _on_ack(self, message: str, **_):
        self._append_angela(message)

    def _on_step(self, step: str, **_):
        self._append_step(step)

    def _on_report(self, report, **_):
        try:
            md = report.to_markdown()
        except Exception:
            md = str(report)
        self._append_angela(md)

    def _on_failed(self, error: str, **_):
        self._append_angela(f"⚠️ Investigação abortou: {error}")

    def _append_user(self, text):
        self._transcript.append(
            f"<div style='color:#93C5FD'><b>Você:</b> {text}</div>"
        )

    def _append_angela(self, text):
        safe = text.replace("\n", "<br>")
        self._transcript.append(
            f"<div style='color:#E6EDF3'><b style='color:#7DD3FC'>Angela:</b><br>{safe}</div><br>"
        )

    def _append_step(self, step):
        self._transcript.append(
            f"<div style='color:#64748B'>· {step}</div>"
        )

    def _append_system(self, text):
        self._transcript.append(
            f"<div style='color:#64748B; font-style:italic'>{text}</div>"
        )
