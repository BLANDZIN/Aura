#!/usr/bin/env python3
"""
AURA V12 — Aplicacao Desktop Completa

Ponto de entrada UNICO:  python AURA.py

Abre o avatar flutuante + chat (leve, instantaneo) — mesma experiencia
rapida que sempre funcionou. Backend inicializa em background.
Botao "Ferramentas" no chat abre o painel completo do Launcher V11.
"""
import sys, os, subprocess, time, platform as _stdlib_platform

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from core.logger import setup_logger
from core.version import AURA_VERSION

logger = setup_logger("aura")


def _ensure_ollama():
    import requests
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            logger.info("Ollama ja rodando")
            return True
    except Exception:
        pass
    logger.info("Tentando iniciar Ollama...")
    try:
        if _stdlib_platform.system() == "Windows":
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except FileNotFoundError:
        logger.warning("Ollama nao encontrado no PATH")
        return False
    except Exception as e:
        logger.warning("Falha ao iniciar Ollama: {}".format(e))
        return False
    for _ in range(25):
        time.sleep(0.2)
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=1)
            if r.status_code == 200:
                logger.info("Ollama iniciado")
                return True
        except Exception:
            pass
    return False


def main():
    logger.info("=" * 50)
    logger.info("  AURA V12 — Inicializando...")
    logger.info("=" * 50)

    _ensure_ollama()

    app = QApplication(sys.argv)
    app.setApplicationName("AURA")
    app.setApplicationVersion(AURA_VERSION)
    app.setStyle("Fusion")

    # EXPERIENCIA PRINCIPAL: Avatar flutuante + Chat (LEVE, RAPIDO)
    # Esta e a interface classica que sempre funcionou.
    # O painel Launcher V11 abre via botao no chat.
    from ui.app import AuraApp

    aura = AuraApp()
    aura.start()

    app.aboutToQuit.connect(aura.shutdown)

    logger.info("AURA V12 iniciada — Avatar + Chat prontos")
    exit_code = app.exec()
    logger.info("AURA encerrada (exit code: {})".format(exit_code))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
