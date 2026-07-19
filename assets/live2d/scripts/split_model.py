#!/usr/bin/env python3
"""
split_model.py — AURA Live2D Pipeline v3
==========================================
Pipeline principal. Analisa TODAS as imagens disponíveis,
seleciona a melhor fonte para cada parte e extrai componentes.

Fontes disponíveis:
  aura_refsheet_gemini.png — Reference sheet profissional com partes pré-separadas
                             (MELHOR qualidade — partes já isoladas nos painéis)
  aura_model.png           — Vista frente/costas com alpha canal real
                             (Bom para corpo completo e costas)
  aura_reference_hd.jpg    — Alta resolução 2112×2016
                             (Bom para detalhes de face em alta resolução)

Estratégia por parte:
  Cabelo       → refsheet_gemini (painéis já separados, alta qualidade)
  Corpo nu     → refsheet_gemini (braços/corpo painéis direita)
  Roupa        → refsheet_gemini (painéis roupas + model.png para costas)
  Rosto        → refsheet_gemini (Head panel) + reference_hd.jpg (maior resolução)
  Olhos        → refsheet_gemini (painel OLHOS com iris/pupila/highlight)
  Acessórios   → refsheet_gemini (painel ACESSÓRIOS)
  Costas       → aura_model.png (única com vista de costas)

Uso:
    python split_model.py
    python split_model.py --source gemini    # só refsheet
    python split_model.py --source all       # todas as fontes (default)
    python split_model.py --canvas 2048      # tamanho canvas exportação
    python split_model.py --debug            # salva mapas de diagnóstico

Resultado:
    output/<categoria>/<parte>.png  — componentes extraídos com alpha
    output/masks/                   — máscaras binárias
    output/templates/               — overlays de debug e mapa de regiões
    output/manifest.json            — metadados de todas as partes
"""

import os
import sys
import json
import time
import argparse
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
LIVE2D_DIR = SCRIPT_DIR.parent
ORIG_DIR   = LIVE2D_DIR / "original"
OUT_DIR    = LIVE2D_DIR / "output"
MASKS_DIR  = OUT_DIR / "masks"
TPL_DIR    = OUT_DIR / "templates"

SOURCES = {
    "gemini":    ORIG_DIR / "aura_refsheet_gemini.png",
    "model":     ORIG_DIR / "aura_model.png",
    "reference": ORIG_DIR / "aura_reference_hd.jpg",
}


# ══════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ══════════════════════════════════════════════════════════════

def log(msg: str, level: str = "INFO") -> None:
    icons = {"INFO":"→","OK":"✓","WARN":"⚠","ERR":"✗","STEP":"◈","HEAD":"▸"}
    print(f"  {icons.get(level,'·')} {msg}")


def remove_checker_background(arr: np.ndarray) -> np.ndarray:
    """
    Detecta e remove o fundo xadrez, retornando array RGBA
    com fundo xadrez tornado transparente.
    O fundo xadrez é cinza neutro (~160-220, acromático).
    """
    if arr.shape[2] == 4:
        # Já tem alpha — verifica se é alpha real ou tudo 255
        if arr[:,:,3].min() < 255:
            return arr  # Alpha real, não precisa remover xadrez
    
    r = arr[:,:,0].astype(int)
    g = arr[:,:,1].astype(int)
    b = arr[:,:,2].astype(int)
    
    # Xadrez: acromático (R≈G≈B) com luminância 130-225
    diff_max = np.maximum(np.maximum(np.abs(r-g), np.abs(g-b)), np.abs(r-b))
    luminance = (r+g+b)//3
    is_checker = (diff_max < 20) & (luminance > 125) & (luminance < 228)
    
    # Cria RGBA com fundo transparente
    result = np.zeros((*arr.shape[:2], 4), dtype=np.uint8)
    result[:,:,:3] = arr[:,:,:3]
    result[:,:,3]  = np.where(is_checker, 0, 255).astype(np.uint8)
    
    return result


def alpha_to_checker(arr: np.ndarray) -> np.ndarray:
    """Converte canal alpha para visualização com fundo xadrez (debug)."""
    h, w = arr.shape[:2]
    out = np.full((h, w, 3), 200, dtype=np.uint8)
    # Padrão xadrez
    for y in range(0, h, 10):
        for x in range(0, w, 10):
            if (y//10 + x//10) % 2 == 0:
                out[y:y+10, x:x+10] = 160
    if arr.shape[2] == 4:
        alpha = arr[:,:,3:4] / 255.0
        out = (arr[:,:,:3] * alpha + out * (1 - alpha)).astype(np.uint8)
    else:
        out = arr[:,:,:3]
    return out


def crop_content(arr: np.ndarray, margin: int = 4) -> np.ndarray:
    """Recorta bounding box do conteúdo visível (alpha > 10)."""
    if arr.shape[2] < 4:
        return arr
    alpha = arr[:,:,3]
    rows = np.where(alpha > 10)[0]
    cols = np.where(alpha > 10)[1]
    if len(rows) == 0:
        return arr
    y1 = max(0, rows.min() - margin)
    y2 = min(arr.shape[0], rows.max() + margin)
    x1 = max(0, cols.min() - margin)
    x2 = min(arr.shape[1], cols.max() + margin)
    return arr[y1:y2, x1:x2]


def save_part(
    arr: np.ndarray,
    output_path: Path,
    label: str,
    source: str,
    results: list,
    crop: bool = True,
    save_mask: bool = True,
) -> bool:
    """Salva uma parte extraída como PNG RGBA."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if arr is None or arr.size == 0:
        log(f"{label}: array vazio", "WARN")
        results.append({"label": label, "status": "empty", "source": source})
        return False
    
    # Garante RGBA
    if arr.shape[2] == 3:
        rgba = np.zeros((*arr.shape[:2], 4), dtype=np.uint8)
        rgba[:,:,:3] = arr
        rgba[:,:,3]  = 255
        arr = rgba
    
    # Verifica conteúdo real
    visible = (arr[:,:,3] > 10).sum()
    if visible < 50:
        log(f"{label}: muito poucos pixels visíveis ({visible})", "WARN")
        results.append({"label": label, "status": "empty", "source": source, "pixels": int(visible)})
        return False
    
    # Crop opcional
    if crop:
        arr = crop_content(arr, margin=6)
    
    # Salva PNG
    Image.fromarray(arr, "RGBA").save(output_path)
    
    # Salva máscara
    if save_mask:
        mask = (arr[:,:,3] > 10).astype(np.uint8) * 255
        MASKS_DIR.mkdir(exist_ok=True)
        mask_path = MASKS_DIR / f"{output_path.stem}_mask.png"
        Image.fromarray(mask, "L").save(mask_path)
    
    meta = {
        "label": label,
        "status": "ok",
        "source": source,
        "pixels": int(visible),
        "size": [int(arr.shape[1]), int(arr.shape[0])],
        "output": str(output_path.relative_to(LIVE2D_DIR)),
    }
    results.append(meta)
    log(f"{label}: {int(visible):,} px  {arr.shape[1]}×{arr.shape[0]}  → {output_path.name}", "OK")
    return True


def apply_region_mask(arr: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    """Recorta região retangular do array RGBA."""
    h, w = arr.shape[:2]
    x1, y1 = max(0,x1), max(0,y1)
    x2, y2 = min(w,x2), min(h,y2)
    region = arr[y1:y2, x1:x2].copy()
    return region


def color_mask(arr: np.ndarray,
               r_range: tuple, g_range: tuple, b_range: tuple,
               invert: bool = False) -> np.ndarray:
    """Filtra pixels por faixa de cor. Retorna array RGBA mascarado."""
    out  = arr.copy()
    r,g,b = arr[:,:,0].astype(int), arr[:,:,1].astype(int), arr[:,:,2].astype(int)
    a    = arr[:,:,3]
    
    in_range = (
        (r >= r_range[0]) & (r <= r_range[1]) &
        (g >= g_range[0]) & (g <= g_range[1]) &
        (b >= b_range[0]) & (b <= b_range[1]) &
        (a > 10)
    )
    if invert:
        in_range = ~in_range
    
    out[:,:,3] = np.where(in_range, a, 0)
    return out


# ══════════════════════════════════════════════════════════════
# EXTRATORES POR FONTE
# ══════════════════════════════════════════════════════════════

class GeminiRefSheetExtractor:
    """
    Extrai componentes da reference sheet do Gemini.
    Esta imagem tem partes já isoladas em painéis.

    Layout mapeado visualmente:
    ┌─────────────────────┬──────────────────────┐
    │  CABELO (0-530)     │  COSTAS+ROSTO (530+) │
    │  y=0-550            │  y=0-450             │
    │  Hair_Back, Sides   │  Head, Neck, Brincos │
    │  Hair_Front, Bangs  │  OLHOS (750+, y<450) │
    ├─────────────────────┼──────────────────────┤
    │  ROUPAS (0-530)     │  CORPO+BRAÇOS (530+) │
    │  y=550-1008         │  y=430-1008          │
    │  Shirt, Sleeves,    │  Body nude, Arms     │
    │  Collar, Bow        │  ACESSÓRIOS          │
    └─────────────────────┴──────────────────────┘
    │              FIGURA CENTRAL (~232-825)      │
    │              (toda altura)                  │
    └─────────────────────────────────────────────┘
    """

    # Coordenadas de cada painel na reference sheet (x1,y1,x2,y2)
    # Mapeadas pela análise de connected components
    PANELS = {
        # ── CABELO ─────────────────────────────────────────────────────────
        "hair_back":         (0,    8,   215,  260),
        "hair_back_left":    (175,  8,   320,  260),
        "hair_right":        (320,  8,   500,  260),
        "hair_front":        (0,    260, 235,  520),
        "hair_side_left":    (235,  260, 480,  520),
        "hair_bangs_left":   (0,    520, 160,  605),
        "hair_bangs_center": (155,  520, 295,  605),
        "hair_bangs_right":  (290,  520, 470,  605),

        # ── ROSTO / PESCOÇO ────────────────────────────────────────────────
        "head_base":         (595,  30,  730,  250),
        "neck":              (595,  150, 730,  300),
        "ear_left":          (730,  30,  820,  250),
        "earring_left":      (730,  30,  830,  250),
        "ear_right":         (875,  30,  985,  250),

        # ── OLHOS ──────────────────────────────────────────────────────────
        "eye_white_lr":      (875,  50,  1000, 160),
        "eye_pupil_lr":      (875,  50,  1000, 160),
        "iris_lr":           (875,  160, 1000, 330),
        "eyelid_lr":         (875,  330, 1000, 440),
        "eye_highlight_lr":  (875,  440, 1000, 540),

        # ── ROUPAS ─────────────────────────────────────────────────────────
        "shirt_full":        (0,    555, 330,  890),
        "sleeve_left":       (0,    830, 170,  1000),
        "sleeve_right":      (290,  830, 480,  1000),
        "collar":            (310,  570, 430,  720),
        "bow":               (310,  700, 445,  900),
        "inner_liner":       (150,  855, 295,  1005),

        # ── CORPO NU / BRAÇOS ──────────────────────────────────────────────
        "body_nude":         (750,  415, 995,  680),
        "arm_left":          (885,  620, 975,  1005),
        "arm_right":         (800,  620, 885,  1005),

        # ── ACESSÓRIOS ─────────────────────────────────────────────────────
        "accessory_chain":   (610,  620, 670,  750),
        "accessory_circle":  (680,  620, 730,  680),

        # ── FIGURA CENTRAL (personagem completa) ───────────────────────────
        "character_full":    (232,  237, 825,  978),
    }

    def __init__(self, img_path: Path):
        self.img  = Image.open(img_path).convert("RGBA")
        self.arr  = np.array(self.img)
        self.arr  = remove_checker_background(self.arr)
        log(f"Gemini RefSheet: {self.img.size[0]}×{self.img.size[1]}", "INFO")

    def extract_panel(self, key: str, margin: int = 6) -> Optional[np.ndarray]:
        """Extrai um painel pelo nome com margem."""
        if key not in self.PANELS:
            return None
        x1,y1,x2,y2 = self.PANELS[key]
        x1,y1 = max(0,x1-margin), max(0,y1-margin)
        x2,y2 = min(self.arr.shape[1],x2+margin), min(self.arr.shape[0],y2+margin)
        return self.arr[y1:y2, x1:x2].copy()

    def extract_hair(self, results: list) -> None:
        """Extrai todas as partes de cabelo."""
        print("\n  ◈ Cabelo (Gemini)...")
        parts = [
            ("hair_back",        OUT_DIR/"hair/back/hair_back.png"),
            ("hair_back_left",   OUT_DIR/"hair/back/hair_back_left.png"),
            ("hair_right",       OUT_DIR/"hair/sides/hair_right.png"),
            ("hair_front",       OUT_DIR/"hair/front/hair_front.png"),
            ("hair_side_left",   OUT_DIR/"hair/sides/hair_side_left.png"),
            ("hair_bangs_left",  OUT_DIR/"hair/fringe/hair_bangs_left.png"),
            ("hair_bangs_center",OUT_DIR/"hair/fringe/hair_bangs_center.png"),
            ("hair_bangs_right", OUT_DIR/"hair/fringe/hair_bangs_right.png"),
        ]
        for key, out_path in parts:
            panel = self.extract_panel(key)
            if panel is not None:
                # Para cabelo: isola apenas pixels escuros (preto)
                hair = color_mask(panel, r_range=(0,100), g_range=(0,100), b_range=(0,110))
                save_part(hair, out_path, key, "gemini", results)

    def extract_face(self, results: list) -> None:
        """Extrai rosto, pescoço, orelhas."""
        print("\n  ◈ Rosto/Pescoço (Gemini)...")
        parts = [
            ("head_base", OUT_DIR/"head/head_base.png"),
            ("neck",      OUT_DIR/"neck/neck.png"),
            ("ear_left",  OUT_DIR/"face/ears/ear_left.png"),
            ("ear_right", OUT_DIR/"face/ears/ear_right.png"),
        ]
        for key, out_path in parts:
            panel = self.extract_panel(key)
            if panel is not None:
                # Para rosto/pescoço: isola pele (não preto, não bordô)
                skin = color_mask(panel, r_range=(180,255), g_range=(140,235), b_range=(120,220))
                save_part(skin, out_path, key, "gemini", results)

    def extract_eyes(self, results: list) -> None:
        """Extrai componentes dos olhos."""
        print("\n  ◈ Olhos (Gemini)...")
        # O painel de olhos está no canto top-right
        # Cada sub-componente ocupa ~metade do painel (esq=L, dir=R)
        eye_regions = {
            "eye_white_l":    (875, 50,  937, 160),
            "eye_white_r":    (937, 50, 1000, 160),
            "iris_l":         (875, 160, 937, 280),
            "iris_r":         (937, 160,1000, 280),
            "pupil_l":        (875, 280, 937, 330),
            "pupil_r":        (937, 280,1000, 330),
            "eyelid_l":       (875, 330, 937, 440),
            "eyelid_r":       (937, 330,1000, 440),
            "highlight_l":    (875, 440, 937, 540),
            "highlight_r":    (937, 440,1000, 540),
        }
        eye_output = {
            "eye_white_l":  OUT_DIR/"face/eyes/left/eye_white_l.png",
            "eye_white_r":  OUT_DIR/"face/eyes/right/eye_white_r.png",
            "iris_l":       OUT_DIR/"face/eyes/iris/iris_l.png",
            "iris_r":       OUT_DIR/"face/eyes/iris/iris_r.png",
            "pupil_l":      OUT_DIR/"face/eyes/pupil/pupil_l.png",
            "pupil_r":      OUT_DIR/"face/eyes/pupil/pupil_r.png",
            "eyelid_l":     OUT_DIR/"face/eyes/left/eyelid_l.png",
            "eyelid_r":     OUT_DIR/"face/eyes/right/eyelid_r.png",
            "highlight_l":  OUT_DIR/"face/eyes/highlight/highlight_l.png",
            "highlight_r":  OUT_DIR/"face/eyes/highlight/highlight_r.png",
        }
        for key, (x1,y1,x2,y2) in eye_regions.items():
            region = self.arr[y1:y2, x1:x2].copy()
            save_part(region, eye_output[key], key, "gemini", results)

    def extract_clothes(self, results: list) -> None:
        """Extrai roupas e acessórios de vestuário."""
        print("\n  ◈ Roupas (Gemini)...")
        parts = [
            ("shirt_full",    OUT_DIR/"clothes/shirt/shirt_full.png"),
            ("sleeve_left",   OUT_DIR/"clothes/shirt/sleeve_left.png"),
            ("sleeve_right",  OUT_DIR/"clothes/shirt/sleeve_right.png"),
            ("collar",        OUT_DIR/"clothes/shirt/collar.png"),
            ("bow",           OUT_DIR/"clothes/bow/bow.png"),
            ("inner_liner",   OUT_DIR/"clothes/shirt/inner_liner.png"),
        ]
        for key, out_path in parts:
            panel = self.extract_panel(key)
            if panel is not None:
                # Roupa: bordô (não-preto, não pele, não fundo)
                clothes = color_mask(panel, r_range=(55,185), g_range=(0,75), b_range=(0,75))
                # Adiciona também o preto (collar, bow, inner)
                black   = color_mask(panel, r_range=(0,80),  g_range=(0,80), b_range=(0,85))
                # Combina
                clothes[:,:,3] = np.maximum(clothes[:,:,3], black[:,:,3])
                save_part(clothes, out_path, key, "gemini", results)

    def extract_body(self, results: list) -> None:
        """Extrai corpo nu e braços."""
        print("\n  ◈ Corpo/Braços (Gemini)...")
        parts = [
            ("body_nude", OUT_DIR/"body/body_nude.png"),
            ("arm_left",  OUT_DIR/"arms/left/arm_left.png"),
            ("arm_right", OUT_DIR/"arms/right/arm_right.png"),
        ]
        for key, out_path in parts:
            panel = self.extract_panel(key)
            if panel is not None:
                skin = color_mask(panel, r_range=(175,255), g_range=(140,235), b_range=(120,225))
                save_part(skin, out_path, key, "gemini", results)

    def extract_accessories(self, results: list) -> None:
        """Extrai acessórios (brincos, corrente)."""
        print("\n  ◈ Acessórios (Gemini)...")
        parts = [
            ("accessory_chain",  OUT_DIR/"accessories/earrings/earring_chain.png"),
            ("accessory_circle", OUT_DIR/"accessories/other/accessory_circle.png"),
            ("earring_left",     OUT_DIR/"accessories/earrings/earring_left.png"),
        ]
        for key, out_path in parts:
            panel = self.extract_panel(key)
            if panel is not None:
                save_part(panel, out_path, key, "gemini", results)

    def extract_character_full(self, results: list) -> None:
        """Extrai o personagem completo central."""
        print("\n  ◈ Personagem completo (Gemini)...")
        panel = self.extract_panel("character_full")
        if panel is not None:
            save_part(panel, OUT_DIR/"body/character_full.png",
                      "character_full", "gemini", results, crop=True)


class ModelPNGExtractor:
    """
    Extrai da vista frente/costas com alpha real (aura_model.png).
    Fonte preferencial para: costas completas, silhueta de corpo.
    """

    def __init__(self, img_path: Path):
        self.img = Image.open(img_path).convert("RGBA")
        self.arr = np.array(self.img)
        h, w    = self.arr.shape[:2]
        alpha   = self.arr[:,:,3]
        
        # Encontra ponto de divisão frente/costas
        col_density = (alpha > 10).sum(axis=0).astype(float)
        mid  = w // 2
        zone = col_density[int(mid*0.7):int(mid*1.3)]
        split_x = int(mid*0.7) + np.argmin(zone)
        
        self.front = self.arr[:, :split_x, :].copy()
        self.back  = self.arr[:, split_x:, :].copy()
        self.split_x = split_x
        log(f"ModelPNG: {w}×{h}  split_x={split_x}", "INFO")

    def extract_back_views(self, results: list) -> None:
        """Extrai vistas de costas (único nesta fonte)."""
        print("\n  ◈ Costas (model.png)...")
        # Cabelo traseiro completo (costas)
        arr = self.back
        hair = color_mask(arr, r_range=(0,80), g_range=(0,80), b_range=(0,85))
        save_part(hair, OUT_DIR/"hair/back/hair_back_view.png",
                  "hair_back_view", "model", results)

        # Roupa costas
        shirt_back = color_mask(arr, r_range=(55,180), g_range=(0,65), b_range=(0,65))
        save_part(shirt_back, OUT_DIR/"clothes/shirt/shirt_back.png",
                  "shirt_back", "model", results)

        # Corpo costas (silhueta pele)
        body_back = color_mask(arr, r_range=(175,255), g_range=(140,235), b_range=(120,225))
        save_part(body_back, OUT_DIR/"body/body_back.png",
                  "body_back", "model", results)

        # Salva vista costas completa
        save_part(arr, OUT_DIR/"templates/view_back_full.png",
                  "view_back_full", "model", results, crop=True)

    def extract_front_views(self, results: list) -> None:
        """Extrai vistas frontais como referência adicional."""
        print("\n  ◈ Frente (model.png — complementar)...")
        arr = self.front
        save_part(arr, OUT_DIR/"templates/view_front_full.png",
                  "view_front_full", "model", results, crop=True)


class HDReferenceExtractor:
    """
    Extrai detalhes de alta resolução da imagem JPEG 2112×2016.
    Fonte preferencial para: detalhes de face, olhos em alta resolução.
    A imagem NÃO tem alpha, então usa remoção de fundo branco.
    """

    def __init__(self, img_path: Path):
        self.img = Image.open(img_path).convert("RGBA")
        self.arr = np.array(self.img)
        h, w    = self.arr.shape[:2]
        
        # Remove fundo branco (JPEG não tem alpha)
        r,g,b = self.arr[:,:,0].astype(int), self.arr[:,:,1].astype(int), self.arr[:,:,2].astype(int)
        is_white = (r>230) & (g>230) & (b>230)
        self.arr[:,:,3] = np.where(is_white, 0, 255).astype(np.uint8)
        
        # Divide frente/costas
        alpha    = self.arr[:,:,3]
        col_dens = (alpha>10).sum(axis=0).astype(float)
        mid      = w//2
        zone     = col_dens[int(mid*0.6):int(mid*1.4)]
        split_x  = int(mid*0.6) + np.argmin(zone)
        
        self.front   = self.arr[:, :split_x, :].copy()
        self.split_x = split_x
        log(f"HD Reference: {w}×{h}  split_x={split_x}  (frente: {split_x}px)", "INFO")

    def extract_face_hd(self, results: list) -> None:
        """Extrai rosto em alta resolução para detalhes finos."""
        print("\n  ◈ Rosto HD (reference_hd.jpg)...")
        arr = self.front
        h, w = arr.shape[:2]
        
        # Área do rosto = ~10-35% vertical, 30-70% horizontal
        face = arr[int(h*0.04):int(h*0.35), int(w*0.25):int(w*0.75)].copy()
        
        # Filtra pele
        skin = color_mask(face, r_range=(175,255), g_range=(140,235), b_range=(120,225))
        save_part(skin, OUT_DIR/"head/head_front_hd.png",
                  "head_front_hd", "reference_hd", results)
        
        # Olhos HD: ~15-28% vertical
        eyes_region = arr[int(h*0.13):int(h*0.26), int(w*0.28):int(w*0.72)].copy()
        save_part(eyes_region, OUT_DIR/"face/eyes/eyes_region_hd.png",
                  "eyes_region_hd", "reference_hd", results)


# ══════════════════════════════════════════════════════════════
# MAPA DE QUALIDADE (qual fonte é melhor para cada parte)
# ══════════════════════════════════════════════════════════════

QUALITY_MAP = {
    # parte → fonte preferencial → justificativa
    "hair_back":      ("gemini",    "Painel isolado, alta qualidade"),
    "hair_bangs":     ("gemini",    "3 variações de franja separadas"),
    "hair_front":     ("gemini",    "Separado do corpo"),
    "eyes_detail":    ("gemini",    "Iris/pupila/highlight separados"),
    "clothes_shirt":  ("gemini",    "Shirt separada do corpo"),
    "clothes_bow":    ("gemini",    "Bow isolado"),
    "body_parts":     ("gemini",    "Arms/body nude separados"),
    "back_views":     ("model",     "Única com vista de costas"),
    "face_detail":    ("reference", "Maior resolução"),
}


# ══════════════════════════════════════════════════════════════
# GERADOR DE RELATÓRIO VISUAL
# ══════════════════════════════════════════════════════════════

def generate_comparison_sheet(results: list) -> None:
    """
    Gera uma imagem comparando todas as partes extraídas.
    """
    try:
        ok_parts = [r for r in results if r.get("status")=="ok" and r.get("output")]
        if not ok_parts:
            return
        
        cols      = 5
        thumb_sz  = 180
        padding   = 10
        label_h   = 22
        rows      = (len(ok_parts) + cols - 1) // cols
        
        sheet_w = cols * (thumb_sz + padding) + padding
        sheet_h = rows * (thumb_sz + label_h + padding) + padding
        sheet   = Image.new("RGBA", (sheet_w, sheet_h), (25, 25, 30, 255))
        draw    = ImageDraw.Draw(sheet)
        
        src_colors = {
            "gemini":       (100, 200, 255),
            "model":        (100, 255, 150),
            "reference_hd": (255, 200, 100),
        }
        
        for idx, part in enumerate(ok_parts):
            col = idx % cols
            row = idx // cols
            px  = col * (thumb_sz + padding) + padding
            py  = row * (thumb_sz + label_h + padding) + padding
            
            # Fundo xadrez
            for ty in range(0, thumb_sz, 15):
                for tx in range(0, thumb_sz, 15):
                    c = (45,45,45) if (ty//15+tx//15)%2==0 else (35,35,35)
                    draw.rectangle([px+tx, py+ty, px+tx+14, py+ty+14], fill=c)
            
            # Thumbnail
            try:
                part_path = LIVE2D_DIR / part["output"]
                if part_path.exists():
                    thumb = Image.open(part_path).convert("RGBA")
                    thumb.thumbnail((thumb_sz-4, thumb_sz-4), Image.LANCZOS)
                    tx = px + (thumb_sz - thumb.width) // 2
                    ty = py + (thumb_sz - thumb.height) // 2
                    sheet.paste(thumb, (tx, ty), thumb)
            except Exception:
                pass
            
            # Label com cor por fonte
            src    = part.get("source","?")
            color  = src_colors.get(src, (200,200,200))
            label  = part["label"][:18]
            draw.rectangle([px, py+thumb_sz, px+thumb_sz, py+thumb_sz+label_h],
                          fill=(20,20,25,255))
            draw.text((px+thumb_sz//2, py+thumb_sz+label_h//2),
                      label, fill=(*color, 255), anchor="mm")
        
        out_path = TPL_DIR / "extracted_parts_sheet.png"
        TPL_DIR.mkdir(exist_ok=True)
        sheet.save(out_path)
        log(f"Sheet de partes salvo: templates/extracted_parts_sheet.png", "OK")
    except Exception as e:
        log(f"Erro ao gerar sheet: {e}", "WARN")


def generate_manifest(results: list, duration: float) -> None:
    """Salva manifesto JSON completo."""
    ok    = [r for r in results if r.get("status")=="ok"]
    empty = [r for r in results if r.get("status")!="ok"]
    
    manifest = {
        "version": "3.0",
        "model":   "AURA",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_s": round(duration, 2),
        "sources_used": list(SOURCES.keys()),
        "quality_map": QUALITY_MAP,
        "stats": {
            "total": len(results),
            "ok":    len(ok),
            "empty": len(empty),
        },
        "parts": results,
        "live2d_layer_order": [
            "hair/back/hair_back.png",
            "hair/back/hair_back_left.png",
            "hair/back/hair_back_view.png",
            "body/body_back.png",
            "body/body_nude.png",
            "body/character_full.png",
            "clothes/shirt/shirt_back.png",
            "clothes/shirt/shirt_full.png",
            "clothes/shirt/sleeve_left.png",
            "clothes/shirt/sleeve_right.png",
            "clothes/shirt/collar.png",
            "arms/left/arm_left.png",
            "arms/right/arm_right.png",
            "neck/neck.png",
            "head/head_base.png",
            "head/head_front_hd.png",
            "hair/front/hair_front.png",
            "hair/sides/hair_right.png",
            "hair/sides/hair_side_left.png",
            "hair/fringe/hair_bangs_left.png",
            "hair/fringe/hair_bangs_center.png",
            "hair/fringe/hair_bangs_right.png",
            "clothes/bow/bow.png",
            "face/ears/ear_left.png",
            "face/ears/ear_right.png",
            "face/eyes/left/eye_white_l.png",
            "face/eyes/right/eye_white_r.png",
            "face/eyes/iris/iris_l.png",
            "face/eyes/iris/iris_r.png",
            "face/eyes/pupil/pupil_l.png",
            "face/eyes/pupil/pupil_r.png",
            "face/eyes/left/eyelid_l.png",
            "face/eyes/right/eyelid_r.png",
            "face/eyes/highlight/highlight_l.png",
            "face/eyes/highlight/highlight_r.png",
            "face/mouth/mouth_neutral.png",
            "accessories/earrings/earring_chain.png",
            "accessories/earrings/earring_left.png",
        ]
    }
    
    out = OUT_DIR / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    log(f"Manifesto: {len(ok)} partes OK / {len(empty)} vazias", "OK")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AURA Live2D — Split Model v3")
    parser.add_argument("--source", default="all",
                        choices=["all","gemini","model","reference"],
                        help="Fonte a usar (default: all)")
    parser.add_argument("--canvas", type=int, default=2048,
                        help="Canvas de exportação em pixels")
    parser.add_argument("--debug",  action="store_true",
                        help="Gera imagens de diagnóstico extras")
    args = parser.parse_args()

    t0 = time.time()
    results = []

    print()
    print("═══════════════════════════════════════════════════════")
    print("  AURA Live2D — Pipeline v3  (multi-source)")
    print("═══════════════════════════════════════════════════════")
    print()

    # Cria estrutura de diretórios
    for d in [MASKS_DIR, TPL_DIR,
              OUT_DIR/"hair/back", OUT_DIR/"hair/front",
              OUT_DIR/"hair/sides", OUT_DIR/"hair/fringe",
              OUT_DIR/"head", OUT_DIR/"neck", OUT_DIR/"body",
              OUT_DIR/"face/eyes/left", OUT_DIR/"face/eyes/right",
              OUT_DIR/"face/eyes/iris", OUT_DIR/"face/eyes/pupil",
              OUT_DIR/"face/eyes/highlight", OUT_DIR/"face/brows/left",
              OUT_DIR/"face/brows/right", OUT_DIR/"face/mouth",
              OUT_DIR/"face/ears", OUT_DIR/"face/nose",
              OUT_DIR/"arms/left", OUT_DIR/"arms/right",
              OUT_DIR/"arms/forearms", OUT_DIR/"arms/hands",
              OUT_DIR/"clothes/shirt", OUT_DIR/"clothes/bow",
              OUT_DIR/"accessories/earrings", OUT_DIR/"accessories/other",
              ]:
        d.mkdir(parents=True, exist_ok=True)

    # ── GEMINI REFSHEET (fonte principal) ─────────────────────────────────────
    if args.source in ("all", "gemini"):
        src = SOURCES["gemini"]
        if src.exists():
            print("▸ Processando: Gemini Reference Sheet (fonte principal)")
            ext = GeminiRefSheetExtractor(src)
            ext.extract_hair(results)
            ext.extract_face(results)
            ext.extract_eyes(results)
            ext.extract_clothes(results)
            ext.extract_body(results)
            ext.extract_accessories(results)
            ext.extract_character_full(results)
        else:
            log(f"Gemini refsheet não encontrada: {src}", "WARN")

    # ── MODEL PNG (costas + silhuetas) ────────────────────────────────────────
    if args.source in ("all", "model"):
        src = SOURCES["model"]
        if src.exists():
            print("\n▸ Processando: Model PNG (vistas frente/costas)")
            ext = ModelPNGExtractor(src)
            ext.extract_back_views(results)
            ext.extract_front_views(results)
        else:
            log(f"Model PNG não encontrado: {src}", "WARN")

    # ── HD REFERENCE (detalhes de rosto) ──────────────────────────────────────
    if args.source in ("all", "reference"):
        src = SOURCES["reference"]
        if src.exists():
            print("\n▸ Processando: HD Reference (detalhes de rosto)")
            ext = HDReferenceExtractor(src)
            ext.extract_face_hd(results)
        else:
            log(f"HD Reference não encontrada: {src}", "WARN")

    # ── RELATÓRIO VISUAL ──────────────────────────────────────────────────────
    print("\n▸ Gerando relatório visual...")
    generate_comparison_sheet(results)

    # ── MANIFESTO ─────────────────────────────────────────────────────────────
    duration = time.time() - t0
    generate_manifest(results, duration)

    # ── RESUMO ────────────────────────────────────────────────────────────────
    ok    = sum(1 for r in results if r.get("status")=="ok")
    empty = sum(1 for r in results if r.get("status")!="ok")

    print()
    print("═══════════════════════════════════════════════════════")
    print(f"  Pipeline concluído em {duration:.1f}s")
    print(f"  ✓ {ok} partes extraídas com sucesso")
    if empty:
        print(f"  ⚠ {empty} partes vazias (necessitam ajuste manual)")
    print()
    print("  Próximos passos:")
    print("  1. python generate_masks.py     → refina bordas")
    print("  2. python export_layers.py      → prepara para Cubism")
    print("  3. Verifique templates/extracted_parts_sheet.png")
    print("  4. Ajuste coordenadas em PANELS[] para partes vazias")
    print("═══════════════════════════════════════════════════════")
    print()


if __name__ == "__main__":
    main()
