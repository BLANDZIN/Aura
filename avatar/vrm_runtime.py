"""Runtime VRM isolado. O backend gráfico é opcional e lazy (Windows/Linux)."""
class VRMRuntime:
    def __init__(self): self.model_path = None; self.loaded = False; self._data = None
    def load(self, path):
        path = str(path)
        with open(path, 'rb') as f: header = f.read(4); self._data = f.read()
        if header != b'glTF': raise ValueError('Arquivo não é um VRM/GLB válido')
        self.model_path, self.loaded = path, True
    def unload(self): self._data = None; self.model_path = None; self.loaded = False
