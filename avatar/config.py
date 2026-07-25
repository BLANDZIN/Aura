"""
avatar/config.py
================
Configurações do sistema de avatar VRM.

Carrega de:
  1. config/avatar.json (config global)
  2. assets/characters/{character}/config.json (config específica)
  3. Defaults (fallback)
"""

import json
import os
from typing import Dict, Any, Optional
from core.logger import setup_logger

logger = setup_logger("avatar_config")


class AvatarConfig:
    """Gerenciador de configurações de avatar."""

    # Defaults globais
    DEFAULTS = {
        "avatar": {
            "active_character": "aura",
            "auto_load": True,
            "animation_speed": 1.0,
            "expression_blendshape_weight": 1.0,
            "lip_sync_enabled": True,
            "background_color": [0.05, 0.05, 0.05, 1.0],
            "lighting": {
                "ambient": [0.6, 0.6, 0.6],
                "directional": [0.9, 0.9, 0.9],
                "position": [2.0, 2.0, 2.0],
            },
        }
    }

    def __init__(self, config_path: str = "config/avatar.json"):
        """
        Inicializa configurações.

        Args:
            config_path: Caminho para config/avatar.json
        """
        self.config_path = config_path
        self.global_config: Dict[str, Any] = {}
        self.character_configs: Dict[str, Dict[str, Any]] = {}

        self._load_global_config()

    def _load_global_config(self) -> None:
        """Carrega config global de config/avatar.json."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.global_config = json.load(f)
                logger.info(f"Config global carregada: {self.config_path}")
            except Exception as e:
                logger.warning(f"Erro ao carregar {self.config_path}: {e}")
                self.global_config = self.DEFAULTS.copy()
        else:
            logger.info(f"Config não encontrada, usando defaults")
            self.global_config = self.DEFAULTS.copy()
            self._save_global_config()

    def _save_global_config(self) -> None:
        """Salva config global em config/avatar.json."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.global_config, f, indent=2, ensure_ascii=False)
            logger.info(f"Config salva em {self.config_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar config: {e}")

    def load_character_config(self, character_name: str) -> Dict[str, Any]:
        """
        Carrega config específica de um personagem.

        Args:
            character_name: Nome do personagem (pasta em assets/characters/)

        Returns:
            Dict com config do personagem
        """
        if character_name in self.character_configs:
            return self.character_configs[character_name]

        char_config_path = f"assets/characters/{character_name}/config.json"

        if not os.path.exists(char_config_path):
            logger.warning(f"Config não encontrada: {char_config_path}")
            # Cria config padrão
            default_char_config = {
                "name": character_name,
                "vrm_file": f"aura-dnv.vrm" if character_name == "aura" else f"{character_name}.vrm",
                "scale": 1.0,
                "position": [0.0, 0.0, 0.0],
                "animations": {},
                "expressions": {},
            }
            self.character_configs[character_name] = default_char_config
            return default_char_config

        try:
            with open(char_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self.character_configs[character_name] = config
            logger.info(f"Config do personagem carregada: {character_name}")
            return config
        except Exception as e:
            logger.error(f"Erro ao carregar config de {character_name}: {e}")
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém valor da config global.

        Args:
            key: Chave (ex: "avatar.active_character")
            default: Valor padrão se não encontrar

        Returns:
            Valor da config
        """
        keys = key.split(".")
        value = self.global_config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    def set(self, key: str, value: Any) -> None:
        """
        Define valor na config global.

        Args:
            key: Chave (ex: "avatar.active_character")
            value: Novo valor
        """
        keys = key.split(".")
        config = self.global_config

        # Navega até a última chave
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Define valor
        config[keys[-1]] = value
        self._save_global_config()
        logger.info(f"Config atualizada: {key} = {value}")

    def get_active_character(self) -> str:
        """Retorna o personagem ativo configurado."""
        return self.get("avatar.active_character", "aura")

    def set_active_character(self, name: str) -> None:
        """Define o personagem ativo."""
        self.set("avatar.active_character", name)

    def get_character_vrm_path(self, character_name: str) -> str:
        """
        Obtém o caminho do arquivo VRM para um personagem.

        Args:
            character_name: Nome do personagem

        Returns:
            Caminho relativo ao arquivo VRM
        """
        char_config = self.load_character_config(character_name)
        vrm_filename = char_config.get("vrm_file", f"{character_name}.vrm")
        return f"assets/characters/{character_name}/{vrm_filename}"

    def is_animation_speed_valid(self, speed: float) -> bool:
        """Valida velocidade de animação."""
        return 0.1 <= speed <= 3.0

    def to_dict(self) -> Dict[str, Any]:
        """Retorna toda a config como dict."""
        return self.global_config.copy()


# Instância global
avatar_config = AvatarConfig()
