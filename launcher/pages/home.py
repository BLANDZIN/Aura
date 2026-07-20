"""
launcher/pages/home.py
=====================
Página Inicial do Launcher — Dashboard com status geral do sistema.
Mostra: estado da AURA, modelo ativo, Angela, atalhos rápidos.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


_CARD_STYLE = """
    QFrame#card {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 20px;
    }
"""

_CARD_GOOD = """
    QFrame#card {
        background: #161B22;
        border: 1px solid #1A7F37;
        border-radius: 12px;
        padding: 20px;
    }
"""

_CARD_WARN = """
    QFrame#card {
        background: #161B22;
        border: 1px solid #9E6A03;
        border-radius: 12px;
        padding: 20px;
    }
"""


class HomePage(QWidget):
    """Dashboard principal com status do sistema."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        # ── Boas-vindas ───────────────────────────────────────────────────
        welcome = QLabel("Bem-vindo ao AURA Launcher")
        welcome.setStyleSheet("color: #E2E8F0; font-size: 24px; font-weight: bold;")
        layout.addWidget(welcome)

        sub = QLabel(
            "A partir da V11, toda configuração é feita por aqui. "
            "Nunca mais edite JSON manualmente."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #94A3B8; font-size: 14px; margin-bottom: 8px;")
        layout.addWidget(sub)

        # ── Grid de cards ─────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(16)

        # Card: Status AURA
        self._aura_card = self._make_card(
            "🤖  AURA", "Não iniciada",
            "Clique em 'Iniciar AURA' no menu lateral para começar.",
            _CARD_WARN
        )
        grid.addWidget(self._aura_card, 0, 0)

        # Card: Modelo ativo
        self._model_card = self._make_card(
            "🧠  Modelo Ativo", "Carregando...",
            "Verifique na página Modelos.",
            _CARD_STYLE
        )
        grid.addWidget(self._model_card, 0, 1)

        # Card: Angela
        self._angela_card = self._make_card(
            "🛠  Angela", "Carregando...",
            "Chief Engineer — trabalha nos bastidores.",
            _CARD_STYLE
        )
        grid.addWidget(self._angela_card, 1, 0)

        # Card: Ollama
        self._ollama_card = self._make_card(
            "🦙  Ollama", "Verificando...",
            "Servidor de modelos locais.",
            _CARD_STYLE
        )
        grid.addWidget(self._ollama_card, 1, 1)

        layout.addLayout(grid)

        # ── Atalhos rápidos ───────────────────────────────────────────────
        shortcuts_title = QLabel("Atalhos Rápidos")
        shortcuts_title.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: bold; margin-top: 12px;")
        layout.addWidget(shortcuts_title)

        shortcuts_row = QHBoxLayout()
        shortcuts_row.setSpacing(12)

        shortcuts = [
            ("🧠", "Gerenciar\nModelos", 2),
            ("⚙️", "Configurações", 1),
            ("📊", "Diagnóstico", 5),
            ("💾", "Backup", 6),
        ]

        from launcher.app import LauncherApp

        for icon, label, page_idx in shortcuts:
            btn = QPushButton(f"{icon}\n{label}")
            btn.setMinimumSize(140, 80)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: #161B22;
                    color: #E2E8F0;
                    border: 1px solid #21262D;
                    border-radius: 10px;
                    font-size: 13px;
                    padding: 12px;
                }
                QPushButton:hover {
                    background: #1E293B;
                    border-color: #388BFD;
                }
            """)
            btn.clicked.connect(lambda checked, i=page_idx: self._navigate(i))
            shortcuts_row.addWidget(btn)

        layout.addLayout(shortcuts_row)
        layout.addStretch()

        # Timer para atualizar status
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(3000)

    def _make_card(self, title: str, value: str, desc: str, style: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(style)
        card.setMinimumHeight(120)

        inner = QVBoxLayout(card)
        inner.setSpacing(6)

        t = QLabel(title)
        t.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        inner.addWidget(t)

        v = QLabel(value)
        v.setObjectName("card_value")
        v.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        inner.addWidget(v)

        d = QLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet("color: #64748B; font-size: 12px;")
        inner.addWidget(d)

        return card

    def _navigate(self, page_idx: int):
        """Navega para uma página do launcher."""
        parent = self.window()
        if hasattr(parent, '_pages'):
            parent._pages.setCurrentIndex(page_idx)
            if hasattr(parent, '_nav_buttons') and page_idx < len(parent._nav_buttons):
                for i, btn in enumerate(parent._nav_buttons):
                    btn.setChecked(i == page_idx)

    def on_show(self):
        """Chamado quando a página é exibida."""
        self._refresh_status()

    def _refresh_status(self):
        """Atualiza os status nos cards."""
        import requests

        # ── Ollama ────────────────────────────────────────────────────────
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            if r.status_code == 200:
                models = r.json().get("models", [])
                ollama_val = f"✓ Online ({len(models)} modelos)"
                ollama_style = _CARD_GOOD
            else:
                ollama_val = "Resposta inesperada"
                ollama_style = _CARD_WARN
        except Exception:
            ollama_val = "✗ Offline"
            ollama_style = _CARD_WARN

        self._update_card(self._ollama_card, ollama_val, "Servidor de modelos locais.", ollama_style)

        # ── Modelo ativo ──────────────────────────────────────────────────
        try:
            from config.settings import settings
            model = settings.get("ai", "model", default="qwen2.5:3b")
            model_val = f"✓ {model}"
            model_style = _CARD_GOOD
        except Exception:
            model_val = "Desconhecido"
            model_style = _CARD_WARN

        self._update_card(self._model_card, model_val, "Modelo atualmente selecionado para a AURA.", model_style)

        # ── Angela ────────────────────────────────────────────────────────
        try:
            from config.settings import settings
            angela_model = settings.get("angela", "model", default="qwen3:4b")
            angela_val = f"{angela_model}"
            angela_style = _CARD_GOOD
        except Exception:
            angela_val = "Desconhecido"
            angela_style = _CARD_WARN

        self._update_card(self._angela_card, angela_val, "Modelo da Chief Engineer.", angela_style)

        # ── AURA status ───────────────────────────────────────────────────
        parent = self.window()
        if hasattr(parent, '_aura_running') and parent._aura_running:
            self._update_card(self._aura_card, "✓ Rodando", "AURA está ativa em segundo plano.", _CARD_GOOD)
        else:
            self._update_card(self._aura_card, "Parada", "Clique em 'Iniciar AURA' para começar.", _CARD_WARN)

    def _update_card(self, card: QFrame, value: str, desc: str, style: str):
        """Atualiza o texto de um card."""
        card.setStyleSheet(style)
        val_lbl = card.findChild(QLabel, "card_value")
        if val_lbl:
            val_lbl.setText(value)
        # Atualiza a descrição (terceiro label)
        labels = card.findChildren(QLabel)
        if len(labels) >= 3:
            labels[2].setText(desc)
