"""
launcher/app.py
==============
Janela principal do Launcher V11.
Sidebar com navegação + área de conteúdo com páginas.
"""

import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
    QSizePolicy, QApplication, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QFont, QIcon

from launcher.pages.home import HomePage
from launcher.pages.settings import SettingsPage
from launcher.pages.models import ModelsPage
from launcher.pages.updates import UpdatesPage
from launcher.pages.extensions import ExtensionsPage
from launcher.pages.diagnostics import DiagnosticsPage
from launcher.pages.backup import BackupPage
from launcher.pages.profiles import ProfilesPage

from core.logger import setup_logger

logger = setup_logger("launcher")


# ── Estilos ───────────────────────────────────────────────────────────────────
SIDEBAR_STYLE = """
    QFrame#sidebar {
        background: #0B0F14;
        border-right: 1px solid #1E293B;
    }
"""
NAV_BTN_STYLE = """
    QPushButton {
        background: transparent;
        color: #94A3B8;
        border: none;
        border-radius: 10px;
        padding: 12px 16px;
        text-align: left;
        font-size: 14px;
    }
    QPushButton:hover {
        background: #1E293B;
        color: #E2E8F0;
    }
    QPushButton:checked {
        background: #1E3A5F;
        color: #7DD3FC;
        font-weight: bold;
    }
"""
HEADER_STYLE = """
    QFrame#header {
        background: #0B0F14;
        border-bottom: 1px solid #1E293B;
    }
"""
LAUNCH_BTN_STYLE = """
    QPushButton {
        background: #1F6FEB;
        color: #FFFFFF;
        border: none;
        border-radius: 10px;
        padding: 14px 28px;
        font-size: 15px;
        font-weight: bold;
    }
    QPushButton:hover { background: #388BFD; }
    QPushButton:pressed { background: #0D4A9E; }
"""


class LauncherApp(QMainWindow):
    """Janela principal do Launcher V11."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AURA V11 — Launcher")
        self.setMinimumSize(1100, 720)
        self.resize(1200, 780)

        # Detecta se AURA está rodando
        self._aura_running = False

        self._build_ui()
        self._connect_signals()

        # Seleciona página inicial
        self._nav_buttons[0].setChecked(True)
        self._pages.setCurrentIndex(0)

        logger.info("Launcher V11 iniciado")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────
        sidebar = self._build_sidebar()
        main_layout.addWidget(sidebar)

        # ── Área direita ──────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        # Header
        header = self._build_header()
        right.addWidget(header)

        # Páginas
        self._pages = QStackedWidget()
        self._pages.setStyleSheet("background: #0D1117;")
        self._pages.addWidget(HomePage())
        self._pages.addWidget(SettingsPage())
        self._pages.addWidget(ModelsPage())
        self._pages.addWidget(UpdatesPage())
        self._pages.addWidget(ExtensionsPage())
        self._pages.addWidget(DiagnosticsPage())
        self._pages.addWidget(BackupPage())
        self._pages.addWidget(ProfilesPage())
        right.addWidget(self._pages, 1)

        right_widget = QWidget()
        right_widget.setLayout(right)
        main_layout.addWidget(right_widget, 1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(SIDEBAR_STYLE)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(4)

        # Logo / título
        logo = QLabel("◉  AURA V11")
        logo.setStyleSheet("color: #7DD3FC; font-size: 20px; font-weight: bold; padding: 8px 12px;")
        layout.addWidget(logo)

        subtitle = QLabel("Launcher")
        subtitle.setStyleSheet("color: #64748B; font-size: 11px; padding: 0 12px 16px 12px;")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Botões de navegação
        nav_items = [
            ("🏠", "Página Inicial", 0),
            ("⚙️", "Configurações", 1),
            ("🧠", "Modelos", 2),
            ("🔄", "Atualizações", 3),
            ("🧩", "Extensões", 4),
            ("📊", "Diagnóstico", 5),
            ("💾", "Backup", 6),
            ("👤", "Perfis", 7),
        ]

        self._nav_buttons = []
        for icon, label, idx in nav_items:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(NAV_BTN_STYLE)
            btn.clicked.connect(lambda checked, i=idx: self._pages.setCurrentIndex(i))
            # Grupo de botões exclusivos
            btn.clicked.connect(lambda checked, b=btn: self._on_nav_clicked(b))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        layout.addStretch()

        # Versão
        version_lbl = QLabel("Versão 11.0.0")
        version_lbl.setStyleSheet("color: #475569; font-size: 11px; padding: 8px 12px;")
        layout.addWidget(version_lbl)

        # Botão iniciar AURA
        launch_btn = QPushButton("▶  Iniciar AURA")
        launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        launch_btn.setStyleSheet(LAUNCH_BTN_STYLE)
        launch_btn.clicked.connect(self._launch_aura)
        layout.addWidget(launch_btn)

        return sidebar

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(56)
        header.setStyleSheet(HEADER_STYLE)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 0, 24, 0)

        self._page_title = QLabel("Página Inicial")
        self._page_title.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: 600;")
        layout.addWidget(self._page_title)

        layout.addStretch()

        # Status AURA
        self._status_lbl = QLabel("●  AURA parada")
        self._status_lbl.setStyleSheet("color: #64748B; font-size: 13px;")
        layout.addWidget(self._status_lbl)

        return header

    def _on_nav_clicked(self, clicked_btn):
        """Garante que apenas um botão fique checked por vez."""
        for btn in self._nav_buttons:
            btn.setChecked(btn is clicked_btn)

        # Atualiza título
        titles = [
            "Página Inicial", "Configurações", "Modelos",
            "Atualizações", "Extensões", "Diagnóstico",
            "Backup", "Perfis",
        ]
        idx = self._pages.currentIndex()
        if idx < len(titles):
            self._page_title.setText(titles[idx])

    def _connect_signals(self):
        self._pages.currentChanged.connect(self._on_page_changed)

    def _on_page_changed(self, idx):
        titles = [
            "Página Inicial", "Configurações", "Modelos",
            "Atualizações", "Extensões", "Diagnóstico",
            "Backup", "Perfis",
        ]
        if idx < len(titles):
            self._page_title.setText(titles[idx])
        if idx < len(self._nav_buttons):
            self._nav_buttons[idx].setChecked(True)

        # Notifica página que foi aberta
        page = self._pages.widget(idx)
        if hasattr(page, 'on_show'):
            page.on_show()

    def _launch_aura(self):
        """Inicia a AURA principal em um processo separado."""
        import subprocess
        import os

        aura_main = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")

        if not os.path.exists(aura_main):
            QMessageBox.critical(self, "Erro", f"main.py não encontrado em:\n{aura_main}")
            return

        try:
            subprocess.Popen(
                [sys.executable, aura_main],
                cwd=os.path.dirname(aura_main),
                start_new_session=True,  # independe do launcher
            )
            self._aura_running = True
            self._status_lbl.setText("●  AURA rodando")
            self._status_lbl.setStyleSheet("color: #3FB950; font-size: 13px;")
            logger.info("AURA iniciada pelo launcher")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao iniciar AURA:\n{e}")
            logger.error(f"Falha ao iniciar AURA: {e}")

    def closeEvent(self, event):
        """Confirma saída se AURA estiver rodando."""
        if self._aura_running:
            reply = QMessageBox.question(
                self, "Confirmar saída",
                "A AURA está rodando em segundo plano.\n"
                "Fechar o launcher não encerra a AURA.\n\n"
                "Deseja fechar o launcher?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        logger.info("Launcher encerrado")
        event.accept()
