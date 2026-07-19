"""
angela/llm/backend.py
Conexão da Angela com o modelo local — Qwen3 4B via Ollama.

Reaproveita ai.ai_provider.OllamaProvider (mesma classe que a AURA usa
para Qwen2.5 3B), instanciado com settings_namespace="angela": modelo,
URL, temperatura e chamadas completamente independentes das da AURA.
Este módulo nunca importa ai/ai_engine.py nem memory/ — Angela não tem
acesso ao histórico de conversa da AURA, e vice-versa (separação
obrigatória).

O LLM aqui só raciocina: recebe um prompt e devolve texto. Nunca lê ou
escreve arquivo diretamente — quem faz isso é a EngineeringPlatform,
chamada por chief_engineer.py. Este módulo é deliberadamente burro.
"""

from typing import List, Optional

from ai.ai_provider import OllamaProvider
from angela.personality import SYSTEM_PROMPT
from core.logger import setup_logger

logger = setup_logger("angela.llm")


class AngelaLLM:
    """Canal exclusivo da Angela com o Qwen3 4B (via Ollama)."""

    def __init__(self):
        self._provider = OllamaProvider(settings_namespace="angela")

    def is_available(self) -> bool:
        return self._provider.is_available()

    def ask(self, user_message: str, context: Optional[List[str]] = None) -> str:
        """
        Envia uma pergunta ao modelo com o SYSTEM_PROMPT da persona e o
        contexto reunido pelo workflow (arquivos lidos, notas de
        arquitetura, hipóteses). Stateless por chamada — histórico da
        investigação fica no InvestigationReport, não aqui.
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if context:
            joined = "\n---\n".join(c for c in context if c)
            if joined:
                messages.append({
                    "role": "user",
                    "content": f"Contexto reunido até aqui:\n{joined}",
                })
        messages.append({"role": "user", "content": user_message})

        try:
            return self._provider.chat(messages)
        except Exception as e:
            logger.error(f"Falha ao consultar o modelo da Angela: {e}")
            return f'{{"erro": "Angela não conseguiu consultar o modelo: {e}"}}'
