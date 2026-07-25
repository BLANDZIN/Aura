"""
avatar/
======
Módulo de Avatar 3D para AURA V12.1+

Responsável por renderização, animação e gerenciamento de personagens VRM.
Toda comunicação ocorre via EventBus — a IA nunca controla diretamente o avatar.

Arquitetura:
    AuraApp (ui/app.py)
        ↓ (eventos EventBus)
    AvatarEngine
        ├─ CharacterManager (carrega personagens de assets/characters/)
        ├─ VRMRuntime (parse + renderização VRM)
        ├─ AnimationController (blend shapes, animações)
        ├─ ExpressionController (expressões faciais, lip-sync)
        ├─ StateMachine (transições de estados)
        └─ OpenGLWidget (renderização Qt)

Eventos Subscritos:
    - ai.thinking, ai.response, ai.error
    - emotion.changed
    - voice.listening, voice.speaking_start, voice.speaking_end
    - flow.done, flow.aborted
    - system.* (quando implementados)

Estados do Avatar:
    IDLE, THINKING, SPEAKING, LISTENING, WORKING, SLEEPING,
    HAPPY, CURIOUS, CONFUSED, ERROR, POWERED_DOWN

Desenvolvido por: Staff Software Engineer
Data: 2026-07-25
"""

__version__ = "0.1.0"
__all__ = [
    "AvatarEngine",
    "CharacterManager",
    "VRMRuntime",
    "AnimationController",
    "ExpressionController",
    "StateMachine",
    "AvatarOpenGLWidget",
]

from .config import AvatarConfig
from .avatar_engine import AvatarEngine
from .character_manager import CharacterManager
from .vrm_runtime import VRMRuntime

# Lazy imports (para evitar dependências pesadas no startup)
def __getattr__(name):
    if name == "AnimationController":
        from .animation_controller import AnimationController
        return AnimationController
    elif name == "ExpressionController":
        from .expression_controller import ExpressionController
        return ExpressionController
    elif name == "StateMachine":
        from .state_machine import StateMachine
        return StateMachine
    elif name == "AvatarOpenGLWidget":
        from .opengl_widget import AvatarOpenGLWidget
        return AvatarOpenGLWidget
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
