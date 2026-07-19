#!/usr/bin/env python3
"""
generate_masks.py — Gerador de Máscaras Refinadas
==================================================
Refina as máscaras brutas do split_model.py usando técnicas de
processamento de imagem para bordas mais precisas.

Técnicas usadas:
  - GrabCut (OpenCV) para separação foreground/background
  - Erosão/Dilatação morfológica para limpar bordas
  - Anti-aliasing nas bordas das máscaras
  - Sugestão de regiões para ajuste manual

Uso:
    python generate_masks.py
    python generate_masks.py --part head_front
    python generate_masks.py --refine-all
    python generate_masks.py --suggest

Resultado:
    output/masks/  — máscaras refinadas por parte
    output/masks/suggestions.json  — sugestões de recorte manual
"""

import os
import sys
import json
import argparse
import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter, ImageChops

SCRIPT_DIR = Path(__file__).parent
LIVE2D_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = LIVE2D_DIR / "output"
MASKS_DIR  = OUTPUT_DIR / "masks"
MASKS_DIR.mkdir(exist_ok=True)


def log(msg: str, level: str = "INFO") -> None:
    icons = {"INFO": "→", "OK": "✓", "WARN": "⚠", "ERR": "✗", "STEP": "◈"}
    print(f"  {icons.get(level,'·')} {msg}")


def refine_mask_morphology(mask: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """
    Aplica operações morfológicas para limpar a máscara.
    - Erosão: remove pixels isolados nas bordas
    - Dilatação: preenche buracos pequenos
    """
    try:
        import cv2
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        # Fecha buracos pequenos
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        # Remove ruído
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
        return opened
    except ImportError:
        # Fallback sem OpenCV — usa PIL
        img = Image.fromarray(mask)
        img = img.filter(ImageFilter.MaxFilter(3))
        img = img.filter(ImageFilter.MinFilter(3))
        return np.array(img)


def smooth_mask_edges(mask: np.ndarray, blur_radius: float = 1.5) -> np.ndarray:
    """
    Suaviza as bordas da máscara para anti-aliasing.
    Evita bordas serrilhadas no Live2D.
    """
    img = Image.fromarray(mask)
    img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    arr = np.array(img)
    # Re-binariza com threshold
    return (arr > 128).astype(np.uint8) * 255


def grabcut_refine(
    source_img: np.ndarray,
    rough_mask: np.ndarray,
    iterations: int = 5
) -> np.ndarray:
    """
    Usa GrabCut do OpenCV para refinar a máscara com precisão de borda.
    Requer OpenCV instalado.
    """
    try:
        import cv2

        # Converte para BGR (OpenCV)
        if source_img.shape[2] == 4:
            bgr = cv2.cvtColor(source_img[:,:,:3], cv2.COLOR_RGB2BGR)
        else:
            bgr = cv2.cvtColor(source_img, cv2.COLOR_RGB2BGR)

        # Máscara inicial para GrabCut
        gc_mask = np.where(rough_mask > 0,
                           cv2.GC_PR_FGD,  # provável foreground
                           cv2.GC_BGD).astype(np.uint8)

        # Modelo interno do GrabCut
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)

        # Bounding rect da região de interesse
        rows = np.where(rough_mask > 0)[0]
        cols = np.where(rough_mask > 0)[1]
        if len(rows) == 0:
            return rough_mask

        rect = (
            max(0, int(cols.min()) - 5),
            max(0, int(rows.min()) - 5),
            min(bgr.shape[1], int(cols.max()) + 5) - max(0, int(cols.min()) - 5),
            min(bgr.shape[0], int(rows.max()) + 5) - max(0, int(rows.min()) - 5),
        )

        cv2.grabCut(bgr, gc_mask, rect, bgd_model, fgd_model, iterations, cv2.GC_INIT_WITH_MASK)
        refined = np.where((gc_mask == 2) | (gc_mask == 0), 0, 255).astype(np.uint8)
        return refined

    except ImportError:
        log("OpenCV não disponível — pulando GrabCut refinement", "WARN")
        return rough_mask
    except Exception as e:
        log(f"GrabCut falhou: {e} — usando máscara original", "WARN")
        return rough_mask


def detect_face_features(head_img: np.ndarray) -> dict:
    """
    Tenta detectar olhos, sobrancelhas e boca dentro da região da cabeça.
    Usa análise de cor para localizar cada feature.
    """
    features = {}
    alpha = head_img[:,:,3]
    h, w  = head_img.shape[:2]

    # Região do rosto (60-90% horizontal, 30-80% vertical da cabeça)
    face_y1 = int(h * 0.30)
    face_y2 = int(h * 0.85)
    face_x1 = int(w * 0.15)
    face_x2 = int(w * 0.85)
    face_region = head_img[face_y1:face_y2, face_x1:face_x2]

    # Olhos: tons vermelhos escuros (íris da AURA)
    r, g, b = face_region[:,:,0], face_region[:,:,1], face_region[:,:,2]
    a = face_region[:,:,3]
    eye_mask = ((r > 70) & (r < 200) & (g < 80) & (b < 80) & (a > 50))
    if eye_mask.any():
        rows = np.where(eye_mask.any(axis=1))[0]
        cols = np.where(eye_mask.any(axis=0))[0]
        features["eyes_region"] = {
            "bbox_in_head": [
                face_x1 + int(cols.min()),
                face_y1 + int(rows.min()),
                face_x1 + int(cols.max()),
                face_y1 + int(rows.max()),
            ],
            "confidence": float(eye_mask.sum()) / (face_region.shape[0] * face_region.shape[1])
        }

    # Sobrancelhas: preto na parte superior do rosto
    brow_region = head_img[face_y1:int(h*0.50), face_x1:face_x2]
    br, bg, bb, ba = brow_region[:,:,0], brow_region[:,:,1], brow_region[:,:,2], brow_region[:,:,3]
    brow_mask = ((br < 70) & (bg < 70) & (bb < 70) & (ba > 50))
    if brow_mask.any():
        rows = np.where(brow_mask.any(axis=1))[0]
        cols = np.where(brow_mask.any(axis=0))[0]
        features["brows_region"] = {
            "bbox_in_head": [
                face_x1 + int(cols.min()),
                face_y1 + int(rows.min()),
                face_x1 + int(cols.max()),
                face_y1 + int(rows.max()),
            ]
        }

    # Boca: tons rosas/vermelhos na parte inferior do rosto
    mouth_region = head_img[int(h*0.55):face_y2, face_x1:face_x2]
    mr, mg, mb, ma = mouth_region[:,:,0], mouth_region[:,:,1], mouth_region[:,:,2], mouth_region[:,:,3]
    mouth_mask = ((mr > 150) & (mg > 50) & (mg < 140) & (mb > 60) & (mb < 150) & (ma > 50))
    if mouth_mask.any():
        rows = np.where(mouth_mask.any(axis=1))[0]
        cols = np.where(mouth_mask.any(axis=0))[0]
        features["mouth_region"] = {
            "bbox_in_head": [
                face_x1 + int(cols.min()),
                int(h*0.55) + int(rows.min()),
                face_x1 + int(cols.max()),
                int(h*0.55) + int(rows.max()),
            ]
        }

    return features


def process_all_masks(refine: bool = True) -> dict:
    """
    Processa todas as máscaras existentes, refinando-as.
    """
    mask_files = list(MASKS_DIR.glob("*_mask.png"))
    if not mask_files:
        log("Nenhuma máscara encontrada. Execute split_model.py primeiro.", "WARN")
        return {}

    log(f"Processando {len(mask_files)} máscaras...", "INFO")
    results = {}

    for mask_path in mask_files:
        part_name = mask_path.stem.replace("_mask", "")
        log(f"Refinando: {part_name}")

        # Carrega máscara original
        mask_img = Image.open(mask_path).convert("L")
        mask_arr = np.array(mask_img)

        if mask_arr.max() == 0:
            log(f"  {part_name}: máscara vazia", "WARN")
            results[part_name] = {"status": "empty"}
            continue

        # Refina morfologicamente
        if refine:
            mask_arr = refine_mask_morphology(mask_arr, kernel_size=3)
            mask_arr = smooth_mask_edges(mask_arr, blur_radius=1.0)

        # Salva máscara refinada
        refined_path = MASKS_DIR / f"{part_name}_refined.png"
        Image.fromarray(mask_arr, "L").save(refined_path)

        pixel_count = int((mask_arr > 128).sum())
        results[part_name] = {
            "status": "ok",
            "pixels": pixel_count,
            "refined_mask": str(refined_path.relative_to(LIVE2D_DIR)),
        }
        log(f"  {part_name}: {pixel_count} px → refinada", "OK")

    return results


def generate_face_suggestions(head_path: Path) -> dict:
    """
    Analisa a parte da cabeça e gera sugestões de onde cortar
    olhos, sobrancelhas, boca para refinamento manual.
    """
    if not head_path.exists():
        log(f"Arquivo não encontrado: {head_path}", "WARN")
        return {}

    head_img = Image.open(head_path).convert("RGBA")
    head_arr = np.array(head_img)

    features = detect_face_features(head_arr)

    suggestions = {
        "source": str(head_path.relative_to(LIVE2D_DIR)),
        "image_size": list(head_img.size),
        "detected_features": features,
        "manual_regions_needed": [
            {
                "part": "eye_left",
                "description": "Olho esquerdo (direita na imagem) — íris vermelha + pupila + brilho",
                "output": "output/face/eyes/left/eye_left.png",
                "hint": "Procure a região avermelhada no terço superior do rosto"
            },
            {
                "part": "eye_right",
                "description": "Olho direito (esquerda na imagem) — íris vermelha + pupila + brilho",
                "output": "output/face/eyes/right/eye_right.png",
                "hint": "Simétrico ao olho esquerdo"
            },
            {
                "part": "brow_left",
                "description": "Sobrancelha esquerda — linha escura fina acima do olho",
                "output": "output/face/brows/left/brow_left.png",
                "hint": "Região preta fina acima do olho"
            },
            {
                "part": "brow_right",
                "description": "Sobrancelha direita",
                "output": "output/face/brows/right/brow_right.png",
                "hint": "Simétrica à sobrancelha esquerda"
            },
            {
                "part": "mouth",
                "description": "Boca — lábios rosas + abertura para expressões",
                "output": "output/face/mouth/mouth_neutral.png",
                "hint": "Região rosada no terço inferior do rosto"
            },
            {
                "part": "earrings",
                "description": "Brincos — acessório fino perto da orelha esquerda",
                "output": "output/accessories/earrings/earring_left.png",
                "hint": "Pequeno acessório branco/prata ao lado do rosto"
            },
        ]
    }

    return suggestions


def main():
    parser = argparse.ArgumentParser(description="AURA Live2D — Gerador de Máscaras Refinadas")
    parser.add_argument("--part",        default=None,  help="Refina apenas uma parte específica")
    parser.add_argument("--refine-all",  action="store_true", default=True, help="Refina todas as máscaras")
    parser.add_argument("--suggest",     action="store_true", help="Gera sugestões de recorte para face")
    parser.add_argument("--no-refine",   action="store_true", help="Pula refinamento morfológico")
    args = parser.parse_args()

    print()
    print("═══════════════════════════════════════════════")
    print("  AURA Live2D — Gerador de Máscaras v1.0")
    print("═══════════════════════════════════════════════")
    print()

    results = {}

    # ── Refina máscaras ───────────────────────────────────────────────────────
    print("◈ Refinando máscaras...")
    results = process_all_masks(refine=not args.no_refine)

    # ── Gera sugestões de face ────────────────────────────────────────────────
    print("\n◈ Analisando região da face...")
    head_path = OUTPUT_DIR / "head" / "head_front.png"
    suggestions = generate_face_suggestions(head_path)

    if suggestions:
        sugg_path = MASKS_DIR / "suggestions.json"
        with open(sugg_path, "w", encoding="utf-8") as f:
            json.dump(suggestions, f, indent=2, ensure_ascii=False)
        log(f"Sugestões de recorte salvas: masks/suggestions.json", "OK")

        print()
        log("PARTES QUE PRECISAM DE RECORTE MANUAL:", "WARN")
        for region in suggestions.get("manual_regions_needed", []):
            print(f"    → {region['part']}: {region['description']}")
            print(f"      Dica: {region['hint']}")

    # ── Resumo ────────────────────────────────────────────────────────────────
    ok    = sum(1 for v in results.values() if v.get("status") == "ok")
    empty = sum(1 for v in results.values() if v.get("status") == "empty")

    print()
    print("═══════════════════════════════════════════════")
    print(f"  ✓ {ok} máscaras refinadas")
    if empty:
        print(f"  ⚠ {empty} máscaras vazias")
    print()
    print("  Próximo passo:")
    print("  → Abra output/templates/region_overlay.png")
    print("  → Verifique as regiões identificadas")
    print("  → Faça ajustes manuais se necessário")
    print("  → Execute export_layers.py para finalizar")
    print("═══════════════════════════════════════════════")
    print()


if __name__ == "__main__":
    main()
