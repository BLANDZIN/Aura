"""
ui/angela_panel.py
Painel dedicado à Angela — Chief Engineer.

Aparece via botão exclusivo (🛠 Angela). Não substitui o ChatPanel da
AURA. Aqui o usuário pode:

  - Conversar diretamente com Angela ("adicione OCR", "audite tudo")
  - Ver o progresso do workflow em tempo real
  - Ler o relatório final
  - Aprovar/rejeitar patches propostos
  - Disparar auditoria completa

Comunicação exclusiva via EventBus.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from angela.communication import Topics
from angela.personality import PERSONA
from core.event_bus import bus
from core.logger import setup_logger

logger = setup_logger("ui.angela_panel")


_STYLE = """
QDialog {
    background-color: #0B0F14;
    color: #E6EDF3;
}
QLabel#header {
    color: #7DD3FC;
    font-size: 16px;
    font-weight: 600;
}
QLabel#sub {
    color: #64748B;
    font-size: 11px;
}
QTextEdit {
    background: #0D1117;
    border: 1px solid #1E293B;
    border-radius: 8px;
    color: #E6EDF3;
    font-family: 'Consolas', 'Menlo', monospace;
    font-size: 12px;
    padding: 10px;
}
QLineEdit {
    background: #161B22;
    border: 1px solid #21262D;
    border-radius: 8px;
    color: #E6EDF3;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus { border-color: #7DD3FC; }
QPushButton {
    background: #1E3A5F;
    color: #E6EDF3;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 13px;
}
QPushButton:hover { background: #2A4E7F; }
QPushButton#audit { background: #0F766E; }
QPushButton#audit:hover { background: #14857D; }
"""


class AngelaPanel(QDialog):
    """Painel modal-less para conversar com a Angela."""

    request_ready = pyqtSignal(str)  # emitido quando o usuário aperta Enter

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"{PERSONA.display}")
        self.setModal(False)
        self.setMinimumSize(720, 560)
        self.setStyleSheet(_STYLE)
        self._build_ui()
        self._wire_events()

    # ── construção da UI ─────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        header = QLabel(PERSONA.display)
        header.setObjectName("header")
        sub = QLabel(
            "Engenheira-Chefe. Trabalha nos bastidores. "
            "Nunca aplica alterações sem sua confirmação."
        )
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        root.addWidget(header)
        root.addWidget(sub)

        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self.transcript, 1)

        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Ex.: 'analise o Learning Engine', 'adicione OCR', 'planeje v10'…"
        )
        self.input.returnPressed.connect(self._on_submit)
        input_row.addWidget(self.input, 1)

        send = QPushButton("Enviar")
        send.clicked.connect(self._on_submit)
        input_row.addWidget(send)

        audit = QPushButton("Auditoria completa")
        audit.setObjectName("audit")
        audit.clicked.connect(self._on_audit)
        input_row.addWidget(audit)
        root.addLayout(input_row)

        self._append_system(
            "Angela pronta. Diga o que precisa e ela seguirá o "
            "processo obrigatório de 12 passos antes de responder."
        )

    # ── eventos ──────────────────────────────────────────────────────
    def _wire_events(self) -> None:
        bus.subscribe(Topics.ACKNOWLEDGED, self._on_ack)
        bus.subscribe(Topics.STEP,         self._on_step)
        bus.subscribe(Topics.REPORT,       self._on_report)
        bus.subscribe(Topics.FAILED,       self._on_failed)

    def closeEvent(self, ev) -> None:  # noqa: N802
        for topic, cb in [
            (Topics.ACKNOWLEDGED, self._on_ack),
            (Topics.STEP,         self._on_step),
            (Topics.REPORT,       self._on_report),
            (Topics.FAILED,       self._on_failed),
        ]:
            try:
                bus.unsubscribe(topic, cb)
            except Exception:
                pass
        super().closeEvent(ev)

    # ── handlers ────────────────────────────────────────────────────
    def _on_submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._append_user(text)
        self.request_ready.emit(text)
        # Angela também pode ouvir direto:
        bus.publish(Topics.REQUEST, text=text)

    def _on_audit(self) -> None:
        self._append_user("Auditoria completa do projeto.")
        # Deixamos AuraApp orquestrar (para acessar a instância viva)
        self.request_ready.emit("__AUDIT__")

    def _on_ack(self, message: str, **_) -> None:
        self._append_angela(message)

    def _on_step(self, step: str, **_) -> None:
        self._append_step(step)

    def _on_report(self, report, **_) -> None:
        try:
            md = report.to_markdown()
        except Exception:
            md = str(report)
        self._append_angela(md)

    def _on_failed(self, error: str, **_) -> None:
        self._append_angela(f"⚠️ Investigação abortou: {error}")

    # ── renderização ────────────────────────────────────────────────
    def _append_user(self, text: str) -> None:
        self.transcript.append(
            f"<div style='color:#93C5FD'><b>Você:</b> {text}</div>"
        )

    def _append_angela(self, text: str) -> None:
        safe = text.replace("\n", "<br>")
        self.transcript.append(
            f"<div style='color:#E6EDF3'>"
            f"<b style='color:#7DD3FC'>Angela:</b><br>{safe}</div><br>"
        )

    def _append_step(self, step: str) -> None:
        self.transcript.append(
            f"<div style='color:#64748B'>· {step}</div>"
        )

    def _append_system(self, text: str) -> None:
        self.transcript.append(
            f"<div style='color:#64748B; font-style:italic'>{text}</div>"
        )

    def append_audit_result(self, markdown: str) -> None:
        self._append_angela(markdown)
