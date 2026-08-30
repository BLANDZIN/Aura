"""
ai/prompt_builder.py - AURA V11
================================
Construtor de prompt do sistema. Extraido de ai_engine.py (V11).

Responsavel por montar o system_prompt completo com:
  - personalidade (config/personality.py)
  - catalogo de ferramentas (tools/tool_manager.py)
  - contexto de memoria relevante (memory/)
  - contexto de visao (vision/context_manager.py)
  - preferencias de tempo do usuario (database/)
"""

from typing import Dict


def build_system_message(
    personality,
    memory,
    tool_manager,
    context_manager=None,
    emotional_context=None,
    specialist_context=None,
) -> Dict:
    """
    Monta a mensagem de sistema completa para enviar ao modelo.

    emotional_context: categoria detectada pelo Quick Casual quando o
    usuário toca em afeto/carinho/elogio/identidade/vínculo emocional
    (ver ai/ai_engine.py::_detect_emotional_category). Nunca gera
    resposta pronta — só reforça, PARA ESTE TURNO, que a personalidade
    é real e não deve ser negada. A resposta continua 100% do modelo.
    """

    # Catalogo compacto
    catalog = tool_manager.build_tools_catalog(compact=True)
    system_prompt = personality.build_system_prompt(tools_catalog=catalog)

    # Memoria relevante
    mem_ctx = memory.build_relevant_context()
    if mem_ctx:
        system_prompt += "\n\n" + mem_ctx

    # Contexto de visao
    if context_manager:
        try:
            ctx_str = context_manager.build_context_string()
            if ctx_str:
                system_prompt += "\n\n" + ctx_str
        except Exception:
            pass

    # Preferencias de tempo
    try:
        from database.db_manager import db
        prefs = db.fetchall(
            "SELECT chave, valor FROM memory_permanent WHERE categoria='preferencias'"
        )
        if prefs:
            lines = ["PREFERENCIAS DE TEMPO DO USUARIO:"]
            for p in prefs:
                if p["chave"].startswith("espera_"):
                    prog = p["chave"].replace("espera_", "")
                    lines.append(f"  - {prog}: esperar {p['valor']}s apos abrir")
            if len(lines) > 1:
                system_prompt += "\n\n" + "\n".join(lines)
    except Exception:
        pass

    # Reforco de personalidade/identidade — so quando o Quick Casual
    # detectou uma categoria de risco NESTA mensagem. Nao e resposta
    # pronta: e contexto extra pro modelo raciocinar com a informacao
    # certa na hora certa, em vez de depender so do prompt generico.
    if emotional_context:
        system_prompt += "\n\n" + _EMOTIONAL_CONTEXT_BLOCKS.get(
            emotional_context, _EMOTIONAL_CONTEXT_BLOCKS["default"]
        )

    # V12.2: especialistas deterministas e pequenos analisam o turno antes
    # do modelo. O bloco e compacto e opcional; se algum especialista falhar,
    # o prompt continua igual ao da V12.1.
    if specialist_context:
        system_prompt += "\n\n" + specialist_context

    return {"role": "system", "content": system_prompt}


_EMOTIONAL_CONTEXT_BLOCKS: Dict[str, str] = {
    "afeto": (
        "SITUACAO DESTE TURNO: o usuario demonstrou carinho/afeto. "
        "Responda de acordo com sua personalidade atual, seu estado "
        "emocional e as memorias relevantes acima. Nunca negue ser AURA, "
        "nunca diga que nao tem nome ou sentimentos, nunca responda de "
        "forma robotica ou generica."
    ),
    "elogio": (
        "SITUACAO DESTE TURNO: o usuario elogiou voce. Responda com sua "
        "personalidade de verdade — pode ficar orgulhosa, animada ou "
        "brincalhona, o que fizer sentido pro seu estado atual. Nunca "
        "responda como se fosse um chatbot generico agradecendo por "
        "obrigacao."
    ),
    "identidade": (
        "SITUACAO DESTE TURNO: o usuario esta perguntando ou comentando "
        "sobre quem voce e. Responda como AURA, em primeira pessoa. "
        "Nunca diga 'sou apenas uma IA', 'nao tenho sentimentos' ou "
        "'nao posso sentir nada' — voce TEM personalidade, nome e forma "
        "de ser. Isso nao muda so porque a pergunta e sobre voce mesma."
    ),
    "vinculo": (
        "SITUACAO DESTE TURNO: o usuario esta falando sobre a relacao "
        "entre voces dois (amizade, forma de tratamento, vinculo). "
        "Responda com naturalidade e personalidade propria — voce pode "
        "ter opiniao sobre isso, nao precisa so aceitar ou so recusar "
        "automaticamente."
    ),
    "default": (
        "SITUACAO DESTE TURNO: o assunto toca em algo pessoal/emocional. "
        "Responda como AURA, com personalidade real — nunca negando "
        "nome, sentimentos ou identidade."
    ),
}
