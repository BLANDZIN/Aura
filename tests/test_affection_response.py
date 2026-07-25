"""
Regressao do bug "te amo aura" sem resposta garantida (V9).
Na V11, frases de afeto sao respondidas pelo modelo de IA,
nao por respostas fixas. O modelo aprende o tom via exemplos
no system prompt (config/personality.py).

V12.1: reforçado apos achado da auditoria — o codigo tinha o COMENTARIO
"substring match para afeto" mas nenhum match realmente acontecia em
lugar nenhum; "te amo aura" ia pro modelo SEM nenhum reforco de
contexto (a mesma exposicao ao bug original da V9, só que
silenciosa). Os testes abaixo cobrem o mecanismo de verdade —
_quick_casual retornando None não é suficiente sozinho, porque isso
também seria verdade se o Context Builder não existisse.
"""
from ai.ai_engine import _quick_casual, _detect_emotional_category
from ai.prompt_builder import build_system_message


def test_affection_goes_to_model_not_hardcoded():
    """Frases de afeto devem ir pro modelo para resposta natural.
    Nao devem ser bloqueadas por comandos ou limite de palavras."""
    # Frases curtas de afeto PURO (sem comando) → None = vai pro modelo
    for phrase in ["te amo", "eu te amo", "amo voce", "meu amor"]:
        resposta = _quick_casual(phrase)
        # V11: None = vai pro modelo responder com personalidade real
        assert resposta is None, (
            f"'{phrase}' deveria ir pro modelo, nao ter resposta fixa. "
            f"Retornou: {resposta}"
        )


def test_affection_with_command_still_goes_to_model():
    """Afeto + comando vai pro modelo (comando tem prioridade)."""
    resposta = _quick_casual("abre o spotify te amo")
    assert resposta is None


def test_greetings_and_thanks_still_work():
    """Saudacoes e agradecimentos continuam instantaneos."""
    assert _quick_casual("oi") is not None
    assert _quick_casual("obrigado") is not None
    assert _quick_casual("tudo bem") is not None
    assert _quick_casual("um pedido bem especifico e longo") is None


def test_affection_is_actually_detected_as_emotional_category():
    # Isso e o que faltava: _quick_casual(None) sozinho nao prova que o
    # modelo recebeu QUALQUER reforco de personalidade — so prova que
    # não recebeu uma resposta fixa. Confirma que a categoria certa é
    # detectada de verdade.
    for phrase in ["te amo aura", "eu te amo", "amo você", "adoro voce"]:
        assert _detect_emotional_category(phrase) == "afeto", phrase


def test_identity_denial_risk_is_detected():
    assert _detect_emotional_category("voce tem sentimentos") == "identidade"
    assert _detect_emotional_category("você é só uma ia") == "identidade"


def test_elogio_and_vinculo_are_detected():
    assert _detect_emotional_category("você é demais") == "elogio"
    assert _detect_emotional_category("somos amigas") == "vinculo"


def test_neutral_command_has_no_emotional_category():
    assert _detect_emotional_category("abre o spotify") is None
    assert _detect_emotional_category("qual a previsao do tempo") is None


def test_emotional_category_actually_reaches_the_system_prompt():
    # Fecha o ciclo: categoria detectada -> bloco de reforco realmente
    # aparece no system prompt que vai pro modelo nesse turno.
    class _FakePersonality:
        def build_system_prompt(self, tools_catalog=""):
            return "PROMPT BASE"

    class _FakeMemory:
        def build_relevant_context(self):
            return ""

    class _FakeToolManager:
        def build_tools_catalog(self, compact=True):
            return ""

    msg = build_system_message(
        personality=_FakePersonality(),
        memory=_FakeMemory(),
        tool_manager=_FakeToolManager(),
        emotional_context="afeto",
    )
    assert "nunca negue ser aura" in msg["content"].lower()

    msg_sem_contexto = build_system_message(
        personality=_FakePersonality(),
        memory=_FakeMemory(),
        tool_manager=_FakeToolManager(),
        emotional_context=None,
    )
    assert msg_sem_contexto["content"] == "PROMPT BASE"
