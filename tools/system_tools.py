"""
tools/system_tools.py — Ferramentas de Sistema (5)
Extraído de tool_manager.py na divisão por categoria (Fase 2/V10) —
comportamento idêntico, só mudou de arquivo.
"""
import psutil

from tools.base_tool import BaseTool
from tools.resolvers import _shell_open


class AbrirProgramaTool(BaseTool):
    name = "abrir_programa"
    description = "Abre programa, app ou aplicativo. Aceita nomes amigáveis e .exe."
    params_doc = '{"programa": "chrome"}  — ex: "calculadora", "discord", "notepad", "chrome.exe"'
    def execute(self, p):
        try:
            prog = p["programa"]
            args = p.get("argumentos", [])
            _shell_open(prog, args)
            return self._success(mensagem=f"Abrindo: {prog}")
        except Exception as e:
            return self._error(f"Erro ao abrir '{p.get('programa')}'", e)

class FecharProgramaTool(BaseTool):
    name = "fechar_programa"
    description = "Fecha processo pelo nome. REQUER CONFIRMAÇÃO."
    params_doc = '{"processo": "chrome.exe"}'
    def execute(self, p):
        try:
            nome   = p["processo"].lower()
            mortos = []
            for proc in psutil.process_iter(["name", "pid"]):
                if nome in proc.info["name"].lower():
                    proc.terminate()
                    mortos.append(proc.info["name"])
            if mortos:
                return self._success(mortos, f"Encerrado(s): {', '.join(mortos)}")
            return self._error(f"Processo '{nome}' não encontrado")
        except Exception as e:
            return self._error("Erro ao fechar processo", e)

class ObterCPUTool(BaseTool):
    name = "obter_cpu"; description = "Retorna uso da CPU."; params_doc = '{}'
    def execute(self, p):
        cpu = psutil.cpu_percent(interval=1)
        return self._success(cpu, f"CPU: {cpu}%")

class ObterRAMTool(BaseTool):
    name = "obter_ram"; description = "Retorna uso da RAM."; params_doc = '{}'
    def execute(self, p):
        ram = psutil.virtual_memory()
        r = {"total_gb": round(ram.total/1e9,1), "usado_gb": round(ram.used/1e9,1), "percentual": ram.percent}
        return self._success(r, f"RAM: {ram.percent}% ({r['usado_gb']}/{r['total_gb']}GB)")

class ObterBateriaTool(BaseTool):
    name = "obter_bateria"; description = "Retorna nível da bateria."; params_doc = '{}'
    def execute(self, p):
        bat = psutil.sensors_battery()
        if not bat:
            return self._error("Sem bateria detectada")
        r = {"percentual": round(bat.percent), "carregando": bat.power_plugged}
        return self._success(r, f"Bateria: {r['percentual']}% ({'carregando' if bat.power_plugged else 'descarregando'})")

class ObterMetricasTool(BaseTool):
    name = "obter_metricas"
    description = "Retorna métricas reais de desempenho desta sessão (tempo de modelo, ferramentas, EventBus, fluxos)."
    params_doc = '{}'
    def execute(self, p):
        from core.metrics import metrics
        summary = metrics.summary()
        if not summary:
            return self._success({}, "Nenhuma métrica coletada ainda nesta sessão")
        return self._success(summary, metrics.to_markdown())


# Auto-registro V11
REGISTRY = [AbrirProgramaTool(), FecharProgramaTool(), ObterCPUTool(), ObterRAMTool(), ObterBateriaTool(), ObterMetricasTool()]