"""Orquestrador do avatar: EventBus -> estado/animação/VRM, sem UI ou IA."""
from core.event_bus import bus
from .config import load_config
from .character_manager import CharacterManager
from .state_machine import AvatarStateMachine
from .animation_controller import AnimationController
from .expression_controller import ExpressionController
from .vrm_runtime import VRMRuntime

class AvatarEngine:
    EVENTS = ('ai.thinking','voice.listening','voice.speaking_start','voice.speaking_end','emotion.changed','tool.started','tool.finished','system.error','system.idle','avatar.set_state')
    def __init__(self, view=None, config=None):
        self.config = config or load_config(); self.view = view
        self.characters = CharacterManager(self.config); self.runtime = VRMRuntime()
        self.states = AvatarStateMachine(self.config); self.animations = AnimationController(self.config); self.expressions = ExpressionController(self.config)
        self._subscriptions = []
        self.character = None
    def start(self):
        self.character = self.characters.resolve(); self.runtime.load(self.character['model'])
        for event in self.EVENTS:
            callback = getattr(self, '_on_' + event.replace('.', '_'), self._on_event)
            bus.subscribe(event, callback); self._subscriptions.append((event, callback))
        self._apply('idle')
    def stop(self):
        for e, cb in self._subscriptions: bus.unsubscribe(e, cb)
        self._subscriptions.clear(); self.runtime.unload()
    def _on_event(self, **kw): self._apply(self._state_for_event(kw))
    def _state_for_event(self, kw): return kw.get('state') or kw.get('avatar_state') or 'idle'
    def _on_emotion_changed(self, estado='calma', **kw):
        self._apply({'animada': 'talking', 'curiosa': 'thinking', 'pensativa': 'thinking',
                     'concentrada': 'executing', 'frustrada': 'error'}.get(estado, 'idle'))
    def _on_tool_started(self, **kw): self._apply('executing')
    def _on_tool_finished(self, **kw): self._apply('idle')
    def _on_system_error(self, **kw): self._apply('error')
    def _on_system_idle(self, **kw): self._apply('idle')
    def _on_ai_thinking(self, status=False, **kw): self._apply('thinking' if status else 'idle')
    def _on_voice_listening(self, status=False, **kw): self._apply('listening' if status else 'idle')
    def _on_voice_speaking_start(self, **kw): self._apply('talking')
    def _on_voice_speaking_end(self, **kw): self._apply('idle')
    def _on_avatar_set_state(self, state='idle', **kw): self._apply(state)
    def _apply(self, state):
        self.states.transition(state)
        if self.view: self.view.set_state(self.states.current)
