#!/usr/bin/env python3
"""
AURA V11 — Build System (Windows + Linux)

USO:
    python build.py            → compilar para esta plataforma
    python build.py clean      → limpar build/ e dist/
    python build.py test       → rodar testes (99)

SAÍDA:
    Windows: dist\AURA\AURA.exe
    Linux:   dist/AURA/AURA
"""

import os, sys, shutil, subprocess, platform as _plat

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)


def run(cmd, check=True, shell=False):
    print(f"  $ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    return subprocess.run(cmd, shell=shell, check=check)


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("[1/4] Instalando PyInstaller...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean():
    for d in ["build", "dist"]:
        if os.path.isdir(d):
            shutil.rmtree(d)
    print("✓ build/ e dist/ removidos")


def make_dirs(dist_dir):
    for d in ["models","extensions","profiles","cache","workspace","logs",
              "database","themes","voices"]:
        os.makedirs(os.path.join(dist_dir, d), exist_ok=True)


def build():
    is_win = _plat.system() == "Windows"
    spec = "aura_windows.spec" if is_win else "aura_linux.spec"
    sep = ";" if is_win else ":"

    print(f"\n{'='*60}")
    print(f"  AURA V11 — Build {'Windows' if is_win else 'Linux'}")
    print(f"{'='*60}\n")

    ensure_pyinstaller()

    print("[2/4] Compilando com PyInstaller...")
    result = run([
        sys.executable, "-m", "PyInstaller",
        spec,
        "--noconfirm", "--clean",
    ], check=False)

    if result.returncode != 0:
        print("\n❌ FALHA NA COMPILAÇÃO!")
        sys.exit(1)

    # Verifica saída
    dist_dir = os.path.join(ROOT, "dist", "AURA")
    exe_name = "AURA.exe" if is_win else "AURA"
    exe_path = os.path.join(dist_dir, exe_name)

    if not os.path.exists(exe_path):
        print(f"\n❌ Binário não encontrado: {exe_path}")
        sys.exit(1)

    print(f"[3/4] Criando estrutura...")
    make_dirs(dist_dir)

    # LEIAME
    with open(os.path.join(dist_dir, "LEIAME.txt"), "w", encoding="utf-8") as f:
        f.write(f"AURA V11 — Assistente Virtual Inteligente\n")
        f.write(f"Execute: {exe_name}\n")
        f.write(f"Requer Ollama: https://ollama.com\n")

    # Launcher Linux
    if not is_win:
        with open(os.path.join(dist_dir, "start.sh"), "w") as f:
            f.write("#!/usr/bin/env bash\ncd \"$(dirname \"$0\")\"\nexec ./AURA\n")
        os.chmod(os.path.join(dist_dir, "start.sh"), 0o755)

    # Tamanho
    size_mb = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, files in os.walk(dist_dir)
        for f in files
    ) / (1024 * 1024)

    print(f"\n{'='*60}")
    print(f"  ✅ BUILD CONCLUÍDO!")
    print(f"  📦 {exe_path}")
    print(f"  📏 {size_mb:.0f} MB")
    print(f"{'='*60}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"

    if cmd == "clean":
        clean()
    elif cmd == "test":
        run([sys.executable, "-m", "pytest", "tests/", "-q"], check=False)
    elif cmd in ("build", "exe", "linux"):
        build()
    else:
        print("Uso: python build.py [build|clean|test]")
