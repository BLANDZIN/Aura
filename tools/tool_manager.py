"""
tools/tool_manager.py — AURA
Registro e execução de ferramentas.

Dividido por categoria na Fase 2/V10 (era um único arquivo de 1252
linhas). ToolManager (registro/dispatch/execute/catálogo) continua
aqui; as 36 classes de Tool moraram para tools/<categoria>_tools.py.

SPECIAL_FOLDERS, WINDOWS_PROGRAMS existiam aqui antes da Fase V10
(portabilidade Linux) e viraram específicos de plataforma dentro de
platforms/windows_platform.py e platforms/linux_platform.py — use
platforms.platform_manager.special_folders()/program_aliases(). Ainda
re-exportados por compatibilidade: KNOWN_SITES, PYAUTOGUI_KEYS,
normalize_params e BaseTool — ai/intent_engine.py, automation/flow_executor.py,
ui/app.py e ui/chat_panel.py já importam esses nomes direto de tools.tool_manager;
mover sem re-exportar quebraria esses imports.
"""
import json
from typing import Any, Dict, List

from core.event_bus import bus
from core.logger import setup_logger
from core.metrics import metrics
from database.db_manager import db

# Re-exports de compatibilidade (ver docstring acima) — não remover.

# NOTA DE ARQUITETURA (V11):
# Imports de automation/error_learning e ai/ai_engine sao feitos dentro
# dos metodos (lazy) para evitar ciclo automation -> tools -> ai -> automation.
from tools.base_tool import BaseTool
from tools.resolvers import HOME, DESKTOP, KNOWN_SITES, PYAUTOGUI_KEYS
from tools.param_normalization import normalize_params, PARAM_ALIASES

from tools.file_tools import (
    CriarPastaTool, AbrirPastaTool, AbrirArquivoTool, RenomearArquivoTool,
    CopiarArquivoTool, MoverArquivoTool, ExcluirArquivoTool, PesquisarArquivoTool,
)
from tools.system_tools import (
    AbrirProgramaTool, FecharProgramaTool, ObterCPUTool, ObterRAMTool, ObterBateriaTool,
    ObterMetricasTool,
)
from tools.browser_tools import (
    AbrirSiteTool, PesquisarWebTool, PesquisarYoutubeTool, PesquisarSiteTool,
)
from tools.search_tools import PesquisarRespostaTool
from tools.control_tools import (
    CapturarTelaTool, MoverMouseTool, ClicarMouseTool, DigitarTextoTool,
    PressionarTeclaTool, AtalhoTeclaTool, RolarPaginaTool, EsperarTool,
    CopiarAreaTransfTool, EscreverAreaTransfTool,
)
from tools.ocr_tools import OCRTool
from tools.procedure_tools import (
    SalvarProcedimentoTool, ExecutarProcedimentoTool, ListarProcedimentosTool,
)
from tools.task_tools import CriarTarefaTool, ListarTarefasTool, ConcluirTarefaTool
from tools.memory_tools import SalvarMemoriaTool, BuscarMemoriaTool

logger = setup_logger("tools")


# ══════════════════════════════════════════════════════════════
# TOOL MANAGER
# ══════════════════════════════════════════════════════════════

class ToolManager:
    # Ações genuinamente destrutivas/arriscadas que merecem confirmação.
    # Conjunto idêntico ao da V9 original (conferido contra o commit
    # baseline) — a divisão por categoria não alterou isso.
    REQUIRES_CONFIRM = {
        "excluir_arquivo", "fechar_programa", "digitar_texto", "clicar_mouse",
    }

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._register_all()

    def _register_all(self):
        """Auto-descoberta de ferramentas via tools/registry.py (V11)."""
        from tools.registry import discover_tools
        tools = discover_tools()
        for tool in tools:
            self._tools[tool.name] = tool
        logger.info(f"{len(self._tools)} ferramentas disponiveis")

    def dispatch(self, intent: Dict[str, Any], user_input: str = "") -> None:
        from automation.learner_bridge import report_action
        acao       = intent.get("acao", "")
        parametros = normalize_params(acao, intent.get("parametros", {}))

        if acao not in self._tools:
            bus.publish("tool.result", sucesso=False,
                        mensagem=f"Ação desconhecida: '{acao}'", resultado=None)
            return

        if intent.get("confirmacao_necessaria", False) or acao in self.REQUIRES_CONFIRM:
            intent["parametros"] = parametros
            bus.publish("tool.confirm_required", intent=intent)
            return

        self._execute(acao, parametros, user_input=user_input)

    def execute_confirmed(self, intent: Dict[str, Any]) -> None:
        acao       = intent.get("acao")
        parametros = normalize_params(acao, intent.get("parametros", {}))
        user_input = intent.get("_user_input", "")
        self._execute(acao, parametros, user_input=user_input)

    def _execute(self, acao: str, parametros: Dict, user_input: str = "") -> None:
        tool = self._tools.get(acao)
        if not tool:
            bus.publish("tool.result", sucesso=False,
                        mensagem=f"Ferramenta '{acao}' não encontrada", resultado=None)
            return

        logger.info(f"Executando: {acao} com {json.dumps(parametros, ensure_ascii=False)[:120]}")
        with metrics.timer("tool", acao):
            resultado = tool.execute(parametros)

        try:
            db.execute(
                "INSERT INTO action_log (acao, parametros, resultado, sucesso) VALUES (?,?,?,?)",
                (acao, json.dumps(parametros, ensure_ascii=False),
                 json.dumps(resultado.get("resultado"), ensure_ascii=False, default=str),
                 int(resultado["sucesso"])),
            )
        except Exception:
            pass

        # Registra no aprendizado de automações (sucesso) ou de erros (falha)
        if resultado.get("sucesso"):
            try:
                from automation.automation_learner import automation_learner
                automation_learner.register_action(acao, parametros)
            except Exception:
                pass
        else:
            try:
                from automation.error_learning import error_learner
                if user_input:
                    error_learner.register_failure(
                        user_input=user_input,
                        acao_tentada=acao,
                        parametros_tentados=parametros,
                        erro_msg=resultado.get("mensagem", ""),
                    )
            except Exception:
                pass

        bus.publish("tool.result",
                    sucesso=resultado["sucesso"],
                    mensagem=resultado["mensagem"],
                    resultado=resultado.get("resultado"))

    def build_tools_catalog(self, compact: bool = True) -> str:
        """
        Gera o catálogo de ferramentas para o system prompt.

        compact=True (padrão): formato enxuto — só nome e params,
        sem descrições longas nem emoji. Corta o catálogo de ~1070
        para ~450 tokens, o que reduz diretamente o tempo de prefill
        do modelo local em toda chamada (o gargalo real de latência
        em LLMs locais em CPU é processar o prompt, não gerar a
        resposta). compact=False mantém o formato completo, útil
        para debug ou se o modelo precisar de mais contexto por
        ferramenta para acertar parâmetros em casos difíceis.
        """
        categories = {
            "Arquivos":      ["criar_pasta","abrir_pasta","abrir_arquivo","renomear_arquivo","copiar_arquivo","mover_arquivo","excluir_arquivo","pesquisar_arquivo"],
            "Sistema":       ["abrir_programa","fechar_programa","obter_cpu","obter_ram","obter_bateria","obter_metricas"],
            "Navegador":     ["abrir_site","pesquisar_web","pesquisar_youtube","pesquisar_site"],
            "Pesquisa":      ["pesquisar_resposta"],
            "Controle":      ["capturar_tela","mover_mouse","clicar_mouse","digitar_texto","pressionar_tecla","atalho_teclado","rolar_pagina","esperar","copiar_area_transf","escrever_area_transf"],
            "OCR":           ["ler_tela"],
            "Procedimentos": ["salvar_procedimento","executar_procedimento","listar_procedimentos"],
            "Tarefas":       ["criar_tarefa","listar_tarefas","concluir_tarefa"],
            "Memória":       ["salvar_memoria","buscar_memoria"],
        }

        if compact:
            lines = ["FERRAMENTAS (acao: params):"]
            for cat, names in categories.items():
                tool_strs = []
                for name in names:
                    tool = self._tools.get(name)
                    if tool:
                        # Extrai só as chaves de parâmetro do params_doc, sem repetir explicação
                        tool_strs.append(f"{name}{tool.params_doc.split('—')[0].strip()}")
                if tool_strs:
                    lines.append(f"{cat}: " + " | ".join(tool_strs))
            return "\n".join(lines)

        # Formato completo (legado) — mantido para debug/configuração manual
        lines = ["FERRAMENTAS DISPONÍVEIS (use EXATAMENTE esses nomes de ação):"]
        emoji_map = {
            "Arquivos": "📁 Arquivos", "Sistema": "🖥️ Sistema",
            "Navegador": "🌐 Navegador", "Pesquisa": "🔍 Pesquisa (texto)", "Controle": "⌨️ Controle",
            "OCR": "👁️ OCR", "Procedimentos": "🔁 Procedimentos",
            "Tarefas": "✅ Tarefas", "Memória": "🧠 Memória",
        }
        for cat, names in categories.items():
            lines.append(f"\n{emoji_map.get(cat, cat)}:")
            for name in names:
                tool = self._tools.get(name)
                if tool:
                    lines.append(f"  • {name}: {tool.description}")
                    lines.append(f"    Params: {tool.params_doc}")
        return "\n".join(lines)

    def list_tools(self) -> list:
        return [{"nome": t.name, "descricao": t.description} for t in self._tools.values()]


# Instância global
tool_manager = ToolManager()
