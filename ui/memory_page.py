"""
ui/memory_page.py
=================
Página de Memória — Visualização e gerenciamento de memórias da AURA.
Pesquisar, editar, excluir, mover entre categorias, exportar.
"""

import json
import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QInputDialog, QComboBox,
)
from PyQt6.QtCore import Qt

from core.logger import setup_logger

logger = setup_logger("memory_page")


class MemoryPage(QWidget):
    """Página de visualização e edição de memória."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._memories = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header
        header = QLabel("💾  Memória da AURA")
        header.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        layout.addWidget(header)

        # Barra de ações
        actions = QHBoxLayout()
        actions.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Pesquisar memórias...")
        self._search.setStyleSheet("""
            QLineEdit {
                background: #161B22; color: #E6EDF0;
                border: 1px solid #334155; border-radius: 8px;
                padding: 10px 14px; font-size: 13px;
            }
            QLineEdit:focus { border-color: #388BFD; }
        """)
        self._search.textChanged.connect(self._filter_memories)
        actions.addWidget(self._search, 1)

        refresh = QPushButton("🔄 Atualizar")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.setStyleSheet("""
            QPushButton {
                background: #21262D; color: #E2E8F0;
                border: 1px solid #30363D; border-radius: 8px;
                padding: 10px 16px; font-size: 13px;
            }
            QPushButton:hover { background: #30363D; }
        """)
        refresh.clicked.connect(self._load_memories)
        actions.addWidget(refresh)

        export = QPushButton("📤 Exportar")
        export.setCursor(Qt.CursorShape.PointingHandCursor)
        export.setStyleSheet(refresh.styleSheet())
        export.clicked.connect(self._export_memories)
        actions.addWidget(export)

        layout.addLayout(actions)

        # Tabela
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Categoria", "Chave", "Valor", "Importância"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet("""
            QTableWidget {
                background: #161B22; color: #E6EDF3;
                border: 1px solid #21262D; border-radius: 8px;
                gridline-color: #21262D;
            }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background: #1E3A5F; }
            QHeaderView::section {
                background: #0B0F14; color: #94A3B8;
                border: none; padding: 8px;
            }
        """)
        self._table.cellDoubleClicked.connect(self._edit_memory)
        layout.addWidget(self._table, 1)

        # Botões de ação
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        edit = QPushButton("✏️ Editar")
        edit.setCursor(Qt.CursorShape.PointingHandCursor)
        edit.setStyleSheet("""
            QPushButton {
                background: #1F6FEB; color: #fff;
                border: none; border-radius: 8px;
                padding: 8px 16px; font-size: 13px;
            }
            QPushButton:hover { background: #388BFD; }
        """)
        edit.clicked.connect(lambda: self._edit_memory())
        btn_row.addWidget(edit)

        delete = QPushButton("🗑 Excluir")
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        delete.setStyleSheet("""
            QPushButton {
                background: #DA3633; color: #fff;
                border: none; border-radius: 8px;
                padding: 8px 16px; font-size: 13px;
            }
            QPushButton:hover { background: #F85149; }
        """)
        delete.clicked.connect(self._delete_memory)
        btn_row.addWidget(delete)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Carrega dados
        self._load_memories()

    def on_show(self):
        self._load_memories()

    def _load_memories(self):
        """Carrega memórias do banco."""
        try:
            from database.db_manager import db
            rows = db.fetchall(
                "SELECT id, categoria, chave, valor, importance FROM memory_permanent "
                "ORDER BY importance DESC, categoria LIMIT 200"
            )
            self._memories = rows
            self._populate_table(rows)
        except Exception as e:
            logger.error(f"Erro ao carregar memórias: {e}")

    def _populate_table(self, rows: list):
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem(row.get("categoria", "")))
            self._table.setItem(i, 1, QTableWidgetItem(row.get("chave", "")))
            val = str(row.get("valor", ""))[:200]
            self._table.setItem(i, 2, QTableWidgetItem(val))
            imp = str(row.get("importance", 5))
            item = QTableWidgetItem(imp)
            if int(imp) >= 8:
                item.setForeground(Qt.GlobalColor.green)
            self._table.setItem(i, 3, item)

    def _filter_memories(self, text: str):
        if not text:
            self._populate_table(self._memories)
            return
        q = text.lower()
        filtered = [
            m for m in self._memories
            if q in str(m.get("categoria", "")).lower()
            or q in str(m.get("chave", "")).lower()
            or q in str(m.get("valor", "")).lower()
        ]
        self._populate_table(filtered)

    def _edit_memory(self, row=None, col=None):
        """Edita uma memória."""
        if row is None:
            row = self._table.currentRow()
        if row < 0 or row >= len(self._memories):
            return
        mem = self._memories[row]
        new_val, ok = QInputDialog.getText(
            self, "Editar Memória",
            f"Categoria: {mem.get('categoria')}\nChave: {mem.get('chave')}\n\nNovo valor:",
            text=str(mem.get("valor", ""))
        )
        if ok and new_val.strip():
            try:
                from database.db_manager import db
                db.execute(
                    "UPDATE memory_permanent SET valor=? WHERE id=?",
                    (new_val.strip(), mem.get("id"))
                )
                self._load_memories()
            except Exception as e:
                QMessageBox.critical(self, "Erro", str(e))

    def _delete_memory(self):
        row = self._table.currentRow()
        if row < 0:
            return
        mem = self._memories[row]
        reply = QMessageBox.question(
            self, "Confirmar",
            f"Excluir memória '{mem.get('chave')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from database.db_manager import db
                db.execute("DELETE FROM memory_permanent WHERE id=?", (mem.get("id"),))
                self._load_memories()
            except Exception as e:
                QMessageBox.critical(self, "Erro", str(e))

    def _export_memories(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Memórias",
            f"aura_memories_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._memories, f, ensure_ascii=False, indent=2, default=str)
            QMessageBox.information(self, "Sucesso", f"Memórias exportadas para:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
