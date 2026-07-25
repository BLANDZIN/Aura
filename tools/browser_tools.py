"""
tools/browser_tools.py — Ferramentas de Navegador (4)
Extraído de tool_manager.py na divisão por categoria (Fase 2/V10) —
comportamento idêntico, só mudou de arquivo.
"""
import webbrowser

from tools.base_tool import BaseTool


class AbrirSiteTool(BaseTool):
    name = "abrir_site"
    description = "Abre URL ou site pelo nome (youtube, github, gmail, etc.)."
    params_doc = '{"url": "youtube"}  — ou URL completa: "https://..."'
    def execute(self, p):
        try:
            url = p.get("url", "").strip()
            if not url:
                invalid = p.get("_invalid_domain")
                if invalid:
                    return self._error(
                        f"'{invalid}' não é um site válido. "
                        f"Se a intenção era abrir um programa, use abrir_programa."
                    )
                return self._error("URL não informada")
            webbrowser.open(url)
            return self._success(mensagem=f"Abrindo: {url}")
        except Exception as e:
            return self._error("Erro ao abrir site", e)

class PesquisarWebTool(BaseTool):
    name = "pesquisar_web"
    description = "Pesquisa texto no Google. Aceita frases longas."
    params_doc = '{"query": "melhores notebooks AMD 2024"}'
    def execute(self, p):
        try:
            query = str(p["query"]).strip()
            url   = "https://www.google.com/search?q=" + query.replace(" ", "+")
            webbrowser.open(url)
            return self._success(mensagem=f"Pesquisando: {query}")
        except Exception as e:
            return self._error("Erro ao pesquisar", e)

class PesquisarYoutubeTool(BaseTool):
    name = "pesquisar_youtube"
    description = "Pesquisa um vídeo no YouTube e abre o resultado."
    params_doc = '{"query": "musicas do renk"}'
    def execute(self, p):
        try:
            query = str(p["query"]).strip()
            url   = "https://www.youtube.com/results?search_query=" + query.replace(" ", "+")
            webbrowser.open(url)
            return self._success(mensagem=f"Pesquisando no YouTube: {query}")
        except Exception as e:
            return self._error("Erro ao pesquisar YouTube", e)

class PesquisarSiteTool(BaseTool):
    name = "pesquisar_site"
    description = "Pesquisa texto dentro de um site específico."
    params_doc = '{"query": "python tutorial", "site": "youtube"}  — site: youtube/google/github/reddit'
    def execute(self, p):
        try:
            query = str(p["query"]).strip()
            site  = str(p.get("site","google")).strip().lower()
            SEARCH_URLS = {
                "youtube":  f"https://www.youtube.com/results?search_query={query.replace(' ','+')}",
                "google":   f"https://www.google.com/search?q={query.replace(' ','+')}",
                "github":   f"https://github.com/search?q={query.replace(' ','+')}",
                "reddit":   f"https://www.reddit.com/search/?q={query.replace(' ','+')}",
                "twitter":  f"https://twitter.com/search?q={query.replace(' ','+')}",
                "amazon":   f"https://www.amazon.com.br/s?k={query.replace(' ','+')}",
                "mercadolivre": f"https://lista.mercadolivre.com.br/{query.replace(' ','-')}",
            }
            url = SEARCH_URLS.get(site, f"https://www.google.com/search?q={query.replace(' ','+')}+site:{site}")
            webbrowser.open(url)
            return self._success(mensagem=f"Pesquisando '{query}' em {site}")
        except Exception as e:
            return self._error("Erro ao pesquisar site", e)


# Auto-registro V11
REGISTRY = [AbrirSiteTool(), PesquisarWebTool(), PesquisarYoutubeTool(), PesquisarSiteTool()]