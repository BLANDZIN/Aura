"""
AURA - Assistente Virtual Inteligente
Ponto de entrada principal do sistema.
"""

import sys
import os

# Garante que o diretório raiz esteja no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from ui.app import AuraApp
from core.logger import setup_logger

logger = setup_logger("main")


def main():
    logger.info("Iniciando AURA...")

    # AA_UseHighDpiPixmaps foi removido no PyQt6 6.x — High DPI já é padrão
    app = QApplication(sys.argv)
    app.setApplicationName("AURA")
    app.setApplicationVersion("1.0.0")

    # Inicia a aplicação principal
    aura = AuraApp()
    aura.start()

    # Encerramento limpo ao fechar
    app.aboutToQuit.connect(aura.shutdown)

    exit_code = app.exec()
    logger.info("AURA encerrado.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
