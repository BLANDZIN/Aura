"""
launcher/pages/_widgets.py — AURA V11
=====================================
Componentes de UI compartilhados por todas as paginas do Launcher.

Centraliza estilos, botoes, cards e layouts para evitar duplicacao
entre as 7 paginas (backup, diagnostics, extensions, home, models,
profiles, settings, updates).
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
)
from PyQt6.QtCore import Qt

# ═══════════════ STYLES ═══════════════

CARD_STYLE = """
    QFrame#card {{
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 16px;
    }}
"""

CARD_ACTIVE_STYLE = """
    QFrame#card {{
        background: #0D2B1F;
        border: 1px solid #1A7F37;
        border-radius: 12px;
        padding: 16px;
    }}
"""

BTN_PRIMARY_STYLE = """
    QPushButton {{
        background: #1F6FEB; color: #fff;
        border: none; border-radius: 8px;
        padding: 8px 16px; font-size: 13px;
    }}
    QPushButton:hover {{ background: #388BFD; }}
    QPushButton:disabled {{ background: #21262D; color: #484F58; }}
"""

BTN_SECONDARY_STYLE = """
    QPushButton {{
        background: #21262D; color: #E2E8F0;
        border: 1px solid #30363D; border-radius: 8px;
        padding: 8px 16px; font-size: 13px;
    }}
    QPushButton:hover {{ background: #30363D; }}
"""

BTN_DANGER_STYLE = """
    QPushButton {{
        background: #DA3633; color: #fff;
        border: none; border-radius: 8px;
        padding: 8px 16px; font-size: 13px;
    }}
    QPushButton:hover {{ background: #F85149; }}
"""

TITLE_STYLE = "color: #E2E8F0; font-size: 20px; font-weight: bold;"
SUBTITLE_STYLE = "color: #64748B; font-size: 13px;"
SECTION_STYLE = "color: #E2E8F0; font-size: 16px; font-weight: bold;"

# ═══════════════ FACTORY FUNCTIONS ═══════════════

def make_card() -> QFrame:
    """Cria um QFrame com estilo de card padrao do Launcher."""
    card = QFrame()
    card.setObjectName("card")
    card.setStyleSheet(CARD_STYLE)
    return card


def make_title(text: str) -> QLabel:
    """Titulo de pagina padrao."""
    lbl = QLabel(text)
    lbl.setStyleSheet(TITLE_STYLE)
    return lbl


def make_subtitle(text: str) -> QLabel:
    """Subtitulo descritivo."""
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(SUBTITLE_STYLE)
    return lbl


def make_btn_primary(text: str) -> QPushButton:
    """Botao azul primario."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(BTN_PRIMARY_STYLE)
    return btn


def make_btn_secondary(text: str) -> QPushButton:
    """Botao cinza secundario."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(BTN_SECONDARY_STYLE)
    return btn


def make_btn_danger(text: str) -> QPushButton:
    """Botao vermelho (excluir, remover)."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(BTN_DANGER_STYLE)
    return btn


def make_metric_card(title_text: str, value_text: str) -> tuple:
    """Cria um card de metrica com titulo + valor. Retorna (card, value_label)."""
    card = make_card()
    inner = QVBoxLayout(card)
    inner.setSpacing(4)

    t = QLabel(title_text)
    t.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600;")
    inner.addWidget(t)

    v = QLabel(value_text)
    v.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
    inner.addWidget(v)

    return card, v


def make_header_row(title: str) -> tuple:
    """Linha de cabecalho: titulo + stretch. Retorna (layout, title_label)."""
    row = QHBoxLayout()
    lbl = make_title(title)
    row.addWidget(lbl)
    row.addStretch()
    return row, lbl
