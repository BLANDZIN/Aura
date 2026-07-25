"""
core/context.py - AURA V11
===========================
AuraContext — objeto de contexto unificado que flui pelo pipeline.

Centraliza user_input, memory, history, provider, tools, settings
em um unico objeto em vez de passar parametros individuais.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AuraContext:
    """Contexto completo de uma interacao com a AURA."""
    user_input: str = ""

    # Memoria e historico
    short_term_messages: List[Dict] = field(default_factory=list)
    memory_context: str = ""
    procedure_context: str = ""

    # Provider e ferramentas
    provider_name: str = "ollama"
    model_name: str = ""
    tools_catalog: str = ""

    # Ambiente
    vision_context: str = ""
    system_info: Dict[str, Any] = field(default_factory=dict)

    # Configuracoes
    temperature: float = 0.7
    max_tokens: int = 2048
    language: str = "pt"

    # Metadados
    session_id: str = ""
    flow_name: Optional[str] = None

    def build_system_context(self) -> str:
        """Monta string de contexto para injetar no prompt."""
        parts = []
        if self.memory_context:
            parts.append(self.memory_context)
        if self.procedure_context:
            parts.append(self.procedure_context)
        if self.vision_context:
            parts.append(self.vision_context)
        return "\n\n".join(parts)
