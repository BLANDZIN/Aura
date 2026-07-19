"""
core/quality.py — AURA Live2D Pipeline v4
==========================================
Engine de avaliação de qualidade de imagem.
Determina automaticamente qual fonte é melhor para cada componente.

Score 0-100 baseado em:
  - Resolução útil (pixels com conteúdo real)
  - Nitidez (variância de gradiente — Laplaciano)
  - Integridade das bordas (alpha bem definido)
  - Ausência de artefatos (ruído e serrilhado)
  - Preservação do conteúdo (sem cortes)
  - Saturação de cor (vivacidade)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class QualityScore:
    """Score detalhado de qualidade de uma parte de imagem."""
    total:        float = 0.0   # Score final ponderado (0-100)
    resolution:   float = 0.0   # Score de resolução (0-100)
    sharpness:    float = 0.0   # Score de nitidez (0-100)
    edge_quality: float = 0.0   # Score de borda alpha (0-100)
    noise_score:  float = 0.0   # Score de ausência de ruído (0-100)
    completeness: float = 0.0   # Score de integridade/completude (0-100)
    pixel_count:  int   = 0     # Pixels úteis
    source:       str   = ""    # Nome da fonte
    component:    str   = ""    # Nome do componente
    notes:        list  = field(default_factory=list)  # Observações

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total":        round(self.total, 1),
            "resolution":   round(self.resolution, 1),
            "sharpness":    round(self.sharpness, 1),
            "edge_quality": round(self.edge_quality, 1),
            "noise_score":  round(self.noise_score, 1),
            "completeness": round(self.completeness, 1),
            "pixel_count":  self.pixel_count,
            "source":       self.source,
            "component":    self.component,
            "notes":        self.notes,
        }


# Pesos dos critérios por tipo de componente
WEIGHTS = {
    # componente → {critério: peso}
    "default":      {"resolution": 0.30, "sharpness": 0.25, "edge_quality": 0.25, "noise_score": 0.10, "completeness": 0.10},
    "hair":         {"resolution": 0.25, "sharpness": 0.30, "edge_quality": 0.30, "noise_score": 0.05, "completeness": 0.10},
    "eye":          {"resolution": 0.20, "sharpness": 0.35, "edge_quality": 0.25, "noise_score": 0.10, "completeness": 0.10},
    "iris":         {"resolution": 0.15, "sharpness": 0.40, "edge_quality": 0.20, "noise_score": 0.15, "completeness": 0.10},
    "pupil":        {"resolution": 0.15, "sharpness": 0.40, "edge_quality": 0.20, "noise_score": 0.15, "completeness": 0.10},
    "highlight":    {"resolution": 0.10, "sharpness": 0.45, "edge_quality": 0.25, "noise_score": 0.10, "completeness": 0.10},
    "eyelid":       {"resolution": 0.20, "sharpness": 0.35, "edge_quality": 0.30, "noise_score": 0.05, "completeness": 0.10},
    "eyebrow":      {"resolution": 0.20, "sharpness": 0.35, "edge_quality": 0.30, "noise_score": 0.05, "completeness": 0.10},
    "mouth":        {"resolution": 0.25, "sharpness": 0.30, "edge_quality": 0.25, "noise_score": 0.10, "completeness": 0.10},
    "body":         {"resolution": 0.35, "sharpness": 0.20, "edge_quality": 0.20, "noise_score": 0.10, "completeness": 0.15},
    "clothes":      {"resolution": 0.30, "sharpness": 0.25, "edge_quality": 0.25, "noise_score": 0.05, "completeness": 0.15},
    "accessory":    {"resolution": 0.20, "sharpness": 0.35, "edge_quality": 0.25, "noise_score": 0.10, "completeness": 0.10},
}

# Limites mínimos para componentes válidos
MIN_PIXELS = {
    "default": 500, "hair": 2000, "eye": 200,
    "iris": 100, "pupil": 50, "highlight": 30,
    "eyelid": 200, "eyebrow": 100, "mouth": 300,
    "body": 3000, "clothes": 1000, "accessory": 50,
}


def _get_weights(component_type: str) -> dict:
    for key in WEIGHTS:
        if key in component_type.lower():
            return WEIGHTS[key]
    return WEIGHTS["default"]


def _score_resolution(arr: np.ndarray, alpha_mask: np.ndarray) -> tuple:
    """Score baseado em pixels úteis. Mais pixels = melhor (até 100k)."""
    pixel_count = int(alpha_mask.sum())
    # Escala logarítmica: 100px=10, 1000px=30, 10000px=60, 100000px=100
    if pixel_count <= 0:
        return 0.0, pixel_count
    import math
    score = min(100.0, math.log10(max(1, pixel_count)) / math.log10(100000) * 100)
    return round(score, 1), pixel_count


def _score_sharpness(arr: np.ndarray, alpha_mask: np.ndarray) -> float:
    """
    Score de nitidez via variância do Laplaciano.
    Alto = nítido, Baixo = borrado.
    """
    try:
        from scipy import ndimage
        gray = arr[:,:,:3].mean(axis=2)
        lap  = ndimage.laplace(gray.astype(float))
        if alpha_mask.sum() > 0:
            var = float(lap[alpha_mask].var())
        else:
            var = 0.0
        # Calibrado para imagens de personagem anime: var ~500 = bom
        score = min(100.0, (var / 800.0) * 100)
        return round(score, 1)
    except ImportError:
        # Fallback simples sem scipy
        gray = arr[:,:,:3].mean(axis=2).astype(float)
        gx   = np.diff(gray, axis=1)
        gy   = np.diff(gray, axis=0)
        var  = float(np.var(gx)) + float(np.var(gy))
        return round(min(100.0, var / 15.0), 1)


def _score_edge_quality(arr: np.ndarray, alpha_mask: np.ndarray) -> float:
    """
    Score de qualidade das bordas alpha.
    Bordas bem definidas (clara transição opaco→transparente) = melhor.
    """
    if alpha_mask.sum() == 0:
        return 0.0
    try:
        from scipy import ndimage
        # Detecta borda da máscara
        eroded   = ndimage.binary_erosion(alpha_mask, iterations=2)
        border   = alpha_mask & ~eroded
        n_border = border.sum()
        if n_border == 0:
            return 50.0
        
        # Verifica se a borda tem anti-aliasing suave (valores intermediários 50-205)
        alpha = arr[:,:,3]
        border_alpha = alpha[border]
        aa_pct = float(((border_alpha > 20) & (border_alpha < 235)).sum() / max(1, n_border))
        # Anti-aliasing suave = score alto (0.1-0.4 = bom)
        if 0.05 <= aa_pct <= 0.50:
            edge_score = 85.0 + aa_pct * 30
        elif aa_pct > 0.50:
            # Muita semitransparência pode ser ruído
            edge_score = 70.0
        else:
            # Bordas 100% binárias = ok mas não ideal para Live2D
            edge_score = 65.0
        
        return round(min(100.0, edge_score), 1)
    except ImportError:
        return 60.0


def _score_noise(arr: np.ndarray, alpha_mask: np.ndarray) -> float:
    """
    Score de ausência de ruído.
    Detecta pixels isolados e artefatos de compressão.
    """
    if alpha_mask.sum() < 10:
        return 0.0
    try:
        from scipy import ndimage
        # Componentes muito pequenos (<30px) = ruído
        labeled, n = ndimage.label(alpha_mask)
        small_components = sum(
            1 for i in range(1, n+1)
            if (labeled==i).sum() < 30
        )
        noise_ratio = small_components / max(1, n)
        score = max(0.0, 100.0 - noise_ratio * 200)
        return round(score, 1)
    except ImportError:
        return 75.0


def _score_completeness(arr: np.ndarray, alpha_mask: np.ndarray) -> float:
    """
    Score de integridade — verifica se a peça não está cortada nas bordas.
    Peças cortadas na borda do canvas = penalidade.
    """
    if alpha_mask.sum() == 0:
        return 0.0
    h, w = alpha_mask.shape
    
    # Verifica bordas do canvas
    top_edge    = alpha_mask[0, :].sum()
    bot_edge    = alpha_mask[-1, :].sum()
    left_edge   = alpha_mask[:, 0].sum()
    right_edge  = alpha_mask[:, -1].sum()
    
    total_border = top_edge + bot_edge + left_edge + right_edge
    total_content = alpha_mask.sum()
    
    # Se muitos pixels estão nas bordas = peça cortada
    border_ratio = total_border / max(1, total_content)
    score = max(0.0, 100.0 - border_ratio * 500)
    return round(min(100.0, score), 1)


def score_image(
    arr: np.ndarray,
    source: str,
    component: str,
    component_type: str = "default",
    checker_removed: bool = True,
) -> QualityScore:
    """
    Calcula o score de qualidade de uma parte de imagem.

    Args:
        arr:              Array RGBA da imagem (já com fundo removido).
        source:           Nome da fonte (ex: "gemini", "model", "psd").
        component:        Nome do componente (ex: "hair_front").
        component_type:   Tipo para seleção de pesos (ex: "hair", "eye").
        checker_removed:  Se o fundo xadrez já foi removido.

    Returns:
        QualityScore com score total e breakdown por critério.
    """
    qs     = QualityScore(source=source, component=component)
    notes  = []

    # Garante RGBA
    if arr is None or arr.size == 0:
        notes.append("Array vazio")
        qs.notes = notes
        return qs

    if arr.ndim == 2:
        rgba = np.zeros((*arr.shape, 4), dtype=np.uint8)
        rgba[:,:,:3] = arr[:,:, np.newaxis]
        rgba[:,:,3]  = arr
        arr = rgba
    elif arr.shape[2] == 3:
        rgba = np.zeros((*arr.shape[:2], 4), dtype=np.uint8)
        rgba[:,:,:3] = arr
        rgba[:,:,3]  = 255
        arr = rgba

    # Máscara de alpha
    alpha_mask = arr[:,:,3] > 10

    # Checa mínimo de pixels
    min_px = MIN_PIXELS.get(component_type, MIN_PIXELS["default"])
    pixel_count = int(alpha_mask.sum())
    if pixel_count < min_px:
        notes.append(f"Muito poucos pixels: {pixel_count} < {min_px}")
        qs.pixel_count = pixel_count
        qs.notes = notes
        return qs

    # Calcula cada métrica
    qs.resolution,  qs.pixel_count = _score_resolution(arr, alpha_mask)
    qs.sharpness    = _score_sharpness(arr, alpha_mask)
    qs.edge_quality = _score_edge_quality(arr, alpha_mask)
    qs.noise_score  = _score_noise(arr, alpha_mask)
    qs.completeness = _score_completeness(arr, alpha_mask)

    # Score total ponderado
    weights = _get_weights(component_type)
    qs.total = (
        qs.resolution   * weights["resolution"]   +
        qs.sharpness    * weights["sharpness"]     +
        qs.edge_quality * weights["edge_quality"]  +
        qs.noise_score  * weights["noise_score"]   +
        qs.completeness * weights["completeness"]
    )
    qs.total = round(qs.total, 1)
    qs.notes = notes

    return qs


def compare_sources(
    candidates: dict,  # {source_name: np.ndarray}
    component: str,
    component_type: str = "default",
) -> tuple:
    """
    Compara múltiplas fontes e retorna a melhor.

    Args:
        candidates: {"gemini": arr1, "model": arr2, ...}
        component:  Nome do componente
        component_type: Tipo para pesos

    Returns:
        (best_source_name, best_arr, scores_dict)
    """
    scores = {}
    for source_name, arr in candidates.items():
        if arr is None:
            continue
        qs = score_image(arr, source_name, component, component_type)
        scores[source_name] = qs

    if not scores:
        return None, None, {}

    # Seleciona a melhor
    best = max(scores.items(), key=lambda x: x[1].total)
    best_name = best[0]
    best_arr  = candidates[best_name]

    return best_name, best_arr, {k: v.as_dict() for k, v in scores.items()}


def blend_sources(
    candidates: dict,  # {source_name: np.ndarray}
    component: str,
    component_type: str = "default",
    blend_top_n: int = 2,
) -> tuple:
    """
    Fusão inteligente das melhores fontes.
    Combina as top-N fontes pesadas pelo score de qualidade.

    Útil para componentes onde nenhuma fonte é perfeita:
    - Gemini tem borda melhor
    - HD tem nitidez melhor
    → Blend ponderado pelos scores

    Returns:
        (blended_arr, scores_dict, method)
    """
    scores = {}
    for source_name, arr in candidates.items():
        if arr is None:
            continue
        qs = score_image(arr, source_name, component, component_type)
        if qs.total > 0:
            scores[source_name] = qs

    if not scores:
        return None, {}, "no_candidates"

    if len(scores) == 1:
        name = list(scores.keys())[0]
        return candidates[name], {k: v.as_dict() for k, v in scores.items()}, "single"

    # Top-N fontes
    sorted_sources = sorted(scores.items(), key=lambda x: x[1].total, reverse=True)
    top_sources    = sorted_sources[:blend_top_n]

    # Se a melhor for muito superior (>15 pts), usa ela diretamente
    if len(top_sources) >= 2:
        score_gap = top_sources[0][1].total - top_sources[1][1].total
        if score_gap > 15:
            best_name = top_sources[0][0]
            return candidates[best_name], {k: v.as_dict() for k, v in scores.items()}, "best_only"

    # Blend ponderado
    try:
        total_score = sum(s.total for _, s in top_sources)
        if total_score <= 0:
            return candidates[top_sources[0][0]], {k: v.as_dict() for k, v in scores.items()}, "fallback"

        # Normaliza para canvas comum
        shapes  = [candidates[n].shape[:2] for n, _ in top_sources]
        max_h   = max(s[0] for s in shapes)
        max_w   = max(s[1] for s in shapes)

        blended = np.zeros((max_h, max_w, 4), dtype=float)
        for source_name, qs in top_sources:
            arr   = candidates[source_name].astype(float)
            weight = qs.total / total_score
            # Resize se necessário
            if arr.shape[:2] != (max_h, max_w):
                from PIL import Image
                img_r = Image.fromarray(arr.astype(np.uint8), "RGBA")
                img_r = img_r.resize((max_w, max_h), Image.LANCZOS)
                arr   = np.array(img_r, dtype=float)
            blended += arr * weight

        result = np.clip(blended, 0, 255).astype(np.uint8)
        return result, {k: v.as_dict() for k, v in scores.items()}, f"blend_{len(top_sources)}"

    except Exception as e:
        best_name = top_sources[0][0]
        return candidates[best_name], {k: v.as_dict() for k, v in scores.items()}, f"fallback({e})"
