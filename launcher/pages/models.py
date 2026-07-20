"""
launcher/pages/models.py
=========================
Gerenciador de Modelos — Instalar, ativar, desativar, baixar, remover, importar.
Observa a pasta models/ e interage com Ollama.
"""

import os
import json
import shutil
import threading
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QMessageBox, QFileDialog, QLineEdit, QProgressBar,
    QInputDialog, QDialog, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont


_CARD_ACTIVE = """
    QFrame#model_card {
        background: #0D2B1F;
        border: 2px solid #1A7F37;
        border-radius: 14px;
        padding: 16px;
    }
    QFrame#model_card:hover {
        border-color: #2EA043;
    }
"""

_CARD_INACTIVE = """
    QFrame#model_card {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 14px;
        padding: 16px;
    }
    QFrame#model_card:hover {
        border-color: #388BFD;
    }
"""

BTN_PRIMARY = """
    QPushButton {
        background: #1F6FEB; color: #fff;
        border: none; border-radius: 8px;
        padding: 8px 16px; font-size: 13px;
    }
    QPushButton:hover { background: #388BFD; }
    QPushButton:disabled { background: #21262D; color: #484F58; }
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


class OllamaListWorker(QThread):
    """Thread para listar modelos do Ollama sem travar UI."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            if r.status_code == 200:
                self.finished.emit(r.json().get("models", []))
            else:
                self.error.emit(f"Status {r.status_code}")
        except Exception as e:
            self.error.emit(str(e))


class OllamaPullWorker(QThread):
    """Thread para baixar modelo do Ollama."""
    progress = pyqtSignal(str, int, int)  # model_name, completed, total
    finished = pyqtSignal(str)
    error = pyqtSignal(str, str)

    def __init__(self, model_name: str):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            import requests
            import json as json_mod
            resp = requests.post(
                "http://localhost:11434/api/pull",
                json={"name": self.model_name, "stream": True},
                stream=True,
                timeout=300,
            )
            for line in resp.iter_lines():
                if line:
                    data = json_mod.loads(line)
                    if "completed" in data and "total" in data:
                        self.progress.emit(
                            self.model_name,
                            data.get("completed", 0),
                            data.get("total", 0),
                        )
                    if data.get("status") == "success":
                        self.finished.emit(self.model_name)
                        return
            self.finished.emit(self.model_name)
        except Exception as e:
            self.error.emit(self.model_name, str(e))


class ModelsPage(QWidget):
    """Gerenciamento visual de modelos de IA."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._models_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "models"
        )
        os.makedirs(self._models_dir, exist_ok=True)

        self._ollama_models = []
        self._local_models = []
        self._active_model = ""
        self._angela_model = ""

        self._build_ui()
        self._refresh()

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

        # ── Título e ações ─────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("🧠  Gerenciador de Modelos")
        title.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("🔄  Atualizar")
        refresh_btn.setStyleSheet(BTN_SECONDARY)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(refresh_btn)

        download_btn = QPushButton("⬇  Baixar Modelo")
        download_btn.setStyleSheet(BTN_PRIMARY)
        download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        download_btn.clicked.connect(self._download_model)
        header.addWidget(download_btn)

        import_btn = QPushButton("📁  Importar GGUF")
        import_btn.setStyleSheet(BTN_SECONDARY)
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._import_gguf)
        header.addWidget(import_btn)

        layout.addLayout(header)

        # ── Status da conexão ──────────────────────────────────────────────
        self._status_lbl = QLabel("Conectando ao Ollama...")
        self._status_lbl.setStyleSheet("color: #94A3B8; font-size: 13px; padding: 8px 0;")
        layout.addWidget(self._status_lbl)

        # ── Progresso download ─────────────────────────────────────────────
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background: #21262D; border: none; border-radius: 6px;
                height: 8px; text-align: center; color: #E2E8F0;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: #1F6FEB; border-radius: 6px;
            }
        """)
        layout.addWidget(self._progress_bar)

        self._progress_lbl = QLabel("")
        self._progress_lbl.setVisible(False)
        self._progress_lbl.setStyleSheet("color: #7DD3FC; font-size: 12px;")
        layout.addWidget(self._progress_lbl)

        # ── Grid de modelos ────────────────────────────────────────────────
        self._models_grid = QGridLayout()
        self._models_grid.setSpacing(16)
        layout.addLayout(self._models_grid)

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

    def on_show(self):
        self._refresh()

    def _refresh(self):
        """Recarrega a lista de modelos."""
        self._load_active_model()
        self._clear_grid()

        # Busca modelos do Ollama
        self._status_lbl.setText("🔍 Buscando modelos do Ollama...")
        self._status_lbl.setStyleSheet("color: #CE93D8; font-size: 13px; padding: 8px 0;")

        self._worker = OllamaListWorker()
        self._worker.finished.connect(self._on_ollama_list)
        self._worker.error.connect(self._on_ollama_error)
        self._worker.start()

    def _load_active_model(self):
        """Carrega qual modelo está ativo nas configs."""
        try:
            from config.settings import settings
            self._active_model = settings.get("ai", "model", default="qwen2.5:3b")
            self._angela_model = settings.get("angela", "model", default="qwen3:4b")
        except Exception:
            self._active_model = ""
            self._angela_model = ""

    def _clear_grid(self):
        """Remove todos os cards do grid."""
        while self._models_grid.count():
            item = self._models_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_ollama_list(self, models: list):
        """Recebe a lista de modelos do Ollama."""
        self._ollama_models = models
        self._status_lbl.setText(f"✓ Ollama conectado — {len(models)} modelo(s) disponíveis")
        self._status_lbl.setStyleSheet("color: #3FB950; font-size: 13px; padding: 8px 0;")
        self._render_models()

    def _on_ollama_error(self, error: str):
        """Erro ao conectar no Ollama."""
        self._ollama_models = []
        self._status_lbl.setText(f"⚠ Ollama indisponível: {error}")
        self._status_lbl.setStyleSheet("color: #F85149; font-size: 13px; padding: 8px 0;")
        self._render_models()

    def _render_models(self):
        """Renderiza os cards de modelos no grid."""
        self._clear_grid()

        all_models = {}

        # Modelos do Ollama
        for m in self._ollama_models:
            name = m.get("name", "unknown")
            size_gb = m.get("size", 0) / (1024 ** 3)
            all_models[name] = {
                "name": name,
                "size": f"{size_gb:.1f} GB",
                "source": "Ollama",
                "details": m,
            }

        # Modelos locais (pasta models/)
        if os.path.isdir(self._models_dir):
            for folder in os.listdir(self._models_dir):
                folder_path = os.path.join(self._models_dir, folder)
                manifest_path = os.path.join(folder_path, "manifest.json")
                if os.path.isdir(folder_path):
                    local_info = {
                        "name": folder,
                        "size": self._folder_size(folder_path),
                        "source": "Local",
                        "details": {},
                    }
                    if os.path.exists(manifest_path):
                        try:
                            with open(manifest_path) as f:
                                local_info["details"] = json.load(f)
                                if "name" in local_info["details"]:
                                    local_info["name"] = local_info["details"]["name"]
                        except Exception:
                            pass
                    # Só adiciona se não existir no Ollama com mesmo nome
                    if folder not in all_models:
                        all_models[folder] = local_info

        if not all_models:
            empty = QLabel(
                "Nenhum modelo encontrado.\n\n"
                "Clique em 'Baixar Modelo' para instalar via Ollama\n"
                "ou 'Importar GGUF' para adicionar um arquivo local."
            )
            empty.setStyleSheet("color: #64748B; font-size: 15px; padding: 40px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._models_grid.addWidget(empty, 0, 0)
            return

        # Renderiza em grid 2 colunas
        row, col = 0, 0
        for name, info in sorted(all_models.items()):
            card = self._make_model_card(name, info)
            self._models_grid.addWidget(card, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

    def _make_model_card(self, name: str, info: dict) -> QFrame:
        """Cria um card para um modelo."""
        is_active = (name == self._active_model)
        is_angela = (name == self._angela_model)

        card = QFrame()
        card.setObjectName("model_card")
        card.setStyleSheet(_CARD_ACTIVE if is_active else _CARD_INACTIVE)
        card.setMinimumWidth(380)

        inner = QVBoxLayout(card)
        inner.setSpacing(8)

        # Cabeçalho
        header = QHBoxLayout()
        status_icon = "✓" if is_active else "○"
        status_color = "#3FB950" if is_active else "#64748B"

        icon_lbl = QLabel(status_icon)
        icon_lbl.setStyleSheet(f"color: {status_color}; font-size: 20px; font-weight: bold;")
        header.addWidget(icon_lbl)

        name_lbl = QLabel(info.get("name", name))
        name_lbl.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: bold;")
        header.addWidget(name_lbl)
        header.addStretch()

        if is_active:
            badge = QLabel("ATIVO")
            badge.setStyleSheet("""
                background: #1A7F37; color: #fff; font-size: 10px;
                font-weight: bold; padding: 2px 8px; border-radius: 6px;
            """)
            header.addWidget(badge)

        if is_angela and not is_active:
            badge2 = QLabel("ANGELA")
            badge2.setStyleSheet("""
                background: #1E3A5F; color: #7DD3FC; font-size: 10px;
                font-weight: bold; padding: 2px 8px; border-radius: 6px;
            """)
            header.addWidget(badge2)

        inner.addLayout(header)

        # Info
        info_lbl = QLabel(f"{info.get('size', '?')}  •  {info.get('source', '?')}")
        info_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        inner.addWidget(info_lbl)

        # Detalhes adicionais do manifest
        details = info.get("details", {})
        if details:
            extra = []
            if "context" in details:
                extra.append(f"Contexto: {details['context']}")
            if "author" in details:
                extra.append(f"Autor: {details['author']}")
            if "version" in details:
                extra.append(f"Versão: {details['version']}")
            if extra:
                extra_lbl = QLabel("  ".join(extra))
                extra_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
                inner.addWidget(extra_lbl)

        # Botões
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        if is_active:
            deactivate_btn = QPushButton("Desativar")
            deactivate_btn.setStyleSheet(BTN_SECONDARY)
            deactivate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            deactivate_btn.clicked.connect(lambda: self._set_active(""))
            btn_row.addWidget(deactivate_btn)
        else:
            activate_btn = QPushButton("Ativar (AURA)")
            activate_btn.setStyleSheet(BTN_PRIMARY)
            activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            activate_btn.clicked.connect(lambda: self._set_active(name))
            btn_row.addWidget(activate_btn)

            angela_btn = QPushButton("Usar na Angela")
            angela_btn.setStyleSheet(BTN_SECONDARY)
            angela_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            angela_btn.clicked.connect(lambda: self._set_angela(name))
            btn_row.addWidget(angela_btn)

        remove_btn = QPushButton("Remover")
        remove_btn.setStyleSheet(BTN_DANGER)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self._remove_model(name))
        btn_row.addWidget(remove_btn)

        inner.addLayout(btn_row)
        return card

    # ══════════════════════════════════════════════════════════════════════
    # Ações
    # ══════════════════════════════════════════════════════════════════════

    def _set_active(self, name: str):
        """Define o modelo ativo para AURA."""
        try:
            from config.settings import settings
            settings.set("ai", "model", value=name or "qwen2.5:3b")
            self._active_model = name
            self._refresh()
            QMessageBox.information(
                self, "Sucesso",
                f"Modelo ativo: {name or 'padrão (qwen2.5:3b)'}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    def _set_angela(self, name: str):
        """Define o modelo da Angela."""
        try:
            from config.settings import settings
            settings.set("angela", "model", value=name)
            self._angela_model = name
            self._refresh()
            QMessageBox.information(self, "Sucesso", f"Angela agora usa: {name}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    def _download_model(self):
        """Abre diálogo para baixar modelo do Ollama."""
        name, ok = QInputDialog.getText(
            self, "Baixar Modelo",
            "Nome do modelo no Ollama:",
            QLineEdit.EchoMode.Normal,
            "qwen2.5:3b"
        )
        if not ok or not name.strip():
            return

        name = name.strip()
        self._progress_bar.setVisible(True)
        self._progress_lbl.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_lbl.setText(f"Baixando {name}...")

        self._pull_worker = OllamaPullWorker(name)
        self._pull_worker.progress.connect(self._on_pull_progress)
        self._pull_worker.finished.connect(self._on_pull_finished)
        self._pull_worker.error.connect(self._on_pull_error)
        self._pull_worker.start()

    def _on_pull_progress(self, name: str, completed: int, total: int):
        """Atualiza barra de progresso do download."""
        self._progress_lbl.setText(f"Baixando {name}... ({completed}/{total})")
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(completed)

    def _on_pull_finished(self, name: str):
        self._progress_bar.setVisible(False)
        self._progress_lbl.setVisible(False)
        QMessageBox.information(self, "Sucesso", f"Modelo '{name}' baixado com sucesso!")
        self._refresh()

    def _on_pull_error(self, name: str, error: str):
        self._progress_bar.setVisible(False)
        self._progress_lbl.setVisible(False)
        QMessageBox.critical(self, "Erro", f"Falha ao baixar '{name}':\n{error}")

    def _import_gguf(self):
        """Importa um arquivo GGUF para a pasta models/."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Importar GGUF",
            "", "Modelos GGUF (*.gguf);;Todos (*.*)"
        )
        if not file_path:
            return

        name, ok = QInputDialog.getText(
            self, "Nome do Modelo",
            "Nome para o modelo importado:",
            text=os.path.splitext(os.path.basename(file_path))[0]
        )
        if not ok or not name.strip():
            return

        name = name.strip()
        dest_dir = os.path.join(self._models_dir, name)
        os.makedirs(dest_dir, exist_ok=True)

        try:
            dest_file = os.path.join(dest_dir, "model.gguf")
            shutil.copy2(file_path, dest_file)

            # Cria manifest.json básico
            manifest = {
                "name": name,
                "author": "Importado",
                "version": "1.0.0",
                "context": 4096,
                "language": "pt",
                "source": "gguf",
                "filename": "model.gguf",
            }
            with open(os.path.join(dest_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f, indent=2)

            QMessageBox.information(
                self, "Sucesso",
                f"Modelo '{name}' importado em:\n{dest_dir}"
            )
            self._refresh()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao importar:\n{e}")

    def _remove_model(self, name: str):
        """Remove um modelo (Ollama ou local)."""
        reply = QMessageBox.question(
            self, "Confirmar Remoção",
            f"Tem certeza que deseja remover o modelo '{name}'?\n\n"
            "Esta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Tenta remover do Ollama
        try:
            import requests
            r = requests.delete(
                "http://localhost:11434/api/delete",
                json={"name": name},
                timeout=10,
            )
            if r.status_code == 200:
                QMessageBox.information(self, "Sucesso", f"Modelo '{name}' removido do Ollama.")
                self._refresh()
                return
        except Exception:
            pass

        # Tenta remover local
        local_path = os.path.join(self._models_dir, name)
        if os.path.isdir(local_path):
            try:
                shutil.rmtree(local_path)
                QMessageBox.information(self, "Sucesso", f"Modelo local '{name}' removido.")
                self._refresh()
                return
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao remover:\n{e}")
                return

        QMessageBox.warning(self, "Aviso", f"Não foi possível remover '{name}'.")

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════

    def _folder_size(self, path: str) -> str:
        """Calcula tamanho de uma pasta."""
        total = 0
        try:
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
        except Exception:
            return "?"

        if total > 1024 ** 3:
            return f"{total / (1024**3):.1f} GB"
        elif total > 1024 ** 2:
            return f"{total / (1024**2):.1f} MB"
        else:
            return f"{total / 1024:.1f} KB"
