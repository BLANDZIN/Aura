#!/usr/bin/env python3
"""
export_as_psd.py — Exporta AURA como PSD para Live2D Cubism
=============================================================
Gera um unico arquivo AURA.psd com todas as camadas
organizadas em grupos, pronto para abrir no Cubism Editor.

Uso:
    python export_as_psd.py
    python export_as_psd.py --canvas 2048
    python export_as_psd.py --output AURA_modelo.psd

Dependencia:
    pip install psd-tools
"""

import sys
import time
import argparse
from pathlib import Path
from PIL import Image

SCRIPT_DIR = Path(__file__).parent
LIVE2D_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = LIVE2D_DIR / "output"
EXPORT_DIR = OUTPUT_DIR / "export"


def log(msg, level="INFO"):
    icons = {"INFO": "->", "OK": "OK", "WARN": "!!", "ERR": "XX", "STEP": ">>"}
    print(f"  {icons.get(level, '.')} {msg}")


# ── Definicao das camadas em ordem de renderizacao ────────────────────────────
# (nome_camada, caminho_relativo_ao_OUTPUT_DIR, grupo, obrigatorio)
# Ordem: de baixo para cima (fundo primeiro, frente por ultimo)
LAYERS = [
    # ── HAIR BACK (atras de tudo) ─────────────────────────────────────────────
    ("Hair_BackView",     "hair/back/hair_back_view.png",          "Hair_Back",   True),
    ("Hair_Back",         "hair/back/hair_back.png",               "Hair_Back",   True),
    ("Hair_BackLeft",     "hair/back/hair_back_left.png",          "Hair_Back",   False),

    # ── BODY ──────────────────────────────────────────────────────────────────
    ("Body_Back",         "body/body_back.png",                    "Body",        True),
    ("Body_Nude",         "body/body_nude.png",                    "Body",        True),
    ("Character_Full",    "body/character_full.png",               "Body",        False),

    # ── CLOTHES ───────────────────────────────────────────────────────────────
    ("Shirt_Back",        "clothes/shirt/shirt_back.png",          "Clothes",     True),
    ("Shirt_Full",        "clothes/shirt/shirt_full.png",          "Clothes",     True),
    ("Sleeve_Left",       "clothes/shirt/sleeve_left.png",         "Clothes",     False),
    ("Sleeve_Right",      "clothes/shirt/sleeve_right.png",        "Clothes",     False),
    ("Collar",            "clothes/shirt/collar.png",              "Clothes",     False),
    ("Inner_Liner",       "clothes/shirt/inner_liner.png",         "Clothes",     False),
    ("Bow",               "clothes/bow/bow.png",                   "Clothes",     False),

    # ── ARMS ──────────────────────────────────────────────────────────────────
    ("Arm_Left",          "arms/left/arm_left.png",                "Arms",        True),
    ("Arm_Right",         "arms/right/arm_right.png",              "Arms",        True),

    # ── HEAD ──────────────────────────────────────────────────────────────────
    ("Neck",              "neck/neck.png",                         "Head",        True),
    ("Head_Base",         "head/head_base.png",                    "Head",        True),
    ("Head_Front_HD",     "head/head_front_hd.png",                "Head",        False),

    # ── HAIR FRONT (sobre a cabeca) ───────────────────────────────────────────
    ("Hair_Front",        "hair/front/hair_front.png",             "Hair_Front",  True),
    ("Hair_SideLeft",     "hair/sides/hair_side_left.png",         "Hair_Front",  False),
    ("Hair_Right",        "hair/sides/hair_right.png",             "Hair_Front",  False),
    ("Hair_BangsLeft",    "hair/fringe/hair_bangs_left.png",       "Hair_Front",  True),
    ("Hair_BangsCenter",  "hair/fringe/hair_bangs_center.png",     "Hair_Front",  True),
    ("Hair_BangsRight",   "hair/fringe/hair_bangs_right.png",      "Hair_Front",  True),

    # ── EARS ──────────────────────────────────────────────────────────────────
    ("Ear_Left",          "face/ears/ear_left.png",                "Face",        False),
    ("Ear_Right",         "face/ears/ear_right.png",               "Face",        False),

    # ── EYES ──────────────────────────────────────────────────────────────────
    ("EyeWhite_L",        "face/eyes/left/eye_white_l.png",        "Eyes",        True),
    ("EyeWhite_R",        "face/eyes/right/eye_white_r.png",       "Eyes",        True),
    ("Iris_L",            "face/eyes/iris/iris_l.png",             "Eyes",        True),
    ("Iris_R",            "face/eyes/iris/iris_r.png",             "Eyes",        True),
    ("Pupil_L",           "face/eyes/pupil/pupil_l.png",           "Eyes",        True),
    ("Pupil_R",           "face/eyes/pupil/pupil_r.png",           "Eyes",        True),
    ("Eyelid_L",          "face/eyes/left/eyelid_l.png",           "Eyes",        True),
    ("Eyelid_R",          "face/eyes/right/eyelid_r.png",          "Eyes",        True),
    ("Highlight_L",       "face/eyes/highlight/highlight_l.png",   "Eyes",        False),
    ("Highlight_R",       "face/eyes/highlight/highlight_r.png",   "Eyes",        False),

    # ── ACCESSORIES ───────────────────────────────────────────────────────────
    ("Earring_Chain",     "accessories/earrings/earring_chain.png","Accessories", False),
    ("Earring_Left",      "accessories/earrings/earring_left.png", "Accessories", False),
    ("Accessory_Circle",  "accessories/other/accessory_circle.png","Accessories", False),
]


def load_image(rel_path: str, canvas_size: int) -> Image.Image:
    """
    Carrega PNG e coloca no canvas padrao.
    Retorna imagem RGBA no tamanho canvas_size x canvas_size.
    Centraliza a parte no canvas para manter alinhamento correto no Cubism.
    """
    src = OUTPUT_DIR / rel_path
    if not src.exists():
        return None

    img = Image.open(src).convert("RGBA")

    # Coloca no canvas centralizado
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    x = max(0, (canvas_size - img.width)  // 2)
    y = max(0, (canvas_size - img.height) // 2)
    canvas.paste(img, (x, y), img)
    return canvas


def build_psd(canvas_size: int, output_path: Path) -> dict:
    """
    Constroi o PSD com todas as camadas organizadas em grupos.
    Retorna estatisticas de exportacao.
    """
    try:
        from psd_tools import PSDImage
    except ImportError:
        print()
        print("  ERRO: psd-tools nao instalado.")
        print("  Execute: pip install psd-tools")
        print()
        sys.exit(1)

    stats = {"ok": 0, "missing": 0, "total": len(LAYERS)}

    print(f"  Criando PSD {canvas_size}x{canvas_size}...")
    psd = PSDImage.new("RGBA", (canvas_size, canvas_size))

    # Agrupa layers por grupo (mantendo ordem)
    groups_order = []
    groups_layers = {}
    for layer_name, rel_path, group_name, required in LAYERS:
        if group_name not in groups_layers:
            groups_order.append(group_name)
            groups_layers[group_name] = []
        groups_layers[group_name].append((layer_name, rel_path, required))

    # Cria grupos e camadas
    # Processa em ordem reversa para que o Cubism exiba na ordem correta
    for group_name in reversed(groups_order):
        layers_in_group = groups_layers[group_name]

        log(f"Grupo: {group_name} ({len(layers_in_group)} camadas)", "STEP")

        # Cria camadas do grupo no PSD principal primeiro
        psd_layers = []
        for layer_name, rel_path, required in layers_in_group:
            img = load_image(rel_path, canvas_size)

            if img is None:
                if required:
                    log(f"  {layer_name}: FALTANDO (obrigatorio)", "WARN")
                else:
                    log(f"  {layer_name}: nao encontrado (opcional)", "INFO")
                # Cria camada transparente placeholder
                img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
                stats["missing"] += 1
            else:
                log(f"  {layer_name}: OK", "OK")
                stats["ok"] += 1

            # Adiciona camada ao PSD
            pixel_layer = psd.create_pixel_layer(
                img,
                name=layer_name,
                top=0,
                left=0,
            )
            psd_layers.append(pixel_layer)

        # Cria grupo e move camadas para ele
        group = psd.create_group(name=group_name)
        for layer in reversed(psd_layers):
            layer.move_to_group(group)

        psd.append(group)

    # Salva
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"Salvando: {output_path.name}...", "INFO")
    psd.save(str(output_path))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="AURA Live2D — Exportador PSD para Cubism"
    )
    parser.add_argument(
        "--canvas", type=int, default=2048,
        choices=[1024, 2048, 4096],
        help="Tamanho do canvas (default: 2048)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Nome do arquivo PSD de saida (default: AURA_<canvas>.psd)"
    )
    args = parser.parse_args()

    canvas = args.canvas
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = EXPORT_DIR / f"AURA_{canvas}.psd"

    t0 = time.time()

    print()
    print("=" * 52)
    print("  AURA Live2D -- Exportador PSD para Cubism")
    print("=" * 52)
    print()
    print(f"  Canvas:  {canvas}x{canvas}")
    print(f"  Saida:   {output_path.name}")
    print(f"  Camadas: {len(LAYERS)}")
    print()

    stats = build_psd(canvas, output_path)

    dur  = time.time() - t0
    size = output_path.stat().st_size / 1024 / 1024 if output_path.exists() else 0

    print()
    print("=" * 52)
    print(f"  Concluido em {dur:.1f}s")
    print(f"  {stats['ok']}/{stats['total']} camadas exportadas")
    print(f"  Tamanho do PSD: {size:.1f} MB")
    print(f"  Arquivo: {output_path}")
    print()
    print("  Como abrir no Live2D Cubism:")
    print("  1. File -> Open")
    print(f"  2. Selecione: {output_path.name}")
    print("  3. Todas as camadas aparecem em grupos")
    print("  4. Ajuste posicoes e adicione deformers")
    print("=" * 52)
    print()


if __name__ == "__main__":
    main()
