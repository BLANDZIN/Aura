"""
avatar/character_manager.py
===========================
Gerenciador de personagens VRM.

Responsabilidades:
  - Descobrir personagens em assets/characters/
  - Carregar/descarregar personagens
  - Gerenciar ciclo de vida do VRM
  - Hot-swap (trocar personagem em runtime)
  - Cache de personagens carregados
"""

import os
from typing import Dict, List, Optional
from pathlib import Path

from core.logger import setup_logger
from .vrm_runtime import VRMRuntime, VRMMetadata
from .config import avatar_config

logger = setup_logger("character_manager")


class Character:
    """Representa um personagem carregado."""

    def __init__(self, name: str, vrm_runtime: VRMRuntime):
        self.name = name
        self.vrm_runtime = vrm_runtime
        self.config = avatar_config.load_character_config(name)
        self.scale = self.config.get("scale", 1.0)
        self.position = self.config.get("position", [0.0, 0.0, 0.0])
        self.is_active = False

    def get_metadata(self) -> VRMMetadata:
        """Retorna metadados do VRM."""
        return self.vrm_runtime.metadata

    def dispose(self) -> None:
        """Libera recursos."""
        if self.vrm_runtime:
            self.vrm_runtime.unload()


class CharacterManager:
    """Gerenciador central de personagens."""

    CHARACTERS_DIR = "assets/characters"

    def __init__(self):
        self.characters: Dict[str, Character] = {}
        self.active_character: Optional[Character] = None
        self._discover_characters()

    def _discover_characters(self) -> None:
        """Descobre personagens disponíveis em assets/characters/."""
        if not os.path.exists(self.CHARACTERS_DIR):
            logger.warning(f"Diretório não encontrado: {self.CHARACTERS_DIR}")
            os.makedirs(self.CHARACTERS_DIR, exist_ok=True)
            return

        character_dirs = [
            d for d in os.listdir(self.CHARACTERS_DIR)
            if os.path.isdir(os.path.join(self.CHARACTERS_DIR, d))
        ]

        logger.info(f"Personagens descobertos: {character_dirs}")

    def get_available_characters(self) -> List[str]:
        """Retorna lista de personagens disponíveis."""
        available = []
        if os.path.exists(self.CHARACTERS_DIR):
            available = [
                d for d in os.listdir(self.CHARACTERS_DIR)
                if os.path.isdir(os.path.join(self.CHARACTERS_DIR, d))
            ]
        return sorted(available)

    def load_character(self, name: str) -> Optional[Character]:
        """
        Carrega um personagem.

        Args:
            name: Nome do personagem (pasta em assets/characters/)

        Returns:
            Character carregado, ou None se erro

        Raises:
            FileNotFoundError: Se personagem não existe
            ValueError: Se arquivo VRM inválido
        """
        if name in self.characters:
            logger.info(f"Personagem já carregado: {name}")
            return self.characters[name]

        vrm_path = avatar_config.get_character_vrm_path(name)

        if not os.path.exists(vrm_path):
            logger.error(f"Arquivo VRM não encontrado: {vrm_path}")
            raise FileNotFoundError(f"VRM não encontrado: {vrm_path}")

        try:
            logger.info(f"Carregando personagem: {name}")
            vrm_runtime = VRMRuntime(vrm_path)
            character = Character(name, vrm_runtime)
            self.characters[name] = character
            logger.info(f"Personagem carregado com sucesso: {name}")
            return character

        except Exception as e:
            logger.error(f"Erro ao carregar personagem {name}: {e}")
            raise

    def unload_character(self, name: str) -> bool:
        """
        Descarrega um personagem.

        Args:
            name: Nome do personagem

        Returns:
            True se descarregado, False se não existia
        """
        if name not in self.characters:
            return False

        character = self.characters[name]
        if character.is_active:
            logger.warning(f"Personagem ativo não pode ser descarregado: {name}")
            return False

        character.dispose()
        del self.characters[name]
        logger.info(f"Personagem descarregado: {name}")
        return True

    def set_active_character(self, name: str) -> bool:
        """
        Define um personagem como ativo.

        Args:
            name: Nome do personagem

        Returns:
            True se sucesso
        """
        if name not in self.characters:
            try:
                self.load_character(name)
            except Exception as e:
                logger.error(f"Não foi possível carregar {name}: {e}")
                return False

        # Desativa personagem anterior
        if self.active_character:
            self.active_character.is_active = False

        # Ativa novo
        self.active_character = self.characters[name]
        self.active_character.is_active = True
        avatar_config.set_active_character(name)

        logger.info(f"Personagem ativo: {name}")
        return True

    def get_active_character(self) -> Optional[Character]:
        """Retorna o personagem ativo."""
        return self.active_character

    def get_character(self, name: str) -> Optional[Character]:
        """Retorna um personagem carregado (não precisa estar ativo)."""
        return self.characters.get(name)

    def get_loaded_characters(self) -> Dict[str, Character]:
        """Retorna todos os personagens carregados."""
        return self.characters.copy()

    def hot_swap(self, old_name: str, new_name: str) -> bool:
        """
        Troca personagem em runtime (hot-swap).

        Args:
            old_name: Nome do personagem ativo
            new_name: Nome do novo personagem

        Returns:
            True se sucesso
        """
        if self.active_character and self.active_character.name != old_name:
            logger.warning(f"Personagem ativo é {self.active_character.name}, não {old_name}")
            return False

        logger.info(f"Hot-swap: {old_name} → {new_name}")

        # Unload do antigo
        self.unload_character(old_name)

        # Load do novo
        if not self.set_active_character(new_name):
            logger.error(f"Falha no hot-swap para {new_name}")
            return False

        logger.info("Hot-swap concluído com sucesso")
        return True

    def shutdown(self) -> None:
        """Descarrega todos os personagens e libera recursos."""
        logger.info("Descarregando todos os personagens...")
        for name in list(self.characters.keys()):
            try:
                self.characters[name].dispose()
            except Exception as e:
                logger.warning(f"Erro ao descarregar {name}: {e}")

        self.characters.clear()
        self.active_character = None
        logger.info("Gerenciador de personagens desligado")

    def __del__(self):
        """Cleanup automático."""
        if self.characters:
            self.shutdown()


# Instância global
character_manager = CharacterManager()
