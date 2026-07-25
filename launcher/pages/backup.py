"""
launcher/pages/backup.py
========================
Página de Backup e Restauração.
Exporta/importa configurações, memórias, banco de dados, modelos.
"""

import os
import json
import shutil
import zipfile
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QMessageBox, QFileDialog, QCheckBox, QProgressBar,
)
from PyQt6.QtCore import Qt
from launcher.pages._widgets import CARD_STYLE as _CARD_STYLE
from launcher.pages._widgets import make_card, make_title, make_subtitle, make_btn_primary, make_btn_secondary, make_btn_danger


_CARD_STYLE = """
    QFrame#backup_card {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 20px;
    }
"""

BTN_PRIMARY_STYLE = """
    QPushButton {
        background: #1F6FEB; color: #fff;
        border: none; border-radius: 8px;
        padding: 10px 20px; font-size: 14px;
    }
    QPushButton:hover { background: #388BFD; }
"""

BTN_SECONDARY_STYLE = """
    QPushButton {
        background: #21262D; color: #E2E8F0;
        border: 1px solid #30363D; border-radius: 8px;
        padding: 10px 20px; font-size: 14px;
    }
    QPushButton:hover { background: #30363D; }
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


class BackupPage(QWidget):
    """Backup e restauração de configurações e dados."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self._build_ui()

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
        title = QLabel("💾  Backup & Restauração")
        title.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        sub = QLabel(
            "Exporte configurações, memórias e dados ou restaure um backup anterior.\n"
            "Backups são salvos como arquivos .zip contendo todos os dados selecionados."
        )
        sub.setStyleSheet("color: #64748B; font-size: 13px;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # ── Criar Backup ───────────────────────────────────────────────────
        backup_card = QFrame()
        backup_card.setObjectName("backup_card")
        backup_card.setStyleSheet(_CARD_STYLE)

        bc = QVBoxLayout(backup_card)
        bc.setSpacing(12)

        bc_title = QLabel("📤  Criar Backup")
        bc_title.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: bold;")
        bc.addWidget(bc_title)

        # Itens para backup
        items_layout = QGridLayout()
        items_layout.setSpacing(10)

        self._cb_config = QCheckBox("Configurações (settings.json, personality.json)")
        self._cb_config.setChecked(True)
        self._cb_config.setStyleSheet(CHECKBOX_STYLE)

        self._cb_memory = QCheckBox("Memórias e banco de dados")
        self._cb_memory.setChecked(True)
        self._cb_memory.setStyleSheet(CHECKBOX_STYLE)

        self._cb_models_meta = QCheckBox("Manifests de modelos (sem .gguf)")
        self._cb_models_meta.setChecked(True)
        self._cb_models_meta.setStyleSheet(CHECKBOX_STYLE)

        self._cb_extensions = QCheckBox("Extensões")
        self._cb_extensions.setChecked(True)
        self._cb_extensions.setStyleSheet(CHECKBOX_STYLE)

        self._cb_profiles = QCheckBox("Perfis")
        self._cb_profiles.setChecked(True)
        self._cb_profiles.setStyleSheet(CHECKBOX_STYLE)

        self._cb_cache = QCheckBox("Cache (pode ser grande)")
        self._cb_cache.setChecked(False)
        self._cb_cache.setStyleSheet(CHECKBOX_STYLE)

        items_layout.addWidget(self._cb_config, 0, 0)
        items_layout.addWidget(self._cb_memory, 0, 1)
        items_layout.addWidget(self._cb_models_meta, 1, 0)
        items_layout.addWidget(self._cb_extensions, 1, 1)
        items_layout.addWidget(self._cb_profiles, 2, 0)
        items_layout.addWidget(self._cb_cache, 2, 1)

        bc.addLayout(items_layout)

        export_btn = QPushButton("📤  Exportar Backup (.zip)")
        export_btn.setStyleSheet(BTN_PRIMARY_STYLE)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._create_backup)
        bc.addWidget(export_btn)

        layout.addWidget(backup_card)

        # ── Restaurar Backup ───────────────────────────────────────────────
        restore_card = QFrame()
        restore_card.setObjectName("backup_card")
        restore_card.setStyleSheet(_CARD_STYLE)

        rc = QVBoxLayout(restore_card)
        rc.setSpacing(12)

        rc_title = QLabel("📥  Restaurar Backup")
        rc_title.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: bold;")
        rc.addWidget(rc_title)

        rc_desc = QLabel(
            "Selecione um arquivo .zip de backup para restaurar.\n"
            "⚠️ Isso substituirá os dados atuais pelos do backup."
        )
        rc_desc.setStyleSheet("color: #94A3B8; font-size: 13px;")
        rc_desc.setWordWrap(True)
        rc.addWidget(rc_desc)

        import_btn = QPushButton("📥  Restaurar Backup (.zip)")
        import_btn.setStyleSheet(BTN_SECONDARY_STYLE)
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._restore_backup)
        rc.addWidget(import_btn)

        layout.addWidget(restore_card)

        # ── Progresso ──────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                background: #21262D; border: none; border-radius: 6px;
                height: 8px;
            }
            QProgressBar::chunk { background: #1F6FEB; border-radius: 6px; }
        """)
        layout.addWidget(self._progress)

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

    def on_show(self):
        pass

    def _create_backup(self):
        """Cria arquivo .zip de backup."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Backup",
            f"AURA_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            "Arquivos ZIP (*.zip)"
        )
        if not file_path:
            return

        self._progress.setVisible(True)
        self._progress.setValue(0)

        try:
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                items = 0

                # Configurações
                if self._cb_config.isChecked():
                    config_dir = os.path.join(self._root_dir, "config")
                    self._add_dir_to_zip(zf, config_dir, "config")
                    items += 1

                # Memória / banco
                if self._cb_memory.isChecked():
                    db_path = os.path.join(self._root_dir, "database")
                    self._add_dir_to_zip(zf, db_path, "database")
                    items += 1

                # Modelos (só manifests)
                if self._cb_models_meta.isChecked():
                    models_dir = os.path.join(self._root_dir, "models")
                    if os.path.isdir(models_dir):
                        for folder in os.listdir(models_dir):
                            fpath = os.path.join(models_dir, folder)
                            if os.path.isdir(fpath):
                                for fname in os.listdir(fpath):
                                    if fname.endswith(('.json', '.png', '.jpg', '.md')):
                                        arcname = f"models/{folder}/{fname}"
                                        zf.write(os.path.join(fpath, fname), arcname)
                    items += 1

                # Extensões
                if self._cb_extensions.isChecked():
                    ext_dir = os.path.join(self._root_dir, "extensions")
                    self._add_dir_to_zip(zf, ext_dir, "extensions")
                    items += 1

                # Perfis
                if self._cb_profiles.isChecked():
                    profiles_dir = os.path.join(self._root_dir, "profiles")
                    self._add_dir_to_zip(zf, profiles_dir, "profiles")
                    items += 1

                # Cache
                if self._cb_cache.isChecked():
                    cache_dir = os.path.join(self._root_dir, "cache")
                    self._add_dir_to_zip(zf, cache_dir, "cache")
                    items += 1

            self._progress.setValue(100)
            QMessageBox.information(
                self, "Backup Criado",
                f"✅ Backup salvo com sucesso!\n\n"
                f"Arquivo: {file_path}\n"
                f"Itens incluídos: {items}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao criar backup:\n{e}")
        finally:
            self._progress.setVisible(False)

    def _restore_backup(self):
        """Restaura de um arquivo .zip."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Backup",
            "", "Arquivos ZIP (*.zip)"
        )
        if not file_path:
            return

        reply = QMessageBox.warning(
            self, "Confirmar Restauração",
            "⚠️ Isso substituirá os dados atuais pelos do backup.\n\n"
            "Recomendamos criar um backup dos dados atuais primeiro.\n\n"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._progress.setVisible(True)
        self._progress.setValue(0)

        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                total = len(zf.namelist())
                for i, member in enumerate(zf.namelist()):
                    zf.extract(member, self._root_dir)
                    self._progress.setValue(int((i + 1) / total * 100))

            self._progress.setValue(100)
            QMessageBox.information(
                self, "Backup Restaurado",
                "✅ Backup restaurado com sucesso!\n\n"
                "Reinicie o launcher para aplicar as alterações."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao restaurar:\n{e}")
        finally:
            self._progress.setVisible(False)

    def _add_dir_to_zip(self, zf: zipfile.ZipFile, dir_path: str, arc_prefix: str):
        """Adiciona uma pasta ao zip recursivamente."""
        if not os.path.isdir(dir_path):
            return
        for root, _, files in os.walk(dir_path):
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = os.path.join(arc_prefix, os.path.relpath(fpath, dir_path))
                zf.write(fpath, arcname)
