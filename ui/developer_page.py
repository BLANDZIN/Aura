"""
ui/developer_page.py
====================
Página do Desenvolvedor — Logs, métricas, eventos, banco, debug.
Observabilidade completa para desenvolvimento e diagnóstico.
"""

import os
import sys
import time
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QTextEdit,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer

from core.logger import setup_logger

logger = setup_logger("developer_page")


TAB_STYLE = """
    QTabWidget::pane { border: none; background: transparent; }
    QTabBar::tab {
        background: transparent; color: #94A3B8;
        padding: 8px 16px; font-size: 12px; border: none;
        border-bottom: 2px solid transparent;
    }
    QTabBar::tab:selected {
        color: #7DD3FC; border-bottom: 2px solid #7DD3FC;
    }
    QTabBar::tab:hover { color: #E2E8F0; }
"""


class DeveloperPage(QWidget):
    """Página de ferramentas do desenvolvedor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)

        tabs.addTab(self._build_logs_tab(), "📋  Logs")
        tabs.addTab(self._build_metrics_tab(), "📊  Métricas")
        tabs.addTab(self._build_events_tab(), "⚡  Eventos")
        tabs.addTab(self._build_db_tab(), "🗄  Banco")
        tabs.addTab(self._build_system_tab(), "💻  Sistema")

        layout.addWidget(tabs)

    # ══════════════════════════════════════════════════════════════════════
    # Aba: Logs
    # ══════════════════════════════════════════════════════════════════════

    def _build_logs_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Logs do Sistema")
        title.setStyleSheet("color: #E2E8F0; font-size: 15px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        refresh = QPushButton("🔄 Atualizar")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.setStyleSheet("""
            QPushButton {
                background: #21262D; color: #E2E8F0;
                border: 1px solid #30363D; border-radius: 6px;
                padding: 6px 12px; font-size: 12px;
            }
            QPushButton:hover { background: #30363D; }
        """)
        header.addWidget(refresh)

        clear = QPushButton("🗑 Limpar")
        clear.clicked.connect(lambda: log_view.clear())
        clear.setStyleSheet(refresh.styleSheet())
        header.addWidget(clear)

        layout.addLayout(header)

        log_view = self._make_log_viewer()
        layout.addWidget(log_view, 1)

        # Carrega logs
        def _load_logs():
            log_view.clear()
            logs_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "logs"
            )
            if os.path.isdir(logs_dir):
                log_files = sorted(os.listdir(logs_dir), reverse=True)[:3]
                for fname in log_files:
                    fpath = os.path.join(logs_dir, fname)
                    try:
                        with open(fpath) as f:
                            log_view.append(f.read()[-5000:])
                    except Exception:
                        pass
            if not log_view.toPlainText():
                log_view.setText("Nenhum log encontrado.")

        refresh.clicked.connect(_load_logs)
        QTimer.singleShot(100, _load_logs)

        return w

    def _make_log_viewer(self) -> QTextEdit:
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setStyleSheet("""
            QTextEdit {
                background: #0B0F14; color: #94A3B8;
                border: 1px solid #1E293B; border-radius: 8px;
                font-family: 'Consolas', 'Menlo', monospace;
                font-size: 11px; padding: 10px;
            }
        """)
        return viewer

    # ══════════════════════════════════════════════════════════════════════
    # Aba: Métricas
    # ══════════════════════════════════════════════════════════════════════

    def _build_metrics_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        title = QLabel("Métricas de Performance")
        title.setStyleSheet("color: #E2E8F0; font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Métrica", "Último Valor", "Média"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setStyleSheet("""
            QTableWidget { background: #161B22; color: #E6EDF3; border: 1px solid #21262D; border-radius: 8px; }
            QHeaderView::section { background: #0B0F14; color: #94A3B8; border: none; padding: 8px; }
        """)

        metrics_info = [
            ("Tempo de resposta", "--", "--"),
            ("Tokens por segundo", "--", "--"),
            ("Tempo de ferramenta", "--", "--"),
            ("Tempo de OCR", "--", "--"),
            ("Tempo de voz", "--", "--"),
            ("Uso de cache", "--", "--"),
            ("Conexões Ollama", "--", "--"),
        ]

        table.setRowCount(len(metrics_info))
        for i, (name, last, avg) in enumerate(metrics_info):
            table.setItem(i, 0, QTableWidgetItem(name))
            table.setItem(i, 1, QTableWidgetItem(last))
            table.setItem(i, 2, QTableWidgetItem(avg))

        layout.addWidget(table)
        return w

    # ══════════════════════════════════════════════════════════════════════
    # Aba: Eventos
    # ══════════════════════════════════════════════════════════════════════

    def _build_events_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        title = QLabel("Eventos do EventBus")
        title.setStyleSheet("color: #E2E8F0; font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        viewer = self._make_log_viewer()
        viewer.setText(
            "Os eventos do sistema são roteados pelo EventBus.\n\n"
            "Eventos principais:\n"
            "  • ai.thinking / ai.response / ai.stream.token / ai.stream.done\n"
            "  • ai.error / ai.intent\n"
            "  • tool.result / tool.confirm_required\n"
            "  • flow.started / flow.step / flow.done / flow.aborted\n"
            "  • tasks.due / tasks.created / tasks.completed\n"
            "  • automation.suggestion\n"
            "  • avatar.set_state\n"
            "  • ui.open_angela\n\n"
            "Use o Monitor para ver métricas em tempo real."
        )
        layout.addWidget(viewer)
        return w

    # ══════════════════════════════════════════════════════════════════════
    # Aba: Banco
    # ══════════════════════════════════════════════════════════════════════

    def _build_db_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        title = QLabel("Banco de Dados SQLite")
        title.setStyleSheet("color: #E2E8F0; font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        viewer = self._make_log_viewer()
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "database", "aura.db"
        )

        try:
            from database.db_manager import db
            tables = db.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            lines = [f"Banco: {db_path}\n"]
            if os.path.exists(db_path):
                size_kb = os.path.getsize(db_path) / 1024
                lines.append(f"Tamanho: {size_kb:.0f} KB\n")

            lines.append("Tabelas:")
            for t in tables:
                name = t.get("name", "?")
                try:
                    count = db.fetchall(f"SELECT COUNT(*) as cnt FROM {name}")
                    cnt = count[0].get("cnt", 0) if count else 0
                    lines.append(f"  • {name}: {cnt} registros")
                except Exception:
                    lines.append(f"  • {name}")
            viewer.setText("\n".join(lines))
        except Exception as e:
            viewer.setText(f"Erro ao ler banco:\n{e}")

        layout.addWidget(viewer)
        return w

    # ══════════════════════════════════════════════════════════════════════
    # Aba: Sistema
    # ══════════════════════════════════════════════════════════════════════

    def _build_system_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        title = QLabel("Informações do Sistema")
        title.setStyleSheet("color: #E2E8F0; font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        viewer = self._make_log_viewer()
        lines = [
            f"Python: {sys.version}",
            f"Executável: {sys.executable}",
            f"Plataforma: {sys.platform}",
            f"Working Dir: {os.getcwd()}",
            "",
        ]

        try:
            import psutil
            lines.append(f"CPU Cores: {psutil.cpu_count()}")
            lines.append(f"RAM Total: {psutil.virtual_memory().total / 1e9:.1f} GB")
        except Exception:
            pass

        viewer.setText("\n".join(lines))
        layout.addWidget(viewer)
        return w
