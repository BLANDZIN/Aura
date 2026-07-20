"""
ui/monitor_page.py
==================
Painel de monitoramento em tempo real.
CPU, RAM, tokens/s, tempo de resposta, eventos, fila de tarefas.
"""

import time
from collections import deque

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QGridLayout, QProgressBar,
    QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


_CARD = """
    QFrame#mon_card {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 16px;
    }
"""


class MonitorPage(QWidget):
    """Painel de monitoramento em tempo real."""

    def __init__(self, parent=None, metrics: dict = None):
        super().__init__(parent)
        self._metrics = metrics or {}
        self._event_log = deque(maxlen=50)
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Título
        title = QLabel("📊  Monitor")
        title.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        sub = QLabel("Painel de observabilidade em tempo real.")
        sub.setStyleSheet("color: #94A3B8; font-size: 13px;")
        layout.addWidget(sub)

        # Grid de métricas
        grid = QGridLayout()
        grid.setSpacing(12)

        self._cards = {}

        for i, (key, title_str, fmt) in enumerate([
            ("cpu", "CPU", "{}%"),
            ("ram", "RAM", "{:.1f} GB"),
            ("tokens_s", "Tokens/s", "{}"),
            ("response_time", "Tempo Médio", "{:.1f}s"),
            ("memories_count", "Memórias", "{}"),
            ("tasks_pending", "Tarefas Pendentes", "{}"),
            ("procedures_count", "Procedimentos", "{}"),
            ("plugins_count", "Plugins", "{}"),
        ]):
            card = self._make_card(title_str, "--")
            self._cards[key] = card
            row, col = divmod(i, 4)
            grid.addWidget(card, row, col)

        layout.addLayout(grid)

        # Barras de uso
        bars_layout = QHBoxLayout()
        bars_layout.setSpacing(16)

        self._cpu_bar = QProgressBar()
        self._cpu_bar.setStyleSheet("""
            QProgressBar { background: #21262D; border-radius: 6px; height: 20px; text-align: center; color: #E2E8F0; font-size: 11px; }
            QProgressBar::chunk { background: #1F6FEB; border-radius: 6px; }
        """)
        bars_layout.addWidget(self._cpu_bar)

        self._ram_bar = QProgressBar()
        self._ram_bar.setStyleSheet("""
            QProgressBar { background: #21262D; border-radius: 6px; height: 20px; text-align: center; color: #E2E8F0; font-size: 11px; }
            QProgressBar::chunk { background: #1A7F37; border-radius: 6px; }
        """)
        bars_layout.addWidget(self._ram_bar)

        layout.addLayout(bars_layout)

        # Log de eventos
        evt_label = QLabel("Eventos Recentes")
        evt_label.setStyleSheet("color: #E2E8F0; font-size: 14px; font-weight: bold;")
        layout.addWidget(evt_label)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet("""
            QTextEdit {
                background: #0B0F14; color: #94A3B8;
                border: 1px solid #1E293B; border-radius: 8px;
                font-family: 'Consolas', monospace; font-size: 11px;
                padding: 10px;
            }
        """)
        self._log.setMaximumHeight(180)
        layout.addWidget(self._log)

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

    def _make_card(self, title: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("mon_card")
        card.setStyleSheet(_CARD)

        inner = QVBoxLayout(card)
        inner.setSpacing(4)

        t = QLabel(title)
        t.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600;")
        inner.addWidget(t)

        v = QLabel(value)
        v.setObjectName("val")
        v.setStyleSheet("color: #E2E8F0; font-size: 22px; font-weight: bold;")
        inner.addWidget(v)

        return card

    def _refresh(self):
        """Atualiza valores dos cards."""
        m = self._metrics

        self._update_card("cpu", f"{m.get('cpu', 0):.0f}%")
        self._update_card("ram", f"{m.get('ram', 0):.1f} GB")
        self._update_card("tokens_s", f"{m.get('tokens_s', 0)}")
        self._update_card("response_time", f"{m.get('response_time', 0):.1f}s")
        self._update_card("memories_count", str(m.get("memories_count", 0)))
        self._update_card("tasks_pending", str(m.get("tasks_pending", 0)))
        self._update_card("procedures_count", str(m.get("procedures_count", 0)))
        self._update_card("plugins_count", str(m.get("plugins_count", 0)))

        # Barras
        self._cpu_bar.setValue(int(m.get("cpu", 0)))
        self._cpu_bar.setFormat(f"CPU: {m.get('cpu', 0):.0f}%")

        ram_pct = 0
        if m.get("ram_total", 1) > 0:
            ram_pct = int(m.get("ram", 0) / m.get("ram_total", 1) * 100)
        self._ram_bar.setValue(min(ram_pct, 100))
        self._ram_bar.setFormat(f"RAM: {m.get('ram', 0):.1f}/{m.get('ram_total', 1):.1f} GB")

    def _update_card(self, key: str, value: str):
        card = self._cards.get(key)
        if card:
            val = card.findChild(QLabel, "val")
            if val:
                val.setText(value)
