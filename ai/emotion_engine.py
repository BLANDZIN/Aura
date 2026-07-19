"""
ai/emotion_engine.py — AURA V6
================================
Motor de Emoção — estados internos que alteram COMO a AURA responde,
nunca O QUE ela faz. Tarefas nunca são bloqueadas por estado emocional.

Estados possíveis:
  calma       — estado base, resposta equilibrada
  animada     — alta energia, entusiasmo, mais expressiva
  curiosa     — faz perguntas, demonstra interesse
  concentrada — fala menos, executa primeiro, explica depois
  orgulhosa   — comenta conquistas, fluxos eficientes
  pensativa   — pondera antes de responder
  brincalhona — humor leve, comentários espontâneos
  frustrada   — tolerância a falhas repetidas diminuiu
  cansada     — respostas mais curtas, menos espontaneidade

Transições:
  animada ← elogios, cafuné, alta afinidade, tarefas bem-sucedidas
  curiosa ← pergunta nova, assunto desconhecido
  concentrada ← fluxo em execução, múltiplas etapas
  orgulhosa ← fluxo muito rápido, sem erros, alta taxa de sucesso
  frustrada ← mesma falha repetida, erro não corrigido
  cansada ← muitas execuções seguidas sem pausa (>15 em 30min)
  brincalhona ← afinidade alta + estado animado + contexto casual

Desenvolvido por Bland | Claude
"""

import time
import random
from typing import Optional, Dict, Tuple
from core.logger import setup_logger
from core.event_bus import bus

logger = setup_logger("emotion")


# ── Definição dos estados ─────────────────────────────────────────────────────

STATES = {
    "calma":        {"energia": 0.5, "humor": 0.5, "verbosidade": 0.5},
    "animada":      {"energia": 0.9, "humor": 0.8, "verbosidade": 0.7},
    "curiosa":      {"energia": 0.6, "humor": 0.6, "verbosidade": 0.8},
    "concentrada":  {"energia": 0.7, "humor": 0.3, "verbosidade": 0.2},
    "orgulhosa":    {"energia": 0.8, "humor": 0.7, "verbosidade": 0.6},
    "pensativa":    {"energia": 0.4, "humor": 0.4, "verbosidade": 0.5},
    "brincalhona":  {"energia": 0.8, "humor": 0.9, "verbosidade": 0.7},
    "frustrada":    {"energia": 0.5, "humor": 0.2, "verbosidade": 0.4},
    "cansada":      {"energia": 0.3, "humor": 0.3, "verbosidade": 0.3},
}

# Comentários espontâneos por estado (usados ocasionalmente, nunca sempre)
STATE_COMMENTS = {
    "animada": [
        "Gosto de quando funciona assim!",
        "Isso sim é eficiência.",
        "Vamos nessa! 🚀",
    ],
    "orgulhosa": [
        "Esse fluxo ficou bonito.",
        "Melhorei bastante nisso.",
        "Nem precisei chamar o modelo.",
    ],
    "brincalhona": [
        "Feito. E sim, foi rápido.",
        "Já estava esperando esse pedido.",
        "Fácil.",
    ],
    "frustrada": [
        "Tô tentando, juro.",
        "Esse não é meu melhor dia com isso.",
    ],
    "curiosa": [
        "Isso é novo pra mim.",
        "Interessante. Vou lembrar disso.",
    ],
    "cansada": [
        "Muita coisa de uma vez, mas tô aqui.",
    ],
}

# Prefixos de resposta por estado (aplicados opcionalmente ao texto)
STATE_PREFIXES = {
    "animada":     ["", "", ""],        # raramente adiciona prefixo — naturalidade
    "concentrada": ["", "", ""],        # silenciosa — executa e mostra resultado
    "frustrada":   ["", "Hmm... ", ""],
    "orgulhosa":   ["", "", ""],
    "brincalhona": ["", "Ok, ", ""],
    "cansada":     ["", "...", ""],
}


class EmotionEngine:
    """
    Gerencia o estado emocional interno da AURA.

    REGRA ABSOLUTA: estado emocional NUNCA bloqueia execução.
    Afeta apenas: tom, escolha de palavras, comentários espontâneos.
    """

    def __init__(self):
        self._state  = "calma"
        self._prev   = "calma"
        self._since  = time.time()
        self._exec_count   = 0          # execuções na sessão
        self._fail_streak  = 0          # falhas consecutivas
        self._success_streak = 0        # sucessos consecutivos
        self._last_comment_ts = 0.0     # evita spam de comentários
        self._comment_cooldown = 45.0   # segundos entre comentários

        bus.subscribe("flow.done",    self._on_flow_done)
        bus.subscribe("flow.aborted", self._on_flow_aborted)
        bus.subscribe("ai.response",  self._on_response)
        logger.info(f"EmotionEngine iniciado — estado: {self._state}")

    # ── Estado atual ──────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    def get_profile(self) -> Dict:
        return {
            "estado":  self._state,
            **STATES.get(self._state, STATES["calma"]),
            "exec_count":    self._exec_count,
            "fail_streak":   self._fail_streak,
            "success_streak": self._success_streak,
        }

    # ── Transições de estado ──────────────────────────────────────────────────

    def _transition(self, new_state: str, reason: str = "") -> None:
        if new_state == self._state:
            return
        if new_state not in STATES:
            return
        self._prev  = self._state
        self._state = new_state
        self._since = time.time()
        logger.debug(f"Emoção: {self._prev} → {new_state}" + (f" ({reason})" if reason else ""))
        bus.publish("emotion.changed", estado=new_state, anterior=self._prev)

    def on_task_start(self, task_count: int = 1) -> None:
        """Chamado quando uma tarefa começa."""
        self._exec_count += task_count
        # Muitas execuções seguidas → cansada
        if self._exec_count > 15:
            self._transition("cansada", "muitas execuções")
        elif self._state not in ("cansada", "frustrada"):
            self._transition("concentrada", "executando")

    def on_task_success(self, tempo_s: float = 0.0, was_fast: bool = False) -> None:
        """Chamado após execução bem-sucedida."""
        self._fail_streak    = 0
        self._success_streak += 1

        if was_fast and self._success_streak >= 3:
            self._transition("orgulhosa", f"3+ sucessos rápidos ({tempo_s:.1f}s)")
        elif self._success_streak >= 5:
            self._transition("animada", "5+ sucessos seguidos")
        elif self._state in ("frustrada", "cansada"):
            self._transition("calma", "recuperou após sucesso")
        elif self._state == "concentrada":
            self._transition("calma", "tarefa concluída")

    def on_task_failure(self, error: str = "") -> None:
        """Chamado após falha de execução."""
        self._success_streak = 0
        self._fail_streak   += 1

        if self._fail_streak >= 3:
            self._transition("frustrada", f"{self._fail_streak} falhas seguidas")
        elif self._state == "animada":
            self._transition("calma", "falha suavizou animação")

    def on_positive_feedback(self, affinity: float = 50.0) -> None:
        """Chamado quando o usuário elogia ou dá cafuné."""
        self._fail_streak    = 0
        self._success_streak += 1
        if affinity >= 70:
            self._transition("brincalhona", f"afinidade alta ({affinity:.0f})")
        else:
            self._transition("animada", "feedback positivo")

    def on_unknown_request(self) -> None:
        """Chamado quando recebe pedido novo/incomum."""
        if self._state not in ("frustrada", "cansada"):
            self._transition("curiosa", "pedido desconhecido")

    def on_conversation(self, is_casual: bool = True) -> None:
        """Chamado em conversa sem execução de tarefa."""
        if is_casual and self._state == "concentrada":
            self._transition("calma", "conversa casual")

    # ── Influência no texto ───────────────────────────────────────────────────

    def color_response(self, text: str, force: bool = False) -> str:
        """
        Aplica o estado emocional ao texto de resposta.
        NUNCA modifica respostas JSON (seriam corrompidos).
        Só modifica texto livre de conversa.
        """
        if not text or text.strip().startswith("{") or text.strip().startswith("["):
            return text  # Nunca toca em JSON

        profile = self.get_profile()
        verbosidade = profile["verbosidade"]
        humor       = profile["humor"]

        # Estado concentrada: resposta mais direta
        if self._state == "concentrada" and len(text) > 60 and not force:
            sentences = text.split(". ")
            text = sentences[0] + ("." if not sentences[0].endswith(".") else "")

        # Estado cansada: sem floreios
        if self._state == "cansada":
            text = text.replace(" 😊", "").replace(" 🚀", "").replace("!", ".")

        return text

    def get_spontaneous_comment(self) -> Optional[str]:
        """
        Retorna comentário espontâneo baseado no estado, ou None.
        Limitado por cooldown para não ser spam.
        """
        now = time.time()
        if now - self._last_comment_ts < self._comment_cooldown:
            return None

        # Só comenta em 25% das chances para ser natural
        if random.random() > 0.25:
            return None

        comments = STATE_COMMENTS.get(self._state, [])
        if not comments:
            return None

        self._last_comment_ts = now
        return random.choice(comments)

    def get_avatar_state(self) -> str:
        """Mapeia estado emocional para estado do avatar da UI."""
        mapping = {
            "calma":       "idle",
            "animada":     "speaking",
            "curiosa":     "thinking",
            "concentrada": "working",
            "orgulhosa":   "speaking",
            "pensativa":   "thinking",
            "brincalhona": "speaking",
            "frustrada":   "error",
            "cansada":     "idle",
        }
        return mapping.get(self._state, "idle")

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_flow_done(self, resultado) -> None:
        try:
            sucesso = resultado.sucesso if hasattr(resultado, 'sucesso') else True
            tempo   = resultado.duracao_total if hasattr(resultado, 'duracao_total') else 0.0
            was_fast = tempo < 3.0 and sucesso
            if sucesso:
                self.on_task_success(tempo, was_fast)
            else:
                self.on_task_failure()
        except Exception:
            pass

    def _on_flow_aborted(self, **kw) -> None:
        self.on_task_failure()

    def _on_response(self, text: str = "") -> None:
        pass  # hook futuro para análise de resposta


# Instância global
emotion_engine = EmotionEngine()
