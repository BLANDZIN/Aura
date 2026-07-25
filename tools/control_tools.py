"""
tools/control_tools.py — Ferramentas de Controle: teclado, mouse, clipboard (10)
Extraído de tool_manager.py na divisão por categoria (Fase 2/V10) —
comportamento idêntico, só mudou de arquivo.
"""
import os
import time

import pyautogui

from tools.base_tool import BaseTool
from tools.resolvers import DESKTOP, PYAUTOGUI_KEYS

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class CapturarTelaTool(BaseTool):
    name = "capturar_tela"
    description = "Tira screenshot da tela inteira ou região."
    params_doc = '{"caminho": "C:/Users/User/Desktop/screen.png"}'
    def execute(self, p: dict) -> dict:
        try:
            caminho = p.get("caminho", str(DESKTOP / f"screenshot_{int(time.time())}.png"))
            img     = pyautogui.screenshot()
            img.save(caminho)
            return self._success(caminho, f"Screenshot salvo: {os.path.basename(caminho)}")
        except Exception as e:
            return self._error("Erro ao capturar tela", e)

class MoverMouseTool(BaseTool):
    name = "mover_mouse"
    description = "Move cursor para coordenadas x, y."
    params_doc = '{"x": 500, "y": 300}'
    def execute(self, p: dict) -> dict:
        try:
            pyautogui.moveTo(int(p["x"]), int(p["y"]), duration=0.25)
            return self._success(mensagem=f"Mouse → ({p['x']}, {p['y']})")
        except Exception as e:
            return self._pyautogui_error("Erro ao mover mouse", e)

class ClicarMouseTool(BaseTool):
    name = "clicar_mouse"
    description = "Clica em coordenadas x, y. botao: left/right/middle."
    params_doc = '{"x": 500, "y": 300, "botao": "left", "cliques": 1}'
    def execute(self, p: dict) -> dict:
        try:
            x = int(p["x"]); y = int(p["y"])
            botao   = p.get("botao", "left")
            cliques = int(p.get("cliques", 1))
            if cliques == 2:
                pyautogui.doubleClick(x, y, button=botao)
            else:
                pyautogui.click(x, y, button=botao, clicks=cliques)
            return self._success(mensagem=f"Clicou em ({x},{y}) [{botao}] x{cliques}")
        except Exception as e:
            return self._pyautogui_error("Erro ao clicar", e)

class DigitarTextoTool(BaseTool):
    name = "digitar_texto"
    description = "Digita texto via teclado. Suporta unicode."
    params_doc = '{"texto": "Olá mundo!", "intervalo": 0.05}'
    def execute(self, p: dict) -> dict:
        try:
            texto     = str(p["texto"])
            intervalo = float(p.get("intervalo", 0.03))
            # pyautogui.typewrite não suporta unicode — usa clipboard
            import pyperclip
            pyperclip.copy(texto)
            pyautogui.hotkey("ctrl", "v")
            return self._success(mensagem=f"Digitado: {texto[:50]}")
        except ImportError:
            # fallback sem pyperclip
            pyautogui.typewrite(texto, interval=intervalo)
            return self._success(mensagem=f"Digitado: {texto[:50]}")
        except Exception as e:
            return self._pyautogui_error("Erro ao digitar", e)

class PressionarTeclaTool(BaseTool):
    name = "pressionar_tecla"
    description = "Pressiona tecla(s) ou atalhos. Ex: Ctrl+C, Win+D, F5."
    params_doc = '{"teclas": "ctrl+c"}  — ou lista: ["ctrl","shift","esc"]'
    def execute(self, p: dict) -> dict:
        try:
            teclas = p.get("teclas", p.get("key", ""))
            if isinstance(teclas, str):
                # Converte "ctrl+c" em lista ["ctrl","c"]
                teclas = [t.strip().lower() for t in teclas.replace("+", " ").split()]
            # Resolve nomes alternativos
            teclas = [PYAUTOGUI_KEYS.get(t, t) for t in teclas]
            if len(teclas) == 1:
                pyautogui.press(teclas[0])
            else:
                pyautogui.hotkey(*teclas)
            return self._success(mensagem=f"Teclas: {'+'.join(teclas)}")
        except Exception as e:
            return self._pyautogui_error("Erro ao pressionar tecla", e)

class AtalhoTeclaTool(BaseTool):
    name = "atalho_teclado"
    description = "Executa atalho de teclado composto. Ex: Ctrl+Alt+Del, Win+R."
    params_doc = '{"atalho": "ctrl+shift+esc"}'
    def execute(self, p: dict) -> dict:
        try:
            atalho = str(p["atalho"])
            teclas = [t.strip().lower() for t in atalho.split("+")]
            teclas = [PYAUTOGUI_KEYS.get(t, t) for t in teclas]
            pyautogui.hotkey(*teclas)
            return self._success(mensagem=f"Atalho executado: {atalho}")
        except Exception as e:
            return self._pyautogui_error("Erro no atalho", e)

class RolarPaginaTool(BaseTool):
    name = "rolar_pagina"
    description = "Rola a página ou scroll. sentido: up/down."
    params_doc = '{"sentido": "down", "cliques": 5}'
    def execute(self, p: dict) -> dict:
        try:
            sentido = str(p.get("sentido", "down")).lower()
            cliques = int(p.get("cliques", 3))
            valor   = cliques if sentido in ("up","cima") else -cliques
            pyautogui.scroll(valor)
            return self._success(mensagem=f"Rolou {sentido} ({cliques} cliques)")
        except Exception as e:
            return self._error("Erro ao rolar página", e)

class EsperarTool(BaseTool):
    name = "esperar"
    description = "Aguarda N segundos antes de continuar o fluxo."
    params_doc = '{"segundos": 2}'
    def execute(self, p: dict) -> dict:
        try:
            seg = float(p.get("segundos", 1))
            time.sleep(seg)
            return self._success(mensagem=f"Aguardei {seg}s")
        except Exception as e:
            return self._error("Erro ao esperar", e)

class CopiarAreaTransfTool(BaseTool):
    name = "copiar_area_transf"
    description = "Lê o conteúdo atual do clipboard/área de transferência."
    params_doc = '{}'
    def execute(self, p: dict) -> dict:
        try:
            import pyperclip
            texto = pyperclip.paste()
            return self._success(texto, f"Clipboard: {texto[:80]}")
        except ImportError:
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.2)
            return self._success(None, "Copiado (pyperclip não disponível para ler)")
        except Exception as e:
            return self._error("Erro ao ler clipboard", e)

class EscreverAreaTransfTool(BaseTool):
    name = "escrever_area_transf"
    description = "Escreve texto no clipboard/área de transferência."
    params_doc = '{"texto": "conteúdo a copiar"}'
    def execute(self, p: dict) -> dict:
        try:
            import pyperclip
            pyperclip.copy(str(p["texto"]))
            return self._success(mensagem="Texto copiado para clipboard")
        except ImportError:
            return self._error("pyperclip não instalado — pip install pyperclip")
        except Exception as e:
            return self._error("Erro ao escrever clipboard", e)


# Auto-registro V11
REGISTRY = [CapturarTelaTool(), MoverMouseTool(), ClicarMouseTool(), DigitarTextoTool(), PressionarTeclaTool(), AtalhoTeclaTool(), RolarPaginaTool(), EsperarTool(), CopiarAreaTransfTool(), EscreverAreaTransfTool()]