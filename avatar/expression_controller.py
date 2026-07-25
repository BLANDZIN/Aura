class ExpressionController:
    def __init__(self, config): self.expressions = config.get('expressions', {})
    def available(self): return tuple(self.expressions)
    def select(self, name): return name if name in self.expressions else 'neutral'
