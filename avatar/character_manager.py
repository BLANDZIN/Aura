"""Descoberta e seleção de personagens, sem dependência da UI."""
from pathlib import Path
from .config import ROOT, load_config

class CharacterManager:
    def __init__(self, config=None):
        self.config = config or load_config()
        self.root = ROOT / self.config.get('characters_path', 'assets/characters')
    def characters(self):
        return {p.name: p for p in self.root.iterdir() if p.is_dir()} if self.root.exists() else {}
    def resolve(self, name=None):
        name = name or self.config['active_character']
        folder = self.characters().get(name)
        if folder is None: raise FileNotFoundError(f'Personagem não encontrado: {name}')
        models = sorted(folder.glob('*.vrm'))
        if not models: raise FileNotFoundError(f'Nenhum modelo VRM em {folder}')
        return {'name': name, 'folder': folder, 'model': models[0]}
