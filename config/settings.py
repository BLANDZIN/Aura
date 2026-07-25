"""
config/settings.py
Gerenciador de configurações do AURA.
Carrega e salva configurações gerais do sistema em settings.json.
"""

import json
import os
from typing import Any
from core.logger import setup_logger

logger = setup_logger("settings")

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULTS = {
    "ai": {
        "provider": "ollama",          # "ollama" | "lmstudio"
        "model": "qwen2.5:3b",         # rápido, roda em 4GB RAM (ver README)
        "base_url": "http://localhost:11434",   # URL do Ollama
        "lmstudio_url": "http://localhost:1234", # URL do LM Studio (porta diferente)
        "temperature": 0.7,
        "max_tokens": 2048,
        "vision_model": "qwen2.5vl:3b",
        "keep_alive": -1,              # -1 = manter modelo em RAM permanentemente
    },
    "ui": {
        "avatar_position": [50, 50],   # x, y em porcentagem da tela
        "avatar_size": 120,
        "always_on_top": True,
        "theme": "dark",
        "chat_width": 420,
        "chat_height": 680,
    },
    "voice": {
        # Só as chaves que voice/voice_manager.py de fato lê. As antigas
        # "enabled"/"tts_engine"/"stt_engine" foram removidas na consolidação
        # da V9 — não tinham nenhum código consumindo (achado #1 da auditoria).
        "tts_enabled": True,
        "stt_enabled": False,
        "auto_speak": False,
        "voice_rate": 180,
        "voice_volume": 0.9,
        "stt_model": "tiny",
        "language": "pt",
    },
    "memory": {
        "short_term_limit": 20,
        "db_path": "database/aura.db",
    },
    "security": {
        "require_confirm_delete": True,
        "require_confirm_scripts": True,
        "require_confirm_close_process": True,
    },
    "vision": {
        "enabled": False,              # Requer modelo visual instalado
        "capture_interval": 5,
    },
    "angela": {
        # Configuração PRÓPRIA da Angela — nunca lida pela AURA (ai.*) e
        # vice-versa. Mesmo servidor Ollama, modelo e propósito diferentes:
        # AURA prioriza velocidade, Angela prioriza precisão técnica.
        "model": "qwen3:4b",
        "base_url": "http://localhost:11434",
        "temperature": 0.3,
        "max_tokens": 4096,
    },
}


class Settings:
    """
    Gerencia todas as configurações persistentes do AURA.
    Mescla defaults com overrides salvos pelo usuário.
    """

    def __init__(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        """Carrega settings, aplicando defaults para chaves ausentes."""
        if not os.path.exists(SETTINGS_FILE):
            self._save(DEFAULTS)
            return DEFAULTS.copy()

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Mescla profunda: defaults + saved
            return self._deep_merge(DEFAULTS, saved)
        except Exception as e:
            logger.error(f"Erro ao carregar settings: {e}. Usando defaults.")
            return DEFAULTS.copy()

    def _save(self, data: dict) -> None:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = base.copy()
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Acessa uma configuração por caminho de chaves.
        Exemplo: settings.get("ai", "model")
        """
        node = self._data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, *keys: str, value: Any) -> None:
        """Define um valor e persiste."""
        node = self._data
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value
        self._save(self._data)
        logger.debug(f"Setting atualizado: {'.'.join(keys)} = {value}")

    def all(self) -> dict:
        return self._data


# Instância global
settings = Settings()
