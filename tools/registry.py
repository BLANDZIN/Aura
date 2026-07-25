"""
tools/registry.py - AURA V11
=============================
Registro automatico de ferramentas por categoria.

Cada modulo de categoria exporta uma lista REGISTRY com suas ferramentas.
O ToolManager chama discover_tools() que importa cada categoria e coleta.
"""

import importlib
from typing import List
from tools.base_tool import BaseTool


# Categorias registradas — cada uma tem um modulo tools/<name>_tools.py
CATEGORIES = {
    "Arquivos":      "tools.file_tools",
    "Sistema":       "tools.system_tools",
    "Navegador":     "tools.browser_tools",
    "Controle":      "tools.control_tools",
    "OCR":           "tools.ocr_tools",
    "Procedimentos": "tools.procedure_tools",
    "Tarefas":       "tools.task_tools",
    "Memoria":       "tools.memory_tools",
    "Pesquisa":      "tools.search_tools",
}


def discover_tools() -> List[BaseTool]:
    """Importa todas as categorias e coleta ferramentas registradas."""
    tools = []
    failed = []
    for category_name, module_name in CATEGORIES.items():
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "REGISTRY"):
                for tool in module.REGISTRY:
                    tools.append(tool)
            else:
                failed.append(f"{category_name}: REGISTRY nao encontrado em {module_name}")
        except Exception as e:
            failed.append(f"{category_name} ({module_name}): {e}")

    if failed:
        from core.logger import setup_logger
        logger = setup_logger("tools.registry")
        for f in failed:
            logger.error(f"FALHA ao carregar categoria: {f}")
        raise RuntimeError(
            f"{len(failed)} categoria(s) de ferramentas falharam ao carregar: "
            + "; ".join(failed)
        )
    return tools


if __name__ == "__main__":
    """Smoke test — descobre e lista todas as ferramentas."""
    from tools.registry import discover_tools
    tools = discover_tools()
    print(f"Ferramentas descobertas: {len(tools)}")
    for t in tools:
        print(f"  {t.name}: {t.description[:60]}")
