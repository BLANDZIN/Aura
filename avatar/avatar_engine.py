"""
avatar/avatar_engine.py
=======================
Motor principal do avatar VRM.

Responsabilidades:
  - Orquestrar todos os componentes (Character, VRM, State Machine)
  - Gerenciar ciclo de vida
  - Expor API unificada
  - Integrar com EventBus
  - Thread-safe

Arquitetura:
    AvatarEngine
    ├─ CharacterManager (personagens)
    ├─ StateMachine (estados)
    ├─ AnimationController (futuro)
    ├─ ExpressionController (futuro)
    └─ VRM Runtime (renderização)
"""

import threading
from typing import Optional, List
from enum import Enum

from core.logger import setup_logger
from core.event_bus import bus
from .character_manager import character_manager, Character
from .state_machine import avatar_state_machine, AvatarState
from .config import avatar_config

logger = setup_logger("avatar_engine")


class AvatarEngine:
    """Motor central do avatar VRM."""

    def __init__(self):
        """Inicializa o motor do avatar."""
        self.character_manager = character_manager
        self.state_machine = avatar_state_machine
        self.config = avatar_config

        self._lock = threading.RLock()
        self._initialized = False

        logger.info("AvatarEngine inicializado")

    def initialize(self) -> bool:
        """
        Inicializa o avatar com o personagem ativo.

        Returns:
            True se sucesso, False caso erro
        """
        with self._lock:
            if self._initialized:
                logger.warning("AvatarEngine já inicializado")
                return True

            try:
                # Carrega personagem ativo da config
                active_char_name = self.config.get_active_character()
                logger.info(f"Carregando personagem ativo: {active_char_name}")

                if not self.character_manager.set_active_character(active_char_name):
                    logger.warning(
                        f"Falha ao carregar {active_char_name}, usando 'aura'"
                    )
                    active_char_name = "aura"
                    if not self.character_manager.set_active_character(active_char_name):
                        logger.error("Não foi possível carregar nenhum personagem")
                        return False

                # Subscribe a eventos (já feito pelo StateMachine)
                bus.subscribe("avatar.switch_character", self._on_switch_character)

                self._initialized = True
                logger.info("AvatarEngine inicializado com sucesso")
                return True

            except Exception as e:
                logger.error(f"Erro ao inicializar AvatarEngine: {e}")
                return False

    def get_active_character(self) -> Optional[Character]:
        """Retorna o personagem ativo."""
        with self._lock:
            return self.character_manager.get_active_character()

    def get_current_state(self) -> AvatarState:
        """Retorna o estado atual do avatar."""
        return self.state_machine.get_current_state()

    def get_available_characters(self) -> List[str]:
        """Retorna lista de personagens disponíveis."""
        return self.character_manager.get_available_characters()

    def switch_character(self, character_name: str) -> bool:
        """
        Troca o personagem ativo (hot-swap).

        Args:
            character_name: Nome do novo personagem

        Returns:
            True se sucesso
        """
        with self._lock:
            current = self.character_manager.get_active_character()

            if current and current.name == character_name:
                logger.warning(f"Já está usando {character_name}")
                return True

            try:
                old_name = current.name if current else "none"
                success = self.character_manager.hot_swap(old_name, character_name)

                if success:
                    bus.publish(
                        "avatar.character_switched",
                        old_character=old_name,
                        new_character=character_name,
                    )
                    logger.info(f"Personagem trocado: {old_name} → {character_name}")

                return success

            except Exception as e:
                logger.error(f"Erro ao trocar personagem: {e}")
                return False

    def reload_character(self) -> bool:
        """
        Recarrega o personagem ativo.

        Útil se o arquivo foi modificado em disco.

        Returns:
            True se sucesso
        """
        with self._lock:
            current = self.character_manager.get_active_character()
            if not current:
                logger.warning("Nenhum personagem ativo")
                return False

            char_name = current.name
            logger.info(f"Recarregando personagem: {char_name}")

            try:
                self.character_manager.unload_character(char_name)
                return self.character_manager.set_active_character(char_name)
            except Exception as e:
                logger.error(f"Erro ao recarregar: {e}")
                return False

    def get_state_info(self) -> dict:
        """Retorna informações do estado atual."""
        current_state = self.state_machine.get_current_state()
        char = self.get_active_character()

        return {
            "current_state": current_state.value,
            "is_transitioning": self.state_machine.is_transitioning,
            "transition_progress": self.state_machine.transition_progress,
            "character": char.name if char else None,
            "character_metadata": (
                {
                    "title": char.get_metadata().title,
                    "version": char.get_metadata().version,
                    "author": char.get_metadata().author,
                    "mesh_count": char.get_metadata().mesh_count,
                }
                if char
                else None
            ),
        }

    def update(self, delta_time_ms: float = 16.0) -> None:
        """
        Atualiza o motor (deve ser chamado em cada frame).

        Args:
            delta_time_ms: Tempo decorrido desde último update (ms)
        """
        with self._lock:
            if not self._initialized:
                return

            # Atualiza state machine
            self.state_machine.update(delta_time_ms)

    def shutdown(self) -> None:
        """Desliga o motor e libera recursos."""
        logger.info("Desligando AvatarEngine...")

        with self._lock:
            try:
                self.state_machine.shutdown()
            except Exception as e:
                logger.warning(f"Erro ao desligar StateMachine: {e}")

            try:
                self.character_manager.shutdown()
            except Exception as e:
                logger.warning(f"Erro ao desligar CharacterManager: {e}")

            self._initialized = False
            logger.info("AvatarEngine desligado")

    # ── Event handlers ──────────────────────────────────────────────────────

    def _on_switch_character(self, character: str) -> None:
        """Handler para avatar.switch_character event."""
        self.switch_character(character)

    def __del__(self):
        """Cleanup automático."""
        if self._initialized:
            self.shutdown()


# Instância global
avatar_engine = AvatarEngine()
