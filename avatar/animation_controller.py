class AnimationController:
    def __init__(self, config): self.config = config
    def animation_for(self, state): return self.config.get('states', {}).get(state, {}).get('animation', state)
