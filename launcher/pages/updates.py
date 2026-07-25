"""
launcher/pages/updates.py — V11 com Auto-Updater
================================================
Verifica versões no GitHub Releases, baixa e aplica atualizações.
"""
import os, sys, threading
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QMessageBox, QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer
from launcher.pages._widgets import make_card, make_btn_primary, make_btn_secondary

_CARD = """QFrame#up_card { background:#161B22; border:1px solid #21262D; border-radius:12px; padding:16px; }"""
_CARD_UPDATE = """QFrame#up_card { background:#1A2744; border:1px solid #388BFD; border-radius:12px; padding:16px; }"""
BTN_PRIMARY = """QPushButton { background:#1F6FEB; color:#fff; border:none; border-radius:8px; padding:8px 16px; font-size:13px; } QPushButton:hover { background:#388BFD; } QPushButton:disabled { background:#21262D; color:#484F58; }"""
BTN_SECONDARY = """QPushButton { background:#21262D; color:#E2E8F0; border:1px solid #30363D; border-radius:8px; padding:8px 16px; font-size:13px; } QPushButton:hover { background:#30363D; }"""

class UpdatesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_check = "Nunca"
        self._updates_available = []
        self._checking = False
        self._updating = False
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0,0,0,0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32,24,32,32)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("🔄  Atualizações")
        title.setStyleSheet("color:#E2E8F0; font-size:20px; font-weight:bold;")
        header.addWidget(title)
        header.addStretch()
        self._check_btn = QPushButton("🔍  Verificar Atualizações")
        self._check_btn.setStyleSheet(BTN_PRIMARY)
        self._check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_btn.clicked.connect(self._check_updates)
        header.addWidget(self._check_btn)
        layout.addLayout(header)

        self._last_lbl = QLabel(f"Última verificação: {self._last_check}")
        self._last_lbl.setStyleSheet("color:#64748B; font-size:12px;")
        layout.addWidget(self._last_lbl)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#CE93D8; font-size:13px;")
        self._status_lbl.setVisible(False)
        layout.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setStyleSheet("QProgressBar { background:#21262D; border-radius:6px; height:8px; } QProgressBar::chunk { background:#1F6FEB; border-radius:6px; }")
        layout.addWidget(self._progress)

        self._modules_grid = QGridLayout()
        self._modules_grid.setSpacing(16)
        layout.addLayout(self._modules_grid)

        self._update_all_btn = QPushButton("⬇  Baixar e Instalar Atualizações")
        self._update_all_btn.setStyleSheet(BTN_PRIMARY + " padding:12px 24px; font-size:15px;")
        self._update_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_all_btn.clicked.connect(self._apply_updates)
        self._update_all_btn.setVisible(False)
        layout.addWidget(self._update_all_btn)

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)
        QTimer.singleShot(300, self._check_updates)

    def on_show(self):
        pass

    def _check_updates(self):
        if self._checking: return
        self._checking = True
        self._check_btn.setEnabled(False)
        self._status_lbl.setText("🔍 Verificando GitHub Releases...")
        self._status_lbl.setVisible(True)
        def _run():
            try:
                from updater.checker import check_for_updates
                updates = check_for_updates()
                self._updates_available = updates
            except Exception:
                self._updates_available = []
            self._last_check = datetime.now().strftime("%d/%m/%Y %H:%M")
            self._checking = False
            QTimer.singleShot(0, self._on_check_done)
        threading.Thread(target=_run, daemon=True).start()

    def _on_check_done(self):
        self._check_btn.setEnabled(True)
        self._last_lbl.setText(f"Última verificação: {self._last_check}")
        if self._updates_available:
            n = len(self._updates_available)
            self._status_lbl.setText(f"🎉 {n} atualização(ões) disponível(is)!")
            self._status_lbl.setStyleSheet("color:#3FB950; font-size:13px;")
            self._update_all_btn.setVisible(True)
        else:
            self._status_lbl.setText("✅ Tudo atualizado!")
            self._status_lbl.setStyleSheet("color:#3FB950; font-size:13px;")
            self._update_all_btn.setVisible(False)
        self._render_modules()

    def _render_modules(self):
        while self._modules_grid.count():
            item = self._modules_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        from updater import MODULES
        update_map = {u.module_id: u for u in self._updates_available}
        for i, (mod_id, mod_info) in enumerate(MODULES.items()):
            update = update_map.get(mod_id)
            card = self._make_module_card(mod_info, update)
            row, col = divmod(i, 2)
            self._modules_grid.addWidget(card, row, col)

    def _make_module_card(self, mod, update=None):
        has_update = update and update.is_update_available
        card = QFrame()
        card.setObjectName("up_card")
        card.setStyleSheet(_CARD_UPDATE if has_update else _CARD)
        inner = QVBoxLayout(card)
        inner.setSpacing(8)
        name_row = QHBoxLayout()
        name = QLabel(f"📦  {mod['name']}")
        name.setStyleSheet("color:#E2E8F0; font-size:15px; font-weight:bold;")
        name_row.addWidget(name)
        name_row.addStretch()
        ver = QLabel(f"v{mod['version']}")
        ver.setStyleSheet("color:#7DD3FC; font-size:12px;")
        name_row.addWidget(ver)
        if has_update:
            arrow = QLabel(f"→ v{update.latest_version}")
            arrow.setStyleSheet("color:#3FB950; font-size:12px; font-weight:bold;")
            name_row.addWidget(arrow)
        inner.addLayout(name_row)
        desc = QLabel(mod.get("desc", ""))
        desc.setStyleSheet("color:#94A3B8; font-size:12px;")
        inner.addWidget(desc)
        if has_update:
            status = QLabel(f"⬆ Atualização disponível (v{update.latest_version})")
            status.setStyleSheet("color:#D29922; font-size:12px;")
            inner.addWidget(status)
        else:
            status = QLabel("✓ Atualizado")
            status.setStyleSheet("color:#3FB950; font-size:12px;")
            inner.addWidget(status)
        return card

    def _apply_updates(self):
        if self._updating or not self._updates_available: return
        reply = QMessageBox.question(self, "Confirmar",
            f"{len(self._updates_available)} módulo(s) serão atualizados.\n\nBackup será criado.\nRollback automático se falhar.\n\nContinuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
        if reply != QMessageBox.StandardButton.Yes: return
        self._updating = True
        self._update_all_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status_lbl.setText("📦 Baixando atualização...")
        self._status_lbl.setStyleSheet("color:#CE93D8; font-size:13px;")
        update = self._updates_available[0]
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        cache_dir = os.path.join(root_dir, "cache")
        os.makedirs(cache_dir, exist_ok=True)
        from updater.downloader import DownloadThread
        def _on_progress(received, total):
            if total > 0:
                self._progress.setValue(int(received/total*100))
                self._status_lbl.setText(f"📦 Baixando... {received/1024/1024:.1f}/{total/1024/1024:.1f} MB")
        def _on_finished(path):
            self._status_lbl.setText("🔧 Aplicando atualização...")
            from updater.installer import create_backup, apply_zip_update, rollback, verify_update_integrity, CRITICAL_MODULES
            backup_dir = os.path.join(cache_dir, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            if not create_backup(root_dir, backup_dir):
                QMessageBox.critical(self, "Erro", "Falha ao criar backup.")
                self._reset_ui(); return
            if not apply_zip_update(path, root_dir):
                self._status_lbl.setText("❌ Falha. Restaurando...")
                rollback(backup_dir, root_dir)
                QMessageBox.critical(self, "Erro", "Falha. Backup restaurado.")
                self._reset_ui(); return
            if not verify_update_integrity(root_dir, CRITICAL_MODULES):
                self._status_lbl.setText("❌ Verificação falhou. Restaurando...")
                rollback(backup_dir, root_dir)
                QMessageBox.critical(self, "Erro", "Módulos críticos falharam. Backup restaurado.")
                self._reset_ui(); return
            self._progress.setValue(100)
            self._status_lbl.setText("✅ Atualização concluída! Reinicie a AURA.")
            self._status_lbl.setStyleSheet("color:#3FB950; font-size:13px;")
            QMessageBox.information(self, "Sucesso", f"✅ Atualização instalada!\nReinicie a AURA.\nBackup: {backup_dir}")
            self._reset_ui()
        def _on_error(error):
            QMessageBox.critical(self, "Erro", f"Download falhou:\n{error}")
            self._reset_ui()
        self._thread = DownloadThread(update.download_url, cache_dir,
            on_progress=_on_progress, on_finished=_on_finished, on_error=_on_error)
        self._thread.start()

    def _reset_ui(self):
        self._updating = False
        self._update_all_btn.setEnabled(True)
        self._update_all_btn.setVisible(False)
        self._progress.setVisible(False)
        self._updates_available = []
