"""
Regressão do achado reportado testando a V9 F2 em ambiente Linux real:
"te amo aura" não tinha nenhum caminho garantido e dependia só do
modelo (Qwen2.5 3B) acertar sem exemplo no prompt — às vezes ele
"quebrava personagem" e negava ter nome/sentimentos.
"""
from ai.ai_engine import _quick_casual


def test_affection_has_guaranteed_in_character_response():
    for phrase in ["te amo aura", "eu te amo", "amo você", "adoro voce"]:
        resposta = _quick_casual(phrase)
        assert resposta is not None, f"'{phrase}' deveria ter resposta garantida"
        # Nunca deve negar ter sentimentos/nome — é exatamente o bug relatado
        assert "não tenho" not in resposta.lower()
        assert "sem nome" not in resposta.lower()


def test_affection_still_skipped_when_combined_with_command_word():
    # "abre o spotify, te amo" tem uma palavra de comando -- deve ir pro
    # modelo normalmente, não pro atalho fixo (mesma regra que já existia
    # pra saudação/agradecimento).
    resposta = _quick_casual("abre te amo aura")
    assert resposta is None


def test_greetings_and_thanks_still_work_unaffected():
    # Garante que a nova branch não quebrou o que já existia.
    assert _quick_casual("oi") is not None
    assert _quick_casual("obrigado") is not None
    assert _quick_casual("tudo bem") is not None
    assert _quick_casual("um pedido bem especifico e longo") is None
