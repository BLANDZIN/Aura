"""
tools/param_normalization.py
Normalização de parâmetros vindos do modelo/decision engine para o nome
canônico que cada ferramenta espera. Extraído de tool_manager.py na
divisão por categoria (Fase 2/V10) — comportamento idêntico, só mudou
de arquivo.

normalize_params continua importável de tools.tool_manager (re-exportado
lá) porque automation/flow_executor.py, ui/chat_panel.py e ui/app.py já
dependem desse caminho.
"""
import re
from datetime import datetime
from typing import Any, Dict

from tools.resolvers import KNOWN_SITES, _resolve_folder, _resolve_new_folder_path, _resolve_program

# ══════════════════════════════════════════════════════════════
# NORMALIZADOR
# ══════════════════════════════════════════════════════════════

PARAM_ALIASES: Dict[str, Dict[str, str]] = {
    "abrir_programa": {
        "program_name":"programa","nome":"programa","app":"programa",
        "aplicativo":"programa","executavel":"programa","nome_programa":"programa",
    },
    "fechar_programa": {
        "nome":"processo","programa":"processo","app":"processo","nome_processo":"processo",
    },
    "abrir_pasta": {
        "nome":"caminho","pasta":"caminho","diretorio":"caminho",
        "folder":"caminho","path":"caminho","dir":"caminho","local":"caminho",
    },
    "abrir_arquivo": {
        "arquivo":"caminho","file":"caminho","path":"caminho","nome":"caminho",
    },
    "criar_pasta": {
        "nome_da_pasta":"caminho","nome":"caminho","pasta":"caminho",
        "nome_pasta":"caminho","folder_name":"caminho","folder":"caminho",
    },
    "excluir_arquivo": {
        "arquivo":"caminho","pasta":"caminho","path":"caminho","file":"caminho","nome":"caminho",
    },
    "renomear_arquivo": {
        "arquivo":"caminho","path":"caminho","nome_atual":"caminho",
    },
    "mover_arquivo": {
        "origem_path":"origem","destino_path":"destino","para":"destino","source":"origem","dest":"destino",
    },
    "copiar_arquivo": {
        "origem_path":"origem","destino_path":"destino","para":"destino","source":"origem","dest":"destino",
    },
    "pesquisar_arquivo": {
        "nome_arquivo":"nome","arquivo":"nome","file":"nome",
        "pasta":"diretorio","dir":"diretorio","local":"diretorio",
    },
    "pesquisar_web": {
        "palavra_chave":"query","termo":"query","busca":"query","pesquisa":"query",
        "search":"query","texto":"query","assunto":"query",
    },
    "pesquisar_youtube": {
        "palavra_chave":"query","termo":"query","busca":"query","pesquisa":"query",
        "search":"query","texto":"query","assunto":"query","video":"query",
    },
    "pesquisar_site": {
        "palavra_chave":"query","termo":"query","busca":"query","texto":"query",
        "plataforma":"site","onde":"site","em":"site",
    },
    "abrir_site": {
        "site":"url","dominio":"url","link":"url","website":"url",
        "endereco":"url","pagina":"url","address":"url",
    },
    "salvar_memoria": {
        "memoria":"valor","informacao":"valor","info":"valor",
        "conteudo":"valor","texto":"valor","content":"valor","dado":"valor",
    },
    "buscar_memoria": {
        "termo":"chave","busca":"chave","pesquisa":"chave","search":"chave",
    },
    "criar_tarefa": {
        "nome":"titulo","task":"titulo","tarefa":"titulo","nome_tarefa":"titulo","title":"titulo",
    },
    "concluir_tarefa": {
        "id":"task_id","tarefa_id":"task_id","id_tarefa":"task_id","task":"task_id",
    },
    "pressionar_tecla": {
        "tecla":"teclas","key":"teclas","keys":"teclas","botao":"teclas",
    },
    "digitar_texto": {
        "text":"texto","content":"texto","conteudo":"texto","mensagem":"texto",
    },
    "rolar_pagina": {
        "direcao":"sentido","direction":"sentido","scroll":"sentido",
        "quantidade":"cliques","amount":"cliques","vezes":"cliques",
    },
    "executar_procedimento": {
        "procedimento":"nome","proc":"nome","automacao":"nome","rotina":"nome","recipe":"nome",
    },
}


def normalize_params(acao: str, params: Dict[str, Any]) -> Dict[str, Any]:
    result  = dict(params)
    aliases = PARAM_ALIASES.get(acao, {})
    for alias, canonical in aliases.items():
        if alias in result and canonical not in result:
            result[canonical] = result.pop(alias)
        elif alias in result:
            result.pop(alias)

    # Pós-processamento específico
    _PP = {
        "criar_pasta":    _pp_criar_pasta,
        "abrir_pasta":    _pp_abrir_pasta,
        "abrir_programa": _pp_abrir_programa,
        "salvar_memoria": _pp_salvar_memoria,
        "pesquisar_web":  _pp_pesquisar_web,
        "abrir_site":     _pp_abrir_site,
    }
    if acao in _PP:
        _PP[acao](result)
    return result


def _pp_criar_pasta(p: Dict) -> None:
    if "caminho" in p:
        p["caminho"] = _resolve_new_folder_path(str(p["caminho"]))

def _pp_abrir_pasta(p: Dict) -> None:
    p["caminho"] = _resolve_folder(str(p.get("caminho", "desktop")))

def _pp_abrir_programa(p: Dict) -> None:
    if "programa" in p:
        p["programa"] = _resolve_program(str(p["programa"]))

def _pp_salvar_memoria(p: Dict) -> None:
    if "valor" not in p:
        return
    p.setdefault("chave",     f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    p.setdefault("categoria", "conversa")
    p.setdefault("importance", 5)

def _pp_pesquisar_web(p: Dict) -> None:
    if "query" not in p and "termo" in p:
        p["query"] = p.pop("termo")

def _pp_abrir_site(p: Dict) -> None:
    url = str(p.get("url", "")).strip()
    if not url:
        return
    key = re.sub(r"[^a-z0-9]", "", url.lower())
    if key in KNOWN_SITES:
        p["url"] = KNOWN_SITES[key]
        return
    if url.startswith(("http://", "https://")):
        return
    # Rede de segurança: só aceita como domínio se tiver um TLD plausível
    # (ex: "google.com", "site.com.br"). Evita transformar palavras comuns
    # como "navegador", "youtube" mal-digitado, etc. em URLs falsas.
    is_valid_domain = bool(re.match(
        r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", url.lower()
    ))
    if is_valid_domain:
        p["url"] = "https://" + url
    else:
        # Marca como inválido — o ToolManager vai reportar erro em vez
        # de abrir um link inexistente. Aqui é só a rede de segurança;
        # o raciocínio correto (abrir_programa + atalho) deve evitar
        # cair nesse caso na maioria das vezes.
        p["url"] = ""
        p["_invalid_domain"] = url
