"""
updater/__init__.py
==================
Sistema de atualização automática da AURA V11.

Verifica versões no GitHub Releases, baixa módulos individuais,
verifica checksums e aplica com rollback seguro.

Uso:
    from updater import check_version, download_update, apply_update

Fluxo:
    1. check_version()    → consulta GitHub Releases API
    2. download_update()  → baixa o .zip do release, verifica SHA256
    3. apply_update()     → extrai sobre os arquivos, backup antes
    4. rollback()         → restaura backup se algo der errado

Módulos individuais (cada um tem sua própria versão):
  core, ui, angela, launcher, models, extensions, assets
"""

__version__ = "11.0.0"

# Manifesto de módulos — versão atual de cada um
# Isto é o que enviamos para o GitHub comparar
MODULES = {
    "core":       {"version": "11.0.0", "name": "Core AURA",       "path": "ai/ automation/ core/ memory/ tools/ tasks/ voice/ vision/ config/ database/"},
    "ui":         {"version": "11.0.0", "name": "Interface (UI)",   "path": "ui/"},
    "angela":     {"version": "1.0.0",  "name": "Angela",          "path": "angela/"},
    "launcher":   {"version": "11.0.0", "name": "Launcher",        "path": "launcher/"},
    "models":     {"version": "11.0.0", "name": "Modelos",         "path": "models/"},
    "extensions": {"version": "1.0.0",  "name": "Plugins",         "path": "extensions/"},
    "assets":     {"version": "1.0.0",  "name": "Assets",          "path": "assets/"},
}
