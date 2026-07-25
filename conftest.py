import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pytest


@pytest.fixture(scope="session")
def qapp():
    """
    QApplication único, vivo pela sessão inteira do pytest.

    Achado da auditoria V12.1: um teste que criava seu próprio
    QApplication (escopo de módulo) e o deixava ser destruído no fim do
    módulo invalidava o dispatcher Qt cacheado como singleton em
    core/event_bus.py::EventBus — testes RODANDO DEPOIS, no mesmo
    processo pytest, que publicavam qualquer evento explodiam com
    "RuntimeError: wrapped C/C++ object ... has been deleted", mesmo
    sem nenhuma relação direta com UI. Um único QApplication vivo até o
    fim do processo evita esse problema de vez.
    """
    try:
        from PyQt6.QtWidgets import QApplication
    except Exception as e:
        pytest.skip(f"PyQt6/display não disponível: {e}")
    app = QApplication.instance() or QApplication([])
    yield app
