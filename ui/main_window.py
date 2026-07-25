# -*- coding: utf-8 -*-
"""
ui/main_window.py - AURA V12
=============================
Launcher completo com sidebar + 10 paginas.
Aberto via botao "Ferramentas" no chat ou iniciado standalone.
DETECTA automaticamente se o backend (AuraApp) ja esta rodando.
"""
import os, sys, time, threading
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from core.logger import setup_logger

logger = setup_logger("main_window")

PAGE_TITLES = [
    "Home", "Chat", "Angela", "Modelos", "Ferramentas",
    "Memoria", "Monitor", "Plugins", "Configuracoes", "Desenvolvedor",
    "Atualizacoes", "Diagnostico", "Backup", "Perfis",
]
NAV_ITEMS = [
    ("\U0001f3e0","Home",0),("\U0001f4ac","Chat",1),("\U0001f6e0","Angela",2),
    ("\U0001f9e0","Modelos",3),("\U0001f527","Ferramentas",4),("\U0001f4be","Memoria",5),
    ("\U0001f4ca","Monitor",6),("\U0001f9e9","Plugins",7),("\u2699\ufe0f","Configuracoes",8),
    ("\U0001f52c","Desenvolvedor",9),
    # V12.1 — Prioridade 6: essas 4 páginas já existiam prontas em
    # launcher/pages/ mas nenhum entry point real as carregava —
    # inclusive a de Atualizações, a UI do próprio updater/. Achado
    # crítico da auditoria V11, ainda presente na V12 antes deste fix.
    ("\U0001f504","Atualizacoes",10),("\U0001fa7a","Diagnostico",11),
    ("\U0001f4e6","Backup",12),("\U0001f465","Perfis",13),
]

STYLE = """
QMainWindow{background:#0B0F14;}
QToolTip{background:#1E293B;color:#E2E8F0;border:1px solid #334155;padding:6px;border-radius:6px;font-size:12px;}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AURA V12")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self._monitor_active = False
        self._monitor_timer = None
        self._metrics = {"cpu":0,"ram":0,"ram_total":0,"memories_count":0,"tasks_pending":0}
        self._pages_loaded = set()

        self._home_page = self._chat_page = self._angela_page = None
        self._models_page = self._tools_page = self._memory_page = None
        self._monitor_page = self._plugins_page = self._settings_page = None
        self._developer_page = None
        self._updates_page = self._diagnostics_page = None
        self._backup_page = self._profiles_page = None

        self._build_ui()

        # Carrega Home IMEDIATAMENTE
        self._nav_buttons[0].setChecked(True)
        QTimer.singleShot(10, lambda: self._ensure_page_loaded(0))

        # Verifica se backend ja esta rodando (AuraApp iniciou antes)
        QTimer.singleShot(50, self._detect_backend)

        # Monitor sempre ativo
        self._start_monitor()
        logger.info("MainWindow V11 iniciada")

    # ==================== UI ====================
    def _build_ui(self):
        self.setStyleSheet(STYLE)
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        right = QVBoxLayout()
        right.setContentsMargins(0,0,0,0)
        right.setSpacing(0)
        right.addWidget(self._build_header())
        right.addWidget(self._build_pages(), 1)
        right.addWidget(self._build_status_bar())
        rw = QWidget()
        rw.setLayout(right)
        root.addWidget(rw, 1)

    def _build_sidebar(self):
        sb = QFrame()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(230)
        sb.setStyleSheet("QFrame#sidebar{background:#0B0F14;border-right:1px solid #1E293B;}")
        ly = QVBoxLayout(sb)
        ly.setContentsMargins(10,18,10,12)
        ly.setSpacing(2)
        logo = QLabel("\u25c9  AURA V12")
        logo.setStyleSheet("color:#7DD3FC;font-size:19px;font-weight:bold;padding:8px 10px;")
        ly.addWidget(logo)
        ly.addSpacing(12)
        self._nav_buttons = []
        self._pages = QStackedWidget()
        for icon, label, idx in NAV_ITEMS:
            btn = QPushButton("  {}  {}".format(icon, label))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("QPushButton{background:transparent;color:#94A3B8;border:none;border-radius:10px;padding:12px 16px;font-size:14px;}QPushButton:hover{background:#1E293B;color:#E2E8F0;}QPushButton:checked{background:#1E3A5F;color:#7DD3FC;font-weight:bold;}")
            btn.setMinimumHeight(44)
            btn.clicked.connect(lambda ch,b=btn,i=idx: self._on_nav(b,i))
            ly.addWidget(btn)
            self._nav_buttons.append(btn)
        ly.addStretch()
        v = QLabel("v11.0.0")
        v.setStyleSheet("color:#475569;font-size:11px;padding:6px 10px;")
        ly.addWidget(v)
        self._sidebar_status = QLabel("\u25c9 Detectando...")
        self._sidebar_status.setStyleSheet("color:#CE93D8;font-size:11px;padding:4px 10px;")
        ly.addWidget(self._sidebar_status)
        return sb

    def _build_header(self):
        hd = QFrame()
        hd.setObjectName("header")
        hd.setFixedHeight(52)
        hd.setStyleSheet("QFrame#header{background:#0B0F14;border-bottom:1px solid #1E293B;}")
        ly = QHBoxLayout(hd)
        ly.setContentsMargins(24,0,20,0)
        self._page_title = QLabel("Home")
        self._page_title.setStyleSheet("color:#E2E8F0;font-size:16px;font-weight:600;")
        ly.addWidget(self._page_title)
        ly.addStretch()
        self._header_model = QLabel("")
        self._header_model.setStyleSheet("color:#64748B;font-size:12px;")
        ly.addWidget(self._header_model)
        return hd

    def _build_pages(self):
        pages = self._pages
        pages.setStyleSheet("background:#0D1117;")
        for i in range(len(NAV_ITEMS)):
            w = QWidget()
            l = QVBoxLayout(w)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s = QLabel("\u25c9")
            s.setStyleSheet("color:#7DD3FC;font-size:32px;")
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t = QLabel("Carregando {}...".format(PAGE_TITLES[i]))
            t.setStyleSheet("color:#94A3B8;font-size:16px;")
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.addWidget(s)
            l.addWidget(t)
            pages.addWidget(w)
        return pages

    def _build_status_bar(self):
        bar = QFrame()
        bar.setObjectName("status_bar")
        bar.setFixedHeight(32)
        bar.setStyleSheet("QFrame#status_bar{background:#0B0F14;border-top:1px solid #1E293B;}")
        ly = QHBoxLayout(bar)
        ly.setContentsMargins(16,0,16,0)
        ly.setSpacing(24)
        self._status_text = QLabel("Detectando backend...")
        self._status_text.setStyleSheet("color:#94A3B8;font-size:11px;")
        ly.addWidget(self._status_text)
        ly.addStretch()
        self._status_cpu = QLabel("CPU: --")
        self._status_cpu.setStyleSheet("color:#64748B;font-size:11px;")
        ly.addWidget(self._status_cpu)
        self._status_ram = QLabel("RAM: --")
        self._status_ram.setStyleSheet("color:#64748B;font-size:11px;")
        ly.addWidget(self._status_ram)
        return bar

    # ==================== NAVIGATION ====================
    def _on_nav(self, clicked_btn: object, page_idx: int) -> None:
        for btn in self._nav_buttons:
            btn.setChecked(btn is clicked_btn)
        self._pages.setCurrentIndex(page_idx)
        if page_idx < len(PAGE_TITLES):
            self._page_title.setText(PAGE_TITLES[page_idx])
        self._ensure_page_loaded(page_idx)
        if page_idx == 1 and self._chat_page:
            QTimer.singleShot(100, self._chat_page.focus_input)

    def _ensure_page_loaded(self, idx: int) -> None:
        if idx in self._pages_loaded:
            return
        self._pages_loaded.add(idx)
        page = self._pages.widget(idx)
        real = self._load_page(idx)
        if real:
            self._pages.removeWidget(page)
            page.deleteLater()
            self._pages.insertWidget(idx, real)
            self._pages.setCurrentIndex(idx)
            if hasattr(real, 'on_show'):
                QTimer.singleShot(50, real.on_show)
            if idx == 1 and hasattr(real, 'focus_input'):
                QTimer.singleShot(100, real.focus_input)

    def _load_page(self, idx):
        try:
            if idx == 0:
                from launcher.pages.home import HomePage
                self._home_page = HomePage()
                return self._home_page
            elif idx == 1:
                from ui.chat_page import ChatPage
                self._chat_page = ChatPage()
                return self._chat_page
            elif idx == 2:
                from ui.angela_page import AngelaPage
                self._angela_page = AngelaPage()
                return self._angela_page
            elif idx == 3:
                from launcher.pages.models import ModelsPage
                self._models_page = ModelsPage()
                return self._models_page
            elif idx == 4:
                from ui.tools_page import ToolsPage
                self._tools_page = ToolsPage()
                return self._tools_page
            elif idx == 5:
                from ui.memory_page import MemoryPage
                self._memory_page = MemoryPage()
                return self._memory_page
            elif idx == 6:
                from ui.monitor_page import MonitorPage
                self._monitor_page = MonitorPage(metrics=self._metrics)
                return self._monitor_page
            elif idx == 7:
                from launcher.pages.extensions import ExtensionsPage
                self._plugins_page = ExtensionsPage()
                return self._plugins_page
            elif idx == 8:
                from launcher.pages.settings import SettingsPage
                self._settings_page = SettingsPage()
                return self._settings_page
            elif idx == 9:
                from ui.developer_page import DeveloperPage
                self._developer_page = DeveloperPage()
                return self._developer_page
            elif idx == 10:
                from launcher.pages.updates import UpdatesPage
                self._updates_page = UpdatesPage()
                return self._updates_page
            elif idx == 11:
                from launcher.pages.diagnostics import DiagnosticsPage
                self._diagnostics_page = DiagnosticsPage()
                return self._diagnostics_page
            elif idx == 12:
                from launcher.pages.backup import BackupPage
                self._backup_page = BackupPage()
                return self._backup_page
            elif idx == 13:
                from launcher.pages.profiles import ProfilesPage
                self._profiles_page = ProfilesPage()
                return self._profiles_page
        except Exception as e:
            logger.error("Erro pagina {}: {}".format(idx, e))
            w = QWidget()
            l = QVBoxLayout(w)
            err = QLabel("Erro ao carregar:\n{}".format(e))
            err.setStyleSheet("color:#F85149;font-size:14px;padding:40px;")
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.addWidget(err)
            return w

    # ==================== BACKEND DETECTION ====================
    def _detect_backend(self):
        """
        Detecta se o backend (AuraApp) ja foi inicializado.
        Se sim, mostra 'Online' imediatamente.
        Se nao, inicializa em background (modo standalone).
        """
        # Tenta acessar modulos que o AuraApp inicializa
        backend_alive = False
        try:
            from database.db_manager import db
            db.execute("SELECT 1")
            from memory.memory_manager import memory
            from tools.tool_manager import tool_manager
            from ai.ai_engine import ai_engine
            backend_alive = True
        except Exception:
            logger.debug("Operacao nao critica falhou", exc_info=True)

        if backend_alive:
            # Backend ja esta rodando — tudo pronto!
            self._sidebar_status.setText("\u25c9 Online")
            self._sidebar_status.setStyleSheet("color:#3FB950;font-size:11px;padding:4px 10px;")
            self._status_text.setText("\u2713 Backend conectado")
            self._status_text.setStyleSheet("color:#3FB950;font-size:11px;")
            self._update_model_info()
            logger.info("MainWindow: backend detectado como ONLINE")
        else:
            # Modo standalone: inicializa backend proprio
            self._status_text.setText("Inicializando backend...")
            self._status_text.setStyleSheet("color:#CE93D8;font-size:11px;")
            self._init_backend_standalone()

    def _update_model_info(self):
        try:
            from config.settings import settings
            model = settings.get('ai', 'model', '?')
            self._header_model.setText("\U0001f9e0 {}".format(model))
        except Exception:
            logger.debug("Operacao nao critica falhou", exc_info=True)

    def _init_backend_standalone(self):
        """Inicializa backend do zero — apenas no modo standalone."""
        def _run():
            steps = []
            for name, fn in [
                ("Banco", lambda: (__import__('database.db_manager', fromlist=['db']).db.execute("SELECT 1"), True)[1]),
                ("Memoria", lambda: setattr(self, '_memory', __import__('memory.memory_manager', fromlist=['memory']).memory) or True),
                ("Ferramentas", lambda: setattr(self, '_tools', __import__('tools.tool_manager', fromlist=['tool_manager']).tool_manager) or True),
                ("IA Engine", lambda: setattr(self, '_ai', __import__('ai.ai_engine', fromlist=['ai_engine']).ai_engine) or True),
                ("Tasks", lambda: setattr(self, '_task_manager', __import__('tasks.task_manager', fromlist=['task_manager']).task_manager) or True),
            ]:
                try:
                    fn()
                    steps.append((name, True))
                except Exception as e:
                    steps.append((name, False, str(e)))

            # Angela
            try:
                from angela import Angela
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                self._angela = Angela(project_root=project_root)
                self._angela.start()
                steps.append(("Angela", True))
            except Exception as e:
                steps.append(("Angela", False, str(e)))

            # Ollama
            try:
                import requests
                r = requests.get("http://localhost:11434/api/tags", timeout=3)
                steps.append(("Ollama", r.status_code == 200))
            except Exception as e:
                steps.append(("Ollama", False, str(e)))

            # Voz
            try:
                from voice.voice_engine import voice_manager as vm
                vm.start()
                steps.append(("Voz", True))
            except Exception as e:
                steps.append(("Voz", False, str(e)))

            all_ok = all(s[1] for s in steps)
            QTimer.singleShot(0, lambda: self._on_standalone_ready(steps, all_ok))

        threading.Thread(target=_run, daemon=True).start()

    def _on_standalone_ready(self, steps, all_ok):
        if all_ok:
            self._sidebar_status.setText("\u25c9 Online")
            self._sidebar_status.setStyleSheet("color:#3FB950;font-size:11px;")
            self._status_text.setText("\u2713 Pronto")
            self._status_text.setStyleSheet("color:#3FB950;font-size:11px;")
            self._update_model_info()
        else:
            self._sidebar_status.setText("\u26a0 Parcial")
            self._sidebar_status.setStyleSheet("color:#D29922;font-size:11px;")
            self._status_text.setText("\u26a0 Alguns componentes falharam")
            self._status_text.setStyleSheet("color:#D29922;font-size:11px;")
        logger.info("Backend standalone: {}/{} ok".format(
            sum(1 for s in steps if s[1]), len(steps)))

    # ==================== MONITOR ====================
    def _start_monitor(self):
        self._monitor_active = True
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._update_monitor)
        self._monitor_timer.start(2000)

    def _update_monitor(self):
        try:
            import psutil
            self._metrics["cpu"] = psutil.cpu_percent(interval=0.05)
            mem = psutil.virtual_memory()
            self._metrics["ram"] = mem.used / (1024**3)
            self._metrics["ram_total"] = mem.total / (1024**3)
            self._status_cpu.setText("CPU: {:.0f}%".format(self._metrics["cpu"]))
            self._status_ram.setText("RAM: {:.1f}/{:.1f}GB".format(
                self._metrics["ram"], self._metrics["ram_total"]))
        except Exception:
            logger.debug("Operacao nao critica falhou", exc_info=True)

    # ==================== SHUTDOWN ====================
    def shutdown(self) -> None:
        """Para timers e limpa referencias. NAO mexe em bus/db."""
        self._monitor_active = False
        if self._monitor_timer:
            self._monitor_timer.stop()
            self._monitor_timer = None
        self._home_page = self._chat_page = self._angela_page = None
        self._models_page = self._tools_page = self._memory_page = None
        self._monitor_page = self._plugins_page = self._settings_page = None
        self._developer_page = None
        self._updates_page = self._diagnostics_page = None
        self._backup_page = self._profiles_page = None
        self._pages_loaded.clear()
        logger.info("Launcher encerrado (AURA continua rodando)")

    def showEvent(self, event: object) -> None:
        """Chamado sempre que a janela for exibida (inclusive reabertura)."""
        super().showEvent(event)
        QTimer.singleShot(50, self._detect_backend)
        QTimer.singleShot(100, lambda: self._ensure_page_loaded(0))

    def closeEvent(self, event: object) -> None:
        """Fecha APENAS o Launcher. AURA (avatar+chat) continua rodando."""
        self.shutdown()
        self.hide()
        event.ignore()
