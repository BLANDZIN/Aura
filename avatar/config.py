"""Configuração declarativa do runtime de avatar."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def load_config(path=None):
    path = Path(path or ROOT / 'config' / 'avatar.json')
    with path.open(encoding='utf-8') as f:
        return json.load(f)
