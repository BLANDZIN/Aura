"""
ai/intent_engine.py — AURA V6
================================
Motor de Intenção. Converte linguagem natural em estrutura semântica
antes de qualquer decisão ser tomada.

Princípio central da V6:
  A AURA não aprende "abrir Spotify" e "abrir Discord" como coisas
  diferentes. Ela aprende "abrir aplicativo(nome)". O IntentEngine
  é o que torna isso possível — extrai a INTENÇÃO real, não o texto.

Estrutura de saída (Intent):
  {
    "acao":      "abrir",          # verbo principal
    "tipo":      "aplicativo",     # categoria do alvo
    "alvo":      "spotify",        # o alvo concreto
    "params":    {"nome": "spotify.exe"},  # parâmetros resolvidos
    "confiança": 0.92,             # 0.0-1.0
    "raw":       "abre o spotify", # texto original
    "ferramenta": "abrir_programa" # ferramenta mapeada
  }

Hierarquia de intenções:
  ABRIR    → aplicativo, site, pasta, arquivo, documento
  CRIAR    → pasta, arquivo, projeto, fluxo, tarefa
  PESQUISAR → google, youtube, spotify, arquivos, sistema
  FECHAR   → aplicativo, aba, janela
  COPIAR   → texto, arquivo, pasta
  MOVER    → arquivo, pasta
  EXECUTAR → procedimento, fluxo, atalho
  CONTROLAR→ teclado, mouse, scroll
  LEMBRAR  → salvar memória, criar nota
  INFORMAR → cpu, ram, bateria, hora, arquivos
  CONVERSAR→ (sem ação de sistema — resposta textual)

Desenvolvido por Bland | Claude
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from core.logger import setup_logger
from core.fuzzy_search import similarity

logger = setup_logger("intent")


@dataclass
class Intent:
    """Representação estruturada de uma intenção do usuário."""
    acao:       str                    # verbo: abrir, criar, pesquisar, etc.
    tipo:       str                    # categoria: aplicativo, site, pasta, etc.
    alvo:       str                    # o alvo concreto: "spotify", "youtube.com"
    params:     Dict[str, Any]         = field(default_factory=dict)
    confianca:  float                  = 0.0   # 0.0-1.0
    raw:        str                    = ""    # texto original do usuário
    ferramenta: str                    = ""    # ferramenta mapeada (ex: abrir_programa)
    eh_fluxo:   bool                   = False # requer múltiplas etapas?
    sub_intents: List['Intent']        = field(default_factory=list)

    def __repr__(self):
        return f"Intent({self.acao}:{self.tipo}({self.alvo}) conf={self.confianca:.2f})"

    def to_tool_intent(self) -> Optional[Dict[str, Any]]:
        """Converte para formato esperado pelo ToolManager/DecisionEngine."""
        if not self.ferramenta:
            return None
        return {
            "acao":       self.ferramenta,
            "parametros": self.params,
            "confirmacao_necessaria": self.ferramenta in {
                "excluir_arquivo", "fechar_programa",
                "digitar_texto", "clicar_mouse",
            },
            "mensagem":   self._default_message(),
        }

    def _default_message(self) -> str:
        msgs = {
            "abrir_programa": f"Abrindo {self.alvo.title()}...",
            "abrir_site":     f"Abrindo {self.alvo}...",
            "abrir_pasta":    f"Abrindo {self.alvo}...",
            "pesquisar_web":  f"Pesquisando '{self.alvo}'...",
            "pesquisar_resposta": f"Buscando resposta sobre '{self.alvo}'...",
            "pesquisar_youtube": f"Pesquisando '{self.alvo}' no YouTube...",
            "criar_pasta":    f"Criando pasta '{self.alvo}'...",
            "capturar_tela":  "Tirando screenshot...",
            "pressionar_tecla": f"Atalho: {self.alvo}",
            "obter_cpu":      "Verificando CPU...",
            "obter_ram":      "Verificando RAM...",
        }
        return msgs.get(self.ferramenta, f"Executando: {self.ferramenta}")


# ══════════════════════════════════════════════════════════════
# TABELAS DE MAPEAMENTO
# ══════════════════════════════════════════════════════════════

# Verbos → ação normalizada
VERB_MAP: Dict[str, str] = {
    # ABRIR
    "abre":"abrir", "abrir":"abrir", "abra":"abrir", "acessa":"abrir",
    "acesse":"abrir", "vai":"abrir", "entra":"abrir", "entre":"abrir",
    "inicia":"abrir", "inicie":"abrir", "lança":"abrir", "lança":"abrir",
    "vê":"abrir", "ve":"abrir",
    # CRIAR
    "cria":"criar", "criar":"criar", "crie":"criar", "nova":"criar",
    "novo":"criar", "adiciona":"criar", "adicione":"criar",
    "faz":"criar", "faca":"criar",
    # PESQUISAR
    "pesquisa":"pesquisar", "pesquisar":"pesquisar", "pesquise":"pesquisar",
    "busca":"pesquisar", "buscar":"pesquisar", "busque":"pesquisar",
    "procura":"pesquisar", "procurar":"pesquisar", "procure":"pesquisar",
    "consulta":"pesquisar", "consultar":"pesquisar", "consulte":"pesquisar",
    "pergunta":"pesquisar", "perguntar":"pesquisar",
    # FECHAR
    "fecha":"fechar", "fechar":"fechar", "feche":"fechar",
    "encerra":"fechar", "encerre":"fechar", "mata":"fechar",
    # CONTROLAR
    "clica":"controlar", "clique":"controlar", "aperta":"controlar",
    "aperte":"controlar", "pressiona":"controlar", "pressione":"controlar",
    "digita":"controlar", "digite":"controlar", "rola":"controlar",
    "role":"controlar", "sobe":"controlar", "desce":"controlar",
    # EXECUTAR
    "executa":"executar", "execute":"executar", "roda":"executar",
    "rode":"executar", "usa":"executar", "use":"executar",
    "ativa":"executar", "ative":"executar",
    # LEMBRAR
    "lembra":"lembrar", "lembre":"lembrar", "salva":"lembrar",
    "salve":"lembrar", "anota":"lembrar", "anote":"lembrar",
    "memoriza":"lembrar", "memorize":"lembrar",
    # INFORMAR
    "quanto":"informar", "como":"informar", "verifica":"informar",
    "verifique":"informar", "mostra":"informar", "mostre":"informar",
    "qual":"informar", "quais":"informar",
    # TIRAR
    "tira":"tirar", "tire":"tirar", "captura":"tirar", "capture":"tirar",
}

# Tipo de alvo por palavra-chave
TYPE_MAP: Dict[str, str] = {
    # APLICATIVOS
    "spotify":"aplicativo", "discord":"aplicativo", "chrome":"aplicativo",
    "firefox":"aplicativo", "edge":"aplicativo", "brave":"aplicativo",
    "steam":"aplicativo", "vscode":"aplicativo", "code":"aplicativo",
    "notepad":"aplicativo", "calculadora":"aplicativo", "calculator":"aplicativo",
    "paint":"aplicativo", "word":"aplicativo", "excel":"aplicativo",
    "powerpoint":"aplicativo", "outlook":"aplicativo", "teams":"aplicativo",
    "whatsapp":"aplicativo", "telegram":"aplicativo", "obs":"aplicativo",
    "vlc":"aplicativo", "audacity":"aplicativo", "bloco":"aplicativo",
    "gerenciador":"aplicativo", "explorador":"aplicativo", "explorer":"aplicativo",
    # SITES
    "youtube":"site", "yt":"site", "google":"site", "gmail":"site",
    "github":"site", "reddit":"site", "twitter":"site", "instagram":"site",
    "facebook":"site", "linkedin":"site", "netflix":"site",
    "chatgpt":"site", "claude":"site", "twitch":"site",
    # PASTA/ARQUIVO
    "pasta":"pasta", "diretório":"pasta", "diretorio":"pasta", "folder":"pasta",
    "arquivo":"arquivo", "file":"arquivo", "documento":"arquivo",
    # ABA/JANELA (atalhos de teclado)
    "aba":"aba", "tab":"aba", "janela":"janela", "window":"janela",
    # SISTEMA
    "cpu":"sistema", "processador":"sistema", "ram":"sistema",
    "memoria":"sistema", "bateria":"sistema", "tela":"sistema",
    "screenshot":"screenshot", "print":"screenshot",
    # PESQUISA
    "musica":"pesquisa_musica", "música":"pesquisa_musica",
    "video":"pesquisa_video", "vídeo":"pesquisa_video",
}

# Atalhos de teclado conhecidos por intenção
KEYBOARD_SHORTCUTS: Dict[str, str] = {
    "nova aba":       "ctrl+t",
    "fechar aba":     "ctrl+w",
    "nova janela":    "ctrl+n",
    "janela privada": "ctrl+shift+n",
    "atualizar":      "f5",
    "recarregar":     "f5",
    "salvar":         "ctrl+s",
    "copiar":         "ctrl+c",
    "colar":          "ctrl+v",
    "desfazer":       "ctrl+z",
    "refazer":        "ctrl+y",
    "selecionar tudo":"ctrl+a",
    "localizar":      "ctrl+f",
    "encontrar":      "ctrl+f",
    "voltar":         "alt+left",
    "avançar":        "alt+right",
    "fechar programa":"alt+f4",
    "alternar apps":  "alt+tab",
    "área de trabalho":"win+d",
    "task manager":   "ctrl+shift+esc",
    "gerenciador":    "ctrl+shift+esc",
    "print screen":   "printscreen",
    "zoom mais":      "ctrl+=",
    "zoom menos":     "ctrl+-",
    "tela cheia":     "f11",
}

# Ferramenta por (acao, tipo)
TOOL_MAP: Dict[Tuple[str,str], str] = {
    ("abrir",    "aplicativo"):       "abrir_programa",
    ("abrir",    "site"):             "abrir_site",
    ("abrir",    "pasta"):            "abrir_pasta",
    ("abrir",    "arquivo"):          "abrir_arquivo",
    ("abrir",    "aba"):              "pressionar_tecla",
    ("abrir",    "janela"):           "pressionar_tecla",
    ("criar",    "pasta"):            "criar_pasta",
    ("criar",    "arquivo"):          "criar_pasta",  # simplificado
    ("pesquisar","site"):             "pesquisar_web",
    ("pesquisar","pesquisa_video"):   "pesquisar_youtube",
    ("pesquisar","pesquisa_musica"):  "pesquisar_web",
    ("pesquisar","*"):                "pesquisar_web",
    ("fechar",   "aplicativo"):       "fechar_programa",
    ("fechar",   "aba"):              "pressionar_tecla",
    ("controlar","*"):                "pressionar_tecla",
    ("tirar",    "screenshot"):       "capturar_tela",
    ("informar", "sistema"):          "obter_cpu",  # refinado depois
    ("lembrar",  "*"):                "salvar_memoria",
    ("executar", "*"):                "executar_procedimento",
}


# ══════════════════════════════════════════════════════════════
# INTENT ENGINE
# ══════════════════════════════════════════════════════════════

class IntentEngine:
    """
    Converte texto natural em Intent estruturado.

    Estratégia em 4 camadas (mais rápida → mais cara):
    1. Atalho de teclado explícito  (< 1ms, regex)
    2. Padrão estrutural direto     (< 2ms, regras + tabelas)
    3. Composição multi-intenção    (< 5ms, detecta "e" entre ações)
    4. Fallback semântico           (< 10ms, fuzzy sobre tabelas)
    """

    def __init__(self):
        self._cache: Dict[str, Intent] = {}

    @staticmethod
    def _norm(text: str) -> str:
        n = unicodedata.normalize("NFD", text.lower().strip())
        n = "".join(c for c in n if unicodedata.category(c) != "Mn")
        return re.sub(r"\s+", " ", n).strip()

    def parse(self, text: str) -> Optional[Intent]:
        """
        Ponto de entrada principal. Retorna Intent ou None se o texto
        não tem intenção de sistema (é conversa pura).
        """
        norm = self._norm(text)

        # Cache: mesmo texto, mesmo resultado
        if norm in self._cache:
            return self._cache[norm]

        # 1. Atalho de teclado explícito
        intent = self._try_keyboard_shortcut(norm)
        if intent:
            self._cache[norm] = intent
            return intent

        # 2. Padrão estrutural direto
        intent = self._try_structured(norm, text)
        if intent:
            self._cache[norm] = intent
            return intent

        # 3. Multi-intenção ("abre spotify E pesquisa lofi")
        intent = self._try_multi_intent(norm, text)
        if intent:
            self._cache[norm] = intent
            return intent

        # 4. Fallback semântico
        intent = self._try_semantic_fallback(norm, text)
        if intent:
            self._cache[norm] = intent
            return intent

        return None  # conversa pura

    def _try_keyboard_shortcut(self, norm: str) -> Optional[Intent]:
        """Detecta pedidos de atalho de teclado explícitos."""
        for phrase, keys in KEYBOARD_SHORTCUTS.items():
            if phrase in norm:
                return Intent(
                    acao="controlar",
                    tipo="atalho",
                    alvo=phrase,
                    params={"teclas": keys},
                    confianca=0.95,
                    raw=norm,
                    ferramenta="pressionar_tecla",
                )
        return None

    def _try_structured(self, norm: str, raw: str) -> Optional[Intent]:
        """
        Extrai verbo + tipo + alvo usando tabelas de mapeamento.
        Abordagem conservadora: só dispara quando tem alta confiança.
        """
        words = norm.split()
        if not words:
            return None

        # Encontra o verbo principal (primeira palavra de ação)
        acao = None
        verb_idx = 0
        for i, w in enumerate(words[:4]):  # verbo quase sempre nas primeiras 4 palavras
            if w in VERB_MAP:
                acao = VERB_MAP[w]
                verb_idx = i
                break

        if not acao:
            return None

        # Remove artigos e preposições após o verbo
        remaining = [w for w in words[verb_idx+1:]
                     if w not in {"o","a","os","as","um","uma","do","da",
                                  "de","no","na","em","pra","para","ao","aos"}]

        if not remaining:
            return None

        # Tenta identificar o tipo e alvo
        tipo = None
        alvo = None
        alvo_idx = 0

        for i, w in enumerate(remaining):
            if w in TYPE_MAP:
                tipo = TYPE_MAP[w]
                alvo = w
                alvo_idx = i
                break

        # Se não achou tipo por palavra exata, tenta por sufixo de domínio
        if not tipo:
            for w in remaining:
                if re.match(r"[\w-]+\.[a-z]{2,}", w):
                    tipo = "site"
                    alvo = w
                    break

        if not tipo:
            # Pesquisa genérica: sem tipo explícito mas acao=pesquisar → pesquisar_web
            if acao == "pesquisar":
                query = " ".join(remaining)
                return Intent(
                    acao="pesquisar", tipo="geral", alvo=query[:40],
                    params={"query": query},
                    confianca=0.82,
                    raw=raw, ferramenta="pesquisar_web",
                )
            return None

        # Parâmetros específicos por (acao, tipo)
        params = self._build_params(acao, tipo, alvo, remaining, raw)
        # Injeta o alvo nos params para _resolve_tool poder inspecioná-lo
        params["_alvo"] = alvo or ""
        ferramenta = self._resolve_tool(acao, tipo, params)
        params.pop("_alvo", None)  # remove antes de retornar

        # Confiança: 0.90 se alvo direto, 0.75 se inferido
        conf = 0.90 if alvo in TYPE_MAP else 0.75

        # Ambiguidade estrutural: "pesquisar" + um alvo que É ELE MESMO um
        # app/site conhecido, SEM nenhuma palavra de busca adicional, é
        # genuinamente ambíguo — "pesquise spotify" pode significar
        # "procure informações sobre o Spotify" OU "abra/vá para o Spotify"
        # (uso coloquial comum). Em vez de uma lista fixa de "sites que
        # sempre significam abrir", reconhecemos a CLASSE estrutural da
        # ambiguidade — pesquisar + alvo=entidade conhecida + nenhum
        # conteúdo de busca além do próprio nome — e baixamos a confiança
        # abaixo do limiar de fast-path do DecisionEngine (0.82), deixando
        # o modelo raciocinar com contexto completo em vez de decidir
        # mecanicamente. Busca com conteúdo real (ex: "pesquisa novidades
        # do spotify") não é ambígua — permanece rápida e mecânica.
        if acao == "pesquisar" and tipo in ("aplicativo", "site") and len(remaining) == 1:
            conf = 0.55  # abaixo do limiar de 0.82 — força raciocínio via LLM

        return Intent(
            acao=acao, tipo=tipo, alvo=alvo or "",
            params=params, confianca=conf,
            raw=raw, ferramenta=ferramenta,
        )

    def _try_multi_intent(self, norm: str, raw: str) -> Optional[Intent]:
        """
        Detecta pedidos compostos: "abre spotify e pesquisa lofi".
        Retorna um Intent com sub_intents preenchidos.
        """
        # Divide por conectivos
        parts = re.split(r'\s+(?:e|depois|então|em seguida|apos|após)\s+', norm)
        if len(parts) < 2:
            return None

        sub_intents = []
        for part in parts:
            sub = self._try_structured(part, part) or self._try_keyboard_shortcut(part)
            if sub:
                sub_intents.append(sub)

        if len(sub_intents) < 2:
            return None

        # Intent principal = primeiro sub-intent, com os demais como sub
        main = sub_intents[0]
        main.sub_intents = sub_intents[1:]
        main.eh_fluxo    = True
        main.confianca   = min(s.confianca for s in sub_intents) * 0.95
        main.raw         = raw
        return main

    def _try_semantic_fallback(self, norm: str, raw: str) -> Optional[Intent]:
        """
        Fallback: tenta achar o melhor match por similaridade nas tabelas.
        Menos preciso, usará confiança mais baixa.
        """
        words = norm.split()

        # Verbo por similaridade
        acao = None
        best_verb_score = 0.0
        for verb, mapped_acao in VERB_MAP.items():
            for w in words[:3]:
                s = similarity(w, verb)
                if s > best_verb_score:
                    best_verb_score = s
                    acao = mapped_acao

        if not acao or best_verb_score < 0.75:
            return None

        # Alvo por similaridade nas palavras restantes
        tipo = None
        alvo = None
        best_type_score = 0.0
        for w in words[1:]:
            for key, mapped_type in TYPE_MAP.items():
                s = similarity(w, key)
                if s > best_type_score:
                    best_type_score = s
                    tipo = mapped_type
                    alvo = key

        if not tipo or best_type_score < 0.70:
            return None

        params = self._build_params(acao, tipo, alvo, words[1:], raw)
        ferramenta = self._resolve_tool(acao, tipo, params)
        conf = round(best_verb_score * best_type_score * 0.85, 3)

        return Intent(
            acao=acao, tipo=tipo, alvo=alvo or "",
            params=params, confianca=conf,
            raw=raw, ferramenta=ferramenta,
        )

    def _build_params(
        self, acao: str, tipo: str, alvo: str,
        remaining: List[str], raw: str
    ) -> Dict[str, Any]:
        """Monta os parâmetros concretos para a ferramenta."""
        from tools.tool_manager import KNOWN_SITES

        params: Dict[str, Any] = {}

        if acao == "abrir" and tipo == "aplicativo":
            # Resolução real (por plataforma) acontece depois em
            # tools/resolvers.py::_resolve_program, via normalize_params.
            # Aqui só passamos o nome pedido adiante.
            params["programa"] = alvo

        elif acao == "abrir" and tipo == "site":
            # Resolve para URL completa
            site_key = re.sub(r"[^a-z0-9]", "", alvo.lower())
            url = KNOWN_SITES.get(site_key) or KNOWN_SITES.get(alvo.lower())
            if not url:
                url = f"https://{alvo}" if "." in alvo else None
            if url:
                params["url"] = url

        elif acao == "abrir" and tipo == "pasta":
            # Resolução real (por plataforma) acontece depois em
            # tools/resolvers.py::_resolve_folder, via normalize_params.
            params["caminho"] = alvo

        elif acao == "abrir" and tipo in ("aba", "janela"):
            shortcut = "ctrl+t" if tipo == "aba" else "ctrl+n"
            params["teclas"] = shortcut

        elif acao in ("pesquisar", "pesquisa"):
            # Remove o nome do site/plataforma da query (ex: "no youtube" → query sem "youtube")
            stop_words = {"no", "na", "no", "em", "pelo", "pela", "no", "youtube",
                          "google", "yt", "spotify", "github", "reddit"}
            query_words = [w for w in remaining
                           if w != alvo and w not in stop_words]
            params["query"] = " ".join(query_words) if query_words else alvo
            # Preserva URL para casos onde o alvo é o motor de busca
            if tipo == "site" and alvo in ("google",):
                from tools.tool_manager import KNOWN_SITES
                site_key = re.sub(r"[^a-z0-9]", "", alvo.lower())
                params["url"] = KNOWN_SITES.get(site_key, f"https://{alvo}.com")

        elif acao == "criar" and tipo == "pasta":
            # Nome da pasta = restante após o verbo
            nome_words = [w for w in remaining
                         if w not in {"pasta","diretorio","diretório","folder"}]
            params["caminho"] = " ".join(nome_words) if nome_words else "Nova Pasta"

        elif acao == "tirar":
            params = {}  # capturar_tela não precisa de parâmetros obrigatórios

        elif acao == "informar":
            # Decide qual ferramenta baseado no alvo
            if alvo in ("cpu", "processador"):
                pass  # ferramenta já será obter_cpu
            elif alvo in ("ram", "memoria"):
                pass  # ferramenta já será obter_ram
            elif alvo in ("bateria",):
                pass  # ferramenta já será obter_bateria

        return params

    def _resolve_tool(self, acao: str, tipo: str, params: Dict) -> str:
        """Mapeia (acao, tipo) para nome de ferramenta."""
        # Caso especial: informar → seleciona ferramenta pelo alvo
        if acao == "informar":
            alvo_in_params = str(params)
            if "cpu" in tipo or "processador" in tipo:
                return "obter_cpu"
            if "ram" in tipo or "memoria" in tipo:
                return "obter_ram"
            if "bateria" in tipo:
                return "obter_bateria"
            return "obter_cpu"  # default

        # Caso especial: pesquisar + site → depende do site alvo
        if acao == "pesquisar" and tipo == "site":
            # Verifica o alvo diretamente (não params['url'] que pode estar vazio)
            alvo_str = params.get("_alvo", "") or ""
            if "youtube" in alvo_str or "yt" in alvo_str:
                return "pesquisar_youtube"
            return "pesquisar_web"

        # Lookup direto
        tool = TOOL_MAP.get((acao, tipo))
        if tool:
            return tool

        # Fallback com wildcard
        tool = TOOL_MAP.get((acao, "*"))
        return tool or ""

    def to_flow_steps(self, intent: Intent) -> List[Dict]:
        """
        Converte um Intent (possivelmente com sub_intents) em lista
        de passos para o FlowExecutor, inserindo esperas adequadas.
        """
        steps = []

        def _add_intent(i: Intent) -> None:
            tool_intent = i.to_tool_intent()
            if not tool_intent:
                return
            steps.append({
                "acao":       tool_intent["acao"],
                "parametros": tool_intent["parametros"],
            })
            # Insere espera após abrir aplicativo (apps demoram para carregar)
            if tool_intent["acao"] == "abrir_programa":
                prog = tool_intent["parametros"].get("programa", "").lower()
                # Tempo de espera por tipo de app
                wait_map = {
                    "spotify.exe": 5, "discord.exe": 4, "steam.exe": 6,
                    "chrome.exe": 2, "firefox.exe": 2, "msedge.exe": 2,
                    "brave.exe": 2, "code.exe": 3, "obs64.exe": 4,
                }
                wait_s = next((v for k,v in wait_map.items() if k in prog), 2)
                steps.append({"acao": "esperar", "parametros": {"segundos": wait_s}})

        _add_intent(intent)
        for sub in intent.sub_intents:
            _add_intent(sub)

        return steps


# Instância global
intent_engine = IntentEngine()
