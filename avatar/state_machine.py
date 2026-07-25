from .config import load_config
class AvatarStateMachine:
    def __init__(self, config=None): self.states = (config or load_config()).get('states', {}); self.current = 'idle'
    def transition(self, state):
        state = state.lower()
        aliases = {'speaking':'talking','working':'executing','happy':'idle','curious':'thinking'}
        state = aliases.get(state, state)
        if state not in self.states: state = 'idle'
        changed = state != self.current; self.current = state
        return changed
