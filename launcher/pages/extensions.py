"""
launcher/pages/extensions.py
============================
Gerenciador de Extensões/Plugins.
Observa a pasta extensions/ e mostra manifest.json de cada plugin.
"""

import os
import json
from typing import List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QMessageBox, QFileDialog, QCheckBox,
)
from PyQt6.QtCore import Qt


_CARD_STYLE = """
    QFrame#ext_card {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 16px;
    }
    QFrame#ext_card:hover {
        border-color: #388BFD;
    }
"""

_CARD_ACTIVE = """
    QFrame#ext_card {
        background: #0D2B1F;
        border: 1px solid #1A7F37;
        border-radius: 12px;
        padding: 16px;
    }
"""

BTN_PRIMARY = """
    QPushButton {
        background: #1F6FEB; color: #fff;
        border: none; border-radius: 8px;
        padding: 8px 16px; font-size: 13px;
    }
    QPushButton:hover { background: #388BFD; }
"""

BTN_DANGER = """
    QPushButton {
        background: #DA3633; color: #fff;
        border: none; border-radius: 8px;
        padding: 8px 16px; font-size: 13px;
    }
    QPushButton:hover { background: #F85149; }
"""

BTN_SECONDARY = """
    QPushButton {
        background: #21262D; color: #E2E8F0;
        border: 1px solid #30363D; border-radius: 8px;
        padding: 8px 16px; font-size: 13px;
    }
    QPushButton:hover { background: #30363D; }
"""


class ExtensionsPage(QWidget):
    """Gerenciamento visual de plugins/extensões."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._extensions_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "extensions"
        )
        os.makedirs(self._extensions_dir, exist_ok=True)
        self._build_ui()
        self._scan_extensions()

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
        title = QLabel("🧩  Extensões")
        title.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("🔄  Atualizar")
        refresh_btn.setStyleSheet(BTN_SECONDARY)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._scan_extensions)
        header.addWidget(refresh_btn)

        import_btn = QPushButton("📁  Instalar Extensão")
        import_btn.setStyleSheet(BTN_PRIMARY)
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._install_extension)
        header.addWidget(import_btn)

        layout.addLayout(header)

        info = QLabel(
            "Extensões são plugins que adicionam funcionalidades à AURA.\n"
            "Cada extensão possui: manifest.json, ícone, configuração, permissões e código."
        )
        info.setStyleSheet("color: #64748B; font-size: 13px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Grid de extensões
        self._ext_grid = QGridLayout()
        self._ext_grid.setSpacing(16)
        layout.addLayout(self._ext_grid)

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

    def on_show(self):
        self._scan_extensions()

    def _scan_extensions(self):
        """Escaneia a pasta extensions/ em busca de plugins."""
        while self._ext_grid.count():
            item = self._ext_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        extensions = []
        if os.path.isdir(self._extensions_dir):
            for folder in sorted(os.listdir(self._extensions_dir)):
                folder_path = os.path.join(self._extensions_dir, folder)
                manifest_path = os.path.join(folder_path, "manifest.json")
                if not os.path.isdir(folder_path):
                    continue

                ext = {
                    "id": folder,
                    "name": folder,
                    "path": folder_path,
                    "manifest": {},
                    "active": True,
                }

                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path) as f:
                            ext["manifest"] = json.load(f)
                        ext["name"] = ext["manifest"].get("name", folder)
                        ext["active"] = ext["manifest"].get("enabled", True)
                    except Exception:
                        pass

                extensions.append(ext)

        if not extensions:
            empty = QLabel(
                "Nenhuma extensão instalada.\n\n"
                "Coloque pastas de extensão em extensions/\n"
                "ou clique em 'Instalar Extensão' para importar."
            )
            empty.setStyleSheet("color: #64748B; font-size: 15px; padding: 40px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._ext_grid.addWidget(empty, 0, 0)
            return

        for i, ext in enumerate(extensions):
            card = self._make_ext_card(ext)
            row, col = divmod(i, 2)
            self._ext_grid.addWidget(card, row, col)

    def _make_ext_card(self, ext: dict) -> QFrame:
        manifest = ext.get("manifest", {})
        is_active = ext.get("active", True)

        card = QFrame()
        card.setObjectName("ext_card")
        card.setStyleSheet(_CARD_ACTIVE if is_active else _CARD_STYLE)

        inner = QVBoxLayout(card)
        inner.setSpacing(8)

        # Header
        header = QHBoxLayout()
        icon = QLabel("🧩")
        icon.setStyleSheet("font-size: 24px;")
        header.addWidget(icon)

        name = QLabel(ext["name"])
        name.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: bold;")
        header.addWidget(name)
        header.addStretch()

        status = QLabel("ATIVO" if is_active else "INATIVO")
        status.setStyleSheet(
            f"background: {'#1A7F37' if is_active else '#30363D'}; "
            f"color: {'#fff' if is_active else '#8B949E'}; "
            "font-size: 10px; font-weight: bold; padding: 2px 8px; border-radius: 6px;"
        )
        header.addWidget(status)
        inner.addLayout(header)

        # Detalhes
        ver = manifest.get("version", "1.0.0")
        author = manifest.get("author", "Desconhecido")
        desc = manifest.get("description", "Sem descrição")
        details = QLabel(f"v{ver}  •  {author}\n{desc}")
        details.setWordWrap(True)
        details.setStyleSheet("color: #94A3B8; font-size: 12px;")
        inner.addWidget(details)

        # Permissões
        perms = manifest.get("permissions", [])
        if perms:
            perm_lbl = QLabel(f"Permissões: {', '.join(perms)}")
            perm_lbl.setStyleSheet("color: #CE93D8; font-size: 11px;")
            inner.addWidget(perm_lbl)

        # Botões
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        toggle_btn = QPushButton("Desativar" if is_active else "Ativar")
        toggle_btn.setStyleSheet(BTN_PRIMARY)
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_btn.clicked.connect(lambda: self._toggle_extension(ext))
        btn_row.addWidget(toggle_btn)

        config_btn = QPushButton("⚙ Config")
        config_btn.setStyleSheet(BTN_SECONDARY)
        config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addWidget(config_btn)

        remove_btn = QPushButton("🗑 Remover")
        remove_btn.setStyleSheet(BTN_DANGER)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self._remove_extension(ext))
        btn_row.addWidget(remove_btn)

        inner.addLayout(btn_row)
        return card

    def _toggle_extension(self, ext: dict):
        """Ativa/desativa uma extensão."""
        new_state = not ext.get("active", True)
        ext["active"] = new_state

        manifest = ext.get("manifest", {})
        manifest["enabled"] = new_state
        ext["manifest"] = manifest

        manifest_path = os.path.join(ext["path"], "manifest.json")
        try:
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Aviso", f"Não foi possível salvar manifest.json:\n{e}")

        self._scan_extensions()

    def _install_extension(self):
        """Importa uma pasta de extensão."""
        folder = QFileDialog.getExistingDirectory(
            self, "Selecionar pasta da extensão"
        )
        if not folder:
            return

        ext_name = os.path.basename(folder)
        dest = os.path.join(self._extensions_dir, ext_name)

        if os.path.exists(dest):
            QMessageBox.warning(
                self, "Aviso",
                f"A extensão '{ext_name}' já existe."
            )
            return

        try:
            import shutil
            shutil.copytree(folder, dest)
            QMessageBox.information(
                self, "Sucesso",
                f"Extensão '{ext_name}' instalada!"
            )
            self._scan_extensions()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao instalar:\n{e}")

    def _remove_extension(self, ext: dict):
        """Remove uma extensão."""
        reply = QMessageBox.question(
            self, "Confirmar Remoção",
            f"Remover a extensão '{ext['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            import shutil
            shutil.rmtree(ext["path"])
            self._scan_extensions()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao remover:\n{e}")
