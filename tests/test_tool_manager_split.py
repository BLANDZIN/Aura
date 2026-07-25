"""
Regressão da divisão de tools/tool_manager.py (1252 linhas -> 9 arquivos
por categoria + tool_manager.py enxuto). Precisa de um display (real ou
Xvfb) porque tools.control_tools importa pyautogui de verdade — pula
graciosamente se não houver um disponível.
"""
import pytest

try:
    import pyautogui  # noqa: F401
except Exception as e:
    # Sem DISPLAY, a falha acontece dentro do mouseinfo (dependência
    # transitiva do pyautogui) como KeyError, não ImportError — então
    # pytest.importorskip (que só pega ImportError) não é suficiente.
    pytest.skip(f"pyautogui/display não disponível: {e}", allow_module_level=True)

# Nomes exatos registrados em _register_all() ANTES da divisão (ver
# AUDITORIA_V9_ETAPA1.md / FASE1_INVENTARIO_V10.md) — a lista congelada
# que a divisão precisa preservar byte a byte.
ORIGINAL_36_TOOLS = {
    "criar_pasta", "abrir_pasta", "abrir_arquivo", "renomear_arquivo",
    "copiar_arquivo", "mover_arquivo", "excluir_arquivo", "pesquisar_arquivo",
    "abrir_programa", "fechar_programa", "obter_cpu", "obter_ram", "obter_bateria",
    "abrir_site", "pesquisar_web", "pesquisar_youtube", "pesquisar_site",
    "capturar_tela", "mover_mouse", "clicar_mouse", "digitar_texto",
    "pressionar_tecla", "atalho_teclado", "rolar_pagina", "esperar",
    "copiar_area_transf", "escrever_area_transf",
    "ler_tela",
    "salvar_procedimento", "executar_procedimento", "listar_procedimentos",
    "criar_tarefa", "listar_tarefas", "concluir_tarefa",
    "salvar_memoria", "buscar_memoria",
}
# obter_metricas: nova na Fase 7 (Observabilidade) — não fazia parte do
# conjunto original de 36, mas segue exatamente o mesmo padrão de
# obter_cpu/obter_ram.
CURRENT_38_TOOLS = ORIGINAL_36_TOOLS | {"obter_metricas", "pesquisar_resposta"}


def test_all_required_tools_registered():
    import tools.tool_manager as tm
    assert set(tm.tool_manager._tools.keys()) == CURRENT_38_TOOLS
    assert len(tm.tool_manager._tools) == 38
    # As 36 originais continuam todas lá — Fase 7 só adicionou, não removeu.
    assert ORIGINAL_36_TOOLS <= set(tm.tool_manager._tools.keys())


def test_backward_compatible_reexports_from_tool_manager():
    # automation/flow_executor.py, ui/app.py e ui/chat_panel.py importam
    # esses nomes direto de tools.tool_manager.
    import tools.tool_manager as tm
    assert "youtube" in tm.KNOWN_SITES
    assert callable(tm.normalize_params)
    assert tm.BaseTool.__name__ == "BaseTool"


def test_pure_logic_tools_execute_correctly():
    import tools.tool_manager as tm
    r = tm.tool_manager._tools["obter_cpu"].execute({})
    assert r["sucesso"] is True

    r = tm.tool_manager._tools["obter_ram"].execute({})
    assert r["sucesso"] is True
    assert "percentual" in r["resultado"]


def test_normalize_params_still_resolves_paths():
    from tools.param_normalization import normalize_params
    n = normalize_params("abrir_pasta", {"pasta": "downloads"})
    assert n["caminho"].lower().endswith("downloads")

    n = normalize_params("criar_pasta", {"nome_da_pasta": "teste/sub"})
    assert "teste" in n["caminho"] and "sub" in n["caminho"]


def test_catalog_still_lists_all_8_categories():
    import tools.tool_manager as tm
    catalog = tm.tool_manager.build_tools_catalog(compact=True)
    for cat in ("Arquivos", "Sistema", "Navegador", "Controle",
                "OCR", "Procedimentos", "Tarefas", "Memória"):
        assert cat in catalog
