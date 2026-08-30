"""
ai/agent_provider.py — AURA V12.2
Arquitetura multi-agente (ver docs/AI_ARCHITECTURE.md e docs/MODELS.md).

Cada agente é um OllamaProvider com namespace próprio em config/settings.py
— mesmo padrão que angela/llm/backend.py já usa pra Angela desde a V9/V10.
Não é mecanismo novo, é extensão do que já existia e já era testado.

Todo agente é OPCIONAL. Se agents_enabled=False, se o Ollama não
responder, ou se o agente estourar o timeout curto (ver _TIMEOUTS
abaixo), ask()/ask_json() retornam None — nunca uma exceção. Quem chama
SEMPRE precisa tratar o None como "cai no fallback determinístico já
existente" (ver tabela "Modo degradado" em docs/AI_ARCHITECTURE.md).
Nenhum destes agentes é obrigatório pro sistema funcionar; a AURA se
comporta como na V12.1 se nenhum estiver disponível.
"""
import json
from typing import Any, Dict, Optional

from ai.ai_provider import OllamaProvider
from config.settings import settings
from core.logger import setup_logger

logger = setup_logger("agent_provider")

# Timeout curto por papel — falhar rápido é melhor que travar num agente
# que é só enriquecimento opcional (ver "Limites por agente" em
# docs/AI_ARCHITECTURE.md). Bem menor que o timeout de leitura da
# conversa principal (300s) de propósito.
_TIMEOUTS = {
    "intent": 3.0, "planner": 5.0, "reflection": 5.0,
    "memory": 3.0, "emotion": 2.0, "vision": 4.0, "autonomy": 3.0,
}

_SYSTEM_PROMPTS = {
    "intent": (
        'Voce extrai intencao de comandos em portugues. Responda SOMENTE '
        'em JSON: {"acao": str, "tipo": str, "alvo": str, "confianca": '
        'float 0-1}. Sem texto antes ou depois do JSON.'
    ),
    "planner": (
        'Voce quebra objetivos em passos estruturados. Responda SOMENTE '
        'em JSON: lista de {"acao": str, "parametros": dict}. Nunca '
        'conversa com o usuario, so retorna o plano.'
    ),
    "reflection": (
        'Voce revisa o resultado de um fluxo executado. Responda SOMENTE '
        'em JSON: {"erros": [str], "melhorias": [str], "repetir": bool}.'
    ),
    "memory": (
        'Voce identifica se uma troca de mensagens revela uma preferencia '
        'do usuario (apelido, forma de tratamento, estilo, habito, gosto). '
        'Responda SOMENTE em JSON: {"categoria": str ou null, "chave": '
        'str ou null, "valor": str ou null}.'
    ),
    "emotion": (
        'Voce ajusta o estado emocional da AURA dado o evento atual. '
        'Responda SOMENTE em JSON: {"estado": str}.'
    ),
    "vision": (
        "Voce recebe dados brutos do ambiente (janela ativa, programas "
        "abertos, clipboard) e devolve uma interpretacao curta em 1-2 "
        "frases, em portugues, SEM JSON — so o resumo em texto direto."
    ),
    "autonomy": (
        'Voce avalia se ha uma boa oportunidade de sugestao proativa '
        'dado o contexto. Responda SOMENTE em JSON: {"sugestao": str '
        'ou null, "confianca": float 0-1}. Nunca execute nada, so sugira.'
    ),
}

AGENT_IDS = tuple(_TIMEOUTS.keys())


def _looks_like_error(resposta: Optional[str]) -> bool:
    """
    Detecta as strings de erro que OllamaProvider.chat() já retorna (o
    método nunca levanta exceção — ver ai/ai_provider.py) em vez de
    deixar esse texto de erro ser tratado como resposta válida do agente.
    """
    if not resposta:
        return True
    stripped = resposta.strip()
    return stripped.startswith('{"erro"') or stripped.startswith("[Erro:")


class AgentProvider:
    """
    Fachada única pros agentes especialistas. `aura` (conversa principal)
    NÃO está aqui — continua em ai/ai_engine.py via ai_provider.get_provider().
    Este módulo é só quem dá apoio a ela.
    """

    def __init__(self):
        self._providers: Dict[str, OllamaProvider] = {}

    def _get_provider(self, agent_id: str) -> OllamaProvider:
        if agent_id not in self._providers:
            self._providers[agent_id] = OllamaProvider(
                settings_namespace=f"agent_{agent_id}"
            )
        return self._providers[agent_id]

    def is_enabled(self) -> bool:
        return bool(settings.get("agents_enabled", default=False))

    def ask(
        self, agent_id: str, prompt: str, context: Optional[str] = None
    ) -> Optional[str]:
        """
        Consulta um agente. Retorna None — nunca uma exceção — se
        agents_enabled=False, agente desconhecido, Ollama indisponível,
        ou timeout. Quem chama sempre precisa tratar o None como "cai no
        fallback atual".
        """
        if not self.is_enabled():
            return None
        if agent_id not in AGENT_IDS:
            logger.warning(f"Agente desconhecido: '{agent_id}'")
            return None

        provider = self._get_provider(agent_id)
        messages = [{"role": "system", "content": _SYSTEM_PROMPTS[agent_id]}]
        if context:
            messages.append({"role": "user", "content": f"Contexto:\n{context}"})
        messages.append({"role": "user", "content": prompt})

        try:
            resposta = provider.chat(messages, timeout=_TIMEOUTS[agent_id])
        except Exception as e:
            logger.debug(f"Agente '{agent_id}' falhou (não crítico): {e}")
            return None

        if _looks_like_error(resposta):
            logger.debug(f"Agente '{agent_id}' indisponível: {resposta[:100]}")
            return None
        return resposta

    def ask_json(
        self, agent_id: str, prompt: str, context: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Como ask(), mas já faz o parse de JSON. None se falhar em
        qualquer etapa (agente indisponível OU resposta não é JSON
        válido) — quem chama trata os dois casos da mesma forma: cai
        no fallback.
        """
        raw = self.ask(agent_id, prompt, context)
        if raw is None:
            return None
        try:
            # Modelos pequenos às vezes cercam o JSON com texto/markdown.
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            logger.debug(f"Agente '{agent_id}' respondeu algo que não é JSON: {raw[:100]}")
            return None


# Instância global — mesmo padrão de tool_manager/flow_executor/memory/etc.
agent_provider = AgentProvider()
