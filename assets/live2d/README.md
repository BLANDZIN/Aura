# AURA Live2D Pipeline

Pipeline para extração e preparação de assets para Live2D Cubism Editor.

## Início rápido

```bash
cd assets/live2d

# 1. Extrai todas as partes
python scripts/split_model.py

# 2. Refina bordas
python scripts/generate_masks.py

# 3. Exporta para Cubism (canvas 2048×2048)
python scripts/export_layers.py --canvas 2048
```

## Dependências

```bash
pip install Pillow numpy scipy
```

OCR (opcional):
```bash
pip install pytesseract
```

## Fontes de imagem

| Arquivo | Uso |
|---|---|
| `aura_refsheet_gemini.png` | Reference sheet com partes pré-separadas (fonte principal) |
| `aura_psd_layermap.png` | Layer map PSD completo (cabeça, olhos, boca, roupas, pernas) |
| `aura_model.png` | Vista frente/costas com alpha (costas completas) |
| `aura_model_v2.png` | Versão maior do model (1065×1008) |
| `aura_reference_hd.jpg` | Alta resolução 2112×2016 (detalhes de rosto) |
| `aura_body_torso.png` | Torso nu isolado |

## Estrutura de saída

```
output/
├── hair/          back, front, sides, fringe
├── head/          head_base, head_front_hd
├── neck/
├── face/
│   ├── eyes/      left, right, iris, pupil, highlight
│   ├── brows/     left, right
│   ├── mouth/
│   └── ears/
├── body/          body_nude, body_back, character_full
├── arms/          left, right
├── clothes/       shirt, bow
├── accessories/   earrings, other
├── expressions/   10 expressões (pastas prontas)
├── masks/         máscaras binárias de cada parte
├── templates/     overlays de debug, spritesheet
└── manifest.json  metadados de todas as partes
```

## Ordem de importação no Cubism

Importe na ordem do `manifest.json` → campo `live2d_layer_order`.
De trás para frente: cabelo traseiro → corpo → roupa → cabeça → olhos.

## Adicionar novas roupas

```
assets/live2d/modules/clothes/nova_roupa/
    shirt.png
    sleeve_left.png
    sleeve_right.png
    metadata.json  ← {"name": "Nova Roupa", "version": "1.0"}
```

O pipeline detecta automaticamente novos módulos.

## Roadmap

- **v4** (atual) — Extração multi-fonte, 42 partes, pipeline funcional
- **v5** — Detecção automática de coordenadas (sem coordenadas fixas)
- **v6** — Engine de fusão inteligente com score por componente
- **v7** — Exportação PSD nativa + integração Cubism API
- **v8** — Geração automática de deformers e parâmetros
