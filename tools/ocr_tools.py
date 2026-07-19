"""
tools/ocr_tools.py — Ferramenta de OCR (1)
Extraído de tool_manager.py na divisão por categoria (Fase 2/V10) —
comportamento idêntico, só mudou de arquivo.
"""
import os

import pyautogui

from tools.base_tool import BaseTool


class OCRTool(BaseTool):
    name = "ler_tela"
    description = "Lê texto visível na tela via OCR. Requer pytesseract instalado."
    params_doc = '{"regiao": null}  — ou {"regiao": [x, y, largura, altura]}'

    def execute(self, p):
        try:
            import pytesseract
            from PIL import Image

            regiao = p.get("regiao")
            if regiao and len(regiao) == 4:
                img = pyautogui.screenshot(region=tuple(regiao))
            else:
                img = pyautogui.screenshot()

            # Tenta configuração do Tesseract no Windows
            if os.name == "nt":
                tesseract_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                ]
                for tp in tesseract_paths:
                    if os.path.exists(tp):
                        pytesseract.pytesseract.tesseract_cmd = tp
                        break

            texto = pytesseract.image_to_string(img, lang="por+eng")
            texto = texto.strip()
            if not texto:
                return self._success("", "Nenhum texto encontrado na tela")
            return self._success(texto, f"Texto lido: {texto[:100]}...")
        except ImportError:
            return self._error("pytesseract não instalado. Execute: pip install pytesseract")
        except Exception as e:
            return self._error("Erro no OCR", e)
