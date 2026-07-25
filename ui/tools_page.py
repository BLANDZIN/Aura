"""
ui/tools_page.py
================
Página de Ferramentas — Lista todas as ferramentas com status.
Agrupadas por categoria: Arquivos, Sistema, Navegador, Controle, etc.
"""

import time
from typing import Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from core.logger import setup_logger

logger = setup_logger("tools_page")


CATEGORY_ICONS = {
    "Arquivos":      "📁",
    "Sistema":       "🖥️",
    "Navegador":     "🌐",
    "Pesquisa":      "🔍",
    "Controle":      "⌨️",
    "OCR":           "👁️",
    "Procedimentos": "🔁",
    "Tarefas":       "✅",
    "Memória":       "🧠",
}

TOOL_CATEGORIES = {
    "Arquivos": [
        "criar_pasta", "abrir_pasta", "abrir_arquivo",
        "renomear_arquivo", "copiar_arquivo", "mover_arquivo",
        "excluir_arquivo", "pesquisar_arquivo",
    ],
    "Sistema": [
        "abrir_programa", "fechar_programa",
        "obter_cpu", "obter_ram", "obter_bateria", "obter_metricas",
    ],
    "Navegador": [
        "abrir_site", "pesquisar_web", "pesquisar_youtube", "pesquisar_site",
    ],
    "Pesquisa":      ["pesquisar_resposta"],
    "Controle": [
        "capturar_tela", "mover_mouse", "clicar_mouse",
        "digitar_texto", "pressionar_tecla", "atalho_teclado",
        "rolar_pagina", "esperar", "copiar_area_transf", "escrever_area_transf",
    ],
    "OCR":           ["ler_tela"],
    "Procedimentos": ["salvar_procedimento", "executar_procedimento", "listar_procedimentos"],
    "Tarefas":       ["criar_tarefa", "listar_tarefas", "concluir_tarefa"],
    "Memória":       ["salvar_memoria", "buscar_memoria"],
}


class ToolsPage(QWidget):
    """Página de visualização e gerenciamento de ferramentas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_tools()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(24, 20, 24, 20)
        self._layout.setSpacing(20)

        title = QLabel("🔧  Ferramentas")
        title.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        self._layout.addWidget(title)

        sub = QLabel("Todas as ferramentas disponíveis, agrupadas por categoria.")
        sub.setStyleSheet("color: #94A3B8; font-size: 13px;")
        self._layout.addWidget(sub)

        self._layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

    def _load_tools(self):
        """Carrega a lista de ferramentas do ToolManager."""
        try:
            from tools.tool_manager import tool_manager
            tools = tool_manager.list_tools()
        except Exception as e:
            logger.error(f"Erro ao carregar ferramentas: {e}")
            tools = []

        # Agrupa por categoria
        tool_map = {t["nome"]: t for t in tools}

        for cat, names in TOOL_CATEGORIES.items():
            section = self._make_category_section(cat, names, tool_map)
            # Insere antes do stretch
            self._layout.insertWidget(self._layout.count() - 1, section)

    def _make_category_section(self, cat: str, names: list, tool_map: dict) -> QWidget:
        icon = CATEGORY_ICONS.get(cat, "📦")
        section = QFrame()
        section.setStyleSheet("""
            QFrame {
                background: #161B22;
                border: 1px solid #21262D;
                border-radius: 12px;
                padding: 16px;
            }
        """)

        layout = QVBoxLayout(section)
        layout.setSpacing(8)

        header = QLabel(f"{icon}  {cat}  ({len(names)})")
        header.setStyleSheet("color: #E2E8F0; font-size: 15px; font-weight: bold;")
        layout.addWidget(header)

        for name in names:
            info = tool_map.get(name, {"nome": name, "descricao": "—"})
            row = self._make_tool_row(info)
            layout.addWidget(row)

        return section

    def _make_tool_row(self, info: dict) -> QWidget:
        row = QFrame()
        row.setStyleSheet("""
            QFrame { background: transparent; border: none; }
            QFrame:hover { background: #1E293B; border-radius: 6px; }
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 6, 8, 6)

        name = QLabel(info.get("nome", "?"))
        name.setStyleSheet("color: #7DD3FC; font-size: 13px; font-weight: bold; min-width: 180px;")
        rl.addWidget(name)

        desc = QLabel(info.get("descricao", ""))
        desc.setStyleSheet("color: #94A3B8; font-size: 12px;")
        desc.setWordWrap(True)
        rl.addWidget(desc, 1)

        # Status (sempre ativo por enquanto)
        status = QLabel("✓ Ativo")
        status.setStyleSheet("color: #3FB950; font-size: 11px;")
        rl.addWidget(status)

        return row
