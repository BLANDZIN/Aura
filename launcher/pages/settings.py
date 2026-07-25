"""
launcher/pages/settings.py
==========================
Página de Configurações — Todas as opções em controles visuais.
Substitui a edição manual de settings.json e personality.json.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QComboBox,
    QSlider, QCheckBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QGroupBox, QGridLayout, QTabWidget,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from launcher.pages._widgets import make_card, make_title, make_btn_primary


_GROUP_STYLE = """
    QGroupBox {
        color: #E2E8F0;
        font-size: 14px;
        font-weight: bold;
        border: 1px solid #21262D;
        border-radius: 10px;
        margin-top: 12px;
        padding: 20px 16px 16px 16px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 16px;
        padding: 0 8px;
    }
"""

LABEL_STYLE = "color: #94A3B8; font-size: 13px;"
VALUE_STYLE = "color: #E2E8F0; font-size: 13px;"

COMBO_STYLE = """
    QComboBox {
        background: #161B22;
        color: #E2E8F0;
        border: 1px solid #21262D;
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
        min-width: 180px;
    }
    QComboBox:hover { border-color: #388BFD; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background: #161B22;
        color: #E2E8F0;
        border: 1px solid #21262D;
        selection-background-color: #1E3A5F;
    }
"""

SLIDER_STYLE = """
    QSlider::groove:horizontal {
        height: 6px;
        background: #21262D;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        width: 18px;
        height: 18px;
        background: #388BFD;
        border-radius: 9px;
        margin: -6px 0;
    }
    QSlider::sub-page:horizontal {
        background: #1F6FEB;
        border-radius: 3px;
    }
"""

CHECKBOX_STYLE = """
    QCheckBox {
        color: #E2E8F0;
        font-size: 13px;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 18px; height: 18px;
        border: 2px solid #30363D;
        border-radius: 4px;
        background: #161B22;
    }
    QCheckBox::indicator:checked {
        background: #1F6FEB;
        border-color: #388BFD;
    }
"""

SAVE_BTN_STYLE = """
    QPushButton {
        background: #1F6FEB;
        color: #fff;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover { background: #388BFD; }
"""


class SettingsPage(QWidget):
    """Todas as configurações da AURA em interface visual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = None
        self._personality = None
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        # Área de scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(16)

        # ── Abas de configuração ──────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: transparent; }
            QTabBar::tab {
                background: transparent; color: #94A3B8;
                padding: 10px 20px; font-size: 13px; border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { color: #7DD3FC; border-bottom: 2px solid #7DD3FC; }
            QTabBar::tab:hover { color: #E2E8F0; }
        """)

        tabs.addTab(self._build_ai_tab(), "🤖  IA & Modelo")
        tabs.addTab(self._build_voice_tab(), "🎤  Voz")
        tabs.addTab(self._build_ui_tab(), "🎨  Interface")
        tabs.addTab(self._build_personality_tab(), "💜  Personalidade")
        tabs.addTab(self._build_angela_tab(), "🛠  Angela")
        tabs.addTab(self._build_advanced_tab(), "🔧  Avançado")

        layout.addWidget(tabs)

        # ── Botão salvar ──────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("💾  Salvar Configurações")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(SAVE_BTN_STYLE)
        save_btn.clicked.connect(self._save_all)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

    # ══════════════════════════════════════════════════════════════════════
    # Aba: IA & Modelo
    # ══════════════════════════════════════════════════════════════════════

    def _build_ai_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)

        # Provider
        g = QGroupBox("Provider de IA")
        g.setStyleSheet(_GROUP_STYLE)
        gg = QGridLayout(g)
        gg.setSpacing(12)

        gg.addWidget(QLabel("Provider:"), 0, 0)
        self._ai_provider = QComboBox()
        self._ai_provider.addItems(["ollama", "lmstudio"])
        self._ai_provider.setStyleSheet(COMBO_STYLE)
        gg.addWidget(self._ai_provider, 0, 1)

        gg.addWidget(QLabel("Modelo AURA:"), 1, 0)
        self._ai_model = QLineEdit()
        self._ai_model.setPlaceholderText("qwen2.5:3b")
        self._ai_model.setStyleSheet("""
            QLineEdit {
                background: #161B22; color: #E2E8F0;
                border: 1px solid #21262D; border-radius: 8px;
                padding: 8px 12px; font-size: 13px;
            }
            QLineEdit:focus { border-color: #388BFD; }
        """)
        gg.addWidget(self._ai_model, 1, 1)

        gg.addWidget(QLabel("URL Ollama:"), 2, 0)
        self._ai_base_url = QLineEdit()
        self._ai_base_url.setPlaceholderText("http://localhost:11434")
        self._ai_base_url.setStyleSheet(self._ai_model.styleSheet())
        gg.addWidget(self._ai_base_url, 2, 1)

        gg.addWidget(QLabel("URL LM Studio:"), 3, 0)
        self._ai_lmstudio_url = QLineEdit()
        self._ai_lmstudio_url.setPlaceholderText("http://localhost:1234")
        self._ai_lmstudio_url.setStyleSheet(self._ai_model.styleSheet())
        gg.addWidget(self._ai_lmstudio_url, 3, 1)

        gg.addWidget(QLabel("Modelo Visão:"), 4, 0)
        self._ai_vision = QLineEdit()
        self._ai_vision.setPlaceholderText("qwen2.5vl:3b")
        self._ai_vision.setStyleSheet(self._ai_model.styleSheet())
        gg.addWidget(self._ai_vision, 4, 1)

        layout.addWidget(g)

        # Parâmetros
        g2 = QGroupBox("Parâmetros de Inferência")
        g2.setStyleSheet(_GROUP_STYLE)
        gg2 = QGridLayout(g2)
        gg2.setSpacing(14)

        gg2.addWidget(QLabel("Temperatura:"), 0, 0)
        self._ai_temp = self._make_slider(0.0, 2.0, 0.7, 0.1)
        gg2.addWidget(self._ai_temp["widget"], 0, 1)

        gg2.addWidget(QLabel("Max Tokens:"), 1, 0)
        self._ai_max_tokens = QSpinBox()
        self._ai_max_tokens.setRange(256, 32768)
        self._ai_max_tokens.setValue(2048)
        self._ai_max_tokens.setStyleSheet(COMBO_STYLE)
        gg2.addWidget(self._ai_max_tokens, 1, 1)

        gg2.addWidget(QLabel("Top-P:"), 2, 0)
        self._ai_top_p = self._make_slider(0.0, 1.0, 0.9, 0.05)
        gg2.addWidget(self._ai_top_p["widget"], 2, 1)

        gg2.addWidget(QLabel("Top-K:"), 3, 0)
        self._ai_top_k = QSpinBox()
        self._ai_top_k.setRange(1, 200)
        self._ai_top_k.setValue(40)
        self._ai_top_k.setStyleSheet(COMBO_STYLE)
        gg2.addWidget(self._ai_top_k, 3, 1)

        gg2.addWidget(QLabel("Keep Alive:"), 4, 0)
        self._ai_keep_alive = QSpinBox()
        self._ai_keep_alive.setRange(-2, 3600)
        self._ai_keep_alive.setValue(-1)
        self._ai_keep_alive.setToolTip(
            "-1 = manter modelo sempre em RAM\n"
            "0 = descarregar após cada resposta\n"
            "N = manter por N segundos"
        )
        self._ai_keep_alive.setStyleSheet(COMBO_STYLE)
        gg2.addWidget(self._ai_keep_alive, 4, 1)

        layout.addWidget(g2)
        layout.addStretch()
        return w

    # ══════════════════════════════════════════════════════════════════════
    # Aba: Voz
    # ══════════════════════════════════════════════════════════════════════

    def _build_voice_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)

        g = QGroupBox("Síntese de Voz (TTS)")
        g.setStyleSheet(_GROUP_STYLE)
        gg = QGridLayout(g)
        gg.setSpacing(14)

        self._voice_tts = QCheckBox("TTS Ativado")
        self._voice_tts.setStyleSheet(CHECKBOX_STYLE)
        gg.addWidget(self._voice_tts, 0, 0, 1, 2)

        self._voice_auto = QCheckBox("Falar respostas automaticamente")
        self._voice_auto.setStyleSheet(CHECKBOX_STYLE)
        gg.addWidget(self._voice_auto, 1, 0, 1, 2)

        gg.addWidget(QLabel("Velocidade:"), 2, 0)
        self._voice_rate = self._make_slider(50, 300, 170, 10)
        gg.addWidget(self._voice_rate["widget"], 2, 1)

        gg.addWidget(QLabel("Volume:"), 3, 0)
        self._voice_volume = self._make_slider(0.0, 1.0, 0.9, 0.05)
        gg.addWidget(self._voice_volume["widget"], 3, 1)

        gg.addWidget(QLabel("Idioma:"), 4, 0)
        self._voice_lang = QComboBox()
        self._voice_lang.addItems(["pt", "en", "es", "fr", "de", "ja", "ko"])
        self._voice_lang.setStyleSheet(COMBO_STYLE)
        gg.addWidget(self._voice_lang, 4, 1)

        layout.addWidget(g)

        g2 = QGroupBox("Reconhecimento de Voz (STT)")
        g2.setStyleSheet(_GROUP_STYLE)
        gg2 = QGridLayout(g2)
        gg2.setSpacing(14)

        self._voice_stt = QCheckBox("STT Ativado")
        self._voice_stt.setStyleSheet(CHECKBOX_STYLE)
        gg2.addWidget(self._voice_stt, 0, 0, 1, 2)

        gg2.addWidget(QLabel("Modelo STT:"), 1, 0)
        self._voice_stt_model = QComboBox()
        self._voice_stt_model.addItems(["tiny", "base", "small", "medium", "large"])
        self._voice_stt_model.setStyleSheet(COMBO_STYLE)
        gg2.addWidget(self._voice_stt_model, 1, 1)

        layout.addWidget(g2)
        layout.addStretch()
        return w

    # ══════════════════════════════════════════════════════════════════════
    # Aba: Interface
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)

        g = QGroupBox("Aparência")
        g.setStyleSheet(_GROUP_STYLE)
        gg = QGridLayout(g)
        gg.setSpacing(14)

        gg.addWidget(QLabel("Tema:"), 0, 0)
        self._ui_theme = QComboBox()
        self._ui_theme.addItems(["dark", "light"])
        self._ui_theme.setStyleSheet(COMBO_STYLE)
        gg.addWidget(self._ui_theme, 0, 1)

        self._ui_ontop = QCheckBox("Avatar sempre visível (always-on-top)")
        self._ui_ontop.setStyleSheet(CHECKBOX_STYLE)
        gg.addWidget(self._ui_ontop, 1, 0, 1, 2)

        gg.addWidget(QLabel("Tamanho do Avatar:"), 2, 0)
        self._ui_avatar_size = QSpinBox()
        self._ui_avatar_size.setRange(60, 300)
        self._ui_avatar_size.setValue(120)
        self._ui_avatar_size.setStyleSheet(COMBO_STYLE)
        gg.addWidget(self._ui_avatar_size, 2, 1)

        gg.addWidget(QLabel("Largura do Chat:"), 3, 0)
        self._ui_chat_width = QSpinBox()
        self._ui_chat_width.setRange(300, 800)
        self._ui_chat_width.setValue(420)
        self._ui_chat_width.setStyleSheet(COMBO_STYLE)
        gg.addWidget(self._ui_chat_width, 3, 1)

        gg.addWidget(QLabel("Altura do Chat:"), 4, 0)
        self._ui_chat_height = QSpinBox()
        self._ui_chat_height.setRange(400, 1200)
        self._ui_chat_height.setValue(680)
        self._ui_chat_height.setStyleSheet(COMBO_STYLE)
        gg.addWidget(self._ui_chat_height, 4, 1)

        layout.addWidget(g)
        layout.addStretch()
        return w

    # ══════════════════════════════════════════════════════════════════════
    # Aba: Personalidade
    # ══════════════════════════════════════════════════════════════════════

    def _build_personality_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)

        # DEV button (canto superior direito, discreto)
        dev_row = QHBoxLayout()
        dev_row.addStretch()
        self._dev_btn = QPushButton("DEV")
        self._dev_btn.setFixedSize(60, 28)
        self._dev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dev_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #475569; border: 1px solid #1E293B;
                border-radius: 6px; font-size: 10px; }
            QPushButton:hover { background: #1E293B; color: #94A3B8; }
        """)
        self._dev_btn.clicked.connect(self._dev_unlock)
        dev_row.addWidget(self._dev_btn)
        layout.addLayout(dev_row)

        # Usuario
        g_user = QGroupBox("Quem e voce? (para a AURA te conhecer)")
        g_user.setStyleSheet(_GROUP_STYLE)
        gg_user = QGridLayout(g_user)
        gg_user.setSpacing(10)
        gg_user.addWidget(QLabel("Seu nome:"), 0, 0)
        self._user_name = QLineEdit()
        self._user_name.setPlaceholderText("Ex: Bland")
        self._user_name.setStyleSheet("""
            QLineEdit { background: #161B22; color: #E2E8F0; border: 1px solid #21262D;
                border-radius: 8px; padding: 8px 12px; font-size: 13px; }
            QLineEdit:focus { border-color: #388BFD; }
        """)
        gg_user.addWidget(self._user_name, 0, 1)
        gg_user.addWidget(QLabel("Genero:"), 1, 0)
        self._user_gender = QComboBox()
        self._user_gender.addItems(["masculino", "feminino"])
        self._user_gender.setStyleSheet(COMBO_STYLE)
        self._user_gender.setCurrentText("masculino")
        gg_user.addWidget(self._user_gender, 1, 1)
        gg_user.addWidget(QLabel("Sobre voce:"), 2, 0)
        self._user_about = QLineEdit()
        self._user_about.setPlaceholderText("Ex: dev, gosto de jogar, engenheiro de software")
        self._user_about.setStyleSheet(self._user_name.styleSheet())
        gg_user.addWidget(self._user_about, 2, 1)
        layout.addWidget(g_user)

        # Personalidade da AURA
        g = QGroupBox("Personalidade da AURA")
        g.setStyleSheet(_GROUP_STYLE)
        gg = QGridLayout(g)
        gg.setSpacing(14)
        gg.addWidget(QLabel("Nome da AURA:"), 0, 0)
        self._pers_name = QLineEdit()
        self._pers_name.setPlaceholderText("AURA")
        self._pers_name.setStyleSheet(self._user_name.styleSheet())
        gg.addWidget(self._pers_name, 0, 1)
        gg.addWidget(QLabel("Humor (0-100):"), 1, 0)
        self._pers_humor = self._make_slider(0, 100, 75, 5)
        gg.addWidget(self._pers_humor["widget"], 1, 1)
        gg.addWidget(QLabel("Energia (0-100):"), 2, 0)
        self._pers_energia = self._make_slider(0, 100, 80, 5)
        gg.addWidget(self._pers_energia["widget"], 2, 1)
        gg.addWidget(QLabel("Empatia (0-100):"), 3, 0)
        self._pers_empatia = self._make_slider(0, 100, 80, 5)
        gg.addWidget(self._pers_empatia["widget"], 3, 1)
        gg.addWidget(QLabel("Formalidade (0-100):"), 4, 0)
        self._pers_formalidade = self._make_slider(0, 100, 30, 5)
        gg.addWidget(self._pers_formalidade["widget"], 4, 1)
        layout.addWidget(g)

        # Prompt customizado (visivel apenas no modo DEV)
        g_prompt = QGroupBox("Prompt Customizado (modo DEV)")
        g_prompt.setStyleSheet(_GROUP_STYLE)
        gg_p = QVBoxLayout(g_prompt)
        gg_p.addWidget(QLabel("Deixe em branco para usar o prompt automatico baseado nos sliders acima."))
        self._pers_custom_prompt = QLineEdit()
        self._pers_custom_prompt.setPlaceholderText("Ex: Voce e uma assistente sarcastica e ironica...")
        self._pers_custom_prompt.setStyleSheet(self._user_name.styleSheet())
        gg_p.addWidget(self._pers_custom_prompt)
        layout.addWidget(g_prompt)

        layout.addStretch()
        return w

    # ══════════════════════════════════════════════════════════════════════
    # Aba: Angela
    # ══════════════════════════════════════════════════════════════════════

    def _build_angela_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)

        g = QGroupBox("Chief Engineer")
        g.setStyleSheet(_GROUP_STYLE)
        gg = QGridLayout(g)
        gg.setSpacing(14)

        gg.addWidget(QLabel("Modelo:"), 0, 0)
        self._angela_model = QLineEdit()
        self._angela_model.setPlaceholderText("qwen3:4b")
        self._angela_model.setStyleSheet("""
            QLineEdit {
                background: #161B22; color: #E2E8F0;
                border: 1px solid #21262D; border-radius: 8px;
                padding: 8px 12px; font-size: 13px;
            }
            QLineEdit:focus { border-color: #388BFD; }
        """)
        gg.addWidget(self._angela_model, 0, 1)

        gg.addWidget(QLabel("URL Base:"), 1, 0)
        self._angela_url = QLineEdit()
        self._angela_url.setPlaceholderText("http://localhost:11434")
        self._angela_url.setStyleSheet(self._angela_model.styleSheet())
        gg.addWidget(self._angela_url, 1, 1)

        gg.addWidget(QLabel("Temperatura:"), 2, 0)
        self._angela_temp = self._make_slider(0.0, 2.0, 0.3, 0.1)
        gg.addWidget(self._angela_temp["widget"], 2, 1)

        gg.addWidget(QLabel("Max Tokens:"), 3, 0)
        self._angela_max_tokens = QSpinBox()
        self._angela_max_tokens.setRange(256, 32768)
        self._angela_max_tokens.setValue(4096)
        self._angela_max_tokens.setStyleSheet(COMBO_STYLE)
        gg.addWidget(self._angela_max_tokens, 3, 1)

        layout.addWidget(g)
        layout.addStretch()
        return w

    # ══════════════════════════════════════════════════════════════════════
    # Aba: Avançado
    # ══════════════════════════════════════════════════════════════════════

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)

        g = QGroupBox("Memória")
        g.setStyleSheet(_GROUP_STYLE)
        gg = QGridLayout(g)
        gg.setSpacing(14)

        gg.addWidget(QLabel("Limite Curto Prazo:"), 0, 0)
        self._mem_short = QSpinBox()
        self._mem_short.setRange(5, 100)
        self._mem_short.setValue(20)
        self._mem_short.setStyleSheet(COMBO_STYLE)
        gg.addWidget(self._mem_short, 0, 1)

        gg.addWidget(QLabel("Caminho Banco:"), 1, 0)
        self._mem_db = QLineEdit()
        self._mem_db.setPlaceholderText("database/aura.db")
        self._mem_db.setStyleSheet("""
            QLineEdit {
                background: #161B22; color: #E2E8F0;
                border: 1px solid #21262D; border-radius: 8px;
                padding: 8px 12px; font-size: 13px;
            }
        """)
        gg.addWidget(self._mem_db, 1, 1)

        layout.addWidget(g)

        g2 = QGroupBox("Segurança")
        g2.setStyleSheet(_GROUP_STYLE)
        gg2 = QGridLayout(g2)
        gg2.setSpacing(14)

        self._sec_delete = QCheckBox("Confirmar antes de excluir arquivos")
        self._sec_delete.setStyleSheet(CHECKBOX_STYLE)
        gg2.addWidget(self._sec_delete, 0, 0)

        self._sec_scripts = QCheckBox("Confirmar antes de executar scripts")
        self._sec_scripts.setStyleSheet(CHECKBOX_STYLE)
        gg2.addWidget(self._sec_scripts, 1, 0)

        self._sec_close = QCheckBox("Confirmar antes de fechar processos")
        self._sec_close.setStyleSheet(CHECKBOX_STYLE)
        gg2.addWidget(self._sec_close, 2, 0)

        layout.addWidget(g2)

        g3 = QGroupBox("Visão (Contexto)")
        g3.setStyleSheet(_GROUP_STYLE)
        gg3 = QGridLayout(g3)
        gg3.setSpacing(14)

        self._vision_enabled = QCheckBox("Captura de tela ativada")
        self._vision_enabled.setStyleSheet(CHECKBOX_STYLE)
        gg3.addWidget(self._vision_enabled, 0, 0)

        gg3.addWidget(QLabel("Intervalo (s):"), 1, 0)
        self._vision_interval = QSpinBox()
        self._vision_interval.setRange(1, 60)
        self._vision_interval.setValue(5)
        self._vision_interval.setStyleSheet(COMBO_STYLE)
        gg3.addWidget(self._vision_interval, 1, 1)

        layout.addWidget(g3)
        layout.addStretch()
        return w

    def _dev_unlock(self):
        """DEV mode protegido por senha."""
        from PyQt6.QtWidgets import QInputDialog, QLineEdit
        senha, ok = QInputDialog.getText(
            self, "DEV Access", "Senha:", QLineEdit.EchoMode.Password)
        if ok and senha == "BLANDDEV":
            self._dev_mode = True
            self._dev_btn.setText("DEV✓")
            self._dev_btn.setStyleSheet("""
                QPushButton { background: #1A7F37; color: #3FB950; border: 1px solid #3FB950;
                    border-radius: 6px; font-size: 10px; }
            """)
            QMessageBox.information(self, "DEV", 
                "Modo DEV ativado.\n\nAgora voce pode editar o prompt e personalidade livremente.\n"
                "Suas configuracoes serao salvas ao clicar em Salvar.")
            # Habilita campos extras
            self._pers_custom_prompt.setEnabled(True)
            self._pers_humor["slider"].setEnabled(True)
            self._pers_energia["slider"].setEnabled(True)
            self._pers_empatia["slider"].setEnabled(True)
            self._pers_formalidade["slider"].setEnabled(True)
        elif ok:
            QMessageBox.warning(self, "Acesso Negado", "Senha incorreta.")

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════

    def _make_slider(self, mn: float, mx: float, val: float, step: float) -> dict:
        """Cria um slider com label de valor."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        if isinstance(step, float) and step < 1:
            slider = QDoubleSpinBox()
            slider.setRange(mn, mx)
            slider.setSingleStep(step)
            slider.setDecimals(2)
            slider.setValue(val)
            slider.setStyleSheet("""
                QDoubleSpinBox {
                    background: #161B22; color: #E2E8F0;
                    border: 1px solid #21262D; border-radius: 8px;
                    padding: 6px 10px; font-size: 13px;
                    min-width: 80px;
                }
            """)
            # Also add a real slider
            real_slider = None
        else:
            slider = QSpinBox()
            slider.setRange(int(mn), int(mx))
            slider.setSingleStep(int(step))
            slider.setValue(int(val))
            slider.setStyleSheet("""
                QSpinBox {
                    background: #161B22; color: #E2E8F0;
                    border: 1px solid #21262D; border-radius: 8px;
                    padding: 6px 10px; font-size: 13px;
                    min-width: 80px;
                }
            """)
            real_slider = None

        row.addWidget(slider)

        # Barra de progresso visual
        pct_lbl = QLabel(f"{val}")
        pct_lbl.setStyleSheet("color: #7DD3FC; font-size: 12px; min-width: 40px;")
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Atualiza label quando valor muda
        def _update_label(v):
            pct_lbl.setText(f"{v}")

        slider.valueChanged.connect(_update_label)

        row.addWidget(pct_lbl)

        return {"widget": container, "slider": slider, "value": lambda: slider.value()}

    # ══════════════════════════════════════════════════════════════════════
    # Carregar / Salvar
    # ══════════════════════════════════════════════════════════════════════

    def _load_settings(self):
        """Carrega configurações atuais nos campos."""
        try:
            from config.settings import settings
            self._settings = settings

            s = settings.all()

            # AI
            self._ai_provider.setCurrentText(s.get("ai", {}).get("provider", "ollama"))
            self._ai_model.setText(s.get("ai", {}).get("model", "qwen2.5:3b"))
            self._ai_base_url.setText(s.get("ai", {}).get("base_url", "http://localhost:11434"))
            self._ai_lmstudio_url.setText(s.get("ai", {}).get("lmstudio_url", "http://localhost:1234"))
            self._ai_vision.setText(s.get("ai", {}).get("vision_model", "qwen2.5vl:3b"))
            self._ai_temp["slider"].setValue(s.get("ai", {}).get("temperature", 0.7))
            self._ai_max_tokens.setValue(s.get("ai", {}).get("max_tokens", 2048))
            self._ai_keep_alive.setValue(s.get("ai", {}).get("keep_alive", -1))

            # Voice
            self._voice_tts.setChecked(s.get("voice", {}).get("tts_enabled", True))
            self._voice_auto.setChecked(s.get("voice", {}).get("auto_speak", False))
            self._voice_rate["slider"].setValue(s.get("voice", {}).get("voice_rate", 170))
            self._voice_volume["slider"].setValue(s.get("voice", {}).get("voice_volume", 0.9))
            self._voice_lang.setCurrentText(s.get("voice", {}).get("language", "pt"))
            self._voice_stt.setChecked(s.get("voice", {}).get("stt_enabled", False))
            self._voice_stt_model.setCurrentText(s.get("voice", {}).get("stt_model", "tiny"))

            # UI
            self._ui_theme.setCurrentText(s.get("ui", {}).get("theme", "dark"))
            self._ui_ontop.setChecked(s.get("ui", {}).get("always_on_top", True))
            self._ui_avatar_size.setValue(s.get("ui", {}).get("avatar_size", 120))
            self._ui_chat_width.setValue(s.get("ui", {}).get("chat_width", 420))
            self._ui_chat_height.setValue(s.get("ui", {}).get("chat_height", 680))

            # Angela
            self._angela_model.setText(s.get("angela", {}).get("model", "qwen3:4b"))
            self._angela_url.setText(s.get("angela", {}).get("base_url", "http://localhost:11434"))
            self._angela_temp["slider"].setValue(s.get("angela", {}).get("temperature", 0.3))
            self._angela_max_tokens.setValue(s.get("angela", {}).get("max_tokens", 4096))

            # Memory
            self._mem_short.setValue(s.get("memory", {}).get("short_term_limit", 20))
            self._mem_db.setText(s.get("memory", {}).get("db_path", "database/aura.db"))

            # Security
            self._sec_delete.setChecked(s.get("security", {}).get("require_confirm_delete", True))
            self._sec_scripts.setChecked(s.get("security", {}).get("require_confirm_scripts", True))
            self._sec_close.setChecked(s.get("security", {}).get("require_confirm_close_process", True))

            # Vision
            self._vision_enabled.setChecked(s.get("vision", {}).get("enabled", False))
            self._vision_interval.setValue(s.get("vision", {}).get("capture_interval", 5))

        except Exception as e:
            QMessageBox.warning(self, "Aviso", f"Erro ao carregar configurações:\n{e}")

        # Personalidade
        try:
            from config.personality import personality
            self._personality = personality
            self._pers_name.setText(personality.get("nome", "AURA"))
            self._pers_humor["slider"].setValue(personality.get("humor", 75))
            self._pers_energia["slider"].setValue(personality.get("energia", 80))
            self._pers_empatia["slider"].setValue(personality.get("empatia", 80))
            self._pers_formalidade["slider"].setValue(personality.get("formalidade", 30))
        except Exception:
            pass

        # Usuario (memoria)
        try:
            from database.db_manager import db
            row = db.fetchone("SELECT valor FROM memory_permanent WHERE chave='nome_usuario'")
            if row:
                raw = row["valor"]
                if ":" in raw:
                    raw = raw.split(":")[-1].strip()
                self._user_name.setText(raw)
            row_g = db.fetchone("SELECT valor FROM memory_permanent WHERE chave='genero_usuario'")
            if row_g:
                g = row_g["valor"]
                if g in ["masculino", "feminino"]:
                    self._user_gender.setCurrentText(g)
            row2 = db.fetchone("SELECT valor FROM memory_permanent WHERE chave='sobre_usuario'")
            if row2:
                self._user_about.setText(row2["valor"])
        except Exception:
            pass

    def _save_all(self):
        """Salva todas as configurações."""
        try:
            if not self._settings:
                from config.settings import settings
                self._settings = settings

            s = self._settings

            # AI
            s.set("ai", "provider", value=self._ai_provider.currentText())
            s.set("ai", "model", value=self._ai_model.text().strip() or "qwen2.5:3b")
            s.set("ai", "base_url", value=self._ai_base_url.text().strip() or "http://localhost:11434")
            s.set("ai", "lmstudio_url", value=self._ai_lmstudio_url.text().strip() or "http://localhost:1234")
            s.set("ai", "vision_model", value=self._ai_vision.text().strip() or "qwen2.5vl:3b")
            s.set("ai", "temperature", value=self._ai_temp["slider"].value())
            s.set("ai", "max_tokens", value=self._ai_max_tokens.value())
            s.set("ai", "keep_alive", value=self._ai_keep_alive.value())

            # Voice
            s.set("voice", "tts_enabled", value=self._voice_tts.isChecked())
            s.set("voice", "auto_speak", value=self._voice_auto.isChecked())
            s.set("voice", "voice_rate", value=self._voice_rate["slider"].value())
            s.set("voice", "voice_volume", value=self._voice_volume["slider"].value())
            s.set("voice", "language", value=self._voice_lang.currentText())
            s.set("voice", "stt_enabled", value=self._voice_stt.isChecked())
            s.set("voice", "stt_model", value=self._voice_stt_model.currentText())

            # UI
            s.set("ui", "theme", value=self._ui_theme.currentText())
            s.set("ui", "always_on_top", value=self._ui_ontop.isChecked())
            s.set("ui", "avatar_size", value=self._ui_avatar_size.value())
            s.set("ui", "chat_width", value=self._ui_chat_width.value())
            s.set("ui", "chat_height", value=self._ui_chat_height.value())

            # Angela
            s.set("angela", "model", value=self._angela_model.text().strip() or "qwen3:4b")
            s.set("angela", "base_url", value=self._angela_url.text().strip() or "http://localhost:11434")
            s.set("angela", "temperature", value=self._angela_temp["slider"].value())
            s.set("angela", "max_tokens", value=self._angela_max_tokens.value())

            # Memory
            s.set("memory", "short_term_limit", value=self._mem_short.value())
            s.set("memory", "db_path", value=self._mem_db.text().strip() or "database/aura.db")

            # Security
            s.set("security", "require_confirm_delete", value=self._sec_delete.isChecked())
            s.set("security", "require_confirm_scripts", value=self._sec_scripts.isChecked())
            s.set("security", "require_confirm_close_process", value=self._sec_close.isChecked())

            # Vision
            s.set("vision", "enabled", value=self._vision_enabled.isChecked())
            s.set("vision", "capture_interval", value=self._vision_interval.value())

            # Salva dados do usuario na memoria
            try:
                from database.db_manager import db
                nome = self._user_name.text().strip()
                about = self._user_about.text().strip()
                gender = self._user_gender.currentText().strip()
                if nome:
                    db.execute("""INSERT OR REPLACE INTO memory_permanent
                        (categoria, chave, valor, importance) VALUES (?,?,?,?)""",
                        ("usuario", "nome_usuario", f"Nome do usuario: {nome}", 10))
                if gender:
                    db.execute("""INSERT OR REPLACE INTO memory_permanent
                        (categoria, chave, valor, importance) VALUES (?,?,?,?)""",
                        ("usuario", "genero_usuario", gender, 9))
                if about:
                    db.execute("""INSERT OR REPLACE INTO memory_permanent
                        (categoria, chave, valor, importance) VALUES (?,?,?,?)""",
                        ("usuario", "sobre_usuario", about, 8))
            except Exception:
                pass

            # Personalidade
            try:
                import json
                from config.personality import personality
                personality_json_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "config", "personality.json"
                )
                pers_data = {
                    "nome": self._pers_name.text().strip() or "AURA",
                    "humor": self._pers_humor["slider"].value(),
                    "energia": self._pers_energia["slider"].value(),
                    "empatia": self._pers_empatia["slider"].value(),
                    "formalidade": self._pers_formalidade["slider"].value(),
                }
                with open(personality_json_path, "w", encoding="utf-8") as f:
                    json.dump(pers_data, f, indent=2, ensure_ascii=False)
                # Recarrega personalidade
                personality._data.clear()
                personality._data.update(pers_data)
            except Exception as e:
                logger = __import__('core.logger', fromlist=['setup_logger']).setup_logger("settings_page")
                logger.warning(f"Não foi possível salvar personality.json: {e}")

            QMessageBox.information(self, "Sucesso", "✅ Configurações salvas com sucesso!")

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao salvar configurações:\n{e}")

    def on_show(self):
        self._load_settings()
