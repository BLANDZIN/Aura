"""
tools/ocr_tools.py — Ferramenta de OCR (1)
==========================================
Lê texto da tela usando OCR multi-backend:

  1. EasyOCR (recomendado) — cross-platform, sem dependência externa
     pip install easyocr  (~90MB download do modelo na 1ª execução)
  2. Tesseract (fallback) — mais rápido se já instalado no sistema
     Precisa de instalação separada: https://github.com/UB-Mannheim/tesseract

A ferramenta tenta EasyOCR primeiro (funciona out-of-the-box),
depois Tesseract como fallback. Zero configuração necessária.
"""

import os

import pyautogui

from tools.base_tool import BaseTool


class OCRTool(BaseTool):
    name = "ler_tela"
    description = "Lê texto visível na tela via OCR (EasyOCR ou Tesseract)"
    params_doc = '{"regiao": null}  — ou {"regiao": [x, y, largura, altura]}'

    # Cache do reader EasyOCR (caro de inicializar, reutilizar)
    _easyocr_reader = None
    _easyocr_available = None  # None = não testado ainda

    def execute(self, p):
        regiao = p.get("regiao")
        if regiao and len(regiao) == 4:
            img = pyautogui.screenshot(region=tuple(regiao))
        else:
            img = pyautogui.screenshot()

        # ── Backend 1: EasyOCR (zero config, cross-platform) ──────────
        texto = self._try_easyocr(img)
        if texto is not None:
            if not texto.strip():
                return self._success("", "Nenhum texto encontrado na tela")
            return self._success(texto, f"Texto lido (EasyOCR): {texto[:100]}...")

        # ── Backend 2: Tesseract (fallback, mais rápido se já tiver) ─
        texto = self._try_tesseract(img)
        if texto is not None:
            if not texto.strip():
                return self._success("", "Nenhum texto encontrado na tela")
            return self._success(texto, f"Texto lido (Tesseract): {texto[:100]}...")

        return self._error(
            "Nenhum motor de OCR disponível. Instale um dos dois:\n"
            "  pip install easyocr   (recomendado, zero config)\n"
            "  ou Tesseract          (https://github.com/UB-Mannheim/tesseract)"
        )

    # ══════════════════════════════════════════════════════════════════════
    # EasyOCR
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def _try_easyocr(cls, img) -> str | None:
        """EasyOCR: pip install easyocr. Modelo baixado automaticamente."""
        if cls._easyocr_available is False:
            return None

        try:
            import easyocr
            import numpy as np

            # Inicializa sob demanda (cache)
            if cls._easyocr_reader is None:
                # ['pt', 'en'] = português + inglês
                cls._easyocr_reader = easyocr.Reader(['pt', 'en'], gpu=False)
                cls._easyocr_available = True

            # Converte PIL → numpy array
            arr = np.array(img)
            results = cls._easyocr_reader.readtext(arr, detail=0)
            texto = " ".join(results).strip()
            return texto

        except ImportError:
            cls._easyocr_available = False
            return None
        except Exception:
            # EasyOCR falhou em runtime → tenta Tesseract
            return None

    # ══════════════════════════════════════════════════════════════════════
    # Tesseract (fallback)
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _try_tesseract(img) -> str | None:
        """Tesseract: mais rápido se já instalado no sistema."""
        try:
            import pytesseract

            # Detecta Tesseract no Windows
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
            return texto.strip()

        except ImportError:
            return None
        except Exception:
            return None
