"""
launcher/pages/diagnostics.py
=============================
Página de Diagnóstico — Observabilidade do sistema.
CPU, RAM, tokens, tempos de resposta, cache, banco.
"""

import os
import sys
import time
import json
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QTextEdit, QMessageBox,
)
from PyQt6.QtCore import Qt
from launcher.pages._widgets import CARD_STYLE as _CARD_STYLE
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from launcher.pages._widgets import make_card, make_title, make_subtitle, make_btn_primary, make_btn_secondary, make_btn_danger


_CARD_STYLE = """
    QFrame#diag_card {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 16px;
    }
"""

BTN_PRIMARY_STYLE = """
    QPushButton {
        background: #1F6FEB; color: #fff;
        border: none; border-radius: 8px;
        padding: 10px 20px; font-size: 13px;
    }
    QPushButton:hover { background: #388BFD; }
"""


class DiagnosticsPage(QWidget):
    """Diagnóstico completo do sistema AURA."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

        # Timer para atualizar métricas
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_metrics)
        self._timer.start(2000)

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("📊  Diagnóstico")
        title.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        test_btn = QPushButton("🔬  Teste Completo")
        test_btn.setStyleSheet(BTN_PRIMARY_STYLE)
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_btn.clicked.connect(self._run_full_test)
        header.addWidget(test_btn)

        layout.addLayout(header)

        # ── Grid de métricas ────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(12)

        # CPU
        self._cpu_card = self._make_metric_card("CPU", "0%")
        grid.addWidget(self._cpu_card, 0, 0)

        # RAM
        self._ram_card = self._make_metric_card("RAM", "0 GB / 0 GB")
        grid.addWidget(self._ram_card, 0, 1)

        # Tokens usados (nesta sessão)
        self._tokens_card = self._make_metric_card("Tokens (sessão)", "0")
        grid.addWidget(self._tokens_card, 0, 2)

        # Cache
        self._cache_card = self._make_metric_card("Cache", "0 itens")
        grid.addWidget(self._cache_card, 1, 0)

        # Banco de dados
        self._db_card = self._make_metric_card("Banco SQLite", "OK")
        grid.addWidget(self._db_card, 1, 1)

        # Ollama
        self._ollama_card = self._make_metric_card("Ollama", "Verificando...")
        grid.addWidget(self._ollama_card, 1, 2)

        layout.addLayout(grid)

        # ── Log de diagnóstico ─────────────────────────────────────────────
        log_label = QLabel("Log de Diagnóstico")
        log_label.setStyleSheet("color: #E2E8F0; font-size: 15px; font-weight: bold;")
        layout.addWidget(log_label)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet("""
            QTextEdit {
                background: #0B0F14;
                color: #E2E8F0;
                border: 1px solid #1E293B;
                border-radius: 8px;
                font-family: 'Consolas', 'Menlo', monospace;
                font-size: 12px;
                padding: 12px;
            }
        """)
        self._log.setMinimumHeight(200)
        layout.addWidget(self._log)

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

    def on_show(self):
        self._refresh_metrics()

    def _make_metric_card(self, title: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("diag_card")
        card.setStyleSheet(_CARD_STYLE)
        card.setMinimumWidth(200)

        inner = QVBoxLayout(card)
        inner.setSpacing(4)

        t = QLabel(title)
        t.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600;")
        inner.addWidget(t)

        v = QLabel(value)
        v.setObjectName("metric_value")
        v.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        inner.addWidget(v)

        return card

    def _update_card(self, card: QFrame, value: str):
        v = card.findChild(QLabel, "metric_value")
        if v:
            v.setText(str(value))

    def _refresh_metrics(self):
        """Atualiza métricas em tempo real."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            self._update_card(self._cpu_card, f"{cpu}%")

            mem = psutil.virtual_memory()
            used_gb = mem.used / (1024 ** 3)
            total_gb = mem.total / (1024 ** 3)
            self._update_card(self._ram_card, f"{used_gb:.1f} / {total_gb:.1f} GB")
        except Exception:
            self._update_card(self._cpu_card, "N/A (psutil)")
            self._update_card(self._ram_card, "N/A (psutil)")

        # Ollama
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=1)
            if r.status_code == 200:
                models = r.json().get("models", [])
                self._update_card(self._ollama_card, f"✓ {len(models)} modelos")
            else:
                self._update_card(self._ollama_card, "Erro")
        except Exception:
            self._update_card(self._ollama_card, "Offline")

        # Banco
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "database", "aura.db"
        )
        if os.path.exists(db_path):
            size_kb = os.path.getsize(db_path) / 1024
            self._update_card(self._db_card, f"OK ({size_kb:.0f} KB)")
        else:
            self._update_card(self._db_card, "Não encontrado")

        # Cache
        cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "cache"
        )
        if os.path.isdir(cache_dir):
            count = len(os.listdir(cache_dir))
            self._update_card(self._cache_card, f"{count} itens")
        else:
            self._update_card(self._cache_card, "Vazio")

    def _run_full_test(self):
        """Executa diagnóstico completo."""
        self._log.clear()
        self._log.append("🔬 Iniciando diagnóstico completo...\n")

        results = []

        # 1. Python
        self._log.append(f"Python: {sys.version}")
        self._log.append(f"Executável: {sys.executable}\n")

        # 2. Dependências
        deps = ["PyQt6", "requests", "psutil", "pyautogui", "pyttsx3", "PIL"]
        for dep in deps:
            try:
                __import__(dep)
                self._log.append(f"  ✓ {dep}")
                results.append(("dep", dep, True))
            except ImportError:
                self._log.append(f"  ✗ {dep} (não instalado)")
                results.append(("dep", dep, False))

        self._log.append("")

        # 3. Ollama
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.status_code == 200:
                models = r.json().get("models", [])
                self._log.append(f"✓ Ollama: {len(models)} modelos")
                for m in models:
                    self._log.append(f"  - {m.get('name', '?')} ({m.get('size', 0) / 1e9:.1f} GB)")
                results.append(("ollama", "conexão", True))
            else:
                self._log.append("✗ Ollama: resposta inesperada")
                results.append(("ollama", "conexão", False))
        except Exception as e:
            self._log.append(f"✗ Ollama indisponível: {e}")
            results.append(("ollama", "conexão", False))

        self._log.append("")

        # 4. Configurações
        try:
            from config.settings import settings
            self._log.append("✓ Configurações carregadas")
            self._log.append(f"  Modelo AURA: {settings.get('ai', 'model')}")
            self._log.append(f"  Modelo Angela: {settings.get('angela', 'model')}")
            self._log.append(f"  Tema: {settings.get('ui', 'theme')}")
            self._log.append(f"  TTS: {'Ativado' if settings.get('voice', 'tts_enabled') else 'Desativado'}")
            results.append(("config", "settings.json", True))
        except Exception as e:
            self._log.append(f"✗ Configurações: {e}")
            results.append(("config", "settings.json", False))

        self._log.append("")

        # 5. Banco de dados
        try:
            from database.db_manager import db
            db.execute("SELECT 1")
            self._log.append("✓ Banco de dados SQLite OK")
            results.append(("banco", "sqlite", True))
        except Exception as e:
            self._log.append(f"✗ Banco de dados: {e}")
            results.append(("banco", "sqlite", False))

        # Resumo
        self._log.append("\n" + "─" * 50)
        total = len(results)
        ok = sum(1 for _, _, success in results if success)
        self._log.append(f"\n📊 Resultado: {ok}/{total} testes passaram")

        if ok == total:
            self._log.append("✅ Sistema saudável!")
        else:
            self._log.append("⚠️ Alguns componentes precisam de atenção.")
