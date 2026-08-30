#!/usr/bin/env python3
"""
scripts/download_models.py — AURA V12.2
==========================================
ESQUELETO DE ARQUITETURA — não é a implementação completa de propósito
(brief original: "ainda não implementar completamente, apenas deixar a
arquitetura preparada"). O que já funciona: checar o que está instalado
e listar o que falta. O que falta implementar: download real via
`ollama pull` com barra de progresso, verificação de checksum contra o
manifesto do Ollama.

Deriva a lista de modelos de config/settings.py (DEFAULTS) em vez de
hardcodar de novo — única fonte de verdade pros nomes de modelo é
o settings.py, este script só lê.

Uso pretendido (ver docs/INSTALL_MODELS.md):
    python scripts/download_models.py --check          # já funciona
    python scripts/download_models.py --minimal         # TODO
    python scripts/download_models.py --full            # TODO
"""
import argparse
import subprocess
import sys
from typing import Dict

sys.path.insert(0, ".")

from config.settings import DEFAULTS


def _agent_models() -> Dict[str, str]:
    """
    Deriva {nome_do_papel: tag_do_modelo} direto do DEFAULTS de
    config/settings.py — não duplica a lista em um terceiro lugar
    (settings.py e docs/MODELS.md já são as fontes de verdade).
    """
    modelos = {"aura": DEFAULTS["ai"]["model"]}
    for chave, bloco in DEFAULTS.items():
        if chave.startswith("agent_") and isinstance(bloco, dict) and "model" in bloco:
            papel = chave.replace("agent_", "")
            modelos[papel] = bloco["model"]
    return modelos


def check_installed_models() -> Dict[str, bool]:
    """
    Retorna {tag_do_modelo: instalado?} consultando `ollama list`.
    Já funciona de ponta a ponta — não precisa do Ollama estar
    respondendo na API HTTP, só o binário `ollama` no PATH.
    """
    modelos = _agent_models()
    try:
        saida = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10,
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  [ERRO] Não consegui rodar 'ollama list': {e}")
        return {tag: False for tag in modelos.values()}

    instalados_raw = saida.lower()
    return {
        tag: tag.split(":")[0].lower() in instalados_raw
        for tag in modelos.values()
    }


def print_status() -> None:
    modelos = _agent_models()
    status = check_installed_models()
    print()
    print("  AURA V12.2 — status dos modelos")
    print("  " + "=" * 44)
    for papel, tag in modelos.items():
        marcado = "✓" if status.get(tag) else "✗"
        obrigatorio = " (obrigatório)" if papel == "aura" else ""
        print(f"  {marcado}  {papel:12s} {tag}{obrigatorio}")
    print()
    faltando = [tag for tag in modelos.values() if not status.get(tag)]
    if faltando:
        print(f"  {len(faltando)} modelo(s) faltando. Ver docs/INSTALL_MODELS.md")
        print("  pros comandos `ollama pull` de cada um.")
    else:
        print("  Todos os modelos da arquitetura completa estão instalados.")
    print()


def download_missing(minimal: bool = True) -> None:
    """
    TODO (V12.3): baixar de verdade via `ollama pull <tag>` com
    streaming de progresso, e validar tamanho baixado contra
    docs/MODELS.md. Por ora, só orienta pro comando manual — evita
    prometer uma barra de progresso que ainda não existe.
    """
    modelos = _agent_models()
    status = check_installed_models()
    alvo = {"aura": modelos["aura"]} if minimal else modelos
    faltando = {p: t for p, t in alvo.items() if not status.get(t)}

    if not faltando:
        print("  Nada pra baixar — já está tudo instalado.")
        return

    print(f"  Rode manualmente (ainda não automatizado nesta versão):")
    for papel, tag in faltando.items():
        print(f"    ollama pull {tag}   # {papel}")


def validate_integrity() -> bool:
    """TODO (V12.3): checar hash/tamanho de cada modelo baixado contra
    o manifesto oficial do Ollama. Esqueleto por ora."""
    raise NotImplementedError(
        "validate_integrity() ainda não implementado — ver docstring do módulo."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AURA V12.2 — gerenciador de modelos dos agentes")
    parser.add_argument("--check", action="store_true", help="Lista o que já está instalado (funciona hoje)")
    parser.add_argument("--minimal", action="store_true", help="TODO: baixar só o obrigatório (aura)")
    parser.add_argument("--full", action="store_true", help="TODO: baixar todos os agentes")
    args = parser.parse_args()

    if args.minimal:
        download_missing(minimal=True)
    elif args.full:
        download_missing(minimal=False)
    else:
        print_status()
