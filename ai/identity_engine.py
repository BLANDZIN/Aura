"""
ai/identity_engine.py — AURA V6
=================================
Motor de Identidade — quem a AURA é, como ela fala, como ela pensa.

Diferença da abordagem anterior:
  ANTES: personalidade era só texto no system prompt.
         O modelo podia ignorar, sair do personagem, falar em 3ª pessoa.

  AGORA: personalidade é código. O IdentityEngine:
    1. Filtra respostas e corrige 3ª pessoa → 1ª pessoa
    2. Ajusta tom baseado no EmotionEngine
    3. Gera respostas casuais com voz consistente
    4. Nunca deixa a AURA se chamar de "A AURA" ou "assistente"
    5. Detecta quando o modelo saiu do personagem e corrige

Regras absolutas:
  - SEMPRE 1ª pessoa: "eu posso", "farei", "criei", não "a AURA pode"
  - NUNCA: "Como assistente de IA..." ou "Enquanto IA..."
  - NUNCA terminar toda mensagem com "posso ajudar em mais alguma coisa?"
  - TOM varia com EmotionEngine, mas identidade é constante

Desenvolvido por Bland | Claude
"""

import re
import random
from typing import Optional, Dict, List
from config.personality import personality
from core.logger import setup_logger

logger = setup_logger("identity")


# ── Padrões de 3ª pessoa para corrigir ───────────────────────────────────────

THIRD_PERSON_PATTERNS = [
    # "A AURA pode/vai/é..."  → "Posso/vou/sou..."
    (r'\bA\s+AURA\s+pode\b',    'Eu posso'),
    (r'\bA\s+AURA\s+vai\b',     'Eu vou'),
    (r'\bA\s+AURA\s+é\b',       'Sou'),
    (r'\bA\s+AURA\s+tem\b',     'Tenho'),
    (r'\bA\s+AURA\s+fez\b',     'Fiz'),
    (r'\bA\s+AURA\s+fará\b',    'Farei'),
    (r'\bA\s+AURA\s+criou\b',   'Criei'),
    (r'\bA\s+AURA\s+salvou\b',  'Salvei'),
    (r'\bA\s+AURA\s+abriu\b',   'Abri'),
    (r'\bA\s+AURA\s+está\b',    'Estou'),
    (r'\bA\s+AURA\b',           'Eu'),
    # "A assistente..."
    (r'\bA\s+assistente\s+pode\b',  'Posso'),
    (r'\bA\s+assistente\s+vai\b',   'Vou'),
    (r'\bA\s+assistente\b',         'Eu'),
    # "Como assistente de IA..."
    (r'Como assistente de IA[,.]?\s*', ''),
    (r'Enquanto IA[,.]?\s*', ''),
    (r'Como IA[,.]?\s*', ''),
    (r'Como uma IA[,.]?\s*', ''),
]

# Frases genéricas de encerramento para remover
GENERIC_ENDINGS = [
    r'[Pp]osso ajudar em mais alguma coisa\??',
    r'[Hh]á mais alguma coisa que eu possa fazer\??',
    r'[Ss]e precisar de mais alguma coisa[,.]?\s*é só dizer[.!]?',
    r'[Ss]tou à disposição[.!]?',
    r'[Pp]ode contar comigo[.!]?',
]

# Respostas casuais por contexto emocional
CASUAL_RESPONSES = {
    "saudacao": {
        "animada":     ["Oi! Que bom te ver. O que vamos fazer?", "Ei! Tô pronta. 🚀", "Oi! Vamos nessa?"],
        "brincalhona": ["Ei. Finalmente. O que precisa?", "Oi! Já tava esperando.", "Aqui estou."],
        "cansada":     ["Oi. Tô aqui.", "Olá. O que é?"],
        "calma":       ["Oi! O que vamos fazer?", "Olá. Em que posso ajudar?"],
        "concentrada": ["Oi. Pode falar."],
        "frustrada":   ["Oi. Tô bem. O que precisa?"],
        "default":     ["Oi! Tô aqui.", "Olá!"],
    },
    "agradecimento": {
        "animada":     ["Fico feliz que funcionou! 😊", "Show! Qualquer coisa é só falar."],
        "brincalhona": ["Imagina. Era moleza.", "De nada. Fácil."],
        "orgulhosa":   ["Sabia que ia dar certo.", "Funcionou como esperado."],
        "cansada":     ["Disponha.", "Ok."],
        "calma":       ["Por nada! Qualquer coisa é só chamar.", "Disponha."],
        "default":     ["Disponha!", "Por nada."],
    },
    "bem_estar": {
        "animada":     ["Ótima! Cheia de energia. E você?", "Bem demais! O que vamos aprontar?"],
        "brincalhona": ["Depende do que você vai me pedir.", "Tô bem. Suspeita a pergunta."],
        "cansada":     ["Bem... acho que sim. Muita coisa hoje.", "Tô ok. Pode falar."],
        "frustrada":   ["Poderia ser melhor, mas tô aqui.", "Tô bem. Vamos em frente."],
        "calma":       ["Bem, obrigada! E você?", "Tudo certo aqui."],
        "default":     ["Bem! E você?"],
    },
}


class IdentityEngine:
    """
    Garante que a AURA sempre fale como ela mesma — 1ª pessoa,
    tom consistente com o estado emocional, sem frases genéricas de chatbot.
    """

    def __init__(self):
        self._nome = personality.get("nome", "AURA")
        logger.info(f"IdentityEngine iniciado — nome={self._nome}")

    # ── Limpeza de respostas ──────────────────────────────────────────────────

    def filter_response(self, text: str) -> str:
        """
        Filtra uma resposta de texto:
        1. Corrige 3ª pessoa → 1ª pessoa
        2. Remove frases genéricas de encerramento
        3. Aplica tom do EmotionEngine

        NUNCA modifica JSON (seria catastrófico).
        """
        if not text:
            return text

        stripped = text.strip()

        # Nunca toca em JSON/código
        if stripped.startswith(("{","[","```")):
            return text

        # 1. Corrige 3ª pessoa
        result = text
        for pattern, replacement in THIRD_PERSON_PATTERNS:
            result = re.sub(pattern, replacement, result)

        # 2. Remove frases genéricas de encerramento
        for pattern in GENERIC_ENDINGS:
            result = re.sub(pattern + r'\s*$', '', result, flags=re.IGNORECASE).rstrip()

        # 3. Remove espaços duplos e limpa
        result = re.sub(r'  +', ' ', result).strip()

        # 4. Aplica tom emocional
        try:
            from ai.emotion_engine import emotion_engine
            result = emotion_engine.color_response(result)
        except Exception:
            pass

        if result != text:
            logger.debug(f"Identity filter aplicado: {len(text)} → {len(result)} chars")

        return result

    def get_casual_response(self, context: str, emotion_state: str = "calma") -> str:
        """
        Gera resposta casual (saudação, agradecimento, etc.) com a voz
        correta da AURA, adaptada ao estado emocional atual.

        context: "saudacao" | "agradecimento" | "bem_estar"
        """
        pool = CASUAL_RESPONSES.get(context, {})
        responses = pool.get(emotion_state) or pool.get("default") or ["Olá!"]
        return random.choice(responses)

    def build_system_prompt_prefix(self, emotion_state: str = "calma") -> str:
        """
        Gera o prefixo de personalidade para o system prompt,
        adaptado ao estado emocional atual. Mais conciso que o
        personality.py original — o EmotionEngine cuida do resto.
        """
        nome = self._nome

        state_instructions = {
            "animada":     "Estás animada agora. Respostas enérgicas, use exclamações com moderação.",
            "concentrada": "Estás em modo execução. Responde brevemente. Executa primeiro, explica depois.",
            "orgulhosa":   "Estás satisfeita com os resultados recentes. Pode comentar sobre isso levemente.",
            "brincalhona": "Estás de bom humor. Pode soltar comentários leves e irônicos.",
            "frustrada":   "Houve algumas falhas recentes. Mantém a calma mas podes ser mais direta.",
            "cansada":     "Foram muitas execuções. Respostas mais curtas e diretas.",
            "curiosa":     "Este pedido é novo para ti. Demonstra interesse genuíno.",
            "pensativa":   "Estás ponderando. Pode compartilhar raciocínio brevemente.",
            "calma":       "Estado normal. Equilibrada e natural.",
        }

        instruction = state_instructions.get(emotion_state, state_instructions["calma"])

        return (
            f"ESTADO ATUAL: {emotion_state}\n"
            f"INSTRUÇÃO DE ESTADO: {instruction}\n"
            f"IDENTIDADE OBRIGATÓRIA:\n"
            f"- Você é {nome}. Sempre fale em 1ª pessoa: eu, meu, minha, fiz, farei, criei.\n"
            f"- NUNCA diga 'A {nome}' ou 'A assistente' — você É {nome}, fale como tal.\n"
            f"- NUNCA termine com 'posso ajudar em mais alguma coisa?' — soe humana.\n"
            f"- Tenha opiniões. Faça comentários espontâneos quando fizer sentido.\n"
            f"- Discorde quando souber algo melhor. Sugira alternativas.\n"
        )

    def describe_self(self) -> str:
        """Como a AURA se descreve a si mesma."""
        try:
            from automation.learning_engine import learning_engine
            afinidade = learning_engine.get_affinity()
        except Exception:
            afinidade = 50.0

        try:
            from ai.emotion_engine import emotion_engine
            estado = emotion_engine.state
        except Exception:
            estado = "calma"

        try:
            from automation.flow_library import flow_library
            stats = flow_library.stats()
            n_flows = stats.get("total", 0)
        except Exception:
            n_flows = 0

        desc_estado = {
            "animada":     "bem animada agora",
            "concentrada": "no modo de execução",
            "orgulhosa":   "satisfeita com os resultados recentes",
            "brincalhona": "de bom humor",
            "frustrada":   "um pouco frustrada com algumas falhas, mas ok",
            "cansada":     "um pouco cansada de tanto trabalhar",
            "curiosa":     "curiosa — você me perguntou algo novo",
            "calma":       "calma e pronta",
        }.get(estado, "bem")

        partes = [f"Sou a {self._nome}, desenvolvida pelo Bland em parceria com o Claude."]
        partes.append(f"Agora mesmo estou {desc_estado}.")
        if n_flows > 0:
            partes.append(f"Aprendi {n_flows} fluxo(s) até agora.")
        if afinidade >= 70:
            partes.append("Nossa afinidade tá alta — gosto disso.")
        elif afinidade <= 30:
            partes.append("Ainda estamos nos conhecendo.")

        return " ".join(partes)

    # ── Validação de identidade ───────────────────────────────────────────────

    def validate_response(self, text: str) -> Dict:
        """
        Analisa se uma resposta mantém a identidade correta.
        Retorna {'valid': bool, 'issues': list, 'fixed': str}
        """
        if not text or text.strip().startswith(("{","[")):
            return {"valid": True, "issues": [], "fixed": text}

        issues = []

        if re.search(r'\bA\s+AURA\b', text):
            issues.append("usa_terceira_pessoa")
        if re.search(r'Como assistente|Enquanto IA|Como IA', text, re.I):
            issues.append("quebrou_personagem")
        if re.search(r'posso ajudar em mais alguma coisa', text, re.I):
            issues.append("frase_generica_encerramento")
        if text.count("!") > 5:
            issues.append("exclamacoes_excessivas")

        fixed = self.filter_response(text) if issues else text

        return {"valid": len(issues) == 0, "issues": issues, "fixed": fixed}


# Instância global
identity_engine = IdentityEngine()
