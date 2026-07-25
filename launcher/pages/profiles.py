"""
launcher/pages/profiles.py
===========================
Gerenciador de Perfis de Usuário.
Cada perfil tem suas próprias configurações, memórias e temas.
"""

import os
import json
import shutil
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QMessageBox, QInputDialog, QLineEdit,
)
from PyQt6.QtCore import Qt
from launcher.pages._widgets import CARD_STYLE as _CARD_STYLE
from launcher.pages._widgets import make_card, make_title, make_subtitle, make_btn_primary, make_btn_secondary, make_btn_danger


_CARD_STYLE = """
    QFrame#profile_card {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 16px;
    }
    QFrame#profile_card:hover {
        border-color: #388BFD;
    }
"""

_CARD_ACTIVE = """
    QFrame#profile_card {
        background: #0E1F2E;
        border: 2px solid #388BFD;
        border-radius: 12px;
        padding: 16px;
    }
"""

BTN_PRIMARY_STYLE = """
    QPushButton {
        background: #1F6FEB; color: #fff;
        border: none; border-radius: 8px;
        padding: 8px 16px; font-size: 13px;
    }
    QPushButton:hover { background: #388BFD; }
"""

BTN_DANGER_STYLE = """
    QPushButton {
        background: #DA3633; color: #fff;
        border: none; border-radius: 8px;
        padding: 8px 16px; font-size: 13px;
    }
    QPushButton:hover { background: #F85149; }
"""

BTN_SECONDARY_STYLE = """
    QPushButton {
        background: #21262D; color: #E2E8F0;
        border: 1px solid #30363D; border-radius: 8px;
        padding: 8px 16px; font-size: 13px;
    }
    QPushButton:hover { background: #30363D; }
"""


class ProfilesPage(QWidget):
    """Gerenciamento de perfis de usuário."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profiles_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "profiles"
        )
        os.makedirs(self._profiles_dir, exist_ok=True)
        self._active_profile = self._load_active()
        self._build_ui()
        self._scan_profiles()

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
        title = QLabel("👤  Perfis")
        title.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        new_btn = QPushButton("➕  Novo Perfil")
        new_btn.setStyleSheet(BTN_PRIMARY_STYLE)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._create_profile)
        header.addWidget(new_btn)

        layout.addLayout(header)

        info = QLabel(
            "Perfis permitem que múltiplos usuários tenham suas próprias "
            "configurações, memórias e preferências.\n"
            f"Perfil ativo: {self._active_profile or 'Nenhum'}"
        )
        info.setStyleSheet("color: #94A3B8; font-size: 13px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Grid de perfis
        self._profiles_grid = QGridLayout()
        self._profiles_grid.setSpacing(16)
        layout.addLayout(self._profiles_grid)

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

    def on_show(self):
        self._scan_profiles()

    def _load_active(self) -> str:
        """Carrega qual perfil está ativo."""
        active_file = os.path.join(self._profiles_dir, ".active")
        if os.path.exists(active_file):
            try:
                with open(active_file) as f:
                    return f.read().strip()
            except Exception:
                pass
        return ""

    def _save_active(self, name: str):
        """Salva o perfil ativo."""
        active_file = os.path.join(self._profiles_dir, ".active")
        with open(active_file, "w") as f:
            f.write(name)

    def _scan_profiles(self):
        """Escaneia perfis salvos."""
        while self._profiles_grid.count():
            item = self._profiles_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        profiles = []
        if os.path.isdir(self._profiles_dir):
            for folder in sorted(os.listdir(self._profiles_dir)):
                if folder.startswith("."):
                    continue
                folder_path = os.path.join(self._profiles_dir, folder)
                if os.path.isdir(folder_path):
                    profile = {
                        "name": folder,
                        "path": folder_path,
                        "is_active": folder == self._active_profile,
                    }
                    # Lê metadata
                    meta_path = os.path.join(folder_path, "profile.json")
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path) as f:
                                profile["meta"] = json.load(f)
                        except Exception:
                            profile["meta"] = {}
                    else:
                        profile["meta"] = {}
                    profiles.append(profile)

        if not profiles:
            empty = QLabel(
                "Nenhum perfil criado.\n\n"
                "Clique em 'Novo Perfil' para criar o primeiro."
            )
            empty.setStyleSheet("color: #64748B; font-size: 15px; padding: 40px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._profiles_grid.addWidget(empty, 0, 0)
            return

        for i, profile in enumerate(profiles):
            card = self._make_profile_card(profile)
            row, col = divmod(i, 2)
            self._profiles_grid.addWidget(card, row, col)

    def _make_profile_card(self, profile: dict) -> QFrame:
        is_active = profile["is_active"]
        meta = profile.get("meta", {})

        card = QFrame()
        card.setObjectName("profile_card")
        card.setStyleSheet(_CARD_ACTIVE if is_active else _CARD_STYLE)

        inner = QVBoxLayout(card)
        inner.setSpacing(8)

        # Header
        header = QHBoxLayout()
        icon = QLabel("👤")
        icon.setStyleSheet("font-size: 24px;")
        header.addWidget(icon)

        name = QLabel(profile["name"])
        name.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: bold;")
        header.addWidget(name)
        header.addStretch()

        if is_active:
            badge = QLabel("ATIVO")
            badge.setStyleSheet("""
                background: #388BFD; color: #fff; font-size: 10px;
                font-weight: bold; padding: 2px 8px; border-radius: 6px;
            """)
            header.addWidget(badge)

        inner.addLayout(header)

        # Info
        created = meta.get("created", "Desconhecido")
        theme = meta.get("theme", "dark")
        model = meta.get("model", "padrão")
        info = QLabel(f"Criado: {created}  •  Tema: {theme}  •  Modelo: {model}")
        info.setStyleSheet("color: #94A3B8; font-size: 12px;")
        inner.addWidget(info)

        # Botões
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        if not is_active:
            activate_btn = QPushButton("Ativar")
            activate_btn.setStyleSheet(BTN_PRIMARY_STYLE)
            activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            activate_btn.clicked.connect(lambda: self._activate_profile(profile["name"]))
            btn_row.addWidget(activate_btn)

        duplicate_btn = QPushButton("Duplicar")
        duplicate_btn.setStyleSheet(BTN_SECONDARY_STYLE)
        duplicate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        duplicate_btn.clicked.connect(lambda: self._duplicate_profile(profile["name"]))
        btn_row.addWidget(duplicate_btn)

        rename_btn = QPushButton("Renomear")
        rename_btn.setStyleSheet(BTN_SECONDARY_STYLE)
        rename_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rename_btn.clicked.connect(lambda: self._rename_profile(profile["name"]))
        btn_row.addWidget(rename_btn)

        if not is_active:
            remove_btn = QPushButton("🗑")
            remove_btn.setStyleSheet(BTN_DANGER_STYLE)
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.clicked.connect(lambda: self._delete_profile(profile["name"]))
            btn_row.addWidget(remove_btn)

        inner.addLayout(btn_row)
        return card

    def _create_profile(self):
        """Cria um novo perfil."""
        name, ok = QInputDialog.getText(
            self, "Novo Perfil",
            "Nome do perfil:",
            QLineEdit.EchoMode.Normal,
            "Meu Perfil"
        )
        if not ok or not name.strip():
            return

        name = name.strip()
        safe_name = name.replace(" ", "_").lower()

        profile_dir = os.path.join(self._profiles_dir, safe_name)
        if os.path.exists(profile_dir):
            QMessageBox.warning(self, "Aviso", f"Perfil '{safe_name}' já existe.")
            return

        os.makedirs(profile_dir, exist_ok=True)

        # Cria metadata
        meta = {
            "name": name,
            "created": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "theme": "dark",
            "model": "padrão",
        }
        with open(os.path.join(profile_dir, "profile.json"), "w") as f:
            json.dump(meta, f, indent=2)

        # Copia configurações atuais como base
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        for fname in ["settings.json", "personality.json"]:
            src = os.path.join(root, "config", fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(profile_dir, fname))

        self._scan_profiles()

    def _activate_profile(self, name: str):
        """Ativa um perfil."""
        profile_dir = os.path.join(self._profiles_dir, name)
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        try:
            # Copia configs do perfil para o config/
            for fname in ["settings.json", "personality.json"]:
                src = os.path.join(profile_dir, fname)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(root, "config", fname))

            self._active_profile = name
            self._save_active(name)
            self._scan_profiles()

            QMessageBox.information(
                self, "Perfil Ativado",
                f"Perfil '{name}' ativado!\n\n"
                "As configurações foram carregadas."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao ativar perfil:\n{e}")

    def _duplicate_profile(self, name: str):
        """Duplica um perfil."""
        new_name, ok = QInputDialog.getText(
            self, "Duplicar Perfil",
            "Nome para a cópia:",
            text=f"{name}_copia"
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()
        safe_new = new_name.replace(" ", "_").lower()
        src = os.path.join(self._profiles_dir, name)
        dst = os.path.join(self._profiles_dir, safe_new)

        if os.path.exists(dst):
            QMessageBox.warning(self, "Aviso", f"'{safe_new}' já existe.")
            return

        try:
            shutil.copytree(src, dst)
            # Atualiza metadata
            meta_path = os.path.join(dst, "profile.json")
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
                meta["name"] = new_name
                meta["created"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                with open(meta_path, "w") as f:
                    json.dump(meta, f, indent=2)

            self._scan_profiles()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao duplicar:\n{e}")

    def _rename_profile(self, name: str):
        """Renomeia um perfil."""
        new_name, ok = QInputDialog.getText(
            self, "Renomear Perfil",
            "Novo nome:",
            text=name
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()
        safe_new = new_name.replace(" ", "_").lower()
        src = os.path.join(self._profiles_dir, name)
        dst = os.path.join(self._profiles_dir, safe_new)

        if src == dst:
            return

        if os.path.exists(dst):
            QMessageBox.warning(self, "Aviso", f"'{safe_new}' já existe.")
            return

        try:
            os.rename(src, dst)
            # Atualiza metadata
            meta_path = os.path.join(dst, "profile.json")
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
                meta["name"] = new_name
                with open(meta_path, "w") as f:
                    json.dump(meta, f, indent=2)

            if self._active_profile == name:
                self._active_profile = safe_new
                self._save_active(safe_new)

            self._scan_profiles()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao renomear:\n{e}")

    def _delete_profile(self, name: str):
        """Remove um perfil."""
        reply = QMessageBox.question(
            self, "Confirmar Remoção",
            f"Remover permanentemente o perfil '{name}'?\n\n"
            "Esta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            shutil.rmtree(os.path.join(self._profiles_dir, name))
            if self._active_profile == name:
                self._active_profile = ""
                self._save_active("")
            self._scan_profiles()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao remover:\n{e}")
