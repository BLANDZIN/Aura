"""
tools/memory_tools.py — Ferramentas de Memória (2)
Extraído de tool_manager.py na divisão por categoria (Fase 2/V10) —
comportamento idêntico, só mudou de arquivo.
"""
from datetime import datetime

from tools.base_tool import BaseTool


class SalvarMemoriaTool(BaseTool):
    name = "salvar_memoria"; description = "Salva informação na memória permanente."
    params_doc = '{"valor": "texto livre"}  — chave/categoria opcionais'
    def execute(self, p):
        from memory.memory_manager import memory
        try:
            memory.permanent.save(
                categoria=p.get("categoria","conversa"),
                chave=p.get("chave", f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                valor=p["valor"], importance=p.get("importance",5))
            return self._success(mensagem=f"Memorizado: {str(p['valor'])[:60]}")
        except Exception as e:
            return self._error("Erro ao salvar memória", e)

class BuscarMemoriaTool(BaseTool):
    name = "buscar_memoria"; description = "Busca informação na memória."
    params_doc = '{"chave": "nome_usuario"}'
    def execute(self, p):
        from memory.memory_manager import memory
        try:
            r = memory.permanent.get(p["chave"])
            return self._success(r, f"Memória: {r}" if r else "Não encontrado")
        except Exception as e:
            return self._error("Erro ao buscar", e)
