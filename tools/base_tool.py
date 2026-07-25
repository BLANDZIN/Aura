"""
tools/base_tool.py
Classe base para todas as ferramentas da AURA. Extraído de tool_manager.py
na divisão por categoria (Fase 2/V10) — comportamento idêntico, só mudou
de arquivo.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict

from core.logger import setup_logger

logger = setup_logger("tools")



from dataclasses import dataclass, field
from typing import Any, Optional
import time


@dataclass
class ToolResult:
    """Resultado padronizado de toda ferramenta AURA (V11).
    
    Todas as 38 ferramentas usam este formato via _success()/_error().
    """
    success: bool
    message: str = ""
    data: Any = None
    metadata: dict = field(default_factory=dict)
    execution_time_ms: float = 0.0

    @classmethod
    def ok(cls, data=None, message="Concluido.", **metadata):
        return cls(success=True, data=data, message=message, metadata=metadata)

    @classmethod
    def fail(cls, message="Erro.", data=None, **metadata):
        return cls(success=False, data=data, message=message, metadata=metadata)

    def to_dict(self):
        return {
            "sucesso": self.success,
            "mensagem": self.message,
            "resultado": self.data,
        }



class BaseTool(ABC):
    name: str = ""
    description: str = ""
    params_doc: str = ""

    @abstractmethod
    def execute(self, parametros: Dict[str, Any]) -> Dict[str, Any]: ...

    def _success(self, resultado=None, mensagem: str = "Concluido.") -> Dict:
        return {"sucesso": True, "resultado": resultado, "mensagem": mensagem}

    def _error(self, mensagem: str, erro=None) -> Dict:
        if erro:
            logger.error(f"[{self.name}] {mensagem}: {erro}")
        return {"sucesso": False, "resultado": None, "mensagem": mensagem}

    def _pyautogui_error(self, mensagem_padrao: str, erro: Exception) -> Dict:
        """
        Trata exceções de ferramentas que usam pyautogui, distinguindo o
        fail-safe (mouse em um canto da tela) de erros genéricos.

        Causa raiz real: pyautogui.FAILSAFE=True dispara FailSafeException
        em QUALQUER chamada pyautogui (não só movimento de mouse — também
        press()/hotkey() puros) sempre que o cursor está em um dos 4
        cantos da tela. Isso é comum (perto do Menu Iniciar, bandeja do
        sistema) e antes desta correção era engolido como erro genérico
        tipo "Erro ao pressionar tecla" — sem nenhuma pista do motivo
        real. Como FlowExecutor aborta o fluxo inteiro no primeiro passo
        que falha, uma sequência de várias etapas parava silenciosamente,
        parecendo que "a ferramenta não funciona".
        """
        try:
            import pyautogui
            is_failsafe = isinstance(erro, pyautogui.FailSafeException)
        except Exception:
            is_failsafe = type(erro).__name__ == "FailSafeException"

        if is_failsafe:
            msg = (
                "Ação interrompida: o mouse está em um canto da tela, o que "
                "ativa uma trava de segurança automática. Mova o mouse para "
                "o centro da tela e tente de novo."
            )
            logger.warning(f"[{self.name}] PyAutoGUI fail-safe ativado (mouse em canto da tela)")
            return {"sucesso": False, "resultado": None, "mensagem": msg}

        return self._error(mensagem_padrao, erro)
