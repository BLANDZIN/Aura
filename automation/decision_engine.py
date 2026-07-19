"""
automation/decision_engine.py — AURA v5
========================================
Motor de Decisão Central.

Decide como executar qualquer objetivo em milissegundos,
sem chamar o modelo de IA a menos que seja estritamente necessário.

Hierarquia de decisão (mais rápido → mais lento):
  1. Cache de contexto  — app já aberto? usa o estado atual
  2. Ação direta        — ação simples e conhecida → ferramenta imediata
  3. Fluxo versionado   — FlowLibrary, escolhe melhor versão por métricas
  4. Procedimento       — memory.procedural (legado compatível)
  5. Planner            — monta plano estruturado a partir de intent
  6. Modelo de IA       — reasoning complexo, última opção

Confiança:
  >= 0.85  → executa imediatamente
  0.65-0.84 → tenta com estratégia alternativa como fallback
  < 0.65   → consulta o modelo

Desenvolvido por Bland | Claude
"""

import time
import re
import unicodedata
from typing import Optional, Dict, Any, List, Tuple
from core.logger import setup_logger
from core.event_bus import bus
from core.fuzzy_search import similarity

logger = setup_logger("decision")


# ══════════════════════════════════════════════════════════════
# CACHE DE CONTEXTO (estado do ambiente atual)
# ══════════════════════════════════════════════════════════════

class ContextCache:
    """
    Cache do estado atual do ambiente do usuário.
    Evita abrir programas que já estão abertos.
    Mantém rastro da última interação para decisões inteligentes.
    """

    def __init__(self):
        self._state: Dict[str, Any] = {
            "open_apps":         [],       # apps conhecidos como abertos
            "last_app_opened":   None,     # último app que a AURA abriu
            "last_action":       None,     # última ação executada
            "last_search_query": None,     # última pesquisa feita
            "last_url_opened":   None,     # última URL aberta
            "last_flow_name":    None,     # último fluxo executado
            "session_start":     time.time(),
        }
        # Programas → processos
        self._APP_PROCESS_MAP = {
            "spotify":  ["spotify.exe", "spotify"],
            "discord":  ["discord.exe", "discord"],
            "chrome":   ["chrome.exe", "googlechrome"],
            "firefox":  ["firefox.exe", "firefox"],
            "edge":     ["msedge.exe", "microsoftedge"],
            "steam":    ["steam.exe", "steam"],
            "youtube":  ["chrome.exe", "msedge.exe", "firefox.exe"],  # via browser
            "notepad":  ["notepad.exe"],
            "code":     ["code.exe", "vscode"],
            "vscode":   ["code.exe"],
        }

    def update_from_context_manager(self, ctx: Dict) -> None:
        """Sincroniza com o ContextManager."""
        if not ctx:
            return
        open_progs = [p.lower() for p in ctx.get("open_programs", [])]
        self._state["open_apps"] = open_progs
        win = ctx.get("active_window", "")
        if win:
            self._state["active_window"] = win.lower()

    def is_app_open(self, app_name: str) -> bool:
        """Verifica se um app já está aberto (sem abrir de novo)."""
        app_lower = app_name.lower().replace(".exe", "")
        open_apps = self._state.get("open_apps", [])

        # Verifica diretamente
        if any(app_lower in a for a in open_apps):
            return True

        # Verifica aliases
        aliases = self._APP_PROCESS_MAP.get(app_lower, [])
        return any(
            any(alias.replace(".exe","") in a for a in open_apps)
            for alias in aliases
        )

    def register_app_opened(self, app_name: str) -> None:
        self._state["last_app_opened"] = app_name.lower()
        app_lower = app_name.lower().replace(".exe","")
        if app_lower not in self._state["open_apps"]:
            self._state["open_apps"].append(app_lower)

    def register_action(self, acao: str, parametros: Dict) -> None:
        self._state["last_action"] = {"acao": acao, "parametros": parametros, "ts": time.time()}
        if acao in ("pesquisar_web", "pesquisar_youtube", "pesquisar_site"):
            self._state["last_search_query"] = parametros.get("query", "")
        if acao == "abrir_site":
            self._state["last_url_opened"] = parametros.get("url", "")
        if acao == "abrir_programa":
            self.register_app_opened(parametros.get("programa", ""))

    def register_flow(self, flow_name: str) -> None:
        self._state["last_flow_name"] = flow_name

    def get_last_app(self) -> Optional[str]:
        return self._state.get("last_app_opened")

    def get(self, key: str, default=None):
        return self._state.get(key, default)


context_cache = ContextCache()


# ══════════════════════════════════════════════════════════════
# DECISION ENGINE
# ══════════════════════════════════════════════════════════════

class Decision:
    """Resultado de uma decisão do motor."""

    def __init__(
        self,
        method:     str,            # "cache"|"direct"|"flow"|"proc"|"planner"|"llm"
        confidence: float,          # 0.0 - 1.0
        payload:    Any   = None,   # dados da decisão (flow, intent, etc.)
        reason:     str   = "",     # motivo legível
        skip_steps: List[str] = None,  # passos que podem ser pulados
    ):
        self.method     = method
        self.confidence = confidence
        self.payload    = payload
        self.reason     = reason
        self.skip_steps = skip_steps or []
        self.ts         = time.time()

    def __repr__(self):
        return f"Decision(method={self.method}, confidence={self.confidence:.2f}, reason='{self.reason}')"


class DecisionEngine:
    """
    Cérebro de decisão da AURA.
    Escolhe o método de execução mais eficiente para cada objetivo.
    """

    # Padrões de ação direta (sem precisar do modelo)
    # IMPORTANTE: estes padrões só devem casar quando a intenção é
    # inequívoca. Um padrão genérico demais (ex: qualquer "abr-")
    # rouba o controle do modelo e da FlowLibrary, impedindo a IA
    # de raciocinar sobre pedidos compostos como "abrir o navegador
    # e criar uma nova aba".
    _DIRECT_PATTERNS = [
        # (regex, acao, extrator_de_params)

        # Só casa "abrir site X" / "abrir X.com" quando o alvo tem cara de
        # domínio (contém ponto) OU está explicitamente marcado como "site".
        # NÃO casa "abre o navegador", "abre uma aba", "abre o programa" etc.
        (r"abr[ea]?\s+(?:o\s+)?site\s+(?:do\s+)?([\w.-]+)",
         "abrir_site", lambda m: {"url": m.group(1)}),

        (r"abr[ea]?\s+(?:o\s+)?([\w-]+\.[a-z]{2,})\b",
         "abrir_site", lambda m: {"url": m.group(1)}),

        # Padrões de "pesquisar" foram removidos daqui — o IntentEngine
        # (Nível 1.5, checado antes deste bloco) já cobre pesquisar_web e
        # pesquisar_youtube de forma mais completa, incluindo a distinção
        # de ambiguidade entre "pesquisar um serviço conhecido" (baixa
        # confiança, vai para o modelo raciocinar) e "pesquisar com
        # conteúdo real" (alta confiança, resolve na hora). Manter esses
        # regex aqui causava um bug real: eles recapturavam QUALQUER
        # "pesquise X" com confiança fixa 0.92, ignorando completamente
        # a análise de ambiguidade do IntentEngine.

        (r"(?:tira|tire|captur[ae])\s+(?:um\s+)?(?:print|screenshot|foto\s+da\s+tela)",
         "capturar_tela", lambda m: {}),

        (r'(?:quanto|como).{0,15}(?:cpu|processador)',
         'obter_cpu', lambda m: {}),

        (r'(?:quanto|como).{0,15}(?:ram|memoria)',
         'obter_ram', lambda m: {}),

        (r'(?:quanto|como).{0,15}(?:bateria|carga)',
         'obter_bateria', lambda m: {}),
    ]

    # Sites conhecidos para resolução direta
    _KNOWN_SITES = {
        "youtube": "https://www.youtube.com",
        "yt": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
        "spotify": "https://open.spotify.com",
        "netflix": "https://www.netflix.com",
        "reddit": "https://www.reddit.com",
        "twitter": "https://www.twitter.com",
        "x": "https://www.x.com",
        "instagram": "https://www.instagram.com",
    }

    def __init__(self):
        self._pattern_cache: Dict[str, Decision] = {}  # cache de decisões por texto

    @staticmethod
    def _normalize(text: str) -> str:
        n = unicodedata.normalize("NFD", text.lower().strip())
        n = "".join(c for c in n if unicodedata.category(c) != "Mn")
        n = re.sub(r"[^\w\s]", " ", n)
        return re.sub(r"\s+", " ", n).strip()

    def decide(
        self,
        user_input:   str,
        context:      Dict = None,
        intent:       Dict = None,   # intent já extraído pelo parser (se houver)
    ) -> Decision:
        """
        Decide como executar o pedido do usuário.

        Args:
            user_input: Texto do usuário.
            context:    Estado atual do computador (do ContextManager).
            intent:     Intent JSON já extraído pelo parser (opcional).

        Returns:
            Decision com method, confidence e payload.
        """
        t0   = time.time()
        text = self._normalize(user_input)

        # Atualiza cache de contexto
        if context:
            context_cache.update_from_context_manager(context)

        # ── Nível 0: Correção de erro já aprendida ───────────────────────────
        # Se a AURA já errou esse exato tipo de pedido antes e foi corrigida,
        # aplica a correção direto — não repete o erro, não precisa do modelo.
        try:
            from automation.error_learning import error_learner
            correction = error_learner.find_known_correction(user_input)
            if correction:
                return Decision(
                    method="direct",
                    confidence=correction["confidence"],
                    payload={
                        "acao": correction["acao"],
                        "parametros": correction["parametros"],
                        "confirmacao_necessaria": False,
                        "mensagem": f"Executando: {correction['acao']}",
                    },
                    reason=(
                        f"Correção aprendida — evitou repetir erro "
                        f"'{correction['evitou']}'"
                    ),
                )
        except Exception as e:
            logger.debug(f"ErrorLearner consulta falhou (não bloqueante): {e}")

        # ── Nível 1: Verificação de contexto ─────────────────────────────────
        # "pesquisa lofi" após o Spotify já estar aberto →
        # não abre o Spotify de novo, só pesquisa
        ctx_decision = self._check_context(text, intent)
        if ctx_decision:
            logger.debug(f"Decisão por contexto em {(time.time()-t0)*1000:.1f}ms: {ctx_decision}")
            return ctx_decision

        # ── Nível 1.5: IntentEngine — intenção estruturada ──────────────────
        # Converte o texto em Intent(acao, tipo, alvo, params) antes de
        # qualquer regex ou modelo. Permite que "abre spotify" e "abre discord"
        # usem o mesmo conceito "abrir_programa(nome)" — fluxos parametrizados.
        # CRÍTICO: usa nome de variável DIFERENTE do parâmetro `intent: Dict`.
        # Bug real de produção corrigido aqui — antes esta linha reatribuía
        # a variável `intent` (que também é o nome do parâmetro da função)
        # para um objeto Intent (dataclass), sobrescrevendo o Dict original.
        # Quando a confiança do IntentEngine era baixa e a função não
        # retornava aqui, a execução chegava no Nível 5 legado
        # (`if intent and "acao" in intent`) com `intent` já sendo o objeto
        # Intent errado — "acao" in Intent() lança TypeError porque Intent
        # não é um container. Isso quebrava QUALQUER mensagem onde o
        # IntentEngine encontrasse algum match de baixa confiança.
        try:
            from ai.intent_engine import intent_engine
            parsed_intent = intent_engine.parse(user_input)
            if parsed_intent and parsed_intent.ferramenta and parsed_intent.confianca >= 0.82:
                if parsed_intent.eh_fluxo and parsed_intent.sub_intents:
                    # Multi-intent → gera lista de steps diretamente
                    steps = intent_engine.to_flow_steps(parsed_intent)
                    logger.info(
                        f"IntentEngine multi-step em {(time.time()-t0)*1000:.1f}ms: "
                        f"{[s['acao'] for s in steps]}"
                    )
                    return Decision(
                        method="planner",
                        confidence=parsed_intent.confianca,
                        payload=steps,
                        reason=f"IntentEngine: {parsed_intent.acao}+subs (conf={parsed_intent.confianca:.2f})"
                    )
                else:
                    tool_intent = parsed_intent.to_tool_intent()
                    if tool_intent:
                        # Alguns atalhos de teclado só fazem sentido se já
                        # existe uma janela do tipo certo em foco. "nova aba"
                        # via Ctrl+T não abre nada se nenhum navegador está
                        # aberto — precisa abrir o navegador primeiro. Sem
                        # essa checagem, "abre o navegador e cria uma nova
                        # aba" disparava só o atalho, ignorando "abrir o
                        # navegador" quando ele ainda não estava rodando.
                        BROWSER_SHORTCUTS = {"ctrl+t", "ctrl+w", "ctrl+shift+n", "ctrl+n"}
                        teclas = tool_intent.get("parametros", {}).get("teclas", "")
                        if teclas in BROWSER_SHORTCUTS:
                            browsers = ["chrome", "firefox", "edge", "brave"]
                            any_open = any(context_cache.is_app_open(b) for b in browsers)
                            if not any_open:
                                default_browser = "chrome.exe"
                                steps = [
                                    {"acao": "abrir_programa", "parametros": {"programa": default_browser}},
                                    {"acao": "esperar", "parametros": {"segundos": 2}},
                                    {"acao": tool_intent["acao"], "parametros": tool_intent["parametros"]},
                                ]
                                logger.info(
                                    f"IntentEngine: nenhum navegador aberto — "
                                    f"expandindo '{teclas}' para abrir {default_browser} primeiro"
                                )
                                return Decision(
                                    method="planner",
                                    confidence=parsed_intent.confianca,
                                    payload=steps,
                                    reason=f"Atalho '{teclas}' precisa de navegador aberto — abrindo {default_browser}"
                                )

                        logger.info(
                            f"IntentEngine em {(time.time()-t0)*1000:.1f}ms: "
                            f"{parsed_intent.acao}:{parsed_intent.tipo}({parsed_intent.alvo})"
                        )
                        return Decision(
                            method="direct",
                            confidence=parsed_intent.confianca,
                            payload=tool_intent,
                            reason=f"IntentEngine: {parsed_intent.acao}:{parsed_intent.tipo}({parsed_intent.alvo})"
                        )
        except Exception as e:
            logger.debug(f"IntentEngine erro (não bloqueante): {e}")

        # ── Nível 2: Ação direta (padrão regex) ──────────────────────────────
        # Fallback conservador: só para casos com pontuação ou padrões
        # que o IntentEngine ainda não cobre (ex: domínios com ponto).
        direct = self._try_direct_action(user_input.lower()) or self._try_direct_action(text)
        if direct:
            logger.debug(f"Decisão regex em {(time.time()-t0)*1000:.1f}ms: {direct}")
            return direct

        # ── Nível 3: FlowLibrary (fluxos versionados com métricas) ───────────
        flow_dec = self._try_flow_library(text, context)
        if flow_dec and flow_dec.confidence >= 0.85:
            logger.debug(f"Decisão por fluxo em {(time.time()-t0)*1000:.1f}ms: {flow_dec}")
            return flow_dec

        # ── Nível 4: Procedimentos legados (memory.procedural) ────────────────
        proc_dec = self._try_procedure(text)
        if proc_dec and proc_dec.confidence >= 0.72:
            logger.debug(f"Decisão por procedimento em {(time.time()-t0)*1000:.1f}ms: {proc_dec}")
            return proc_dec

        # ── Nível 5: Intent já extraído → Planner ────────────────────────────
        if intent and "acao" in intent:
            return Decision(
                method="planner",
                confidence=0.80,
                payload=intent,
                reason="Intent extraído pelo parser"
            )

        # ── Nível 6: Modelo de IA ─────────────────────────────────────────────
        logger.debug(f"Roteando para modelo em {(time.time()-t0)*1000:.1f}ms")
        return Decision(
            method="llm",
            confidence=0.50,
            reason="Nenhum atalho encontrado — reasoning necessário"
        )

    def _check_context(self, text: str, intent: Dict = None) -> Optional[Decision]:
        """
        Verifica se o estado atual do ambiente permite pular etapas.
        Ex: Spotify já aberto → pula "abrir_programa spotify"
        """
        # ── Controle de mídia/playback — checado com prioridade máxima ──────
        # Bug real encontrado: comandos como "pula uma música" continham a
        # substring "musica", e a heurística de busca do Spotify logo
        # abaixo capturava QUALQUER menção a "musica"/"música" como se
        # fosse um pedido de busca — transformando "pula uma música no
        # spotify" em uma pesquisa web literal e quebrada ("pula uma no
        # spotify spotify"), em vez de enviar o atalho de teclado de
        # avançar faixa. Aqui reconhecemos comandos de controle de mídia
        # como sua própria categoria, mapeados para teclas de mídia nativas
        # do Windows (nexttrack/prevtrack/playpause/volumeup/volumedown),
        # que funcionam independente de qual app de música está em foco.
        MEDIA_CONTROL_PATTERNS = [
            (r"\b(?:pul[ae]|proxim[ao]|avan[çc]ar?)\s+(?:um[a]?\s+|a\s+|de\s+)?(?:musica|m[uú]sica|faixa)\b", "nexttrack"),
            (r"\bpr[oó]xima\s+(?:musica|m[uú]sica|faixa)\b", "nexttrack"),
            (r"\b(?:musica|m[uú]sica|faixa)\s+anterior\b", "prevtrack"),
            (r"\bvolt(?:a|ar)\s+(?:a\s+)?(?:musica|m[uú]sica|faixa)\b", "prevtrack"),
            (r"\bpaus[ae]r?\s+(?:a\s+)?(?:musica|m[uú]sica)?\b", "playpause"),
            (r"\b(?:aumenta|aumentar|sobe|sobre)\s+(?:o\s+)?volume\b", "volumeup"),
            (r"\b(?:diminui|diminuir|abaixa|abaixar)\s+(?:o\s+)?volume\b", "volumedown"),
        ]
        for pattern, media_key in MEDIA_CONTROL_PATTERNS:
            if re.search(pattern, text):
                return Decision(
                    method="direct",
                    confidence=0.93,
                    payload={"acao": "pressionar_tecla",
                             "parametros": {"teclas": media_key},
                             "confirmacao_necessaria": False,
                             "mensagem": f"Controle de mídia: {media_key}"},
                    reason=f"Comando de playback reconhecido → {media_key}"
                )

        # Se recebemos intent de multi-ação, verifica quais etapas podem ser puladas
        if intent and isinstance(intent, list):
            skip = []
            filtered = []
            for step in intent:
                acao   = step.get("acao", "")
                params = step.get("parametros", {})
                if acao == "abrir_programa":
                    prog = params.get("programa", "").replace(".exe","")
                    if context_cache.is_app_open(prog):
                        skip.append(f"abrir_programa({prog})")
                        logger.info(f"Contexto: pulando abrir {prog} (já aberto)")
                        continue
                filtered.append(step)

            if skip and filtered:
                return Decision(
                    method="planner",
                    confidence=0.90,
                    payload=filtered,
                    reason=f"Pulou etapas (já aberto): {', '.join(skip)}",
                    skip_steps=skip
                )

        # Verifica pedidos de pesquisa quando app já está aberto
        last_app = context_cache.get_last_app() or ""

        # Palavras-gatilho restritas a verbos de BUSCAR/TOCAR algo
        # específico — "musica"/"música" como substring solta foi removida
        # daqui de propósito, pois qualquer comando de playback control
        # (pula, próxima, pausa, volume) também contém essa palavra e seria
        # incorretamente capturado por esta busca antes de chegar aqui.
        # Comandos de playback já foram tratados no bloco acima.
        if last_app == "spotify" and any(
            w in text for w in ["pesquisa", "toca", "play"]
        ):
            query = re.sub(r"(?:pesquis[ae]|toca|play)\s*", "", text).strip()
            if query:
                return Decision(
                    method="direct",
                    confidence=0.88,
                    payload={"acao": "pesquisar_web",
                             "parametros": {"query": f"{query} spotify"},
                             "mensagem": f"Pesquisando '{query}' no Spotify..."},
                    reason="Spotify já aberto — pesquisa direta"
                )

        if last_app in ("chrome","firefox","edge","browser") and any(
            w in text for w in ["pesquis", "busqu", "procur"]
        ):
            query = re.sub(r"(?:pesquis[ae]|busqu[ea]|procur[ae])\s*", "", text).strip()
            if query:
                return Decision(
                    method="direct",
                    confidence=0.85,
                    payload={"acao": "pesquisar_web",
                             "parametros": {"query": query},
                             "mensagem": f"Pesquisando: {query}"},
                    reason="Navegador já aberto — pesquisa direta"
                )

        return None

    def _try_direct_action(self, text: str) -> Optional[Decision]:
        """Tenta mapear o texto para uma ação direta via regex."""
        for pattern, acao, extrator in self._DIRECT_PATTERNS:
            m = re.search(pattern, text)
            if not m:
                continue

            try:
                params = extrator(m)
            except Exception:
                continue

            # Resolve URL para sites conhecidos
            if acao == "abrir_site":
                raw_url = params.get("url", "")
                site = raw_url.lower().split(".")[0]
                if site in self._KNOWN_SITES:
                    params["url"] = self._KNOWN_SITES[site]
                elif re.match(r"^[\w-]+\.[a-z]{2,}$", raw_url.lower()):
                    # Já tem cara de domínio válido (ex: github.io)
                    if not raw_url.startswith("http"):
                        params["url"] = "https://" + raw_url
                else:
                    # Não é site conhecido nem parece domínio válido —
                    # não inventa URL. Deixa cair para o modelo decidir
                    # (provavelmente é abrir_programa, não abrir_site).
                    continue

            return Decision(
                method="direct",
                confidence=0.92,
                payload={"acao": acao, "parametros": params,
                         "confirmacao_necessaria": False,
                         "mensagem": f"Executando: {acao}"},
                reason=f"Padrão direto: {acao}"
            )

        return None

    def _try_flow_library(self, text: str, context: Dict = None) -> Optional[Decision]:
        """Busca na FlowLibrary o melhor fluxo versionado."""
        try:
            from automation.flow_library import flow_library
            open_apps = context.get("open_programs", []) if context else []
            flow = flow_library.find_best_for(text, open_apps)
            if not flow:
                return None

            score = flow.get("match_score", 0.0)
            taxa  = flow.get("taxa_sucesso", 1.0)
            # Confiança = media de score de similaridade e taxa de sucesso
            confidence = (score * 0.6 + taxa * 0.4)

            return Decision(
                method="flow",
                confidence=round(confidence, 3),
                payload=flow,
                reason=f"FlowLibrary: '{flow['nome']}' "
                       f"(score={score:.2f} taxa={taxa:.2f})"
            )
        except Exception as e:
            logger.debug(f"FlowLibrary erro: {e}")
            return None

    def _try_procedure(self, text: str) -> Optional[Decision]:
        """Busca em memory.procedural (compatibilidade legada)."""
        try:
            from memory.memory_manager import memory
            procs = memory.procedural.get_all()
            if not procs:
                return None

            best_score = 0.0
            best_proc  = None

            for proc in procs:
                nome = self._normalize(proc.get("nome", "").replace("_"," "))
                desc = self._normalize(proc.get("descricao",""))
                score = max(
                    similarity(text, nome),
                    similarity(text, desc),
                    0.88 if nome in text else 0.0,
                    0.88 if text in nome else 0.0,
                )
                if score > best_score:
                    best_score = score
                    best_proc  = proc

            if best_score >= 0.70 and best_proc:
                return Decision(
                    method="proc",
                    confidence=round(best_score * 0.9, 3),
                    payload=best_proc,
                    reason=f"Procedimento: '{best_proc['nome']}' (score={best_score:.2f})"
                )
        except Exception as e:
            logger.debug(f"Procedure erro: {e}")

        return None

    def evaluate_confidence(
        self,
        method:     str,
        confidence: float,
        history:    List[Dict] = None,
    ) -> Tuple[str, str]:
        """
        Avalia o nível de confiança e decide a ação.

        Returns:
            (acao, mensagem) onde acao é:
            "execute"   — confiança suficiente, executa
            "try_alt"   — tenta alternativa antes
            "ask_user"  — pede confirmação ao usuário

        IMPORTANTE: method == "llm" SEMPRE executa (chama o modelo).
        A confiança baixa nesse caso só indica que nenhum atalho rápido
        serviu — é exatamente o sinal para consultar a IA, não para
        travar pedindo confirmação ao usuário. "ask_user" só se aplica
        a decisões de atalho (direct/flow/proc) com confiança realmente baixa.
        """
        if method == "llm":
            return "execute", ""

        if confidence >= 0.85:
            return "execute", ""
        elif confidence >= 0.65:
            if history:
                recentes = history[-5:] if len(history) >= 5 else history
                sucesso_recente = sum(1 for h in recentes if h.get("sucesso")) / max(1, len(recentes))
                if sucesso_recente >= 0.6:
                    return "execute", ""
            return "try_alt", "Tentando com alternativa disponível..."
        else:
            return "ask_user", "Não tenho certeza do que fazer. Pode detalhar?"


# ══════════════════════════════════════════════════════════════
# REFLEXÃO PÓS-EXECUÇÃO
# ══════════════════════════════════════════════════════════════

class ReflectionEngine:
    """
    Reflexão silenciosa após cada execução.
    Analisa o resultado e atualiza fluxos/memória automaticamente.
    Roda em thread daemon — zero impacto na velocidade.
    """

    def reflect(
        self,
        flow_name:  str,
        passos:     List[Dict],
        sucesso:    bool,
        tempo_s:    float,
        objetivo:   str = "",
        erro_msg:   str = "",
    ) -> None:
        """Inicia reflexão assíncrona após execução."""
        import threading
        threading.Thread(
            target=self._reflect_async,
            args=(flow_name, passos, sucesso, tempo_s, objetivo, erro_msg),
            daemon=True
        ).start()

    def _reflect_async(
        self,
        flow_name:  str,
        passos:     List[Dict],
        sucesso:    bool,
        tempo_s:    float,
        objetivo:   str,
        erro_msg:   str,
    ) -> None:
        """
        Reflexão real — analisa e otimiza silenciosamente.
        Perguntas internas:
          1. O fluxo foi eficiente?
          2. Algum passo pode ser removido?
          3. O tempo de espera estava certo?
          4. Devo atualizar o fluxo?
        """
        try:
            from automation.flow_library import flow_library

            # Registra execução com métricas
            if flow_name:
                flow_library.register_execution(
                    nome=flow_name,
                    sucesso=sucesso,
                    tempo_s=tempo_s,
                    objetivo=objetivo,
                    erro_msg=erro_msg,
                    passos_usados=passos,
                )

            # Verifica se há sugestão de otimização
            if flow_name and sucesso:
                sugestao = flow_library.suggest_optimization(flow_name)
                if sugestao:
                    logger.info(f"[REFLEXÃO] Sugestão para '{flow_name}': {sugestao}")
                    bus.publish("aura.reflection",
                                flow=flow_name,
                                sugestao=sugestao)

            # Limpeza periódica de fluxos ruins (1 em cada 20 execuções)
            import random
            if random.random() < 0.05:  # 5% de chance
                removidos = flow_library.cleanup()
                if removidos:
                    logger.info(f"[REFLEXÃO] Limpeza: {removidos} fluxo(s) obsoleto(s) removido(s)")

        except Exception as e:
            logger.debug(f"Reflexão erro (silencioso): {e}")


# ══════════════════════════════════════════════════════════════
# SISTEMA DE INICIATIVA
# ══════════════════════════════════════════════════════════════

class InitiativeEngine:
    """
    Gera sugestões proativas baseadas no contexto atual.
    Nunca interrompe o fluxo principal — apenas enriquece.
    """

    # Sugestões por app aberto (app → sugestão)
    _APP_SUGGESTIONS = {
        "spotify": [
            "Posso pesquisar uma música ou playlist para você.",
            "Quer que eu controle o Spotify por aqui?",
        ],
        "youtube": [
            "Posso pesquisar vídeos novos se quiser.",
            "Quer verificar as últimas novidades de algum canal?",
        ],
        "chrome": [
            "Posso pesquisar algo no navegador.",
            "Tem algum site que quer abrir?",
        ],
        "discord": [
            "Discord aberto. Quer que eu navegue por algum servidor?",
        ],
        "steam": [
            "Steam rodando. Quer abrir algum jogo?",
        ],
        "vscode": [
            "VS Code aberto. Posso ajudar com algum arquivo ou pasta?",
        ],
    }

    def get_suggestion(
        self,
        context: Dict,
        last_action: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Retorna sugestão proativa baseada no contexto.
        Retorna None na maioria das vezes para não ser intrusiva.
        """
        import random

        # Só sugere em 15% das execuções bem-sucedidas
        if random.random() > 0.15:
            return None

        open_apps = context.get("open_programs", [])

        for app, suggestions in self._APP_SUGGESTIONS.items():
            if any(app in prog.lower() for prog in open_apps):
                return random.choice(suggestions)

        return None

    def generate_opinion(self, flow_name: str, context: Dict) -> Optional[str]:
        """
        Gera opinião fundamentada sobre o fluxo executado.
        Só emite quando há dados suficientes.
        """
        try:
            from automation.flow_library import flow_library
            flow = flow_library.get(flow_name)
            if not flow or flow.get("uso_count", 0) < 3:
                return None

            taxa  = flow.get("taxa_sucesso", 1.0)
            tempo = flow.get("tempo_medio", 0.0)

            if taxa >= 0.9 and tempo < 5:
                return f"Esse fluxo costuma ser bem rápido — {tempo:.0f}s em média."
            elif taxa < 0.7:
                return f"Esse caminho tem falhado às vezes ({taxa:.0%} de sucesso). Posso tentar outro?"
            return None
        except Exception:
            return None


# Instâncias globais
decision_engine  = DecisionEngine()
reflection_engine = ReflectionEngine()
initiative_engine = InitiativeEngine()
