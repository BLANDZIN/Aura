"""
tests/test_search_tools.py
==========================
Testes para a ferramenta pesquisar_resposta (V11).
"""
import pytest

try:
    import pyautogui
except Exception as e:
    pytest.skip("pyautogui/display indisponivel", allow_module_level=True)


class TestPesquisarResposta:

    def test_tool_registered(self):
        import tools.tool_manager as tm
        assert "pesquisar_resposta" in tm.tool_manager._tools

    def test_tool_metadata(self):
        import tools.tool_manager as tm
        tool = tm.tool_manager._tools["pesquisar_resposta"]
        assert tool.name == "pesquisar_resposta"

    def test_empty_query_error(self):
        import tools.tool_manager as tm
        tool = tm.tool_manager._tools["pesquisar_resposta"]
        result = tool.execute({"query": ""})
        assert result["sucesso"] is False

    def test_missing_query_error(self):
        import tools.tool_manager as tm
        tool = tm.tool_manager._tools["pesquisar_resposta"]
        result = tool.execute({})
        assert result["sucesso"] is False

    def test_valid_query_success(self):
        import tools.tool_manager as tm
        tool = tm.tool_manager._tools["pesquisar_resposta"]
        result = tool.execute({"query": "Python"})
        assert result["sucesso"] is True
        assert "resultado" in result

    def test_catalog_includes_tool(self):
        import tools.tool_manager as tm
        catalog = tm.tool_manager.build_tools_catalog(compact=True)
        assert "pesquisar_resposta" in catalog

    def test_list_tools_includes_tool(self):
        import tools.tool_manager as tm
        names = [t["nome"] for t in tm.tool_manager.list_tools()]
        assert "pesquisar_resposta" in names
