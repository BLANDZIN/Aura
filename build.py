#!/usr/bin/env python3
"""AURA V11 Build — Windows + Linux. Self-contained, no external files needed."""
import os, sys, shutil, subprocess, platform as _plat

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

def run(cmd, check=True):
    print("  $", " ".join(cmd) if isinstance(cmd, list) else cmd)
    return subprocess.run(cmd, check=check)

def clean():
    for d in [os.path.join(ROOT, "dist"), os.path.join(ROOT, "build", "aura_linux"), os.path.join(ROOT, "build", "build")]:
        if os.path.isdir(d): shutil.rmtree(d)
    print("Clean OK")

def generate_spec_content() -> str:
    """
    Gera o conteúdo do .spec do PyInstaller como string — função pura,
    sem tocar em disco nem instalar nada. Extraída de ensure_spec_and_deps()
    pra ficar testável sem side effects (achado da auditoria V12).
    """
    is_win = _plat.system() == "Windows"
    icon_line = ""
    version_line = ""

    if is_win:
        icon_path = os.path.join(ROOT, "assets", "aura.ico")
        if os.path.isfile(icon_path):
            icon_line = f"    icon=r'{icon_path}',"
        version_path = os.path.join(ROOT, "build", "version_info.txt")
        if os.path.isfile(version_path):
            version_line = f"    version=r'{version_path}',"

    return f'''# -*- mode: python ; coding: utf-8 -*-
# Auto-generated spec for AURA V11
from pathlib import Path
ROOT = Path(r"{ROOT}")
ENTRY = ROOT / "AURA.py"
DATAS = [
    (str(ROOT / "config" / "settings.json"), "config"),
    (str(ROOT / "config" / "personality.json"), "config"),
]
a = Analysis(
    [str(ENTRY)], pathex=[str(ROOT)], binaries=[], datas=DATAS,
    hiddenimports=[], hookspath=[], hooksconfig={{}}, runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numba"],
    win_no_prefer_redirects=False, win_private_assemblies=False,
    cipher=None, noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="AURA", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None,
    console=False, disable_windowed_traceback=False,
    {icon_line}
    {version_line}
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, upx_exclude=[], name="AURA",
)
'''


def ensure_spec_and_deps():
    """Escreve o .spec gerado por generate_spec_content() e garante o PyInstaller instalado."""
    spec_path = os.path.join(ROOT, "aura_build.spec")
    with open(spec_path, "w") as f:
        f.write(generate_spec_content())

    # Ensure PyInstaller
    try:
        import PyInstaller
    except ImportError:
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    return spec_path

def make_dirs(dist_dir):
    for d in ["models","extensions","profiles","cache","workspace","logs","database","themes","voices"]:
        os.makedirs(os.path.join(dist_dir, d), exist_ok=True)

def build():
    is_win = _plat.system() == "Windows"
    en = "AURA.exe" if is_win else "AURA"
    
    print("=" * 50)
    print(f"  AURA V11 — Build {'Windows' if is_win else 'Linux'}")
    print("=" * 50)
    
    clean()
    spec_path = ensure_spec_and_deps()
    
    print("\n[1/2] Compilando com PyInstaller (pode levar alguns minutos)...")
    os.environ["AURA_ROOT"] = ROOT
    r = run([sys.executable, "-m", "PyInstaller", spec_path, "--noconfirm", "--clean"], check=False)
    if r.returncode != 0:
        print("\n❌ BUILD FAILED. Verifique os erros acima.")
        sys.exit(1)
    
    dist_dir = os.path.join(ROOT, "dist", "AURA")
    exe_path = os.path.join(dist_dir, en)
    if not os.path.isfile(exe_path):
        print(f"\n❌ Binario nao encontrado: {exe_path}")
        sys.exit(1)
    
    print("\n[2/2] Criando estrutura...")
    make_dirs(dist_dir)
    
    # README
    with open(os.path.join(dist_dir, "LEIAME.txt"), "w", encoding="utf-8") as f:
        f.write(f"AURA V11\nExecute: {en}\nRequer Ollama: https://ollama.com\n")
    
    # Linux start script
    if not is_win:
        start = os.path.join(dist_dir, "start.sh")
        with open(start, "w") as f:
            f.write('#!/usr/bin/env bash\ncd "$(dirname "$0")"\nexec ./AURA\n')
        os.chmod(start, 0o755)
    
    size_mb = sum(os.path.getsize(os.path.join(dp, fl))
                  for dp, _, fls in os.walk(dist_dir) for fl in fls) / (1024 * 1024)
    
    # Clean up generated spec
    try: os.remove(spec_path)
    except: pass
    for f in os.listdir(ROOT):
        if f.endswith(".spec") and f != "aura_build.spec":
            try: os.remove(os.path.join(ROOT, f))
            except: pass
    
    print(f"\n{'=' * 50}")
    print(f"  ✅ BUILD CONCLUIDO!")
    print(f"  📦 {exe_path}")
    print(f"  📏 {size_mb:.0f} MB")
    print(f"{'=' * 50}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "clean":
        clean()
    elif cmd == "test":
        run([sys.executable, "-m", "pytest", "tests/", "-q"], check=False)
    else:
        build()
