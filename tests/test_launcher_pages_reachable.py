"""
Regressão do achado crítico #1 da auditoria V11 (V11_AUDITORIA.md) —
4 das 8 páginas de launcher/pages/ (updates, diagnostics, backup,
profiles) existiam prontas mas nenhum entry point real as carregava.
Reincidiu identicamente na V12 antes deste fix (mesmo bug, código
novo). Requer PyQt6 + display — pula graciosamente sem um.
"""
import pytest

try:
    from PyQt6.QtWidgets import QApplication
except Exception as e:
    pytest.skip(f"PyQt6/display não disponível: {e}", allow_module_level=True)


def test_all_nav_items_have_matching_page_titles(qapp):
    from ui.main_window import NAV_ITEMS, PAGE_TITLES
    assert len(NAV_ITEMS) == len(PAGE_TITLES)


def test_all_14_launcher_pages_load_without_error(qapp):
    from ui.main_window import MainWindow, NAV_ITEMS

    w = MainWindow()
    try:
        for i in range(len(NAV_ITEMS)):
            page = w._load_page(i)
            assert page is not None, f"Página idx={i} não carregou"
    finally:
        w.shutdown()


def test_updates_diagnostics_backup_profiles_are_reachable(qapp):
    # O achado específico: essas 4 são exatamente as que ficaram órfãs.
    from ui.main_window import MainWindow, PAGE_TITLES
    from launcher.pages.updates import UpdatesPage
    from launcher.pages.diagnostics import DiagnosticsPage
    from launcher.pages.backup import BackupPage
    from launcher.pages.profiles import ProfilesPage

    esperado = {
        "Atualizacoes": UpdatesPage, "Diagnostico": DiagnosticsPage,
        "Backup": BackupPage, "Perfis": ProfilesPage,
    }
    w = MainWindow()
    try:
        for titulo, classe in esperado.items():
            idx = PAGE_TITLES.index(titulo)
            page = w._load_page(idx)
            assert isinstance(page, classe)
    finally:
        w.shutdown()
