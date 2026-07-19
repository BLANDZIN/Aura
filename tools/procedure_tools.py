"""
tools/procedure_tools.py — Ferramentas de Automação Procedimental (3)
Extraído de tool_manager.py na divisão por categoria (Fase 2/V10) —
comportamento idêntico, só mudou de arquivo.
"""
from tools.base_tool import BaseTool


class SalvarProcedimentoTool(BaseTool):
    name = "salvar_procedimento"
    description = "Salva uma sequência de ações como procedimento reutilizável."
    params_doc = '{"nome": "rotina_manha", "descricao": "Rotina da manhã", "passos": [{"acao":"abrir_programa","parametros":{"programa":"chrome.exe"}}]}'

    def execute(self, p):
        from memory.memory_manager import memory
        try:
            nome    = p["nome"].strip().lower().replace(" ", "_")
            passos  = p["passos"]
            desc    = p.get("descricao", nome)
            importance = int(p.get("importance", 7))
            if not isinstance(passos, list) or not passos:
                return self._error("'passos' deve ser uma lista não vazia")
            memory.procedural.save(nome=nome, descricao=desc, passos=passos, importance=importance)
            return self._success(nome, f"Procedimento '{nome}' salvo com {len(passos)} passo(s)")
        except Exception as e:
            return self._error("Erro ao salvar procedimento", e)

class ExecutarProcedimentoTool(BaseTool):
    name = "executar_procedimento"
    description = "Executa um procedimento salvo pelo nome."
    params_doc = '{"nome": "rotina_manha"}'

    def execute(self, p):
        from memory.memory_manager import memory
        from automation.planner import planner
        from automation.flow_executor import flow_executor
        try:
            nome = str(p["nome"]).strip().lower().replace(" ", "_")
            proc = memory.procedural.get(nome)
            if not proc:
                # Tenta busca parcial
                todos = memory.procedural.get_all()
                matches = [x for x in todos if nome in x["nome"].lower()]
                if matches:
                    proc = matches[0]
                else:
                    return self._error(f"Procedimento '{nome}' não encontrado")
            plan = planner._plan_from_procedure(proc)
            flow_executor.execute(plan, async_mode=True)
            return self._success(nome, f"Executando procedimento: '{proc['nome']}' ({len(proc['passos'])} etapa(s))")
        except Exception as e:
            return self._error("Erro ao executar procedimento", e)

class ListarProcedimentosTool(BaseTool):
    name = "listar_procedimentos"
    description = "Lista todos os procedimentos salvos."
    params_doc = '{}'

    def execute(self, p):
        from memory.memory_manager import memory
        try:
            procs = memory.procedural.get_all()
            if not procs:
                return self._success([], "Nenhum procedimento salvo ainda")
            items = [f"• {pr['nome']}: {pr.get('descricao','')} ({len(pr['passos'])} passos)" for pr in procs]
            return self._success(procs, "\n".join(items))
        except Exception as e:
            return self._error("Erro ao listar procedimentos", e)
