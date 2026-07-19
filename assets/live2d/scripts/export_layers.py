#!/usr/bin/env python3
"""
export_layers.py — Exportador para Live2D Cubism (v2)
Coloca cada parte no canvas padrao e exporta pronto para Cubism.

Uso:
    python export_layers.py
    python export_layers.py --canvas 2048
    python export_layers.py --canvas 4096
"""

import os, sys, json, time, argparse
from pathlib import Path
from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).parent
LIVE2D_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = LIVE2D_DIR / "output"
EXPORT_DIR = OUTPUT_DIR / "export"
EXPORT_DIR.mkdir(exist_ok=True)


def log(msg, level="INFO"):
    icons = {"INFO": "->", "OK": "OK", "WARN": "!!"}
    print(f"  {icons.get(level, '.')} {msg}")


PARTS = [
    ("hair_back_view",    "hair/back/hair_back_view.png",          "Hair_Back",   True),
    ("hair_back",         "hair/back/hair_back.png",               "Hair_Back",   True),
    ("hair_back_left",    "hair/back/hair_back_left.png",          "Hair_Back",   False),
    ("body_back",         "body/body_back.png",                    "Body",        True),
    ("body_nude",         "body/body_nude.png",                    "Body",        True),
    ("character_full",    "body/character_full.png",               "Body",        True),
    ("shirt_back",        "clothes/shirt/shirt_back.png",          "Clothes",     True),
    ("shirt_full",        "clothes/shirt/shirt_full.png",          "Clothes",     True),
    ("sleeve_left",       "clothes/shirt/sleeve_left.png",         "Clothes",     False),
    ("sleeve_right",      "clothes/shirt/sleeve_right.png",        "Clothes",     False),
    ("collar",            "clothes/shirt/collar.png",              "Clothes",     False),
    ("inner_liner",       "clothes/shirt/inner_liner.png",         "Clothes",     False),
    ("arm_left",          "arms/left/arm_left.png",                "Body",        True),
    ("arm_right",         "arms/right/arm_right.png",              "Body",        True),
    ("neck",              "neck/neck.png",                         "Head",        True),
    ("head_base",         "head/head_base.png",                    "Head",        True),
    ("head_front_hd",     "head/head_front_hd.png",                "Head",        False),
    ("hair_front",        "hair/front/hair_front.png",             "Hair_Front",  True),
    ("hair_side_left",    "hair/sides/hair_side_left.png",         "Hair_Front",  False),
    ("hair_right",        "hair/sides/hair_right.png",             "Hair_Front",  False),
    ("hair_bangs_left",   "hair/fringe/hair_bangs_left.png",       "Hair_Front",  True),
    ("hair_bangs_center", "hair/fringe/hair_bangs_center.png",     "Hair_Front",  True),
    ("hair_bangs_right",  "hair/fringe/hair_bangs_right.png",      "Hair_Front",  True),
    ("bow",               "clothes/bow/bow.png",                   "Clothes",     False),
    ("ear_left",          "face/ears/ear_left.png",                "Face",        False),
    ("ear_right",         "face/ears/ear_right.png",               "Face",        False),
    ("eye_white_l",       "face/eyes/left/eye_white_l.png",        "Face",        True),
    ("eye_white_r",       "face/eyes/right/eye_white_r.png",       "Face",        True),
    ("iris_l",            "face/eyes/iris/iris_l.png",             "Face",        True),
    ("iris_r",            "face/eyes/iris/iris_r.png",             "Face",        True),
    ("pupil_l",           "face/eyes/pupil/pupil_l.png",           "Face",        True),
    ("pupil_r",           "face/eyes/pupil/pupil_r.png",           "Face",        True),
    ("eyelid_l",          "face/eyes/left/eyelid_l.png",           "Face",        True),
    ("eyelid_r",          "face/eyes/right/eyelid_r.png",          "Face",        True),
    ("highlight_l",       "face/eyes/highlight/highlight_l.png",   "Face",        False),
    ("highlight_r",       "face/eyes/highlight/highlight_r.png",   "Face",        False),
    ("eyes_region_hd",    "face/eyes/eyes_region_hd.png",          "Face",        False),
    ("earring_chain",     "accessories/earrings/earring_chain.png","Accessories", False),
    ("earring_left",      "accessories/earrings/earring_left.png", "Accessories", False),
    ("accessory_circle",  "accessories/other/accessory_circle.png","Accessories", False),
]


def place_on_canvas(img, canvas_size):
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    x = max(0, (canvas_size - img.width)  // 2)
    y = max(0, (canvas_size - img.height) // 2)
    canvas.paste(img, (x, y), img if img.mode == "RGBA" else None)
    return canvas


def generate_spritesheet(parts_info):
    cols = 6; thumb = 160; pad = 8; label_h = 20
    rows = (len(parts_info) + cols - 1) // cols
    W = cols * (thumb + pad) + pad
    H = rows * (thumb + label_h + pad) + pad
    sheet = Image.new("RGBA", (W, H), (22, 22, 28, 255))
    draw  = ImageDraw.Draw(sheet)

    for idx, p in enumerate(parts_info):
        col = idx % cols
        row = idx // cols
        px  = col * (thumb + pad) + pad
        py  = row * (thumb + label_h + pad) + pad

        for ty in range(0, thumb, 12):
            for tx in range(0, thumb, 12):
                c = (40,40,40) if (ty//12+tx//12)%2==0 else (32,32,32)
                draw.rectangle([px+tx,py+ty,px+tx+11,py+ty+11], fill=c)

        if p["status"] == "ok":
            try:
                t = Image.open(p["export_path"]).convert("RGBA")
                t.thumbnail((thumb-4, thumb-4), Image.LANCZOS)
                tx = px + (thumb - t.width)  // 2
                ty = py + (thumb - t.height) // 2
                sheet.paste(t, (tx, ty), t)
                lc = (100, 220, 100)
            except Exception:
                lc = (200, 100, 100)
        else:
            draw.rectangle([px, py, px+thumb, py+thumb], fill=(50,25,25,255))
            lc = (200, 80, 80)

        draw.rectangle([px, py+thumb, px+thumb, py+thumb+label_h], fill=(18,18,22,255))
        draw.text((px+thumb//2, py+thumb+label_h//2),
                  p["label"][:14], fill=lc, anchor="mm")

    out = EXPORT_DIR / "spritesheet.png"
    sheet.save(out)
    ok_count = sum(1 for p in parts_info if p["status"]=="ok")
    log(f"Spritesheet: {W}x{H}  ({ok_count}/{len(parts_info)} partes) -> export/spritesheet.png", "OK")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--canvas", type=int, default=2048, choices=[1024, 2048, 4096])
    parser.add_argument("--no-sprite", action="store_true")
    args   = parser.parse_args()
    canvas = args.canvas
    t0     = time.time()

    print()
    print("=" * 50)
    print(f"  AURA Live2D -- Exportador v2  (canvas {canvas}x{canvas})")
    print("=" * 50)
    print()
    print("Exportando partes...")

    parts_info = []
    ok = miss_req = miss_opt = 0

    for label, rel_path, group, required in PARTS:
        src_path    = OUTPUT_DIR / rel_path
        export_path = EXPORT_DIR / rel_path
        export_path.parent.mkdir(parents=True, exist_ok=True)

        info = {"label": label, "group": group,
                "required": required, "export_path": str(export_path)}

        if src_path.exists():
            try:
                img = Image.open(src_path).convert("RGBA")
                place_on_canvas(img, canvas).save(export_path)
                info["status"] = "ok"
                ok += 1
                tag = "" if required else " (opt)"
                log(f"{label}{tag}: {img.width}x{img.height} -> {canvas}x{canvas}", "OK")
            except Exception as e:
                info["status"] = "error"
                log(f"{label}: erro -- {e}", "WARN")
        else:
            info["status"] = "missing"
            Image.new("RGBA", (canvas, canvas), (0,0,0,0)).save(export_path)
            if required:
                miss_req += 1
                log(f"{label}: FALTANDO (obrigatorio)", "WARN")
            else:
                miss_opt += 1
                log(f"{label}: nao encontrado (opcional)", "INFO")

        parts_info.append(info)

    if not args.no_sprite:
        print()
        generate_spritesheet(parts_info)

    groups = {}
    for p in parts_info:
        groups.setdefault(p["group"], []).append(
            {"id": p["label"], "status": p["status"], "required": p["required"]}
        )

    config = {
        "model": "AURA", "canvas": canvas,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {"ok": ok, "missing_required": miss_req, "missing_optional": miss_opt},
        "layer_order": [p["label"] for p in parts_info],
        "groups": groups,
    }
    json.dump(config, open(EXPORT_DIR / "cubism_config.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    log("Configuracao Cubism: export/cubism_config.json", "OK")

    dur = time.time() - t0
    print()
    print("=" * 50)
    print(f"  Concluido em {dur:.1f}s")
    print(f"  {ok}/{len(PARTS)} partes exportadas no canvas {canvas}x{canvas}")
    if miss_req:
        print(f"  !! {miss_req} obrigatorias faltando")
    print()
    print("  Para importar no Live2D Cubism:")
    print("  1. Novo projeto -> canvas 2048x2048")
    print("  2. File -> Import -> Image")
    print("  3. Selecione a pasta: output\\export\\")
    print("  4. Veja export/spritesheet.png para conferir")
    print("=" * 50)
    print()


if __name__ == "__main__":
    main()
