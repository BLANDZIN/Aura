"""
ai/ai_engine.py — AURA v5
===========================
Motor de IA integrado ao DecisionEngine.

Hierarquia de execução (mais rápido → mais lento):
  1. Casual puro        — saudações sem comando (< 1ms)
  2. Ajuste de tempo    — "spotify demora X segundos" (< 2ms)
  3. Decision Engine    — ação direta, fluxo, procedimento (< 10ms)
  4. Modelo de IA       — quando realmente necessário

Após cada execução:
  - ReflectionEngine atualiza métricas silenciosamente
  - InitiativeEngine pode gerar sugestão proativa
  - ContextCache registra o estado atual

Desenvolvido por Bland | Claude
"""

import json, re, threading, unicodedata, time
from typing import Optional, Dict, Any, List

# NOTA DE ARQUITETURA (V11):
# Os imports de automation/ (planner, flow_executor, decision_engine, flow_library)
# sao feitos DENTRO dos metodos (lazy imports) para evitar ciclos de dependencia
# com o grafo: ai -> automation -> tools -> ai.
# Este e o padrao correto para dependencias cruzadas em Python — manter assim.
from ai.ai_provider import get_provider
from config.personality import personality
from memory.memory_manager import memory
from core.event_bus import bus
from core.logger import setup_logger

def _user_gender() -> str:
    """Retorna 'm' ou 'f' baseado na memoria do usuario."""
    try:
        from database.db_manager import db
        row = db.fetchone(
            "SELECT valor FROM memory_permanent WHERE chave='genero_usuario'")
        if row and row["valor"] in ("masculino", "feminino"):
            return "m" if row["valor"] == "masculino" else "f"
    except Exception:
        pass
    return "m"

logger = setup_logger("ai_engine")


# ── Normalização ──────────────────────────────────────────────────────────────

from core.text_utils import normalize as _normalize


# ── Respostas casuais puras ───────────────────────────────────────────────────

_GREETINGS = {
    "oi","ola","e ai","eae","oi aura","ola aura",
    "bom dia","boa tarde","boa noite",
    "bom dia aura","boa tarde aura","boa noite aura",
}
_THANKS    = {"obrigado","obrigada","valeu","brigado","brigada",
              "muito obrigado","muito obrigada","obg","vlw"}
_WELLBEING = {"tudo bem","como vai","como voce esta","como esta","tudo bom","td bem"}
# Sem isso, "te amo aura" cai direto pro modelo sem nenhum exemplo de
# como reagir — e um modelo pequeno local pode "quebrar personagem" e
# negar ter nome/sentimentos exatamente nesse tipo de caso fora do que
# foi exemplificado no prompt. Mesmo padrão de _GREETINGS/_THANKS: uma
# resposta garantida em vez de depender só do modelo acertar.
_AFFECTION = (
    "te amo", "amo voce", "amo você", "adoro voce", "adoro você",
    "gosto de voce", "gosto muito de voce", "gosto de você",
    "meu amor", "minha vida", "meu bem",
    "voce e tudo", "você é tudo", "voce e incrivel", "você é incrível",
    "coração", "coracao",
)
# V12.1 — Prioridade 1: categorias de risco de identidade. Usadas só pra
# ENRIQUECER o contexto enviado ao modelo (ai/prompt_builder.py), nunca
# pra gerar resposta pronta — ver _detect_emotional_category() abaixo e
# a decisão registrada em V12.1_DIRETRIZES (Quick Casual é Context
# Builder, não Response Builder).
_ELOGIO = (
    "voce e demais", "você é demais", "voce e otima", "você é ótima",
    "voce e a melhor", "você é a melhor", "adorei voce", "adorei você",
    "voce e engracada", "você é engraçada", "voce e fofa", "você é fofa",
    "melhor assistente", "voce e perfeita", "você é perfeita",
    "sua personalidade e", "sua personalidade é", "adoro sua personalidade",
)
_IDENTIDADE_RISCO = (
    "voce tem sentimentos", "você tem sentimentos", "voce sente",
    "você sente", "voce e real", "você é real", "voce e consciente",
    "você é consciente", "voce e so um programa", "você é só um programa",
    "voce e so uma ia", "você é só uma ia", "voce existe de verdade",
    "você existe de verdade", "voce tem alma", "você tem alma",
    "voce tem personalidade", "você tem personalidade",
)
_VINCULO = (
    "minha namorada", "meu namorado", "somos amigas", "somos amigos",
    "voce e minha amiga", "você é minha amiga", "voce e meu amigo",
    "você é meu amigo", "voce e minha melhor amiga", "eu confio em voce",
    "eu confio em você", "voce e importante pra mim", "você é importante pra mim",
)
_EMOTIONAL_CATEGORIES = (
    ("afeto", _AFFECTION),
    ("elogio", _ELOGIO),
    ("identidade", _IDENTIDADE_RISCO),
    ("vinculo", _VINCULO),
)


def _detect_emotional_category(text: str) -> Optional[str]:
    """
    Detecta se a mensagem toca em afeto/elogio/identidade/vínculo — usado
    SÓ para decidir se o system prompt deste turno ganha um reforço de
    personalidade (ai/prompt_builder.py::build_system_message). Nunca
    decide a resposta em si; quem responde continua sendo sempre o modelo.
    """
    for categoria, termos in _EMOTIONAL_CATEGORIES:
        if any(t in text for t in termos):
            return categoria
    return None

_COMMAND_WORDS = {
    "abra","abrir","abre","busque","pesquise","pesquisa","procure",
    "crie","criar","delete","exclua","mova","copie","feche",
    "digit","clique","capture","salve","memorize","lembre","liste",
    "mostra","verifica","execute","executa","inicia","inicie",
    "tire","tira","faz","faca","coloca","coloque","acha","ache",
    "encontra","encontre","acessa","acesse","baixa","baixe",
    "ajusta","ajuste","muda","mude","aumenta","diminui","configura",
}

# Perguntas de identidade — respondidas instantaneamente via IdentityEngine,
# sem pagar o custo (tokens de prompt + tempo de inferência) de uma chamada
# ao modelo para algo que tem resposta fixa e conhecida. Substring matching
# (não set exato como _GREETINGS) porque perguntas de identidade variam
# bem mais em fraseado: "quem te criou", "quem fez você", "quem te programou".
_IDENTITY_TRIGGERS = (
    "quem te criou", "quem criou voce", "quem te fez", "quem fez voce",
    "quem te desenvolveu", "quem desenvolveu voce", "quem te programou",
    "quem e voce", "quem é você",
)
_IDENTITY_DENIAL_TRIGGERS = (
    "voce e o chatgpt", "voce e chatgpt", "você é o chatgpt",
    "voce e gpt", "voce e gemini", "voce e uma ia generica",
    "voce e a siri", "voce e a alexa",
)


def _try_identity_question(user_input: str) -> Optional[str]:
    """Intercepta perguntas de identidade antes do modelo."""
    text = _normalize(user_input)
    if any(t in text for t in _IDENTITY_DENIAL_TRIGGERS):
        return "Não, sou a AURA. Fui desenvolvida especialmente para o Bland, pelo Bland e pelo Claude."
    if any(t in text for t in _IDENTITY_TRIGGERS):
        try:
            from ai.identity_engine import identity_engine
            return identity_engine.describe_self()
        except Exception:
            return "Sou a AURA, desenvolvida pelo Bland em parceria com o Claude."
    return None


def _quick_casual(user_input: str) -> Optional[str]:
    """
    Respostas fixas SÓ para cortesia pura (saudação/agradecimento/bem-estar)
    — sem risco de quebra de personagem, então tudo bem serem fixas.

    Afeto/elogio/identidade/vínculo NÃO são tratados aqui desde a V12.1
    (decisão arquitetural): essas categorias vão sempre para o modelo,
    só que com o contexto reforçado por _detect_emotional_category() +
    ai/prompt_builder.py — ver process()._run(). O objetivo é preservar
    personalidade dinâmica de verdade, não substituí-la por frase pronta.
    """
    text  = _normalize(user_input)
    words = set(text.split())
    if words.intersection(_COMMAND_WORDS): return None
    if len(words) > 5: return None

    humor   = personality.get("humor",   75)
    energia = personality.get("energia", 80)

    if text in _GREETINGS:
        import random
        pool = (["Oi! O que vamos fazer?", "Ei! Tô aqui. Manda ver.", "Oi! Pronta."]
                if (humor > 60 and energia > 60)
                else ["Olá! Em que posso ajudar?", "Oi."])
        return random.choice(pool)

    if text in _THANKS:
        import random
        return random.choice(["Sempre! 😊","Disponha!","Qualquer coisa é só falar."]) if humor > 60 else "Disponha."

    if text in _WELLBEING:
        return "Tudo certo aqui! E você?" if energia > 60 else "Bem, obrigada."

    return None


# ── Ajuste de tempo de espera ─────────────────────────────────────────────────

def _detect_wait_adjustment(text: str) -> Optional[Dict]:
    t = text.lower()
    patterns = [
        r"(?:espera|aguarda|wait|tempo|delay)\s+(\d+)\s*(?:segundo|sec|s\b)",
        r"(\d+)\s*(?:segundo|sec)\s*(?:de espera|para|pra)",
        r"aumenta.*?(\d+)\s*segundo",
        r"demora.*?(\d+)\s*segundo",
        r"coloca\s+(\d+)\s*segundo",
    ]
    segundos = None
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            segundos = int(m.group(1))
            break
    if not segundos:
        return None

    programas = {
        "spotify":"spotify","discord":"discord","steam":"steam",
        "chrome":"chrome","firefox":"firefox","edge":"edge",
        "youtube":"youtube","whatsapp":"whatsapp","telegram":"telegram",
        "outlook":"outlook","teams":"teams","obs":"obs","vscode":"vscode",
    }
    programa = next((v for k,v in programas.items() if k in t), None)
    if not programa:
        return None
    return {"programa": programa, "segundos": segundos}


def _apply_wait_adjustment(programa: str, segundos: int) -> str:
    try:
        # Atualiza FlowLibrary
        from automation.flow_library import flow_library
        flows = flow_library.get_all()
        updated = []
        for flow in flows:
            nome   = flow.get("nome","")
            passos = flow.get("passos",[])
            if not any(programa in str(p.get("parametros",{})).lower() for p in passos):
                continue
            novos = []
            changed = False
            for p in passos:
                if isinstance(p, dict) and p.get("acao") == "esperar":
                    p = dict(p); p["parametros"] = {"segundos": segundos}
                    changed = True
                novos.append(p)
            if changed:
                flow_library.save(nome=nome, passos=novos,
                                  descricao=flow.get("descricao",""),
                                  importancia=flow.get("importancia",7))
                updated.append(nome)

        # Atualiza procedimentos legados também
        procs = memory.procedural.get_all()
        for proc in procs:
            nome   = proc.get("nome","")
            passos = proc.get("passos",[])
            if not any(programa in str(p).lower() for p in passos):
                continue
            novos = []
            changed = False
            for p in passos:
                if isinstance(p, dict) and p.get("acao") == "esperar":
                    p = dict(p); p["parametros"] = {"segundos": segundos}
                    changed = True
                novos.append(p)
            if changed:
                memory.procedural.save(nome=nome,
                                       descricao=proc.get("descricao",nome),
                                       passos=novos,
                                       importance=proc.get("importance",7))
                if nome not in updated:
                    updated.append(nome)

        if updated:
            return f"Ajustado! {programa.title()} vai esperar {segundos}s agora. Fluxos atualizados: {', '.join(updated)}"

        # Sem fluxo — salva preferência
        memory.permanent.save(categoria="preferencias",
                              chave=f"espera_{programa}",
                              valor=str(segundos), importance=7)
        return f"Anotado! Vou esperar {segundos}s ao usar {programa.title()}."

    except Exception as e:
        logger.error(f"Ajuste espera erro: {e}")
        return f"Anotado: {programa} = {segundos}s."


# ── Parser JSON robusto ───────────────────────────────────────────────────────

def _extract_json_objects(text: str) -> List[Dict]:
    results = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in ('{', '['):
            opener = ch; closer = '}' if opener == '{' else ']'
            depth = 0; j = i; in_str = False; escape = False
            while j < n:
                c = text[j]
                if escape:              escape = False
                elif c == '\\' and in_str: escape = True
                elif c == '"':          in_str = not in_str
                elif not in_str:
                    if c == opener:     depth += 1
                    elif c == closer:
                        depth -= 1
                        if depth == 0:
                            try:
                                parsed = json.loads(text[i:j+1])
                                if isinstance(parsed, dict) and "acao" in parsed:
                                    results.append(parsed)
                                elif isinstance(parsed, list):
                                    results.extend(d for d in parsed
                                                   if isinstance(d, dict) and "acao" in d)
                            except Exception:
                                pass
                            i = j; break
                j += 1
        i += 1
    return results


def _parse_multi_json(text: str) -> Optional[List[Dict]]:
    objects = _extract_json_objects(text.strip())
    if not objects:
        return None
    seen, unique = set(), []
    for obj in objects:
        key = obj.get("acao","") + str(sorted(obj.get("parametros",{}).items()))
        if key not in seen:
            seen.add(key); unique.append(obj)
    return unique if unique else None


# ── AIEngine ──────────────────────────────────────────────────────────────────


def _detect_text_action(response: str) -> bool:
    """Detecta se o modelo descreveu uma acao em texto ao inves de JSON."""
    action_indicators = [
        "vou abrir", "vou pesquisar", "vou tocar", "vou criar",
        "vou iniciar", "vou fechar", "vou salvar", "vou procurar",
        "abra o", "abrir o", "pesquisar", "tocar a", "criar uma",
        "posso abrir", "posso pesquisar", "posso tocar",
        "deixa eu abrir", "deixa eu pesquisar",
        "claro", "claro que sim", "com certeza",
    ]
    lower = response.lower().strip()
    # Only match if response has NO JSON and describes an action
    has_json = "{" in response and '"acao"' in response
    if has_json:
        return False
    return any(ind in lower for ind in action_indicators)



class AIEngine:
    def __init__(self):
        self.provider     = get_provider()
        self._processing  = False
        # V12.1 — protege o check-and-set de _processing. Antes, a flag só
        # era setada DENTRO de _run() (já rodando em thread própria), então
        # havia uma janela real entre threading.Thread(...).start() retornar
        # e a thread de fato começar a executar onde uma segunda chamada a
        # process() (voz + texto quase simultâneos, duplo-envio no chat)
        # também passava pelo "if self._processing: return" e disparava
        # OUTRA thread concorrente — as duas competindo pelas mesmas
        # variáveis de instância (_last_executed_steps, _current_user_input)
        # e pelo memory.short_term compartilhado. Causa estrutural plausível
        # para o "perda de objetivo" relatado (V12.1, doc de comportamentos).
        self._processing_lock = threading.Lock()
        self._signals     = None
        self._ctx         = None
        self._current_user_input      = ""
        self._checking_correction_for = None
        self._last_executed_steps: List[Dict] = []
        self._last_executed_input = ""

        # ── Motores cognitivos V6 ─────────────────────────────────────────────
        try:
            from ai.emotion_engine   import emotion_engine
            from ai.identity_engine  import identity_engine
            from automation.learning_engine import learning_engine
            self._emotion   = emotion_engine
            self._identity  = identity_engine
            self._learning  = learning_engine
            logger.info("Motores V6 ativos: EmotionEngine, IdentityEngine, LearningEngine")
        except Exception as e:
            self._emotion = self._identity = self._learning = None
            logger.warning(f"Motores V6 parcialmente indisponíveis: {e}")

        self._try_init_signals()
        self._start_context()

        # Executor de fluxos (V11 — extraido para modulo proprio)
        from ai.executor import FlowExecutor
        self._executor = FlowExecutor(self)

    def _try_init_signals(self):
        try:
            from PyQt6.QtCore import QObject, pyqtSignal
            class _Sig(QObject):
                thinking    = pyqtSignal(bool)
                response    = pyqtSignal(str)
                intent      = pyqtSignal(dict)
                error       = pyqtSignal(str)
                stream_tok  = pyqtSignal(str)
                stream_done = pyqtSignal(str)
            self._signals = _Sig()
            self._signals.thinking.connect(   lambda s: bus.publish("ai.thinking",     status=s))
            self._signals.response.connect(   lambda t: bus.publish("ai.response",     text=t))
            self._signals.intent.connect(     lambda i: bus.publish("ai.intent",       intent=i, user_input=""))
            self._signals.error.connect(      lambda e: bus.publish("ai.error",        error=e))
            self._signals.stream_tok.connect( lambda t: bus.publish("ai.stream.token", token=t))
            self._signals.stream_done.connect(lambda t: bus.publish("ai.stream.done",  full_text=t))
            logger.info("AIEngine: sinais Qt ativos")
        except Exception:
            logger.info("AIEngine: modo direto")

    def _start_context(self):
        try:
            from vision.context_manager import context_manager
            context_manager.start()
            self._ctx = context_manager
        except Exception as e:
            logger.warning(f"ContextManager: {e}")

    def _emit(self, name: str, value) -> None:
        if self._signals:
            getattr(self._signals, name).emit(value)
        else:
            ev = {
                "thinking":   ("ai.thinking",     {"status":    value}),
                "response":   ("ai.response",     {"text":      value}),
                "intent":     ("ai.intent",       {"intent":    value, "user_input": self._current_user_input}),
                "error":      ("ai.error",        {"error":     value}),
                "stream_tok": ("ai.stream.token", {"token":     value}),
                "stream_done":("ai.stream.done",  {"full_text": value}),
            }
            event, kwargs = ev[name]
            bus.publish(event, **kwargs)

    def reload_provider(self): self.provider = get_provider()

    def _build_system_message(self, emotional_context: Optional[str] = None) -> Dict:
        """Delega para prompt_builder (V11)."""
        from tools.tool_manager import tool_manager
        from ai.prompt_builder import build_system_message
        return build_system_message(
            personality=personality,
            memory=memory,
            tool_manager=tool_manager,
            context_manager=self._ctx,
            emotional_context=emotional_context,
        )
    def _parse_intent(self, response: str) -> Dict[str, Any]:
        objects = _parse_multi_json(response)
        if objects:
            if len(objects) > 1:
                return {"tipo": "fluxo", "dados": objects}
            obj = objects[0]
            if "fluxo" in obj:
                return {"tipo": "fluxo", "dados": obj["fluxo"]}
            return {"tipo": "acao", "dados": obj}
        return {"tipo": "texto", "dados": {"mensagem": response}}

    def _dispatch_intent(self, intent: Dict) -> None:
        """Delega para FlowExecutor (V11)."""
        self._executor.dispatch_intent(intent)

    def _dispatch_flow(self, steps: List[Dict], descricao: str = "") -> None:
        """Delega para FlowExecutor (V11)."""
        self._executor.dispatch_flow(steps, descricao)

    def _flow_signature(self, steps: List[Dict]) -> str:
        """Delega para FlowExecutor (V11)."""
        return FlowExecutor.flow_signature(steps)

    _SAVE_TRIGGERS = (
        "salva isso", "salvar isso", "lembra disso",
        "lembrar disso", "cria um atalho", "criar atalho",
        "salva esse fluxo", "memoriza isso", "salve isso",
        "salva como", "salve como", "cria um gatilho", "criar gatilho",
        "salve como gatilho", "salva como gatilho",
    )

    # Palavras genéricas que não devem virar nome de fluxo mesmo que
    # apareçam logo após "como" em frases naturais tipo "salva isso
    # como gatilho" — usar "gatilho" como nome quebra a busca fuzzy
    # futura, já que não tem relação semântica com a ação salva.
    _GENERIC_NAME_WORDS = {
        "gatilho", "atalho", "isso", "fluxo", "acao", "ação",
        "comando", "shortcut", "trigger",
    }

    def _extract_flow_name(self, save_request_text: str, fallback_text: str) -> str:
        """
        Extrai um nome de fluxo significativo. Tenta capturar algo
        explícito após "como" na frase de salvamento, mas rejeita
        palavras genéricas demais (que não ajudam a busca fuzzy
        depois) e cai para uma assinatura derivada da ação original.
        """
        m = re.search(r"como\s+([\w_-]+)", save_request_text.lower())
        if m:
            candidato = m.group(1)
            if candidato not in self._GENERIC_NAME_WORDS:
                return candidato
        # Fallback: deriva do texto que gerou a ação original (mais
        # específico que a frase de salvamento, que costuma ser genérica
        # tipo "salva isso", "cria um atalho pra isso").
        base = _normalize(fallback_text)
        # Remove palavras de comando comuns para deixar só o essencial
        for w in ("abre","abrir","cria","criar","pesquisa","pesquisar","por","favor","pra","mim"):
            base = re.sub(rf"\b{w}\b", "", base)
        base = re.sub(r"\s+", "_", base.strip())
        return base[:40] or "atalho_novo"

    def _is_save_request(self, user_input: str) -> bool:
        """Detecta se a mensagem é um pedido para salvar a última ação/fluxo."""
        text = _normalize(user_input)
        return any(t in text for t in self._SAVE_TRIGGERS)

    def _save_last_as_flow(self, user_input: str) -> str:
        """Delega para FlowExecutor (V11)."""
        return self._executor.save_last_as_flow(
            self._last_executed_steps,
            self._last_executed_input or user_input,
            user_input
        )

    def _maybe_save_explicit_flow(self, user_input: str, steps: List[Dict]) -> None:
        """
        Salva um fluxo nomeado na FlowLibrary SOMENTE quando o usuário
        pede explicitamente para lembrar/salvar NA MESMA mensagem que
        já contém o fluxo (ex: "abre chrome e youtube, e salva isso
        como abrir_tudo"). Para o caso mais comum — pedir pra salvar
        DEPOIS, em mensagem separada — ver _save_last_as_flow, chamado
        no início do process().
        """
        if not self._is_save_request(user_input):
            return
        if not steps:
            return
        try:
            from automation.flow_library import flow_library
            nome = self._extract_flow_name(user_input, user_input)
            flow_library.save(
                nome=nome, passos=steps,
                descricao=user_input[:100], importancia=7
            )
            logger.info(f"Fluxo salvo explicitamente pelo usuário: '{nome}'")
            self._emit("response", f"Salvei como '{nome}'. Posso reusar quando você pedir.")
        except Exception as e:
            logger.debug(f"Erro ao salvar fluxo explícito: {e}")

    def process(self, user_input: str) -> None:
        with self._processing_lock:
            if self._processing:
                logger.warning("IA já processando."); return
            self._processing = True

        def _run():
            self._current_user_input = user_input  # exposto para error_learner via tool_manager
            self._emit("thinking", True)
            t_start = time.time()

            try:
                memory.short_term.add("user", user_input)

                # ── Nível -1: O usuário está corrigindo uma falha anterior? ────
                # Se a mensagem anterior da AURA foi um erro, e este pedido
                # representa a forma certa de fazer a mesma coisa, salva
                # o par erro→correção permanentemente. Não impede o
                # processamento normal — só aprende em paralelo.
                try:
                    from automation.error_learning import error_learner
                    pending = error_learner.get_pending_failure()
                    if pending:
                        # A correção real (acao/parametros) só é conhecida
                        # depois que esta mensagem for decidida/executada.
                        # Guardamos a intenção de checar ao final do processamento.
                        self._checking_correction_for = pending
                    else:
                        self._checking_correction_for = None
                except Exception:
                    self._checking_correction_for = None

                # ── Nível 0: Casual puro ──────────────────────────────────────
                casual = _quick_casual(user_input)
                if casual:
                    # Aplica identidade na resposta casual
                    if self._identity:
                        casual = self._identity.filter_response(casual)
                    if self._emotion:
                        self._emotion.on_conversation(is_casual=True)
                    memory.short_term.add("assistant", casual)
                    self._emit("response", casual)
                    return

                # ── Nível 0.2: Pergunta de identidade ─────────────────────────
                # "quem te criou", "você é o chatgpt" etc — respondido
                # instantaneamente, sem chamar o modelo. Antes disto, o
                # exemplo ficava só no system prompt (custo em toda chamada,
                # mesmo quando a pergunta não era feita) e ainda assim
                # dependia do modelo reproduzir fielmente. Agora é 100%
                # determinístico e não paga custo de tokens em outras mensagens.
                identity_answer = _try_identity_question(user_input)
                if identity_answer:
                    memory.short_term.add("assistant", identity_answer)
                    self._emit("response", identity_answer)
                    return

                # ── Nível 0.5: Reforço positivo ───────────────────────────────
                # Detecta elogios/agradecimentos ANTES de qualquer decisão.
                # Aumenta afinidade e muda estado emocional imediatamente.
                if self._learning and self._learning.detect_positive_signal(user_input):
                    last_flow = self._last_executed_input
                    if self._learning:
                        self._learning.register_positive(user_input, flow_name="")
                    if self._emotion:
                        aff = self._learning.get_affinity() if self._learning else 50.0
                        self._emotion.on_positive_feedback(affinity=aff)
                    # Não retorna — deixa a IA responder normalmente também

                # ── Nível 1: Ajuste de tempo ──────────────────────────────────
                adj = _detect_wait_adjustment(user_input)
                if adj:
                    resp = _apply_wait_adjustment(adj["programa"], adj["segundos"])
                    memory.short_term.add("assistant", resp)
                    self._emit("response", resp)
                    return

                # ── Nível 1.5: Pedido de salvar o que acabou de ser feito ──────
                # Verificado AQUI, no início, e não só dentro do branch de
                # fluxo multi-ação — porque "salve isso como gatilho" quase
                # sempre vem como mensagem SEPARADA depois de uma ação já
                # executada (inclusive ação única, tipo "abre o youtube").
                # Antes esse pedido virava uma chamada nova e desconexa ao
                # modelo e se perdia, já que não existia vínculo com o que
                # tinha sido feito antes.
                if self._is_save_request(user_input) and self._last_executed_steps:
                    resp = self._save_last_as_flow(user_input)
                    memory.short_term.add("assistant", resp)
                    self._emit("response", resp)
                    return

                # ── Nível 2: Decision Engine ──────────────────────────────────
                ctx = self._ctx.get() if self._ctx else {}
                from automation.decision_engine import (
                    decision_engine, reflection_engine, initiative_engine,
                    context_cache
                )
                decision = decision_engine.decide(user_input, ctx)
                action, ask_msg = decision_engine.evaluate_confidence(
                    decision.method, decision.confidence
                )

                if action == "ask_user":
                    self._emit("response", ask_msg)
                    memory.short_term.add("assistant", ask_msg)
                    return

                flow_name = None
                passos    = []

                # ── Ação direta (padrão regex, <10ms) ────────────────────────
                if decision.method == "direct":
                    intent   = decision.payload
                    acao_d   = intent.get("acao", "")
                    params_d = intent.get("parametros", {})
                    mensagem = intent.get("mensagem", "Executando...")

                    # Se havia uma falha pendente, verifica se este pedido
                    # é a correção dela (mesmo texto do usuário, ação diferente)
                    if getattr(self, "_checking_correction_for", None):
                        try:
                            from automation.error_learning import error_learner
                            error_learner.check_correction(
                                user_input=user_input,
                                acao_corrigida=acao_d,
                                parametros_corrigidos=params_d,
                            )
                        except Exception:
                            pass

                    self._emit("response", mensagem)
                    context_cache.register_action(acao_d, params_d)
                    self._last_executed_steps = [intent]
                    self._last_executed_input = user_input
                    self._emit("intent", intent)
                    return

                # ── Fluxo da FlowLibrary ──────────────────────────────────────
                elif decision.method == "flow":
                    flow      = decision.payload
                    flow_name = flow.get("nome","flow")
                    passos    = flow.get("passos", [])
                    context_cache.register_flow(flow_name)
                    self._emit("response", f"⚡ {flow_name}...")
                    self._last_executed_steps = passos
                    self._last_executed_input = user_input
                    self._dispatch_flow(passos, flow_name)
                    return

                # ── Procedimento legado ───────────────────────────────────────
                elif decision.method == "proc":
                    proc      = decision.payload
                    flow_name = proc.get("nome","proc")
                    passos    = proc.get("passos", [])
                    context_cache.register_flow(flow_name)
                    self._emit("response", f"⚡ {flow_name}...")
                    self._last_executed_steps = passos
                    self._last_executed_input = user_input
                    from automation.planner import planner
                    from automation.flow_executor import flow_executor
                    plan = planner._plan_from_procedure(proc)
                    flow_executor.execute(plan)
                    return

                # ── Intent via planner ────────────────────────────────────────
                elif decision.method == "planner" and decision.payload:
                    payload = decision.payload
                    if isinstance(payload, list):
                        self._last_executed_steps = payload
                        self._last_executed_input = user_input
                        self._dispatch_flow(payload)
                    else:
                        mensagem = payload.get("mensagem","Executando...")
                        self._emit("response", mensagem)
                        self._last_executed_steps = [payload]
                        self._last_executed_input = user_input
                        self._dispatch_intent(payload)
                    return

                # ── Modelo de IA (apenas quando necessário) ───────────────────
                emotional_category = _detect_emotional_category(_normalize(user_input))
                if emotional_category:
                    logger.info(f"Contexto emocional detectado: {emotional_category}")
                messages = [self._build_system_message(emotional_context=emotional_category)]
                messages.extend(memory.short_term.get_messages())
                logger.info(f"→ IA (necessário): '{user_input[:80]}'")

                response = self.provider.chat(messages)
                memory.short_term.add("assistant", response)
                logger.debug(f"JA: '{response[:300]}'")

                # Se o modelo descreveu uma acao em texto ao inves de JSON,
                # reenvia — mas SEM presumir que a acao era realmente
                # pretendida. V10/V11 forcavam JSON incondicionalmente aqui,
                # o que convertia qualquer flourish conversacional ("vou
                # colocar uma musica legal pra voce!" dito so por entusiasmo)
                # em uma execucao de verdade. O retry agora pergunta em vez
                # de mandar: se a intencao era mesmo agir, JSON; se era so
                # conversa, texto normal. Achado do doc de comportamentos
                # V12.1 ("perda de objetivo" / acao nao pedida).
                if _detect_text_action(response):
                    logger.info("Modelo descreveu acao em texto — confirmando intencao real")
                    retry_msg = {
                        "role": "system",
                        "content": (
                            "Sua resposta anterior descreveu uma acao em texto "
                            "livre, sem JSON. Antes de responder de novo, "
                            "pergunte-se: eu REALMENTE pretendia executar essa "
                            "acao agora, ou so estava sendo expressiva/conversando? "
                            "Se a intencao era mesmo agir: responda EXCLUSIVAMENTE "
                            "com JSON, nada de texto antes ou depois. "
                            "Ex: {'acao': 'abrir_programa', 'parametros': {'programa': 'spotify.exe'}}. "
                            "Se nao era uma acao de verdade (so entusiasmo, "
                            "figura de linguagem, ou o usuario nao pediu nada "
                            "disso): responda normalmente em texto, sem "
                            "descrever acoes que voce nao vai tomar."
                        )
                    }
                    retry_msgs = list(messages)
                    retry_msgs.append({"role": "assistant", "content": response})
                    retry_msgs.append(retry_msg)
                    response = self.provider.chat(retry_msgs)
                    memory.short_term.add("assistant", response)
                    logger.debug(f"JA (retry): '{response[:300]}'")

                parsed = self._parse_intent(response)

                if parsed["tipo"] == "fluxo":
                    steps     = parsed["dados"]
                    flow_name = self._flow_signature(steps)
                    passos    = steps
                    self._last_executed_steps = steps
                    self._last_executed_input = user_input
                    self._dispatch_flow(steps, "Fluxo IA")
                    # Não auto-salva mais como atalho nomeado a partir de
                    # texto livre do usuário (gerava nomes-lixo tipo
                    # "vamos_tenta_cire_uma_nova_aba" que poluíam a
                    # FlowLibrary e eram reaplicados por engano em frases
                    # parecidas no futuro). O flow_name agora é uma
                    # assinatura estável baseada nas ações reais
                    # (ex: "abrir_programa+pressionar_tecla"), usada
                    # só para a Reflexão registrar taxa de sucesso —
                    # não para virar gatilho de busca fuzzy.
                    self._maybe_save_explicit_flow(user_input, steps)

                elif parsed["tipo"] == "acao":
                    intent    = parsed["dados"]
                    acao_d    = intent.get("acao", "")
                    params_d  = intent.get("parametros", {})
                    flow_name = acao_d or "acao"
                    passos    = [intent]
                    mensagem  = intent.get("mensagem","Executando...")

                    # Mesma checagem de correção do caminho "direct"
                    if getattr(self, "_checking_correction_for", None):
                        try:
                            from automation.error_learning import error_learner
                            error_learner.check_correction(
                                user_input=user_input,
                                acao_corrigida=acao_d,
                                parametros_corrigidos=params_d,
                            )
                        except Exception:
                            pass

                    self._emit("response", mensagem)
                    context_cache.register_action(acao_d, params_d)
                    self._last_executed_steps = [intent]
                    self._last_executed_input = user_input
                    self._dispatch_intent(intent)
                else:
                    raw_msg = parsed["dados"]["mensagem"]
                    # Reseta o estado emocional para "conversa casual" ANTES
                    # de filtrar a resposta. Sem isso, se o último estado
                    # ainda fosse "concentrada" (herdado de uma tarefa
                    # anterior), color_response() cortava a resposta para
                    # só a primeira frase — uma brincadeira/provocação do
                    # usuário podia ter a graça na segunda frase, cortada
                    # silenciosamente, deixando a AURA parecer seca e
                    # robótica exatamente quando deveria ser mais espontânea.
                    if self._emotion:
                        self._emotion.on_conversation(is_casual=True)
                    # Aplica filtro de identidade em respostas textuais
                    if self._identity:
                        raw_msg = self._identity.filter_response(raw_msg)
                    self._emit("response", raw_msg)

                # ── Emoção pós-execução ───────────────────────────────────────
                t_exec = time.time() - t_start
                if self._emotion:
                    if parsed.get("tipo") in ("acao", "fluxo"):
                        was_fast = t_exec < 3.0
                        self._emotion.on_task_success(t_exec, was_fast)
                    # Atualiza avatar conforme estado emocional
                    avatar_st = self._emotion.get_avatar_state()
                    bus.publish("avatar.set_state", state=avatar_st)

                # ── Reflexao pos-execucao ─────────────────────────────────
                if flow_name:
                    self._executor.register_success(
                        flow_name, passos, user_input, t_exec
                    )

                # ── Comentário espontâneo do EmotionEngine ────────────────────
                if self._emotion:
                    comment = self._emotion.get_spontaneous_comment()
                    if comment:
                        self._emit("response", f"💭 {comment}")

                # ── Iniciativa (ocasional) ────────────────────────────────────
                suggestion = initiative_engine.get_suggestion(ctx)
                if suggestion:
                    self._emit("response", f"💡 {suggestion}")

            except Exception as e:
                logger.error(f"Erro AIEngine: {e}", exc_info=True)
                self._emit("error", str(e))
            finally:
                self._processing = False
                self._emit("thinking", False)

        threading.Thread(target=_run, daemon=True).start()

    @property
    def is_processing(self) -> bool: return self._processing


ai_engine = AIEngine()
