"""
avatar/state_machine.py
=======================
Máquina de estados do avatar.

Estados Possíveis:
  - IDLE: Estado padrão, respiração suave
  - THINKING: Processando (partículas orbitando)
  - SPEAKING: Falando (ondas sonoras, lip-sync)
  - LISTENING: Ouvindo (orelhas ativas)
  - WORKING: Executando tarefa (engrenagem)
  - SLEEPING: Dormindo (olhos fechados)
  - HAPPY: Feliz (sorriso, corpo energizado)
  - CURIOUS: Curioso (cabeça inclinada)
  - CONFUSED: Confuso (balançando cabeça)
  - ERROR: Erro (cores vermelhas, tenso)
  - POWERED_DOWN: Desligado (translúcido)

Transições:
  - Baseadas em eventos do EventBus
  - Suavização automática (morphing)
  - Timeout automático para estados temporários
"""

import time
import threading
from enum import Enum
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass

from core.logger import setup_logger
from core.event_bus import bus

logger = setup_logger("avatar_state_machine")


class AvatarState(Enum):
    """Estados possíveis do avatar."""

    IDLE = "idle"
    THINKING = "thinking"
    SPEAKING = "speaking"
    LISTENING = "listening"
    WORKING = "working"
    SLEEPING = "sleeping"
    HAPPY = "happy"
    CURIOUS = "curious"
    CONFUSED = "confused"
    ERROR = "error"
    POWERED_DOWN = "powered_down"


@dataclass
class StateTransition:
    """Define uma transição entre estados."""

    from_state: AvatarState
    to_state: AvatarState
    condition: Optional[Callable] = None
    duration_ms: float = 500.0  # Duração da transição em ms
    auto_return: Optional[AvatarState] = None  # Estado para retornar automaticamente
    timeout_ms: Optional[float] = None  # Timeout para auto-return


class AvatarStateMachine:
    """Máquina de estados do avatar com transições suaves."""

    def __init__(self):
        self.current_state = AvatarState.IDLE
        self.previous_state = AvatarState.IDLE
        self.transition_start_time = 0.0
        self.is_transitioning = False
        self.transition_progress = 0.0

        self._timeout_timer: Optional[threading.Timer] = None
        self._lock = threading.RLock()

        self._subscribe_to_events()
        logger.info(f"State Machine iniciada — estado: {self.current_state.value}")

    def _subscribe_to_events(self) -> None:
        """Subscreve aos eventos do EventBus."""
        bus.subscribe("ai.thinking", self._on_ai_thinking)
        bus.subscribe("ai.response", self._on_ai_response)
        bus.subscribe("ai.error", self._on_ai_error)
        bus.subscribe("emotion.changed", self._on_emotion_changed)
        bus.subscribe("voice.listening", self._on_voice_listening)
        bus.subscribe("voice.speaking_start", self._on_voice_speaking_start)
        bus.subscribe("voice.speaking_end", self._on_voice_speaking_end)
        bus.subscribe("flow.done", self._on_flow_done)
        bus.subscribe("flow.aborted", self._on_flow_aborted)

    def transition_to(self, new_state: AvatarState, duration_ms: float = 500.0) -> bool:
        """
        Transiciona para um novo estado.

        Args:
            new_state: Novo estado desejado
            duration_ms: Duração da transição em ms

        Returns:
            True se transição iniciada, False se já em estado ou transição bloqueada
        """
        with self._lock:
            if new_state == self.current_state:
                return False

            logger.debug(f"Transição: {self.current_state.value} → {new_state.value}")

            self.previous_state = self.current_state
            self.current_state = new_state
            self.is_transitioning = True
            self.transition_start_time = time.time()
            self.transition_progress = 0.0

            # Publica evento
            bus.publish(
                "avatar.state_changed",
                old_state=self.previous_state.value,
                new_state=new_state.value,
            )

            return True

    def transition_to_with_timeout(
        self,
        new_state: AvatarState,
        timeout_ms: float = 2000.0,
        duration_ms: float = 500.0,
        return_state: Optional[AvatarState] = None,
    ) -> bool:
        """
        Transiciona para novo estado e retorna automaticamente após timeout.

        Args:
            new_state: Novo estado desejado
            timeout_ms: Tempo até retorno automático (ms)
            duration_ms: Duração da transição (ms)
            return_state: Estado para retornar (default: IDLE)

        Returns:
            True se sucesso
        """
        if return_state is None:
            return_state = AvatarState.IDLE

        success = self.transition_to(new_state, duration_ms)

        if success:
            # Cancela timer anterior
            if self._timeout_timer:
                self._timeout_timer.cancel()

            # Cria novo timer
            self._timeout_timer = threading.Timer(
                timeout_ms / 1000.0,
                lambda: self.transition_to(return_state, duration_ms),
            )
            self._timeout_timer.daemon = True
            self._timeout_timer.start()

        return success

    def update(self, delta_time_ms: float = 16.0) -> float:
        """
        Atualiza a transição.

        Args:
            delta_time_ms: Tempo decorrido desde último update (ms)

        Returns:
            Progresso da transição (0.0-1.0)
        """
        with self._lock:
            if not self.is_transitioning:
                self.transition_progress = 1.0
                return 1.0

            elapsed = (time.time() - self.transition_start_time) * 1000.0
            duration = 500.0  # Default (poderia ser armazenado)

            progress = min(1.0, elapsed / duration)
            self.transition_progress = progress

            if progress >= 1.0:
                self.is_transitioning = False

            return progress

    def get_blend_factor(self) -> float:
        """
        Retorna fator de blend para interpolação de estados.

        Varia de 0.0 (estado anterior) até 1.0 (novo estado).

        Returns:
            Fator (0.0-1.0) com easing aplicado
        """
        # Easing suave (ease-in-out)
        t = self.transition_progress
        return t * t * (3.0 - 2.0 * t)  # Smoothstep

    def get_current_state(self) -> AvatarState:
        """Retorna estado atual."""
        return self.current_state

    def get_previous_state(self) -> AvatarState:
        """Retorna estado anterior."""
        return self.previous_state

    def is_in_state(self, state: AvatarState) -> bool:
        """Verifica se está em estado específico (sem transição)."""
        return self.current_state == state and not self.is_transitioning

    # ── Event handlers ──────────────────────────────────────────────────────

    def _on_ai_thinking(self, status: bool) -> None:
        """Subscrição: ai.thinking."""
        if status:
            self.transition_to(AvatarState.THINKING)
        else:
            self.transition_to(AvatarState.IDLE)

    def _on_ai_response(self, text: str) -> None:
        """Subscrição: ai.response."""
        # Calcula timeout baseado no comprimento do texto
        words = len(text.split())
        timeout_ms = max(2000, words * 300)  # 300ms por palavra

        self.transition_to_with_timeout(
            AvatarState.SPEAKING,
            timeout_ms=timeout_ms,
            return_state=AvatarState.IDLE,
        )

    def _on_ai_error(self, error: str) -> None:
        """Subscrição: ai.error."""
        self.transition_to_with_timeout(
            AvatarState.ERROR,
            timeout_ms=4000,
            return_state=AvatarState.IDLE,
        )

    def _on_emotion_changed(self, estado: str, anterior: str) -> None:
        """Subscrição: emotion.changed."""
        # Mapeia emoção para estado do avatar
        emotion_to_state = {
            "calma": AvatarState.IDLE,
            "animada": AvatarState.HAPPY,
            "curiosa": AvatarState.CURIOUS,
            "concentrada": AvatarState.WORKING,
            "orgulhosa": AvatarState.HAPPY,
            "pensativa": AvatarState.THINKING,
            "brincalhona": AvatarState.HAPPY,
            "frustrada": AvatarState.CONFUSED,
            "cansada": AvatarState.SLEEPING,
        }

        new_state = emotion_to_state.get(estado, AvatarState.IDLE)
        self.transition_to_with_timeout(
            new_state,
            timeout_ms=2500,  # Mais curto que resposta de IA
            return_state=AvatarState.IDLE,
        )

    def _on_voice_listening(self, status: bool) -> None:
        """Subscrição: voice.listening."""
        if status:
            self.transition_to(AvatarState.LISTENING)
        else:
            self.transition_to(AvatarState.IDLE)

    def _on_voice_speaking_start(self, text: str = "") -> None:
        """Subscrição: voice.speaking_start."""
        self.transition_to(AvatarState.SPEAKING)

    def _on_voice_speaking_end(self) -> None:
        """Subscrição: voice.speaking_end."""
        self.transition_to(AvatarState.IDLE)

    def _on_flow_done(self, resultado) -> None:
        """Subscrição: flow.done."""
        sucesso = resultado.sucesso if hasattr(resultado, "sucesso") else True

        if sucesso:
            self.transition_to_with_timeout(
                AvatarState.HAPPY,
                timeout_ms=2000,
                return_state=AvatarState.IDLE,
            )
        else:
            self.transition_to_with_timeout(
                AvatarState.ERROR,
                timeout_ms=3000,
                return_state=AvatarState.IDLE,
            )

    def _on_flow_aborted(self, **kw) -> None:
        """Subscrição: flow.aborted."""
        self.transition_to_with_timeout(
            AvatarState.CONFUSED,
            timeout_ms=3000,
            return_state=AvatarState.IDLE,
        )

    def shutdown(self) -> None:
        """Desliga a state machine."""
        if self._timeout_timer:
            self._timeout_timer.cancel()

        logger.info("State Machine desligada")


# Instância global
avatar_state_machine = AvatarStateMachine()
