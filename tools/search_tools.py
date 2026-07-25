"""
tools/search_tools.py — AURA V11
=================================
Ferramentas de pesquisa inteligente.

  pesquisar_resposta — Busca na web e retorna TEXTO (sem abrir navegador)
  pesquisar_web       — Abre navegador com pesquisa (comportamento atual)

Backend em cascata:
  1. DuckDuckGo Instant Answer API (JSON, sem CAPTCHA)
  2. Wikipedia API (para fatos/definições)
  3. Fallback: sugere usar pesquisar_web
"""

import re
import json
import urllib.parse

import requests

from tools.base_tool import BaseTool
from core.logger import setup_logger

logger = setup_logger("search_tools")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _search_ddg_instant(query: str) -> str | None:
    """
    DuckDuckGo Instant Answer API — JSON, sem CAPTCHA.
    Retorna None se não encontrou nada.
    """
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
            "t": "AURA_V11",
        }
        resp = requests.get(url, params=params, headers={"User-Agent": _USER_AGENT}, timeout=10)
        data = resp.json()

        results = []

        # Abstract (resposta direta da DDG)
        abstract = (data.get("AbstractText") or "").strip()
        if abstract and len(abstract) > 20:
            source = data.get("AbstractSource", "")
            results.append(f"📖 {abstract}")
            if source:
                results[-1] += f"\n   Fonte: {source}"

        # Answer (resposta instantânea)
        answer = (data.get("Answer") or "").strip()
        if answer and len(answer) > 10:
            results.append(f"💡 {answer}")

        # Definition
        definition = (data.get("Definition") or "").strip()
        if definition and len(definition) > 20 and definition != abstract:
            results.append(f"📚 {definition}")

        # Related topics (tópicos relacionados)
        for topic in data.get("RelatedTopics", [])[:3]:
            text = (topic.get("Text") or "").strip()
            if text and len(text) > 20:
                results.append(f"• {text}")

        # Infobox (tabela de fatos)
        infobox = data.get("Infobox", {}) if isinstance(data.get("Infobox"), dict) else {}
        if infobox and infobox.get("content"):
            for item in infobox.get("content", [])[:5]:
                label = item.get("label", "")
                value = item.get("value", "")
                if label and value:
                    results.append(f"  {label}: {value}")

        if results:
            return "\n".join(results)
        return None

    except Exception as e:
        logger.debug(f"DDG Instant API failed: {e}")
        return None


def _search_wikipedia(query: str, lang: str = "pt") -> str | None:
    """
    Wikipedia API — ideal para fatos, definições, biografias.
    """
    try:
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
            "format": "json",
            "srprop": "snippet",
        }
        resp = requests.get(url, params=params, headers={"User-Agent": _USER_AGENT}, timeout=10)
        data = resp.json()

        results = []
        for item in data.get("query", {}).get("search", [])[:3]:
            title = item.get("title", "")
            snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
            results.append(f"• {title}: {snippet}...")

        if results:
            return f"📚 Wikipedia:\n" + "\n".join(results)

        return None

    except Exception as e:
        logger.debug(f"Wikipedia API failed: {e}")
        return None


def _search_web_text(query: str) -> str:
    """Busca na web e retorna texto. Cascata: DDG → Wikipedia → fallback."""
    # 1. DuckDuckGo Instant Answer
    result = _search_ddg_instant(query)
    if result:
        return f"Sobre '{query}':\n{result}"

    # 2. Wikipedia
    result = _search_wikipedia(query)
    if result:
        return result

    # 3. Fallback
    return (
        f"Não consegui acessar a web para '{query}'.\n"
        f"Você pode:\n"
        f"  • Pedir 'pesquisar_web' para abrir no navegador\n"
        f"  • Perguntar algo que eu saiba responder com meu conhecimento\n"
        f"  • Tentar com outras palavras"
    )


class PesquisarRespostaTool(BaseTool):
    """
    Pesquisa na web e retorna TEXTO — NÃO abre navegador.

    Use quando o usuário quer uma resposta rápida:
    - "qual a cotação do dólar hoje?"
    - "quem é Elon Musk?"
    - "quantos km tem a Terra?"

    Para conhecimento geral (história, ciência, cultura), a IA responde
    direto do próprio conhecimento, sem usar esta ferramenta.
    """
    name = "pesquisar_resposta"
    description = "Busca na web e retorna TEXTO com a resposta, sem abrir navegador"
    params_doc = '{"query": "o que você quer saber"}'

    def execute(self, p):
        try:
            query = str(p.get("query", "")).strip()
            if not query:
                return self._error("Query de pesquisa vazia")

            texto = _search_web_text(query)
            return self._success(
                texto,
                f"Busquei '{query[:60]}' na web"
            )

        except Exception as e:
            return self._error("Erro na pesquisa", e)


# Auto-registro V11
REGISTRY = [PesquisarRespostaTool()]